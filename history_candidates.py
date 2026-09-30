"""
Rotation candidates from a Spotify account data export.

The station chooses from hand sorted mood playlists, and sorting several hundred
tracks by memory alone tends to produce the same few dozen favourites. This
script reads a year of listening history and proposes the tracks worth sorting,
so that the hand sort starts from evidence rather than recall.

The tracks it looks for are not the most played. Those are already known and
would be chosen anyway. The valuable band is the one below them, tracks played a
moderate number of times across many separate days and rarely abandoned early.
Those are the records that survive repetition without being anyone's conscious
favourite, which is exactly what a rotation needs.

Usage

    python history_candidates.py "/path/to/Spotify Account Data" candidates.csv

The export folder is the one Spotify sends as "Account data", containing files
named StreamingHistory_music_0.json and onwards. Only music history is read;
podcast and audiobook history are ignored.

Limits of the source data

The account data export records four things per play: when it ended, the artist,
the title and the milliseconds played. It carries no track identifier and no
skip flag. Two consequences follow.

    A play is treated as abandoned if it lasted under EARLY_EXIT_MS. That is
    Spotify's own threshold for a play to count as a stream, and it is a proxy
    for a skip rather than a record of one. A play cut short by the end of a
    session is counted the same as a deliberate skip.

    Tracks are identified by artist and title together. Spotify identifiers are
    attached where the same artist and title appear in the liked songs or
    playlists in the same export, and left blank otherwise.

The extended streaming history export carries both identifiers and a skip flag,
and supersedes this script's proxies when it is available.

Dayparts

Each play is assigned to a daypart by the local hour at which it ended. The
export stores times in UTC, so they are converted to TIMEZONE first. A track's
leaning is judged against the listener's overall distribution across dayparts,
not against an absolute share, so a daypart with little listening in it can
still attract tracks that are played there unusually often. Mood based
playlists such as a focus or running set cannot be inferred from timing and are
left to the hand sort.
"""

import argparse
import csv
import glob
import json
import math
import os
from collections import Counter, defaultdict
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# Local timezone used to turn the export's UTC timestamps into listening hours.
TIMEZONE = "Europe/London"

# A play shorter than this is treated as abandoned. Spotify counts a stream
# only after thirty seconds, so the same threshold is used here.
EARLY_EXIT_MS = 30_000

# Dayparts by local hour, as (name, first hour, hour after last). Late wraps
# past midnight and is handled separately.
DAYPARTS = (
    ("Mornings", 6, 10),
    ("Daytime", 10, 17),
    ("Evenings", 17, 23),
)
LATE = "Late"

# The most played tracks by completed plays. Excluded from the candidate band
# because they are already known and would be chosen by hand regardless.
TOP_BAND_SIZE = 100

# Minimum evidence for a track to count as surviving repetition.
MIN_COMPLETED_PLAYS = 4
MIN_DISTINCT_DAYS = 3
MAX_EARLY_EXIT_RATE = 0.30

# A track leans towards a daypart when a one sided binomial test rejects, at
# this significance level, the hypothesis that its plays follow the listener's
# overall distribution across dayparts. Each track is tested once per daypart,
# so across N tracks roughly 4 * N * DAYPART_LEAN_ALPHA leanings are expected
# to arise by chance alone.
DAYPART_LEAN_ALPHA = 0.01


def daypart(hour):
    """The daypart name for a local hour between 0 and 23."""
    for name, start, end in DAYPARTS:
        if start <= hour < end:
            return name
    return LATE


def load_plays(export_dir):
    """Every music play in the export, oldest first.

    The history is split across numbered files, each a JSON list of plays. They
    are concatenated and sorted so that the order does not depend on how the
    filenames happen to sort.
    """
    paths = sorted(glob.glob(os.path.join(export_dir, "StreamingHistory_music_*.json")))
    if not paths:
        raise SystemExit(f"No StreamingHistory_music_*.json files found in {export_dir}")
    plays = []
    for path in paths:
        with open(path, encoding="utf-8") as handle:
            plays.extend(json.load(handle))
    plays.sort(key=lambda play: play["endTime"])
    return plays


def load_known_uris(export_dir):
    """Spotify identifiers keyed by (artist, title), from liked songs and playlists.

    Matching is on exact artist and title after case folding. A track saved
    under two identifiers, such as an album and a single release of the same
    recording, keeps whichever is read first; either plays the same audio.
    """
    known = {}

    library_path = os.path.join(export_dir, "YourLibrary.json")
    if os.path.exists(library_path):
        with open(library_path, encoding="utf-8") as handle:
            for track in json.load(handle).get("tracks", []):
                key = (track["artist"].casefold(), track["track"].casefold())
                known.setdefault(key, track["uri"])

    for path in sorted(glob.glob(os.path.join(export_dir, "Playlist*.json"))):
        with open(path, encoding="utf-8") as handle:
            for playlist in json.load(handle).get("playlists", []):
                for item in playlist.get("items", []):
                    track = item.get("track")
                    if not track or not track.get("trackUri"):
                        continue
                    key = (track["artistName"].casefold(), track["trackName"].casefold())
                    known.setdefault(key, track["trackUri"])

    return known


