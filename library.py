"""
Track selection for the station.

Until now the station has ridden whatever Spotify decided to play and confined
itself to talking over it. This module is the other half, the part that chooses.
It holds the library, remembers what has been played and skipped, and answers
the only question the loop actually asks, which is what should go on next.

Nothing here talks to Spotify. The loop hands it a list of tracks and tells it
what happened; it hands back a choice. That separation is deliberate, because it
means the rules below can be tested at a few thousand plays a second without an
account, a network or a subscription.

Three rules govern a choice, and all three are ordinary radio practice rather
than anything clever.

    A track is not repeated inside REPEAT_HOURS.
    An artist is not repeated inside ARTIST_MINUTES.
    A skipped track is weighted down, and the penalty decays back to parity.

The last of those matters most. Roughly half of all skips are tracks that are
liked but were heard too recently, so a permanent penalty would slowly strip the
library of exactly the records that belong in it. The penalty therefore halves
every SKIP_HALF_LIFE_DAYS and is gone within a couple of months.

State lives in a SQLite file beside this module so that rotation survives a
restart. A station that forgets what it played the moment it is stopped is a
station with no rotation at all.
"""

import os
import random
import sqlite3
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(HERE, "rotation.db")

# A track is not played again inside this many hours.
REPEAT_HOURS = 4

# An artist is not played again inside this many minutes.
ARTIST_MINUTES = 45

# A freshly skipped track is weighted at 1 - SKIP_PENALTY of its normal chance,
# and that penalty halves every SKIP_HALF_LIFE_DAYS. At 0.7 and 14 days a track
# skipped a moment ago sits at about 30 per cent of parity, 65 per cent after a
# fortnight, 82 per cent after a month, and is effectively back to normal inside
# two. Repeated skips compound, because only the most recent one is stored but
# each one restarts the decay.
SKIP_PENALTY = 0.7
SKIP_HALF_LIFE_DAYS = 14

# No track is ever weighted to zero, because a weight of zero is an eviction
# rather than a demotion and this library is too small to evict anything.
MINIMUM_WEIGHT = 0.05

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    uri     TEXT PRIMARY KEY,
    title   TEXT NOT NULL,
    artist  TEXT NOT NULL,
    album   TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS history (
    uri        TEXT NOT NULL,
    artist     TEXT NOT NULL,
    played_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS history_played_at ON history (played_at);
CREATE TABLE IF NOT EXISTS skips (
    uri         TEXT PRIMARY KEY,
    skipped_at  REAL NOT NULL
);
"""


def primary_artist(artists):
    """The first credited artist of a track.

    The artist rule exists to stop the same voice returning too soon, and a
    featured guest is not that voice. Matching on the joined credit would let a
    collaboration slip past a rule the lead artist should have been caught by.
    """
    return (artists or "").split(",")[0].strip()


def connect(path=DB_PATH):
    """Open the rotation store, creating it if this is the first run."""
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    connection.commit()
    return connection


def sync_tracks(connection, tracks):
    """Replace the known library with the given tracks.

    Rotation history is deliberately untouched. A track dropped from the
    playlist and added back a week later should return with its history intact,
    because the listener's ear has a longer memory than the playlist does.
    """
    connection.execute("DELETE FROM tracks")
    connection.executemany(
        "INSERT OR REPLACE INTO tracks (uri, title, artist, album) "
        "VALUES (?, ?, ?, ?)",
        [(t["uri"], t["title"], t["artist"], t["album"]) for t in tracks],
    )
    connection.commit()
    return connection.execute("SELECT COUNT(*) FROM tracks").fetchone()[0]


def record_play(connection, uri, artist, now=None):
    """Note that a track has been played, for the two recency rules."""
    connection.execute(
        "INSERT INTO history (uri, artist, played_at) VALUES (?, ?, ?)",
        (uri, artist, time.time() if now is None else now),
    )
    connection.commit()


def record_skip(connection, uri, now=None):
    """Note that a track was skipped, restarting its penalty decay."""
    connection.execute(
        "INSERT OR REPLACE INTO skips (uri, skipped_at) VALUES (?, ?)",
        (uri, time.time() if now is None else now),
    )
    connection.commit()


def skip_weight(skipped_at, now):
    """Relative chance of a track being chosen, given when it was last skipped.

    Returns 1.0 for a track that has never been skipped, and climbs back towards
    1.0 from below for one that has.
    """
    if skipped_at is None:
        return 1.0
    days = max(0.0, (now - skipped_at) / 86400.0)
    weight = 1.0 - SKIP_PENALTY * (0.5 ** (days / SKIP_HALF_LIFE_DAYS))
    return max(MINIMUM_WEIGHT, weight)


def _recent(connection, seconds, now):
    """Sets of track uris and artists played within the given window."""
    cutoff = now - seconds
    rows = connection.execute(
        "SELECT uri, artist, played_at FROM history WHERE played_at >= ?",
        (cutoff,),
    ).fetchall()
    return rows


def choose(connection, exclude=(), now=None):
    """Pick the next track, or None if the library is empty.

    The two recency rules are relaxed rather than enforced to the point of
    silence. A library smaller than the rules assume would otherwise leave
    nothing playable, and a station that stops talking because its own policy
    painted it into a corner is worse than one that repeats an artist early.
    """
    now = time.time() if now is None else now
    tracks = connection.execute(
        "SELECT uri, title, artist, album FROM tracks"
    ).fetchall()
    if not tracks:
        return None

    rows = _recent(connection, REPEAT_HOURS * 3600, now)
    recent_uris = {r["uri"] for r in rows}
    artist_cutoff = now - ARTIST_MINUTES * 60
    recent_artists = {
        r["artist"] for r in rows if r["played_at"] >= artist_cutoff
    }

    skips = {
        r["uri"]: r["skipped_at"]
        for r in connection.execute("SELECT uri, skipped_at FROM skips")
    }

    excluded = set(exclude)
    pools = [
        # Everything the rules allow.
        lambda t: (t["uri"] not in recent_uris
                   and t["artist"] not in recent_artists),
        # The artist rule is the first to go, being the shorter window.
        lambda t: t["uri"] not in recent_uris,
        # Then the repeat rule, which leaves only the caller's exclusions.
        lambda t: True,
    ]

    for allows in pools:
        candidates = [
            t for t in tracks if t["uri"] not in excluded and allows(t)
        ]
        if candidates:
            weights = [skip_weight(skips.get(t["uri"]), now) for t in candidates]
            chosen = random.choices(candidates, weights=weights, k=1)[0]
            return dict(chosen)

    return None
