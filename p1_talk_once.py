"""
Phase 1: make it talk, once.

Reads the currently playing track, writes a single presenter line about it,
renders that line to audio with Piper, then waits for the right moment and
speaks over the track's outro while ducking Spotify's volume.

The ordering matters and is the core idea of the whole orchestrator. The audio
is generated first and the playback moment is chosen afterwards, because
generation takes several seconds and generating on demand produces dead air.
Everything later in the project is this sequence on a loop.

Two break styles are supported:

    soft (default)  fade Spotify down, talk over the outro, fade back up
    hard (--hard)   let the track finish, pause, speak, resume

Soft breaks suit song patter. Hard breaks suit news and weather bulletins, and
are the automatic fallback when a device does not support volume control.

Usage:
    .venv/bin/python p1_talk_once.py
    .venv/bin/python p1_talk_once.py --hard
"""

import os
import subprocess
import sys
import time
import wave

from dotenv import load_dotenv

import radio_auth

HERE = os.path.dirname(os.path.abspath(__file__))
AUDIO_DIR = os.path.join(HERE, "audio")
VOICE_DIR = os.path.join(HERE, "voices")
CLIP_PATH = os.path.join(AUDIO_DIR, "break.wav")

POLL_SECONDS = 1

# Headroom between the end of the spoken clip and the end of the track, so the
# presenter finishes just before the next song starts rather than being cut off.
TAIL_PADDING_MS = 1500

# Volume Spotify is faded to while the presenter speaks, as a percentage of the
# level found at startup.
DUCK_FRACTION = 0.30
FADE_STEPS = 6

# Each fade step is an HTTP request to Spotify, so a fade costs roughly the
# round-trip latency multiplied by the step count, not just the sleep time. Both
# the fade down and the fade back up have to be inside the break window or the
# volume is restored after the next track has already started. Measured on the
# machine this runs on: see the figure step 5 prints.
FADE_MS = 1200


def break_window_ms(clip_ms):
    """Total track time a break needs, end to end.

    The window covers the fade down, the spoken clip, the fade back up, and a
    tail of quiet track afterwards. Leaving the fades out is what caused the
    volume to be restored a second into the following track.
    """
    return clip_ms + (2 * FADE_MS) + TAIL_PADDING_MS


def build_line(track, station_name):
    """Compose the presenter's line from real track metadata.

    Phase 2 replaces this with a language model. Keeping it a template here
    proves the metadata-to-speech path in isolation, so any problem found while
    running this script belongs to Spotify, Piper or the audio device, and not
    to a prompt.
    """
    year = track["year"]
    year_clause = " from {}".format(year) if year else ""
    return (
        "You're listening to Radio {station}. "
        "That was {artists}, with {title}, off the album {album}{year_clause}. "
        "Stay with us."
    ).format(
        station=station_name,
        artists=track["artists"],
        title=track["title"],
        album=track["album"],
        year_clause=year_clause,
    )


def ensure_voice(voice):
    """Download the Piper voice model if absent.

    Kept separate from synthesise so that a one-off download does not get
    counted in the reported generation time, which is the figure the break
    timing is tuned against.
    """
    os.makedirs(VOICE_DIR, exist_ok=True)
    if os.path.exists(os.path.join(VOICE_DIR, voice + ".onnx")):
        return
    venv_python = os.path.join(HERE, ".venv", "bin", "python")
    python_bin = venv_python if os.path.exists(venv_python) else sys.executable
    print("  voice {} not present, downloading to {}".format(voice, VOICE_DIR))
    fetch = subprocess.run(
        [python_bin, "-m", "piper.download_voices", voice,
         "--download-dir", VOICE_DIR],
        capture_output=True,
    )
    if fetch.returncode != 0:
        sys.exit(
            "Could not download the voice {}.\n{}".format(
                voice, fetch.stderr.decode("utf-8", "replace")
            )
        )


def synthesise(text, voice):
    """Render text to a wav file with Piper and return its duration in ms."""
    os.makedirs(AUDIO_DIR, exist_ok=True)
    os.makedirs(VOICE_DIR, exist_ok=True)

    piper_bin = os.path.join(HERE, ".venv", "bin", "piper")
    if not os.path.exists(piper_bin):
        piper_bin = "piper"

    command = [
        piper_bin,
        "--model", voice,
        "--data-dir", VOICE_DIR,
        "--output-file", CLIP_PATH,
    ]

    result = subprocess.run(
        command, input=text.encode("utf-8"), capture_output=True
    )
    if result.returncode != 0:
        sys.exit(
            "Piper failed.\n"
            "Command: {}\n"
            "Error: {}".format(" ".join(command), result.stderr.decode("utf-8", "replace"))
        )

    with wave.open(CLIP_PATH, "rb") as handle:
        duration_ms = int(1000 * handle.getnframes() / handle.getframerate())
    return duration_ms


def play_clip():
    """Play the rendered clip through the default output device and block."""
    subprocess.run(["afplay", CLIP_PATH], check=True)