def summarise(plays, tz):
    """Per track statistics, keyed by (artist, title) as written in the export."""
    stats = defaultdict(lambda: {
        "plays": 0,
        "completed": 0,
        "days": set(),
        "dayparts": Counter(),
        "first": None,
        "last": None,
    })
    for play in plays:
        ended_utc = datetime.strptime(play["endTime"], "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc)
        ended = ended_utc.astimezone(tz)
        entry = stats[(play["artistName"], play["trackName"])]
        entry["plays"] += 1
        entry["first"] = entry["first"] or ended
        entry["last"] = ended
        # Only completed plays shape a track's daypart and its spread across
        # days. An abandoned play says the track was not wanted at that moment,
        # which is the opposite of evidence that it belongs there.
        if play["msPlayed"] >= EARLY_EXIT_MS:
            entry["completed"] += 1
            entry["days"].add(ended.date())
            entry["dayparts"][daypart(ended.hour)] += 1
    return stats


def baseline_shares(stats):
    """The share of all completed plays falling in each daypart."""
    totals = Counter()
    for entry in stats.values():
        totals.update(entry["dayparts"])
    grand_total = sum(totals.values())
    return {name: totals[name] / grand_total for name in totals}


def binomial_upper_tail(k, n, p):
    """Probability of k or more successes in n trials of probability p.

    Computed exactly by summing the binomial terms. Play counts per track are
    small enough that no approximation is needed.
    """
    return sum(math.comb(n, i) * p ** i * (1 - p) ** (n - i) for i in range(k, n + 1))


def daypart_lean(entry, baseline):
    """The daypart a track is played in unusually often, with the evidence for it.

    If a track's plays followed the listener's usual pattern, the number falling
    in a daypart would be binomially distributed, with the track's completed
    plays as the trials and the baseline share as the probability. For each
    daypart the chance of seeing at least the observed count under that
    assumption is computed. The daypart with the smallest such probability is
    the leaning, provided it falls at or below DAYPART_LEAN_ALPHA.

    Testing against a probability rather than a fixed ratio lets every daypart
    qualify on equal terms. A ratio to the baseline is capped at one over the
    baseline share, which makes a heavily used daypart almost impossible to
    reach, whereas the test simply asks how surprising the count is.

    Returns the daypart name, its probability and its lift, the track's share in
    the daypart divided by the baseline share. The lift is reported as a measure
    of how strong the leaning is, not used to decide it. A track with no clear
    daypart returns an empty name.
    """
    best_name, best_p = "", 1.0
    for name, count in entry["dayparts"].items():
        if not baseline.get(name):
            continue
        p_value = binomial_upper_tail(count, entry["completed"], baseline[name])
        if p_value < best_p:
            best_name, best_p = name, p_value
    if best_p > DAYPART_LEAN_ALPHA:
        return "", None, None
    lift = (entry["dayparts"][best_name] / entry["completed"]) / baseline[best_name]
    return best_name, best_p, lift


def build_rows(stats, known_uris):
    """One output row per track, with its band and daypart leaning."""
    by_completed = sorted(stats, key=lambda key: stats[key]["completed"], reverse=True)
    top_band = set(by_completed[:TOP_BAND_SIZE])
    baseline = baseline_shares(stats)

    rows = []
    for key, entry in stats.items():
        artist, title = key
        early_exit_rate = 1 - entry["completed"] / entry["plays"]
        distinct_days = len(entry["days"])

        if key in top_band:
            band = "top"
        elif (entry["completed"] >= MIN_COMPLETED_PLAYS
              and distinct_days >= MIN_DISTINCT_DAYS
              and early_exit_rate <= MAX_EARLY_EXIT_RATE):
            band = "candidate"
        else:
            continue

        lean, p_value, lift = daypart_lean(entry, baseline)

        rows.append({
            "band": band,
            "artist": artist,
            "title": title,
            "completed_plays": entry["completed"],
            "total_plays": entry["plays"],
            "early_exit_rate": round(early_exit_rate, 2),
            "distinct_days": distinct_days,
            "daypart_lean": lean,
            "daypart_p": f"{p_value:.1e}" if lean else "",
            "daypart_lift": round(lift, 1) if lean else "",
            **{f"plays_{name.lower()}": entry["dayparts"][name] for name, _, _ in DAYPARTS},
            f"plays_{LATE.lower()}": entry["dayparts"][LATE],
            "first_played": entry["first"].date().isoformat(),
            "last_played": entry["last"].date().isoformat(),
            "uri": known_uris.get((artist.casefold(), title.casefold()), ""),
        })

    # Candidates are ranked by the number of separate days on which they were
    # finished, since that is the direct measure of surviving repetition. Total
    # completed plays breaks ties.
    rows.sort(key=lambda row: (row["band"] != "top", -row["distinct_days"], -row["completed_plays"]))
    return rows


def write_csv(rows, out_path):
    """Write the rows as CSV, suitable for sorting in a spreadsheet."""
    if not rows:
        raise SystemExit("No tracks met the thresholds; nothing written.")
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def report(plays, stats, rows):
    """A short summary on standard output, so the result can be judged at a glance."""
    candidates = [row for row in rows if row["band"] == "candidate"]
    with_uri = sum(1 for row in candidates if row["uri"])
    leans = Counter(row["daypart_lean"] or "no clear daypart" for row in candidates)

    print(f"Plays read:            {len(plays)}")
    print(f"Distinct tracks:       {len(stats)}")
    print(f"Top band:              {sum(1 for row in rows if row['band'] == 'top')}")
    print(f"Candidates:            {len(candidates)}")
    print(f"Candidates with URI:   {with_uri}")
    print("Candidate daypart leanings:")
    for name, count in leans.most_common():
        print(f"    {name:<18} {count}")


def main():
    parser = argparse.ArgumentParser(description=__doc__.strip().splitlines()[0])
    parser.add_argument("export_dir", help="Folder of the Spotify account data export")
    parser.add_argument("out_csv", help="Path of the CSV to write")
    args = parser.parse_args()

    plays = load_plays(args.export_dir)
    stats = summarise(plays, ZoneInfo(TIMEZONE))
    rows = build_rows(stats, load_known_uris(args.export_dir))
    write_csv(rows, args.out_csv)
    report(plays, stats, rows)
    print(f"Written to {args.out_csv}")


if __name__ == "__main__":
    main()
