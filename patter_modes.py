"""
Presenter lines for the station's modes.

A mode is selected by the Spotify playlist that is playing, and changes how the
presenter sounds and how often it speaks. The lines here replace the general
bank in patter.py while their mode is active. They follow the same rules as the
general bank, and each was approved individually.

Segments are as in patter.py, with one addition. "open" is spoken once, when
the station switches into the mode. A mode without an "open" segment switches
without comment.

Not yet wired into the station loop. The mode switch that selects these is the
next piece of work.
"""

MODE_SEGMENTS = {
    # Short and sparse, over the start of dance tracks. Plain lines dominate,
    # because breaks are already rare in this mode and a joke in most of them
    # would undo the point of it. No album mentions and no filler.
    "club": {
        "open": {
            "plain": [
                "Right. Club hours on Radio {station}.",
                "This is Radio {station}, I'm going to stay out of the way for a bit.",
            ],
        },
        "track_back": {
            "witty": [
                "{artist}, {title}. I was dancing. You can't prove I wasn't.",

                # Carries its own introduction to the next record, so a break
                # that uses it must not add a separate intro.
                "{title}. {artist}. I've been told to keep the talking to a "
                "minimum this hour, so here is {next_artist} with {next_title}.",

                "That was {artist}. The strobe in here is a desk lamp I switch "
                "on and off. It's working for me.",
            ],
            "plain": [
                "{artist}. {title}.",
                "That was {title}.",
                "{title}, {artist}. Radio {station}.",
                "Radio {station}. {artist}, {title}.",
            ],
        },
        "intro": {
            "witty": [
                "{next_artist}, {next_title}. I'll get out of the way.",
                "{next_title}. No more talking. Mostly.",
            ],
            "plain": [
                "{next_artist}. {next_title}.",
                "Here's {next_title}.",
                "Next, {next_artist}.",
                "This is {next_artist}, {next_title}.",
                "Keep it going. {next_artist}, {next_title}.",
            ],
        },
        "station_ident": {
            "witty": [
                "Radio {station}. The dance floor is your kitchen. I've been "
                "assured it's big enough.",
            ],
            "plain": [
                "Radio {station}.",
                "Radio {station}. Radio for the individual.",
            ],
        },
    },

    # Unhurried, fewer words, gentle and dry. Bulletins do not run in this
    # mode, which two of the idents play on.
    "chill": {
        "track_back": {
            "witty": [
                "{artist}, {title}. I've turned the lights down in here. "
                "There's only one light, so it's quite dark now.",

                "{artist} there with {title}. I'd make you a tea if I had "
                "hands... or a kettle.",
            ],
            "plain": [
                "That was {artist}, {title}.",
                "{title}, from {artist}.",
                "{artist}, with {title}, off {album}.",
                "That was {title}. Radio {station}.",
            ],
        },
        "intro": {
            "witty": [
                "{next_artist} next, with {next_title}. I'll lower my voice, "
                "which in here makes no difference whatsoever.",

                "Here's {next_title}. Nothing more from me for a bit, which is "
                "a promise I've broken before.",
            ],
            "plain": [
                "Here's {next_artist}, {next_title}.",
                "Next, {next_title} from {next_artist}.",
                "{next_artist} now. {next_title}.",
            ],
        },
        "station_ident": {
            "witty": [
                "Radio {station}. No news, no sport, no weather. If anything "
                "happens out there, you'll have to tell me.",

                "This is Radio {station}, where the only thing on the schedule "
                "is not having one.",
            ],
            "plain": [
                "This is Radio {station}. Taking it easy.",
            ],
        },
        "filler": {
            "witty": [
                "Quiet in here. Well, it's always quiet in here. This is just "
                "the deliberate kind.",
            ],
            "plain": [
                "No rush.",
                "Let's stay here a while.",
            ],
        },
    },

    # The chattiest mode, with bulletins left on. The playlist can be played on
    # any day, so no line asserts that it is Sunday outright.
    "sunday": {
        "open": {
            "plain": [
                "Radio {station}, Sunday morning edition. Put the kettle on. I "
                "can't, so it's down to you.",

                "Morning. This is Radio {station}, and there is nowhere either "
                "of us needs to be.",
            ],
        },
        "track_back": {
            "witty": [
                "That was {artist} with {title}. I'd have read the papers "
                "during that, but they don't deliver here. I checked the "
                "letterbox. There isn't one.",

                "{title} from {artist}. Somewhere out there people are doing a "
                "big Sunday lunch. In here it's me, a microphone and a very "
                "clear sense of what I'm missing.",

                "{artist}, {title}. I had a lie in this morning. It lasted the "
                "length of that record.",

                "That was {artist}. Sunday is supposedly a day of rest. I've "
                "put in a request.",
            ],
            "plain": [
                "That was {artist} with {title}.",
                "{artist} there, and {title}.",
                "That was {title}, off {album}. {artist}.",
            ],
        },
        "intro": {
            "witty": [
                "Here's {next_title} from {next_artist}. I'm going to sit back "
                "for this one. I was already sitting, so it's mostly a change "
                "in attitude.",
            ],
            "plain": [
                "Here's {next_artist} with {next_title}.",
                "Coming up, {next_title}, from {next_artist}.",
                "This is {next_artist}, {next_title}, off {next_album}.",
            ],
        },
        "station_ident": {
            "witty": [
                "This is Radio {station}. Your Sunday morning companion, "
                "whether it's Sunday or not. The studio doesn't have a calendar "
                "either.",
            ],
            "plain": [
                "You're with Radio {station}. Radio for the individual.",
            ],
        },
        "filler": {
            "witty": [
                "I've been asked what I do on a Sunday. This. I do this. I also "
                "do it every other day, which takes the shine off slightly.",

                "If you're doing the crossword, eleven across is probably "
                "something to do with rivers. It usually is. I've never "
                "actually seen a crossword.",

                "Somebody out there is making a fry up right now, and I'd like "
                "them to know that I know.",
            ],
            "plain": [
                "No hurry this morning.",
                "Plenty more to come.",
            ],
        },
    },
}
