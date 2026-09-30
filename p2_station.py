"""
The station.

Chooses the music from a named Spotify playlist and puts a presenter over it.
Tracks are picked by the rotation rules in library.py and queued one ahead.
With no playlist configured, or one that cannot be read, the station rides
whatever Spotify is already playing instead, so start a playlist on shuffle in
that case.

There are two kinds of interruption, on two clocks, and they behave differently
on purpose.

Ordinary breaks are music led. A counter fires one every two or three tracks,
timed so the presenter lands exactly as the track finishes, and the talking
carries on over the start of the next one without the music ever stopping. A
break is a sequence of parts: an opening, sometimes a thought, and usually an
introduction to whatever the queue says is coming.

Bulletins are clock led. They fire on the hour and the half hour, punctually,
interrupting whatever is playing rather than waiting for it to end. The
presenter fades in over the music to say so, the music fades out and stops, a
second voice reads the news or the sport starting with the time, and the
presenter comes back to introduce the next song, which then starts. The music
genuinely stops, because that is what a news break is.

Audio for both is rendered ahead of time in a background thread, a track ahead
for breaks and three minutes ahead for bulletins. Generating on demand would
produce dead air.

Usage:
    .venv/bin/python p2_station.py
    .venv/bin/python p2_station.py --bulletin news
    .venv/bin/python p2_station.py --bulletin sport

The --bulletin form schedules one bulletin of that kind a few seconds from
startup, so the sequence can be heard without waiting for the half hour.
Ordinary scheduling resumes once it has aired.
"""

import datetime
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor

from dotenv import load_dotenv

import bulletin
import patter
import library
import radio_auth
import radio_speech

HERE = os.path.dirname(os.path.abspath(__file__))

POLL_SECONDS = 2

# How long the station tolerates having nowhere to play before it gives up.
# Spotify reports no active device when every client has gone away, which on a
# personal station means the listener has finished rather than that something
# has broken. Pausing normally leaves the device present and the track readable,
# so an ordinary pause does not trip this.
NO_DEVICE_TIMEOUT_SECONDS = 30

# How long to wait after a skip for the music to start by itself before
# pressing play.
RESUME_CHECK_SECONDS = 2

# Ordinary chat fires after this many tracks, redrawn after every break so the
# rhythm does not become predictable.
BREAK_EVERY_MIN = 2
BREAK_EVERY_MAX = 3

# How often the optional parts of an ordinary break appear.
CHAT_CHANCE = 0.6
INTRO_CHANCE = 0.75

# How often a break is played entirely straight, with no witty line anywhere in
# it. Every other break carries exactly one.
NO_JOKE_CHANCE = 0.2

# Gap between the end of the opening part and the end of the track.
OUTRO_LEAD_MS = 500

# Spotify's crossfade setting, in milliseconds, read from .env.
#
# Crossfade does not end the outgoing track early. The incoming track starts
# early and the two overlap, so the outgoing one stays audible until its nominal
# end. What changes is that the API reports the new track as current from the
# moment it starts, which is why a break waiting on the old track's remaining
# time never fires.
#
# So this figure is used only to open the decision window early enough to beat
# that changeover. The speech is then held back to land on the nominal end,
# where the outgoing track actually stops being audible. Over estimating is
# safe; under estimating means the break never fires.
DEFAULT_CROSSFADE_MS = 0

# Bulletins are rendered this far ahead of their slot. Under Piper, fetching the
# feeds and synthesising seventy seconds of speech took around twenty seconds.
# Kokoro runs at roughly real time on an 8GB Apple M1, and measured on real feeds a
# news bulletin took 86 seconds to prepare and a sport bulletin 97. Rendering is
# single file, so a break already being made when the preroll opens adds to
# that. Three minutes covers the slowest case with room to spare: being early
# costs nothing, being late costs punctuality. The trade is that ordinary breaks
# are held back for this long before every bulletin, since the two are not
# allowed to overlap.
BULLETIN_PREROLL_SECONDS = 180

# Level Spotify is faded to while the presenter speaks.
DUCK_FRACTION = 0.30

