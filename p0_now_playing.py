"""
Phase 0: prove the plumbing.

Polls Spotify every two seconds and prints what is playing, how far through it
is, and which device it is coming from. When a track changes, it reports whether
the track played out or was skipped early. That skip signal is the same feedback
the finished orchestrator will use to learn which tracks do not survive rotation.

This script is read-only. It never queues, skips or pauses anything.

Usage:
    .venv/bin/python p0_now_playing.py
"""

import time

import radio_auth

POLL_SECONDS = 2
BAR_WIDTH = 30

# A track abandoned before this fraction of its duration counts as a skip rather
# than a natural end. Radio convention is roughly the last fifth of a track.
COMPLETION_THRESHOLD = 0.8


def fmt_ms(ms):
    seconds = int(ms / 1000)
    return "{}:{:02d}".format(seconds // 60, seconds % 60)


def progress_bar(progress_ms, duration_ms):
    if not duration_ms:
        return "-" * BAR_WIDTH
    filled = int(BAR_WIDTH * progress_ms / duration_ms)
    filled = max(0, min(BAR_WIDTH, filled))
    return "#" * filled + "-" * (BAR_WIDTH - filled)


def main():
    sp = radio_auth.get_client()
    print("Connected. Polling every {} seconds. Ctrl-C to stop.\n".format(POLL_SECONDS))

    last_uri = None
    last_progress = 0
    last_duration = 0
    warned_no_device = False

    while True:
        try:
            state = sp.current_playback()
        except Exception as error:
            # A dropped connection is normal over a long run and is not a
            # reason to stop watching.
            print("\n  Spotify unreachable ({}), retrying".format(
                type(error).__name__))
            time.sleep(POLL_SECONDS)
            continue

        if state is None or state.get("item") is None:
            if not warned_no_device:
                print("No active device. Start playback in the Spotify app.")
                warned_no_device = True
            time.sleep(POLL_SECONDS)
            continue

        warned_no_device = False
        track = radio_auth.describe(state["item"])
        progress = state.get("progress_ms") or 0
        device = state["device"]

        if track["uri"] != last_uri:
            if last_uri is not None:
                fraction = last_progress / last_duration if last_duration else 0.0
                verdict = "skipped" if fraction < COMPLETION_THRESHOLD else "played out"
                print("\n     {} at {}%\n".format(verdict, int(fraction * 100)))

            print("NOW  {} - {}".format(track["artists"], track["title"]))
            print(
                "     {} ({})  |  {}  |  volume {}%".format(
                    track["album"],
                    track["year"],
                    device["name"],
                    device.get("volume_percent"),
                )
            )

        print(
            "\r     [{}] {} / {}".format(
                progress_bar(progress, track["duration_ms"]),
                fmt_ms(progress),
                fmt_ms(track["duration_ms"]),
            ),
            end="",
            flush=True,
        )

        last_uri = track["uri"]
        last_progress = progress
        last_duration = track["duration_ms"]

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
