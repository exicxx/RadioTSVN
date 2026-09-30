"""
Shared Spotify authentication for the radio orchestrator.

Uses the Authorization Code flow with PKCE, which Spotify recommends for
applications that cannot keep a secret, such as a script running on a personal
machine. No client secret is required or stored anywhere. The only credential
needed is the client ID, which is not sensitive and is sent in plain text as
part of every authorisation request.

Reads configuration from scripts/.env. The OAuth token is cached in
scripts/.spotify_cache, so the browser consent screen appears only on the first
run. Both files are gitignored.

The requested scopes cover reading playback state and controlling playback.
Nothing here can modify the library, playlists or account settings.
"""

import os
import sys

import spotipy

import normalise
from dotenv import load_dotenv
from spotipy.oauth2 import SpotifyPKCE

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, ".env")
CACHE_PATH = os.path.join(HERE, ".spotify_cache")

# The playlist scopes are what let the station choose the music rather than
# merely talk over it. Adding them invalidates an existing token, so the cache
# has to be deleted and the browser approval repeated once.
SCOPES = " ".join(
    [
        "user-read-playback-state",
        "user-modify-playback-state",
        "user-read-currently-playing",
        "playlist-read-private",
        "playlist-read-collaborative",
    ]
)


def get_client():
    """Return an authenticated spotipy client, or exit with a readable error."""
    load_dotenv(ENV_PATH)

    client_id = os.getenv("SPOTIFY_CLIENT_ID")
    redirect_uri = os.getenv("SPOTIFY_REDIRECT_URI", "http://127.0.0.1:8888/callback")

    if not client_id:
        sys.exit(
            "No client ID found.\n"
            "  1. Copy .env.example to .env\n"
            "  2. Paste the Client ID from the app's Basic Information page into it\n"
            "  3. Confirm this redirect URI is registered on that app: " + redirect_uri
        )

    auth_manager = SpotifyPKCE(
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=SCOPES,
        cache_path=CACHE_PATH,
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth_manager)


def describe(item):
    """Flatten a Spotify track object into the fields the presenter needs.

    Every title and album the presenter says passes through here, so this is
    where catalogue text is made speakable. Doing it at the single point of
    entry means breaks, bulletin handovers and queue reads are all covered
    without any of them having to remember.
    """
    return {
        "uri": item["uri"],
        "title": normalise.for_speech(item["name"]),
        "artists": normalise.for_speech(
            ", ".join(a["name"] for a in item["artists"])
        ),
        "album": normalise.for_speech(item["album"]["name"]),
        "year": item["album"].get("release_date", "")[:4],
        "duration_ms": item["duration_ms"],
    }
