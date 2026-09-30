# RadioTSVN

Radio for the Individual.

A personal radio station built on the Spotify Web API. Tracks are selected from
a Spotify playlist under standard rotation rules, a synthesised presenter speaks
between them, and news, sport and weather bulletins are read from public feeds
on the hour and half hour. Speech is synthesised locally. No language model runs
during playback.

## Status

The station runs end to end on macOS: track selection, presenter breaks and
bulletins. Selection currently draws from a single playlist. Switching between
mood playlists by time of day is planned and not yet implemented.

## Requirements

- macOS. Speech is played through `afplay`, and Spotify must play on the same
  machine so that the two are mixed by the system.
- Python 3.13.
- Spotify Premium on the listening account and on the account that owns the
  Spotify developer app, as required by Spotify since February 2026.
- Approximately 500MB of disk space for voice models.

## Setup

1. Create the environment.

   ```bash
   python3.13 -m venv .venv
   .venv/bin/python -m pip install -r requirements.txt
   ```

2. Create a Spotify app in the
   [developer dashboard](https://developer.spotify.com/dashboard), with Web API
   enabled and the redirect URI `http://127.0.0.1:8888/callback`. Spotify does
   not accept `localhost` in redirect URIs. Each user requires their own app,
   because a development mode app is limited to five manually added users.

3. Copy `.env.example` to `.env` and enter the app's client ID. Authentication
   uses PKCE, so no client secret is required.

4. Download the Kokoro model files (approximately 350MB).

   ```bash
   mkdir -p voices/kokoro
   curl -L -o voices/kokoro/kokoro-v1.0.onnx https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
   curl -L -o voices/kokoro/voices-v1.0.bin https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
   ```

   Piper fallback voices are downloaded automatically on first use.

5. Set `LIBRARY_PLAYLIST` and the bulletin settings in `.env`
   (see [Configuration](#configuration)).

6. Verify the setup in stages, with a track playing in the Spotify desktop app.
   The first run opens a browser window to authorise the app.

   ```bash
   .venv/bin/python p0_now_playing.py   # authentication and playback state
   .venv/bin/python p1_talk_once.py     # speech and volume ducking over one track
   ```

7. Run the station.

   ```bash
   .venv/bin/python p2_station.py
   ```

   `--bulletin news` or `--bulletin sport` schedules a bulletin a few seconds
   after start, for testing. Ctrl-C stops the station and restores the volume.

## Configuration

All settings are read from `.env`. `.env.example` lists each one with its
default.

| Setting | Description |
|---|---|
| `SPOTIFY_CLIENT_ID` | Client ID of the Spotify app |
| `SPOTIFY_REDIRECT_URI` | Redirect URI registered on the app |
| `LIBRARY_PLAYLIST` | Name of the playlist tracks are selected from |
| `STATION_NAME` | Station name as spoken, following "Radio" |
| `PRESENTER_VOICE` | Kokoro voice (e.g. `bm_george`) or Piper voice (e.g. `en_GB-alan-medium`) |
| `NEWS_VOICE` | Voice used for bulletins |
| `PIPER_VOICE` | Presenter voice used if Kokoro fails to load |
| `CROSSFADE_MS` | Spotify's crossfade setting in milliseconds, or 0 |
| `NEWS_MIX` | News categories and headline counts, in reading order |
| `LOCAL_NEWS_FEED` | RSS feed used for the `local` news category |
| `SPORTS` | Sports covered, in reading order |
| `WEATHER_LOCATION` | Place name with optional country code, or latitude and longitude |

A bulletin setting left out of `.env` takes its default. A bulletin setting
present but empty disables that section.

**News.** `NEWS_MIX` takes a comma separated list of `category:count` pairs, for
example `uk:2, local:1, world:1`. Available categories are `uk`, `world`,
`politics`, `business`, `technology`, `health`, `science`, `entertainment`
(BBC News), `space` (phys.org) and `local`. The `local` category reads
`LOCAL_NEWS_FEED`, which accepts any RSS feed. BBC regional feeds follow the
pattern `https://feeds.bbci.co.uk/news/england/<region>/rss.xml`.

**Sport.** `SPORTS` takes a comma separated list. `rugby-premiership` and `afl`
provide dedicated segments with results and fixtures. Any other entry is read
as a BBC Sport section by its URL name, such as `cricket`, `football`,
`formula1`, `golf`, `tennis`, `rugby-league`, `boxing`, `cycling` or
`athletics`, and contributes one headline per bulletin.

**Weather.** `WEATHER_LOCATION` accepts a place name with an optional two letter
country code (`London, GB`), or coordinates (`53.48, -2.24`). Place names are
resolved through the Open-Meteo geocoding API.

## Playlists

The station selects from one playlist, named by `LIBRARY_PLAYLIST` and matched
case-insensitively against the listener's playlists. A playlist of at least 100
tracks is recommended, so that the repetition rules have sufficient range.

Since February 2026 the Spotify Web API returns playlist contents to development
mode apps only for playlists the user owns or collaborates on. Public playlists
owned by other users return no tracks. To use another user's playlist, copy its
tracks into a playlist in the listener's own library.

If no playlist is configured, or it cannot be read, the station falls back to
presenting over whatever Spotify is playing.

Planned mood playlists, for selection by time of day:

| Playlist | Character |
|---|---|
| General Listening | Base rotation, no strong mood |
| Mornings | Warm, mid tempo |
| Focus | Steady, unobtrusive vocals |
| Lift | Fast, loud |
| Evenings | Slower, warmer |
| Late | Sparse, quiet |

### Candidates from listening history

`history_candidates.py` reads a Spotify account data export (requested from the
account's Privacy settings) and proposes tracks for these playlists.

```bash
.venv/bin/python history_candidates.py "/path/to/Spotify Account Data" candidates.csv
```

The most played tracks are excluded, and the remaining tracks are ranked by the
number of separate days on which they were played to completion. A daypart
leaning is assigned where a track's plays in that daypart exceed the listener's
overall distribution, tested with a one-sided binomial test at 0.01. The account
data export contains neither track identifiers nor a skip flag, so a play under
30 seconds is treated as a skip, and identifiers are matched from the export's
liked songs and playlists where available.

## Method

**Track selection.** Each track is drawn by weighted random choice under three
rules. A track is not repeated within four hours, an artist is not repeated
within 45 minutes, and a skipped track has its weight reduced by 70 percent,
with the reduction halving every 14 days. The decaying penalty reflects that
many skips indicate recent repetition rather than dislike. Play and skip history
is stored in a local SQLite file.

**Presenter breaks.** A break occurs every two to three tracks, timed to begin as
a track ends and to continue over the start of the next without stopping the
music. Lines are drawn from a bank of templates in two tiers, witty and plain,
with at most one witty line per break. The bank is written in advance: the
hand-written lines are in `patter.py` and a generated extension in
`patter_bulk.py`.

**Bulletins.** Bulletins are clock-driven and fire on the hour (news and
weather) and half hour (sport and weather). The presenter announces the
bulletin over the music, playback fades and pauses, a second voice reads the
bulletin, and the presenter introduces the next track. Sections with no content
are omitted. Bulletin audio is rendered three minutes ahead of its slot.

**Speech.** Speech is synthesised with
[Kokoro](https://github.com/thewh1teagle/kokoro-onnx) (ONNX build), with
[Piper](https://github.com/OHF-Voice/piper1-gpl) as an automatic fallback.
Text is split at sentence ends and ellipses and each piece synthesised
separately, so that pause lengths can be set by punctuation. A text normaliser
rewrites forms a synthesiser misreads, such as "feat.", remaster tags and sums
of money.

**No runtime model.** There is no language model in the playback loop.
Presenter lines are written ahead of time and selected at runtime, and bulletins
are assembled directly from feed content.

## Data sources

All sources are free and require no key.

- BBC News and BBC Sport RSS feeds
- [phys.org](https://phys.org) space news RSS
- [Open-Meteo](https://open-meteo.com) forecast and geocoding APIs
- [Squiggle](https://api.squiggle.com.au) API for AFL results, and AFL.com.au RSS
- ESPN public scoreboard for Premiership rugby results and fixtures

Responses are cached for five minutes. Requests identify the project in their
User-Agent.

## Limitations

- Spotify withdrew audio features, audio analysis, recommendations and previews
  for new apps in November 2024, with further removals in February 2026.
  Proposed restrictions to development mode include the player endpoints this
  project depends on.
- Track intro lengths are unavailable, so the presenter occasionally speaks over
  vocals on tracks without an instrumental intro.
- Mood and energy cannot be derived from Spotify, so playlists are sorted by
  hand.
- The station stops after 30 seconds without an active Spotify device.
- Kokoro synthesises at approximately real time on a laptop CPU. A bulletin
  takes 80 to 100 seconds to render.
- BBC files all rugby union in a single feed, so Premiership stories are
  selected by keyword and occasional international stories pass through.

## Files

| File | Purpose |
|---|---|
| `p2_station.py` | Station loop |
| `library.py` | Track selection and rotation state |
| `patter.py`, `patter_bulk.py` | Presenter line bank |
| `bulletin.py` | Bulletin assembly |
| `feeds.py` | News, sport and weather retrieval |
| `radio_speech.py` | Speech synthesis, playback and volume control |
| `normalise.py` | Text normalisation for speech |
| `radio_auth.py` | Spotify authentication |
| `history_candidates.py` | Playlist candidates from listening history |
| `p0_now_playing.py`, `p1_talk_once.py` | Setup verification |

## Licence

GPL-3.0. See [LICENSE](LICENSE).