# A track abandoned before this fraction of its duration counts as a skip.
COMPLETION_THRESHOLD = 0.8

CHANGEOVER_SAMPLES = 8

# Spotify drops connections. A station is meant to run for hours, so a reset
# socket is a thing to wait out, not a reason to stop. Backoff doubles from the
# poll interval up to this ceiling and resets on the first successful call.
MAX_BACKOFF_SECONDS = 60


def next_slot_time(now):
    """The next hour or half hour boundary strictly after now."""
    base = now.replace(second=0, microsecond=0)
    if now.minute < 30:
        return base.replace(minute=30)
    return base.replace(minute=0) + datetime.timedelta(hours=1)


def read_playback(sp):
    """Return (track, progress_ms, device) or (None, 0, None) if nothing plays.

    Network failures are raised rather than swallowed, because "Spotify is
    unreachable" and "nothing is playing" want different handling and the
    difference matters when reading the log afterwards.
    """
    state = sp.current_playback()
    if state is None or state.get("item") is None:
        return None, 0, None
    return (
        radio_auth.describe(state["item"]),
        state.get("progress_ms") or 0,
        state["device"],
    )


def find_playlist(sp, name):
    """The id of the listener's playlist with this exact name, or None.

    Spotify's own folders are invisible to the API and have been a rejected
    feature request since 2015, so playlists are matched by name and have to be
    named individually. The comparison ignores case and surrounding space,
    because a name typed into .env will not always match one typed into the app.
    """
    wanted = name.strip().lower()
    offset = 0
    while True:
        page = sp.current_user_playlists(limit=50, offset=offset)
        items = page.get("items") or []
        for playlist in items:
            if (playlist.get("name") or "").strip().lower() == wanted:
                return playlist["id"]
        if len(items) < 50:
            return None
        offset += 50


def read_library(sp, playlist_id):
    """Every playable track on a playlist, flattened for the rotation store.

    Local files and unavailable tracks are dropped rather than carried, because
    a track the station cannot queue is worse than one it never knew about. The
    endpoint pages at a hundred, so a playlist of any size has to be walked.
    """
    tracks = []
    offset = 0
    while True:
        page = sp.playlist_items(
            playlist_id, limit=100, offset=offset, additional_types=("track",)
        )
        items = page.get("items") or []
        for entry in items:
            # Spotify renamed this field from "track" to "item" in its February
            # 2026 changes, alongside moving the endpoint from /tracks to
            # /items. Reading the old name alone returns nothing for every row
            # and makes a full playlist look empty, so both are accepted.
            item = entry.get("item") or entry.get("track") or {}
            if not item.get("uri") or item.get("is_local"):
                continue
            # Podcast episodes can sit on a playlist too. A missing type is
            # treated as a track rather than rejected, so that a further change
            # to the response cannot silently empty the library again.
            if item.get("type", "track") != "track":
                continue
            described = radio_auth.describe(item)
            tracks.append({
                "uri": described["uri"],
                "title": described["title"],
                "artist": library.primary_artist(described["artists"]),
                "album": described["album"],
            })
        if len(items) < 100:
            return tracks
        offset += 100


def open_library(sp, name):
    """Load the listener's playlist into the rotation store.

    Returns an open connection, or None if anything at all goes wrong. A failure
    here is not fatal and must not be, because the station riding Spotify's own
    shuffle is exactly what it did before it could choose, and that is a far
    better outcome than refusing to go on air.
    """
    if not name:
        return None
    try:
        playlist_id = find_playlist(sp, name)
        if playlist_id is None:
            print("Playlist {!r} not found. Riding Spotify's own order."
                  .format(name))
            return None
        tracks = read_library(sp, playlist_id)
        if not tracks:
            print("Playlist {!r} is empty. Riding Spotify's own order."
                  .format(name))
            return None
        connection = library.connect()
        count = library.sync_tracks(connection, tracks)
        print("Library: {} tracks from {!r}.".format(count, name))
        return connection
    except Exception as error:
        print("Could not read {!r} ({}). Riding Spotify's own order."
              .format(name, type(error).__name__))
        return None