def set_volume(sp, level):
    """Set Spotify volume, returning False if the device refuses the request."""
    try:
        sp.volume(max(0, min(100, int(level))))
        return True
    except Exception:
        return False


def fade(sp, start, end):
    """Ramp Spotify's volume. Returns elapsed milliseconds, or None if refused."""
    started = time.time()
    for step in range(1, FADE_STEPS + 1):
        level = start + (end - start) * step / FADE_STEPS
        if not set_volume(sp, level):
            return None
        time.sleep(0.08)
    return int(1000 * (time.time() - started))


def read_playback(sp):
    """Return (track, progress_ms, device) or (None, 0, None) if nothing plays."""
    state = sp.current_playback()
    if state is None or state.get("item") is None:
        return None, 0, None
    return radio_auth.describe(state["item"]), state.get("progress_ms") or 0, state["device"]


def wait_for_track_with_room(sp, needed_ms):
    """Block until a track is playing with enough time left to talk over it."""
    announced = None
    while True:
        track, progress, device = read_playback(sp)
        if track is None:
            print("Waiting for playback to start in the Spotify app...")
            time.sleep(POLL_SECONDS)
            continue

        remaining = track["duration_ms"] - progress
        if remaining >= needed_ms:
            return track, device

        if announced != track["uri"]:
            print(
                "  {} - {} has only {:.1f}s left, waiting for the next track.".format(
                    track["artists"], track["title"], remaining / 1000
                )
            )
            announced = track["uri"]
        time.sleep(POLL_SECONDS)


def main():
    hard_break = "--hard" in sys.argv

    load_dotenv(os.path.join(HERE, ".env"))
    voice = os.getenv("PIPER_VOICE", "en_GB-alan-medium")
    station_name = os.getenv("STATION_NAME", "T7")

    sp = radio_auth.get_client()

    print("Step 1: reading current playback")
    track, progress, device = read_playback(sp)
    if track is None:
        sys.exit("Nothing is playing. Start a track in the Spotify app and run again.")
    print("  {} - {}".format(track["artists"], track["title"]))
    print("  device {}, volume {}%".format(device["name"], device.get("volume_percent")))

    print("\nStep 2: writing the line")
    line = build_line(track, station_name)
    print("  \"{}\"".format(line))

    print("\nStep 3: rendering it with Piper")
    ensure_voice(voice)
    started = time.time()
    clip_ms = synthesise(line, voice)
    print(
        "  {:.1f}s of audio, generated in {:.1f}s, saved to {}".format(
            clip_ms / 1000, time.time() - started, CLIP_PATH
        )
    )

    needed_ms = break_window_ms(clip_ms)

    print("\nStep 4: waiting for the right moment")
    print(
        "  break window {:.1f}s = {:.1f}s fade down + {:.1f}s speech "
        "+ {:.1f}s fade up + {:.1f}s tail".format(
            needed_ms / 1000,
            FADE_MS / 1000,
            clip_ms / 1000,
            FADE_MS / 1000,
            TAIL_PADDING_MS / 1000,
        )
    )
    # The clip was written about a specific track, so if that track no longer has
    # room the line would be wrong. Re-read metadata and rebuild if it changed.
    current, progress, device = read_playback(sp)
    if current is None or current["uri"] != track["uri"] or (
        current["duration_ms"] - progress
    ) < needed_ms:
        track, device = wait_for_track_with_room(sp, needed_ms)
        print("  target changed to {} - {}, re-rendering".format(track["artists"], track["title"]))
        line = build_line(track, station_name)
        clip_ms = synthesise(line, voice)
        needed_ms = break_window_ms(clip_ms)

    while True:
        current, progress, device = read_playback(sp)
        if current is None or current["uri"] != track["uri"]:
            sys.exit("Track changed before the break could air. Run again.")
        remaining = current["duration_ms"] - progress
        if remaining <= needed_ms:
            break
        print(
            "\r  {:.0f}s until the break".format((remaining - needed_ms) / 1000),
            end="",
            flush=True,
        )
        time.sleep(POLL_SECONDS)

    original_volume = device.get("volume_percent")
    ducked = int((original_volume or 100) * DUCK_FRACTION)

    if hard_break or original_volume is None:
        print("\n\nStep 5: hard break, pausing Spotify")
        sp.pause_playback()
        play_clip()
        sp.start_playback()
        print("  resumed")
    else:
        print("\n\nStep 5: soft break, ducking {}% to {}%".format(original_volume, ducked))
        down_ms = fade(sp, original_volume, ducked)
        if down_ms is None:
            # Some Connect devices reject volume changes. Fall back rather than
            # talking underneath a track at full volume.
            print("  device refused volume control, falling back to a hard break")
            sp.pause_playback()
            play_clip()
            sp.start_playback()
        else:
            play_clip()
            up_ms = fade(sp, ducked, original_volume)
            print("  restored to {}%".format(original_volume))
            print(
                "  measured fades: {}ms down, {}ms up. FADE_MS is set to {}ms; "
                "raise it if either figure exceeds it.".format(
                    down_ms, up_ms if up_ms is not None else "n/a", FADE_MS
                )
            )

    print("\nThat was a radio station.")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
