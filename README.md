# RadioTSVN

**Radio for the Individual.**

A personal radio station built on Spotify. It picks tracks from a playlist, and
an AI presenter talks between them. Twice an hour it stops for news, sport and
weather read from live feeds by a second voice. Everything runs on one Mac, the
speech is synthesised locally, and no language model is involved while it plays.

## What it does

**Music.** The station chooses every track itself from one Spotify playlist and
queues it one ahead. Selection follows ordinary radio practice. No track repeats
inside four hours, no artist repeats inside 45 minutes, and a skipped track is
played less often for a while, with the penalty wearing off over a couple of
months. A skip means "not now", not "never".

**Breaks.** Every two or three tracks the presenter comes in as a song finishes
and talks over the start of the next one, without the music stopping. A break is
an opening, sometimes a thought, and usually an introduction to the next record.
The lines come from a hand written bank with a generated extension, in two
tiers, witty and plain, with at most one joke per break.

**Bulletins.** On the hour and half hour the presenter announces the bulletin
over the music, the music fades out and stops, and a second voice reads it,
starting with the time. News and weather on the hour, sport and weather on the
half. The presenter then introduces the next song. A section with nothing in it
is left out instead of being announced as empty.

## Design

There is no language model in the playback loop. Presenter lines are
written ahead of time and selected at runtime. Bulletins need no generation at
all, because they are filled from feeds.