def queue_next(sp, rotation, exclude):
    """Choose the next track and hand it to Spotify, one ahead of the current.

    Queueing one track ahead rather than starting playback directly is what
    keeps the crossfade working, since playback is never interrupted. It also
    means the station's choice is visible in the queue, which is where the
    presenter reads what is coming up.
    """
    if rotation is None:
        return None
    try:
        pick = library.choose(rotation, exclude=exclude)
        if pick is None:
            return None
        sp.add_to_queue(pick["uri"])
        return pick
    except Exception as error:
        print("  could not queue the next track ({})"
              .format(type(error).__name__))
        return None


def read_next(sp):
    """Return the track Spotify intends to play next, or None if unknown."""
    try:
        queue = sp.queue().get("queue") or []
    except Exception:
        return None
    return radio_auth.describe(queue[0]) if queue else None


def playing_within(sp, seconds):
    """True once Spotify reports playback, polling for up to the given time.

    Spotify's reported state trails a command by a moment, so a single read made
    straight after a skip can still say paused when the music has in fact
    started. Returns as soon as playback is seen, so the usual cost is well
    under a second.
    """
    deadline = time.time() + seconds
    while time.time() < deadline:
        try:
            state = sp.current_playback()
            if state and state.get("is_playing"):
                return True
        except Exception:
            pass
        time.sleep(0.3)
    return False


def attempt(action):
    """Run a Spotify call that is allowed to fail without stopping the station."""
    try:
        action()
        return True
    except Exception:
        return False


def compose_break(track, next_track, station_name, recent_types, recent_lines):
    """Build the parts of one ordinary break, in playing order."""
    fields = {
        "artist": track["artists"],
        "title": track["title"],
        "album": track["album"],
        "year": patter.spoken_year(track["year"]),
        "station": station_name,
        "next_artist": next_track["artists"] if next_track else "",
        "next_title": next_track["title"] if next_track else "",
        "next_album": next_track["album"] if next_track else "",
        "next_year": patter.spoken_year(
            next_track["year"] if next_track else ""
        ),
    }

    # A missing year resolves to an empty string rather than to a stand in
    # phrase. The presenter does not gesture at how old a record is, because a
    # vague allusion to a track's age is the clearest sign that nobody wrote
    # the line. Naming the year outright is allowed and is deliberately rare,
    # so any line that uses these fields is one where the year is known.

    opening = patter.choose_segment(recent_types)
    plan = [opening]

    # Chat only follows a part that referred to the track just played, so the
    # break reads as "that was X, a thought, here comes Y".
    if opening == "track_back" and random.random() < CHAT_CHANCE:
        plan.append("filler")

    if next_track is not None and random.random() < INTRO_CHANCE:
        plan.append("intro")

    # At most one part of a break carries a joke, and which part it is falls
    # evenly across whichever parts the break actually has. Letting each part
    # roll for itself in turn would hand the outro first refusal every time,
    # which is the fault that made two and three witty lines in a row so
    # obvious when the bank was first heard aloud. Some breaks carry no joke at
    # all, because a punchline on every single break is its own kind of tell.
    carrier = None
    if random.random() >= NO_JOKE_CHANCE:
        carrier = random.randrange(len(plan))

    return [
        _part(segment, "witty" if index == carrier else "plain",
              fields, recent_lines)
        for index, segment in enumerate(plan)
    ]


def _part(segment, tone, fields, recent_lines):
    template, text = patter.build_line(segment, tone, fields, recent_lines)
    return {"segment": segment, "template": template, "text": text}


def render_break(parts, voice, number):
    """Synthesise every part of an ordinary break. Runs on a worker thread."""
    for index, part in enumerate(parts):
        part["path"], part["duration_ms"] = radio_speech.synthesise(
            part["text"], voice, "break_{:04d}_{}".format(number, index)
        )
    return parts


def render_bulletin(parts, presenter_voice, newsreader_voice, number):
    """Synthesise a bulletin, switching voice for the part the newsreader reads."""
    for index, part in enumerate(parts):
        voice = newsreader_voice if part["role"] == "newsreader" else presenter_voice
        part["path"], part["duration_ms"] = radio_speech.synthesise(
            part["text"], voice, "bulletin_{:04d}_{}".format(number, index)
        )
    return parts


