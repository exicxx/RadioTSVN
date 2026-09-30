"""
Assembly of the hourly and half hourly bulletins.

A bulletin is three parts with two voices, because that is how a station does it
and because the change of voice is most of what tells a listener the music has
stopped on purpose.

    announcement   presenter    over the music, before it fades out
    body           newsreader   in silence, opening with the time
    signoff        presenter    in silence, ending by naming the next song

Nothing here invents content. If the feeds return nothing for a section, that
section is absent, and if they return nothing at all the bulletin is cancelled
rather than aired empty. A presenter who announces that there is no rugby news
is worse than one who never raises the subject.
"""

import random

import feeds
import patter

ANNOUNCEMENTS = {
    "news": [
        "Right, that's enough out of me. Time for the news.",
        "Let's pause things there. News coming up.",
        "Hold that thought, because it's time for the news.",
        "Stay where you are. Here comes the news.",
    ],
    "sport": [
        "Let's leave the music there a moment. Time for the sport.",
        "Right, that's the music paused. Here's the sport.",
        "Hang on to that one. Sport coming up.",
        "Stay with us, because here's the sport.",
    ],
}

SIGNOFFS = {
    "with_next": [
        "That's your {label} at {time_phrase}. Coming up, {next_artist}, {next_title}.",
        "And that's the {label} at {time_phrase}. Right, back to it. This is "
        "{next_artist} with {next_title}.",
        "That's where we'll leave the {label}. {next_artist} now, and {next_title}.",
        "Your {label} at {time_phrase}. Here's {next_title} from {next_artist}.",
    ],
    "without_next": [
        "That's your {label} at {time_phrase}. Back to the music.",
        "And that's the {label}. Let's get on with it.",
        "That's where we'll leave the {label} for now. Music coming up.",
    ],
}

LABELS = {"news": "news", "sport": "sport"}


def _body(kind, slot_time):
    """Assemble the spoken body. Returns text, or None if there is nothing."""
    spoken_time = patter.time_phrase(slot_time)
    sections = []

    if kind == "news":
        stories = feeds.news()
        if stories:
            sections.append(" ".join(s["speech"] for s in stories))
    else:
        items = feeds.sport()
        if items:
            sections.append(" ".join(i["speech"] for i in items))

    forecast = feeds.weather()
    if forecast:
        sections.append(forecast["speech"])

    if not sections:
        return None

    opener = "It's {}, and here's your {}.".format(spoken_time, LABELS[kind])
    return opener + " " + " ".join(sections)


def signoff(kind, slot_time, station_name, next_track, recent_lines=()):
    """Build the closing part, which hands over to whatever plays next.

    Separate from compose because the next track is only known for certain once
    playback is paused. Until then the queue can move, and a handover naming the
    wrong song is worse than one naming no song at all.
    """
    fields = {
        "label": LABELS[kind],
        "time_phrase": patter.time_phrase(slot_time),
        "station": station_name,
        "next_artist": next_track["artists"] if next_track else "",
        "next_title": next_track["title"] if next_track else "",
    }
    pool = SIGNOFFS["with_next" if next_track else "without_next"]
    candidates = [line for line in pool if line not in recent_lines] or pool
    template = random.choice(candidates)
    return {"role": "presenter", "text": template.format(**fields),
            "over_music": False, "template": template}


def compose(kind, slot_time, station_name, next_track, recent_lines=()):
    """Build a bulletin. Returns a list of parts, or None to cancel it.

    Each part carries the role that should read it, so the caller can pick the
    voice. Cancelling is a normal outcome: every source can be down at once, and
    a silent half hour is better than a bulletin with nothing in it.
    """
    body = _body(kind, slot_time)
    if body is None:
        return None

    announcement = random.choice(ANNOUNCEMENTS[kind])

    return [
        {"role": "presenter", "text": announcement, "over_music": True,
         "template": announcement},
        {"role": "newsreader", "text": body, "over_music": False,
         "template": None},
        signoff(kind, slot_time, station_name, next_track, recent_lines),
    ]
