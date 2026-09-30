"""
Station modes, selected by the Spotify playlist that is playing.

A playlist belongs to the station when its name contains the station prefix,
"Radio TSVN" by default and set by PLAYLIST_PREFIX. The rest of the name picks
the mode. "Radio TSVN - Club" is club, "Radio TSVN - Sunday Morning" is sunday,
and a station playlist naming no known mode, such as "Radio TSVN - General
Listening", is general.

Anything else playing, whether a playlist without the prefix, an album, a
podcast or a bare queue, means the station is silent. The listener has chosen
plain music, and the presenter stays out of it until a station playlist is
playing again.

Matching ignores case and spaces, so "RadioTSVN - club" and "Radio TSVN - Club"
are the same playlist as far as the station is concerned.
"""

import os

DEFAULT_PREFIX = "Radio TSVN"

GENERAL = "general"
SILENT = "silent"

# Keywords that select a mode, checked in this order against the part of the
# name after the prefix. The first match wins.
MODE_KEYWORDS = (
    ("club", "club"),
    ("chill", "chill"),
    ("sunday", "sunday"),
)

# Every mode that has a presenter, general first.
PRESENTED = (GENERAL,) + tuple(mode for _, mode in MODE_KEYWORDS)


def voice_setting(mode):
    """The .env setting naming the presenter's voice in a mode.

    General uses PRESENTER_VOICE. Every other mode has its own setting, such as
    PRESENTER_VOICE_CLUB, and falls back to the general voice when it is unset.
    """
    return "PRESENTER_VOICE" if mode == GENERAL else "PRESENTER_VOICE_" + mode.upper()


def _squash(text):
    """Lower case with all whitespace removed, for forgiving comparison."""
    return "".join((text or "").split()).casefold()


def prefix():
    """The configured station prefix."""
    return os.getenv("PLAYLIST_PREFIX", DEFAULT_PREFIX).strip() or DEFAULT_PREFIX


def mode_for_name(name, station_prefix=None):
    """The mode for a playlist name, or SILENT if it is not a station playlist."""
    wanted = _squash(station_prefix or prefix())
    squashed = _squash(name)
    if not wanted or wanted not in squashed:
        return SILENT
    remainder = squashed.split(wanted, 1)[1]
    for keyword, mode in MODE_KEYWORDS:
        if keyword in remainder:
            return mode
    return GENERAL


class PlaylistNames:
    """Playlist names looked up by Spotify URI, remembered once read.

    The name of any playlist is available to a development mode app even when
    its contents are not, so this works for every playlist the listener can
    play. Names are cached for the life of the process, since a rename during a
    session is rare and the cost of missing one is a single wrong mode.
    """

    def __init__(self, sp):
        self._sp = sp
        self._names = {}

    def name(self, uri):
        """The playlist's name, or None if it cannot be read."""
        if uri in self._names:
            return self._names[uri]
        try:
            found = self._sp.playlist(uri, fields="name").get("name")
        except Exception:
            # Not remembered, so a transient failure is retried on the next
            # track change rather than fixing the station in the wrong mode.
            return None
        self._names[uri] = found
        return found


def mode_for_context(context, names):
    """The mode for a playback context, with the playlist name where known.

    Returns (mode, name). Only a playlist context can select a mode. Albums,
    artists, podcasts and a queue with no context all return SILENT. If the
    playlist's name cannot be read, the mode is None, meaning unknown, and the
    caller should keep the mode it already has rather than fall silent over a
    network error.
    """
    if not context or context.get("type") != "playlist":
        return SILENT, None
    name = names.name(context.get("uri"))
    if name is None:
        return None, None
    return mode_for_name(name), name