def air_break(sp, parts, device):
    """Duck Spotify, play every part back to back, restore.

    The volume stays down across the whole sequence, including the track change
    that happens partway through, which is what makes the talking continuous
    rather than interrupted by the join.
    """
    original = device.get("volume_percent")
    ducked = int(original * DUCK_FRACTION) if original is not None else None

    if ducked is None or radio_speech.fade(sp, original, ducked) is None:
        # No volume control here. Pausing would stop the track change the
        # sequence is built around, so the parts play over the join at full
        # volume instead, which is the lesser problem.
        for part in parts:
            radio_speech.play(part["path"])
        return

    for part in parts:
        radio_speech.play(part["path"])
    radio_speech.fade(sp, ducked, original)


def air_bulletin(sp, parts, device, expected_next_uri=None, rebuild=None,
                 pool=None):
    """Fade the music out, stop it, read the bulletin, then start the next track.

    The announcement is the only part that goes over music. Everything after it
    plays in silence with playback paused, and the volume is restored before the
    next track begins so it starts at full level rather than fading up.

    The handover is rewritten if the queue has moved. A bulletin is composed a
    minute before its slot, and in that minute the song usually changes, which
    makes the next track read at composition time the song that is now playing
    and about to be skipped. The queue is only stable once playback is paused,
    so it is re read there and the closing line is rebuilt in the background
    while the body is being read. The body runs for over a minute, so the
    rewrite costs no silence.
    """
    original = device.get("volume_percent")
    announcement = parts[0]
    body = parts[1:-1]
    closing = parts[-1]

    if original is None:
        attempt(sp.pause_playback)
        radio_speech.play(announcement["path"])
    else:
        ducked = int(original * DUCK_FRACTION)
        if radio_speech.fade(sp, original, ducked) is None:
            attempt(sp.pause_playback)
            radio_speech.play(announcement["path"])
        else:
            radio_speech.play(announcement["path"])
            radio_speech.fade(sp, ducked, 0)
            attempt(sp.pause_playback)

    # Paused, so the queue has stopped moving and can be trusted.
    rewrite = None
    if rebuild is not None and pool is not None:
        actual_next = read_next(sp)
        actual_uri = actual_next["uri"] if actual_next else None
        if actual_uri != expected_next_uri:
            print("  queue moved during the preroll, rewriting the handover")
            rewrite = pool.submit(rebuild, actual_next)

    for part in body:
        radio_speech.play(part["path"])

    if rewrite is not None:
        try:
            closing = rewrite.result(timeout=30)
        except Exception as error:
            print("  handover rewrite failed ({}), using the original".format(
                type(error).__name__))
    radio_speech.play(closing["path"])

    if original is not None:
        radio_speech.set_volume(sp, original)
    attempt(sp.next_track)
    # Skipping while paused resumes playback on most devices, and asking a
    # device that is already playing to resume is refused with a 403,
    # "Restriction violated", which spotipy logs even though nothing is wrong.
    # So play is only pressed if the skip did not start the music by itself,
    # which keeps the safety net for devices that behave differently.
    if not playing_within(sp, RESUME_CHECK_SECONDS):
        attempt(sp.start_playback)
    return closing


# Piper voices used when a configured voice cannot be loaded. Both are small,
# fast and well proven on modest hardware, which is what a fallback needs.
FALLBACK_PRESENTER = "en_GB-alan-medium"
FALLBACK_NEWSREADER = "en_GB-cori-high"


def usable_voice(wanted, fallback):
    """Return wanted if it can be used, otherwise the fallback.

    A voice that fails to load should cost the station its preferred sound, not
    its ability to go on air at all.
    """
    try:
        radio_speech.ensure_voice(wanted)
        return wanted
    except Exception as error:
        print("Voice {} unavailable ({}). Using {} instead.".format(
            wanted, error, fallback))
        radio_speech.ensure_voice(fallback)
        return fallback


