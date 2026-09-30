"""
Voice audition, for choosing the presenter and newsreader voices.

Renders a short test script in each voice and plays them one after another,
so that voices can be compared by ear. Each voice introduces itself by name, so
it can be identified without watching the terminal. The chosen voices are then
set in .env.

Usage

    .venv/bin/python audition_voices.py                  general presenter
    .venv/bin/python audition_voices.py --mode club      a mode's presenter
    .venv/bin/python audition_voices.py --mode news      the newsreader
    .venv/bin/python audition_voices.py --voices bm_george,bm_lewis

Modes are general, club, chill, sunday and news. By default every British
Kokoro voice is auditioned. --voices limits the audition to a comma separated
list, which may include Piper voices. --no-play renders the clips without
playing them. Clips are kept in audio/audition for replaying.

Kokoro renders at roughly real time, so a full audition of eight voices takes a
couple of minutes, and each voice plays as soon as it is ready.
"""

import argparse
import os

from dotenv import load_dotenv

import modes
import radio_speech

HERE = os.path.dirname(os.path.abspath(__file__))
AUDITION_DIR = os.path.join(radio_speech.AUDIO_DIR, "audition")

# The audition has its own script rather than borrowing station lines. Every
# role opens the same way, so voices are compared on identical words, and then
# adds a line or two in the character of that role.
OPENING = ("Testing, testing. Hi, I'm {name}, you're listening to Radio {station}, "
           "and this is the test script for {label}.")

ROLES = {
    "general": (
        "the General Listening playlist",
        "This is where most of the day happens. A bit of music, a bit of chat, "
        "and the news on the hour.",
    ),
    "club": (
        "the Club playlist",
        "Short and loud. I'll say the name of the track, and then I'll get out "
        "of the way.",
    ),
    "chill": (
        "the Chill playlist",
        "Nice and slow. Nowhere to be, and nothing to rush.",
    ),
    "sunday": (
        "the Sunday Morning playlist",
        "Kettle on, feet up. There's plenty of music this morning, and not a "
        "lot of hurry.",
    ),
    # Figures are written as a feed would print them, so the audition also
    # shows how the text normaliser reads them.
    "news": (
        "the news",
        "Here are the headlines. A \u00a32.4bn rail investment for the North of "
        "England. Leicester beat Northampton by twenty seven points to "
        "nineteen. And in London, fourteen degrees, with a sixty percent "
        "chance of rain.",
    ),
}


def name_for_voice(voice):
    """The spoken first name of a voice, from its identifier.

    Kokoro voices are named like bm_george and Piper voices like
    en_GB-alan-medium, so the name is the part after the underscore, or the
    middle part of a Piper name.
    """
    if "-" in voice:
        parts = voice.split("-")
        return parts[1].capitalize() if len(parts) > 1 else voice
    return voice.split("_", 1)[-1].capitalize()


def script_for(role, voice, station):
    """The audition text for one role, spoken by one voice."""
    label, rest = ROLES[role]
    return OPENING.format(name=name_for_voice(voice), station=station,
                          label=label) + " " + rest


def british_kokoro_voices():
    """Every British English voice in the installed Kokoro voice pack."""
    return [v for v in radio_speech._kokoro_engine().get_voices()
            if v.startswith(("bf_", "bm_"))]


def main():
    parser = argparse.ArgumentParser(description="Audition presenter and newsreader voices.")
    parser.add_argument("--mode", default=modes.GENERAL, choices=list(ROLES))
    parser.add_argument("--voices", help="comma separated voices to audition")
    parser.add_argument("--no-play", action="store_true", help="render without playing")
    args = parser.parse_args()

    load_dotenv(os.path.join(HERE, ".env"))
    station = os.getenv("STATION_NAME", "T7")
    voices = ([v.strip() for v in args.voices.split(",") if v.strip()]
              if args.voices else british_kokoro_voices())
    setting = "NEWS_VOICE" if args.mode == "news" else modes.voice_setting(args.mode)

    print("Auditioning {} voices for {}.".format(len(voices), args.mode))
    print()
    os.makedirs(AUDITION_DIR, exist_ok=True)

    for number, voice in enumerate(voices, start=1):
        print("{}/{}  {}".format(number, len(voices), voice), flush=True)
        text = script_for(args.mode, voice, station)
        try:
            radio_speech.ensure_voice(voice)
            path, _ = radio_speech.synthesise(
                text, voice, os.path.join("audition", "{}_{}".format(args.mode, voice))
            )
        except Exception as error:
            print("      unavailable ({})".format(error))
            continue
        if not args.no_play:
            radio_speech.play(path)

    print("\nSet the chosen voice in .env as {}=<voice>.".format(setting))
    print("Clips are in {} for replaying.".format(AUDITION_DIR))


if __name__ == "__main__":
    main()