Speech uses [Kokoro](https://github.com/thewh1teagle/kokoro-onnx) through its
ONNX build, running at roughly real time on the M1, with
[Piper](https://github.com/OHF-Voice/piper1-gpl) as an automatic fallback if
Kokoro cannot load. Pauses are set by punctuation, since Kokoro gives every mark
the same short pause and a comic beat needs more room than a comma.

## Requirements

- macOS. Speech is played with `afplay`, and Spotify must play on the same Mac
  so that the system mixes the two. A phone or Connect speaker breaks the effect.
- Python 3.13.
- Spotify Premium, on both the listener's account and the account that owns the
  Spotify developer app. This has been a Spotify requirement since February 2026.
- About 500MB of disk for the voice models.

## Setup

**1. Create the environment.**

```bash
python3.13 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

**2. Create a Spotify app.** Every user needs their own. Spotify limits a
development mode app to five users added by hand, and higher tiers are not
available to individuals.

Sign in at the [Spotify developer dashboard](https://developer.spotify.com/dashboard)
first, since the dashboard redirects to the marketing homepage when signed out.
Create an app, tick Web API, and register this redirect URI exactly.

```
http://127.0.0.1:8888/callback
```

Spotify no longer accepts `localhost`, so the loopback address has to be written
as `127.0.0.1`.

**3. Configure.**

```bash
cp .env.example .env
```

Paste the app's Client ID from its Basic Information page into `.env`. There is
no client secret. Authentication uses PKCE, which is the flow Spotify recommends
for software that cannot keep a secret, and the client ID is not sensitive.

**4. Download the Kokoro model.** About 350MB.

```bash
mkdir -p voices/kokoro
curl -L -o voices/kokoro/kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -L -o voices/kokoro/voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

The Piper fallback voices download themselves on first use.

**5. Make a playlist and name it in `.env`.** See [Playlists](#playlists).

**6. Check each stage.** The scripts are numbered in build order, and each one
checks a piece the next depends on. Open the Spotify desktop app and start
something playing first. The first run opens a browser to authorise the app.

```bash
.venv/bin/python p0_now_playing.py
```

Prints what Spotify is playing. Confirms authentication and playback access.

```bash
.venv/bin/python p1_talk_once.py
```

Speaks one line over the current track, with at least thirty seconds of it left.
Confirms speech and volume ducking. Add `--hard` to pause, speak and resume
instead.

**7. Run the station.**

```bash
.venv/bin/python p2_station.py
```

Ctrl-C stops it and restores the volume. To hear a bulletin without waiting for
the half hour, use one of these.

```bash
.venv/bin/python p2_station.py --bulletin news
.venv/bin/python p2_station.py --bulletin sport
```

## Playlists

The station reads **one playlist**, the one named in `LIBRARY_PLAYLIST`. The name
match ignores case and surrounding spaces. A playlist of 100 tracks or more
gives the rotation rules room to work, and a smaller one will repeat artists
more often than it should.

The playlist must be one the listener **owns or collaborates on**. Since
February 2026 Spotify only returns the contents of those playlists to
development mode apps, and a public playlist belonging to someone else comes
back empty. To use someone else's playlist, open it in the Spotify app, select
every track, add them to a new playlist in the listener's own library, and name
that one in `.env`.

If `LIBRARY_PLAYLIST` is empty, or the playlist cannot be read, the station
falls back to riding whatever Spotify plays, in which case a playlist should be
started on shuffle by hand.

**Planned.** A set of mood playlists switched by time of day, which is not built
yet. The intended set, named individually because Spotify folders are invisible
to the API, is below.

| Playlist | Character |
|---|---|
| General Listening | The base rotation. Survives being heard often, no strong mood |
| Mornings | Warm and mid tempo. Nothing abrasive before about ten |
| Focus | Steady and undemanding, vocals that do not pull attention |
| Lift | Fast and loud |
| Evenings | Slower and warmer |
| Late | Sparse and quiet. After about eleven |

### Building a playlist from listening history

`history_candidates.py` reads a Spotify account data export, requested from the
Privacy page of the Spotify account settings, and proposes tracks for these
playlists. It skips the most played tracks, which are already known, and looks
for the band below them. That means tracks finished on several separate days and
rarely abandoned early, since those survive repetition. It also flags tracks
played at a particular time of day unusually often, using a binomial test
against the listener's own daily pattern.

```bash
.venv/bin/python history_candidates.py "/path/to/Spotify Account Data" candidates.csv
```

The account data export has no track identifiers and no skip flag, so a play
under thirty seconds stands in for a skip. Identifiers are matched from liked
songs and playlists in the same export where possible.

## Configuration

Set in `.env`. See `.env.example` for the full list.

| Setting | Meaning |
|---|---|
| `SPOTIFY_CLIENT_ID` | The Spotify app's client ID |
| `SPOTIFY_REDIRECT_URI` | Must match the app's registered redirect URI |
| `LIBRARY_PLAYLIST` | Name of the playlist the station chooses from |
| `STATION_NAME` | The name spoken on air, as "Radio" plus this. Write it as it should sound |
| `PRESENTER_VOICE` | A Kokoro voice such as `bm_george`, or a Piper voice such as `en_GB-alan-medium` |
| `NEWS_VOICE` | The newsreader's voice. A different voice from the presenter tells the listener the music stopped on purpose |
| `PIPER_VOICE` | Fallback presenter voice if Kokoro cannot load |
| `CROSSFADE_MS` | Match Spotify's crossfade setting, or 0 if it is off |

Content is set in code. `feeds.py` holds the news mix (`NEWS_MIX`), the sports
(`SPORT_MIX`), and the weather location, which defaults to London. The sport
segment is built around Premiership rugby union and Australian rules football.
Every BBC Sport feed follows the same URL pattern, so adding a sport is one line.
The presenter's lines are in `patter.py` (hand written) and `patter_bulk.py`
(generated).

## Sources

All free and keyless.

- BBC News and BBC Sport RSS, and phys.org for space news
- [Open-Meteo](https://open-meteo.com) for weather
- [Squiggle](https://api.squiggle.com.au) for AFL fixtures and results, and
  AFL.com.au for AFL news
- ESPN's public scoreboard for Premiership rugby fixtures and results

Requests are cached for a few minutes and identify the station in their
User-Agent.

## Known limits

- **Spotify's API is a moving target.** Audio features, recommendations and
  previews were withdrawn for new apps in November 2024, and February 2026 cut
  further. Spotify has proposed restricting development mode to fewer
  endpoints, and the player endpoints this project relies on are in scope. The
  foundation is not guaranteed long term.
- **No intro lengths.** The endpoint that exposed them was withdrawn, so the
  presenter will occasionally talk over a vocal on a track with a cold open.
- **No sound analysis.** Energy, tempo and mood are not available from Spotify
  any more, which is why playlists are sorted by hand.
- **Goes off air when Spotify does.** After thirty seconds with no active
  Spotify device the station stops, since on a personal station that means the
  listener has finished. An ordinary pause does not trigger it.
- **Kokoro needs time.** A bulletin takes around a minute and a half to render
  on an M1, so bulletins are prepared three minutes ahead.

## Files

| File | Role |
|---|---|
| `p2_station.py` | The station loop |
| `library.py` | Track selection and rotation rules, stored in `rotation.db` |
| `patter.py`, `patter_bulk.py` | The presenter's line bank |
| `bulletin.py` | Assembles news and sport bulletins |
| `feeds.py` | Fetches news, sport and weather |
| `radio_speech.py` | Speech synthesis, playback and volume ducking |
| `normalise.py` | Rewrites text so it is spoken properly, for example "feat." and money |
| `radio_auth.py` | Spotify authentication |
| `history_candidates.py` | Playlist candidates from a listening history export |
| `p0_now_playing.py`, `p1_talk_once.py` | Setup checks, in build order |

## Licence

GPL-3.0. See [LICENSE](LICENSE).