def main():
    load_dotenv(os.path.join(HERE, ".env"))
    presenter_voice = os.getenv(
        "PRESENTER_VOICE", os.getenv("PIPER_VOICE", FALLBACK_PRESENTER)
    )
    newsreader_voice = os.getenv("NEWS_VOICE", presenter_voice)
    station_name = os.getenv("STATION_NAME", "T7")
    crossfade_ms = int(os.getenv("CROSSFADE_MS", DEFAULT_CROSSFADE_MS))

    sp = radio_auth.get_client()
    print("Radio {} on air. Crossfade allowance {:.0f}s. Ctrl-C to stop.".format(
        station_name, crossfade_ms / 1000))
    presenter_voice = usable_voice(presenter_voice, FALLBACK_PRESENTER)
    newsreader_voice = usable_voice(newsreader_voice, FALLBACK_NEWSREADER)
    print("Presenter {}, newsreader {}.\n".format(presenter_voice, newsreader_voice))

    # The library can only be read once the client exists, which is why this
    # sits after authorisation rather than with the other settings above.
    rotation = open_library(sp, os.getenv("LIBRARY_PLAYLIST", "").strip())
    queued_uri = None
    if rotation is not None:
        # Spotify's shuffle and the station's rotation are two things choosing
        # the same music, and the station's is the one that knows what it played
        # four hours ago.
        if not attempt(lambda: sp.shuffle(False)):
            print("Could not turn Spotify shuffle off. Do it by hand or the "
                  "two will fight.")

    pool = ThreadPoolExecutor(max_workers=1)

    last_uri = None
    last_progress = 0
    last_duration = 0
    tracks_since_break = 0
    target_gap = random.randint(BREAK_EVERY_MIN, BREAK_EVERY_MAX)
    recent_types = []
    recent_lines = []
    pending_break = None
    pending_bulletin = None
    forced_kind = None
    if "--bulletin" in sys.argv:
        index = sys.argv.index("--bulletin")
        forced_kind = sys.argv[index + 1] if index + 1 < len(sys.argv) else "news"
        if forced_kind not in ("news", "sport"):
            sys.exit("--bulletin takes either news or sport")

    slot = next_slot_time(datetime.datetime.now())
    if forced_kind:
        slot = (datetime.datetime.now()
                + datetime.timedelta(seconds=BULLETIN_PREROLL_SECONDS // 4))
    break_count = 0
    bulletin_count = 0
    resync = False
    warned_no_device = False
    no_device_since = None
    volume_to_restore = None
    changeovers = []
    backoff = POLL_SECONDS

    print("Next bulletin at {}{}.\n".format(
        slot.strftime("%H:%M:%S" if forced_kind else "%H:%M"),
        " ({}, forced for testing)".format(forced_kind) if forced_kind else ""))

    try:
        while True:
            try:
                track, progress, device = read_playback(sp)
            except Exception as error:
                print("\n  Spotify unreachable ({}). Retrying in {}s."
                      .format(type(error).__name__, backoff))
                time.sleep(backoff)
                backoff = min(backoff * 2, MAX_BACKOFF_SECONDS)
                continue
            backoff = POLL_SECONDS

            if track is None:
                if no_device_since is None:
                    no_device_since = time.time()
                if not warned_no_device:
                    print("\nNo active device. Waiting for playback.")
                    warned_no_device = True
                waited = time.time() - no_device_since
                if waited >= NO_DEVICE_TIMEOUT_SECONDS:
                    print("No active device for {}s. Going off air."
                          .format(NO_DEVICE_TIMEOUT_SECONDS))
                    break
                time.sleep(POLL_SECONDS)
                continue
            warned_no_device = False
            no_device_since = None

            if resync:
                last_uri, last_progress, last_duration = (
                    track["uri"], progress, track["duration_ms"],
                )
                resync = False

            if track["uri"] != last_uri:
                if last_uri is not None:
                    fraction = last_progress / last_duration if last_duration else 0.0
                    verdict = "skipped" if fraction < COMPLETION_THRESHOLD else "played"
                    print("\n  {} at {}%".format(verdict, int(fraction * 100)))
                    if verdict == "played":
                        changeovers.append(max(0, last_duration - last_progress))
                        del changeovers[:-CHANGEOVER_SAMPLES]
                        if len(changeovers) >= 3:
                            median = sorted(changeovers)[len(changeovers) // 2]
                            print("    changeover runs {:.0f}s early (median of {});"
                                  " CROSSFADE_MS is {:.0f}s".format(
                                      median / 1000, len(changeovers),
                                      crossfade_ms / 1000))
                    tracks_since_break += 1
                    if rotation is not None:
                        # The loop already worked out whether that was a skip
                        # for the sake of the log. The rotation store wants the
                        # same verdict, so it is reused rather than recomputed.
                        if verdict == "skipped":
                            library.record_skip(rotation, last_uri)
                print("\nNOW  {} - {}".format(track["artists"], track["title"]))

                if rotation is not None:
                    library.record_play(
                        rotation, track["uri"],
                        library.primary_artist(track["artists"]),
                    )
                    # One ahead is enough. Queueing further would commit the
                    # station to choices made before it knew what was skipped.
                    pick = queue_next(
                        sp, rotation, exclude=(track["uri"], queued_uri)
                    )
                    if pick is not None:
                        queued_uri = pick["uri"]
                        print("  queued {} - {}".format(
                            pick["artist"], pick["title"]))

                if pending_break is not None and pending_break["uri"] != track["uri"]:
                    print("  discarding a break written for the previous track")
                    pending_break = None

            now = datetime.datetime.now()

            # Clock led bulletin. Rendered ahead of the slot, aired on it.
            if pending_bulletin is None:
                if (slot - now).total_seconds() <= BULLETIN_PREROLL_SECONDS:
                    kind = forced_kind or ("news" if slot.minute == 0 else "sport")
                    expected_next = read_next(sp)
                    parts = bulletin.compose(
                        kind, slot, station_name, expected_next, recent_lines
                    )
                    if parts is None:
                        print("\n  no {} content available, skipping the {} bulletin"
                              .format(kind, slot.strftime("%H:%M")))
                        forced_kind = None
                        slot = next_slot_time(datetime.datetime.now())
                        print("  next bulletin at {}".format(slot.strftime("%H:%M")))
                    else:
                        bulletin_count += 1
                        print("\n  preparing the {} {} bulletin".format(
                            slot.strftime("%H:%M"), kind))


                        def rebuild_handover(fresh, kind=kind, slot=slot,
                                             number=bulletin_count):
                            """Re render the closing line for a corrected next track."""
                            part = bulletin.signoff(
                                kind, slot, station_name, fresh, recent_lines
                            )
                            part["path"], part["duration_ms"] = radio_speech.synthesise(
                                part["text"], presenter_voice,
                                "bulletin_{:04d}_handover".format(number),
                            )
                            return part

                        pending_bulletin = {
                            "slot": slot,
                            "kind": kind,
                            "next_uri": expected_next["uri"] if expected_next else None,
                            "rebuild": rebuild_handover,
                            "future": pool.submit(
                                render_bulletin, parts, presenter_voice,
                                newsreader_voice, bulletin_count,
                            ),
                        }

            if pending_bulletin is not None and now >= pending_bulletin["slot"]:
                if pending_bulletin["future"].done():
                    try:
                        parts = pending_bulletin["future"].result()
                    except Exception as error:
                        print("\n  bulletin generation failed: {}".format(error))
                        pending_bulletin = None
                        slot = next_slot_time(now)
                        continue

                    total_ms = sum(p["duration_ms"] for p in parts)
                    print("\n  ON AIR  {} bulletin ({:.0f}s)".format(
                        pending_bulletin["kind"], total_ms / 1000))
                    volume_to_restore = device.get("volume_percent")
                    aired_closing = air_bulletin(
                        sp, parts, device,
                        expected_next_uri=pending_bulletin["next_uri"],
                        rebuild=pending_bulletin["rebuild"],
                        pool=pool,
                    )
                    volume_to_restore = None

                    for part in parts[:-1] + [aired_closing]:
                        if part.get("template"):
                            recent_lines.append(part["template"])
                    forced_kind = None
                    slot = next_slot_time(datetime.datetime.now())
                    print("  next bulletin at {}".format(slot.strftime("%H:%M")))
                    pending_bulletin = None
                    pending_break = None
                    tracks_since_break = 0
                    target_gap = random.randint(BREAK_EVERY_MIN, BREAK_EVERY_MAX)
                    resync = True
                    continue

            # Music led break. Suppressed while a bulletin is queued, so the two
            # cannot land on top of each other.
            if (pending_break is None and pending_bulletin is None
                    and tracks_since_break >= target_gap):
                break_count += 1
                next_track = read_next(sp)
                parts = compose_break(
                    track, next_track, station_name, recent_types, recent_lines
                )
                print("\n  preparing {}".format(
                    " then ".join(p["segment"] for p in parts)))
                if next_track is None:
                    print("  queue is empty, no intro this time")
                pending_break = {
                    "uri": track["uri"],
                    "next_uri": next_track["uri"] if next_track else None,
                    "future": pool.submit(render_break, parts, presenter_voice,
                                          break_count),
                }

            if pending_break is not None and pending_break["future"].done():
                try:
                    parts = pending_break["future"].result()
                except Exception as error:
                    print("\n  generation failed: {}".format(error))
                    pending_break = None
                    continue

                opening_ms = parts[0]["duration_ms"]
                lead_in = radio_speech.FADE_MS + opening_ms + OUTRO_LEAD_MS
                if track["duration_ms"] - progress - crossfade_ms <= lead_in:
                    if pending_break["next_uri"] is not None:
                        now_next = read_next(sp)
                        if now_next is None or now_next["uri"] != pending_break["next_uri"]:
                            before = len(parts)
                            parts = [p for p in parts if p["segment"] != "intro"]
                            if len(parts) != before:
                                print("\n  queue changed, dropping the intro")

                    # Firing early enough to beat the changeover is not the same
                    # as speaking at the right moment. Hold until the opening
                    # part will finish exactly as the track does.
                    hold_ms = (track["duration_ms"] - progress
                               - radio_speech.FADE_MS - opening_ms)
                    if hold_ms > 0:
                        print("\n  holding {:.1f}s so the line lands on the end"
                              .format(hold_ms / 1000))
                        time.sleep(hold_ms / 1000.0)

                    total_ms = sum(p["duration_ms"] for p in parts)
                    print("\n  ON AIR  {}  ({:.1f}s total, {:.1f}s before the join)"
                          .format(" then ".join(p["segment"] for p in parts),
                                  total_ms / 1000, opening_ms / 1000))
                    volume_to_restore = device.get("volume_percent")
                    air_break(sp, parts, device)
                    volume_to_restore = None

                    for part in parts:
                        recent_lines.append(part["template"])
                    recent_types.append(parts[0]["segment"])
                    pending_break = None
                    tracks_since_break = 0
                    target_gap = random.randint(BREAK_EVERY_MIN, BREAK_EVERY_MAX)
                    resync = True
                    print("  next break in {} tracks".format(target_gap))
                    continue

            if not resync:
                last_uri = track["uri"]
                last_progress = progress
                last_duration = track["duration_ms"]

            if pending_bulletin is not None:
                status = "bulletin " + pending_bulletin["slot"].strftime("%H:%M")
            elif pending_break is not None:
                status = "queued"
            else:
                status = "{}/{}".format(tracks_since_break, target_gap)
            print("\r     {}:{:02d} / {}:{:02d}   break {}        ".format(
                progress // 60000, (progress // 1000) % 60,
                track["duration_ms"] // 60000, (track["duration_ms"] // 1000) % 60,
                status,
            ), end="", flush=True)

            time.sleep(POLL_SECONDS)

    finally:
        pool.shutdown(wait=False)
        if volume_to_restore is not None:
            radio_speech.set_volume(sp, volume_to_restore)
            print("\nRestored volume to {}%.".format(volume_to_restore))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nOff air.")
