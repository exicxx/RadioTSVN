"""
The presenter's script bank.

These lines were written by hand in a style session rather than generated. They
are track agnostic, meaning they fill their slots from whatever is playing and
can air over any record. Per track lines, which say something true about one
specific recording, are generated in bulk ahead of time and do not live here.

The interface is what matters to the rest of the station. choose_segment and
build_line are the only two functions the loop calls, so putting a generated per
track pool behind them is a change to this module rather than to the loop.

Available slots: artist, title, album and year, plus next_artist, next_title,
next_album and next_year on intros, and station everywhere. The station slot is
filled from the STATION_NAME setting, and is written as spoken, so a name the
synthesiser would misread should be spelled phonetically there.
"""

import random

# The generated bank is optional. Deleting patter_bulk.py reverts the whole bulk
# run and leaves the hand written lines below untouched.
try:
    import patter_bulk
except ImportError:
    patter_bulk = None

# A pool entry is either a line on its own or a (line, weight) pair. A bare line
# carries a weight of one, which keeps the bank readable, since the great
# majority of lines are ordinary. A weight below one marks a line that is worth
# keeping but should not be heard often, relative to the rest of its tier.
RARE = 0.25

# Every segment holds two tiers. The witty tier is what the station is for. The
# plain tier exists so that the witty lines have something to land against,
# because a break made of two or three jokes in a row was the clearest fault
# when the bank was first heard aloud rather than read. The loop asks for a
# tone, and allows exactly one witty part per break.
#
# track_forward, a trail for records further ahead than the next one, is not
# written yet. It was held back while Spotify chose the tracks, and the station
# now chooses its own, so the information it needs is available.
SEGMENTS = {
    "track_back": {
        "witty": [
            "That was {artist} with {title}, and I'd like it noted that I "
            "resisted playing the whole of {album} back to back, which given "
            "the week I've had is more restraint than anyone had a right to "
            "expect. Don't tell the shareholders I'm in here.",

            "That was {artist} with {title}, and I'd like it noted that I "
            "resisted playing the whole of {album} back to back, which given "
            "the week I've had is more restraint than anyone had a right to "
            "expect. Technically I'm not licensed to have a favourite album. "
            "Technically.",

            "{title} there from {artist}. There are records you put on and "
            "records that put themselves on, and that one's been letting "
            "itself in through the back door for about a fortnight.",

            "{artist}, {title}. I'd apologise for the volume but you chose the "
            "station, and you knew what you were getting into.",

            "That was {title} from {artist}. I had a whole thing prepared "
            "about that record and I've lost it, which I'm fairly sure is not "
            "supposed to be possible.",

            "{artist}, {title}, off {album}. You've now heard that at a volume "
            "of my choosing, which is the only real power I have in here.",

            "{artist} there with {title}. I've played that a lot lately. If "
            "anyone's auditing this station they'll have questions, and I'll "
            "make the intern answer for them... wait, I am also the intern...",

            "That was {artist} with {title}. I'd normally get someone to check "
            "the levels on that, but the someone is me, and I was busy "
            "talking... well talking to myself.",

            "{title} from {artist}. Off {album}, that one, which I mention "
            "purely because I have the information in front of me and it seems "
            "a waste not to use it.",
        ],
        "plain": [
            "That was {artist} with {title}.",
            "{artist} there. {title}.",
            "{title} from {artist}, off {album}.",
            "That's {artist}, {title}.",
            "{artist} and {title} there.",
            "You've been listening to {title} by {artist}.",
            "{title}, that one. {artist}.",
            "That was {title}, from {album}. {artist}.",
            "{artist} there with {title}. Radio {station}.",
            "{title}. {artist}. Radio {station}.",
        ],
    },
    "station_ident": {
        "witty": [
            "This is Radio {station}, where the playlist was assembled by one person "
            "with no corporate oversight, no focus group and no obligation to "
            "explain these song choices to anybody. Whether that's a feature "
            "or a warning... is up to you.",

            "You're with Radio {station}. Everything you hear was picked because "
            "somebody liked it, which sounds obvious until you consider how "
            "much radio is made the other way round.",

            "Radio {station}. Playing twenty four seven... God I need a holiday.",

            "Radio {station}. Radio for the individual... and I do mean the "
            "individual. I've seen the figures.",

            "Radio {station}, radio for the individual. Stations built for everybody "
            "end up playing the same eight songs.",
        ],
        "plain": [
            "You're listening to Radio {station}.",
            "This is Radio {station}.",
            "Radio {station}. More music shortly.",
            "You're with Radio {station}.",
            "Radio {station}, carrying on.",
            "This is Radio {station}. Stay with me.",
            "Radio {station}. Radio for the individual.",
            "This is Radio {station}, radio for the individual.",
        ],
    },
    "intro": {
        "witty": [
            # Held below its tier mates because it sits close to the line. Kept
            # deliberately rare rather than softened.
            (
                "Coming up, {next_artist}, and this is {next_title}. I'd tell "
                "you to brace yourself but you'll be fine.",
                RARE,
            ),

            "Right. {next_artist} next, and this is {next_title}. I'll be "
            "quiet now.",

            "Coming up it's {next_artist} with {next_title}. I've queued it, "
            "I've announced it, and my involvement ends there.",

            "{next_artist} now. {next_title}. Nothing further from me.",

            "This is {next_title} from {next_artist}. I'd give you my opinion "
            "on it, but nobody asked so I'll shut up.",
        ],
        "plain": [
            "Coming up, {next_artist} with {next_title}.",
            "This is {next_artist}, {next_title}.",
            "{next_artist} next. {next_title}.",
            "Here's {next_artist} with {next_title}.",
            "{next_title}, from {next_artist}.",
            "Next up, {next_artist} and {next_title}.",
            "This one's {next_artist}, {next_title}.",
            "{next_artist} now, with {next_title}.",
            "Coming up it's {next_title} from {next_artist}.",
            "Here's {next_title}. {next_artist}.",
            "This is {next_artist} with {next_title}, off {next_album}.",
            "{next_artist} next, {next_title}, from {next_album}.",
            "Next, {next_artist} with {next_title}.",
            "{next_title} now, from {next_artist}.",
            "Here's {next_artist}. {next_title}.",
        ],
    },
    "filler": {
        "witty": [
            "It has started raining, which sounds about right for this station "
            "and possibly for this entire city. I'd take it up with the higher "
            "ups if they let me out this god damn studio.",

            "I'm told there's a correct number of times you can play a record "
            "in one week before it becomes a problem. I've decided not to find "
            "out what it is.",

            "There is no window in here. I've asked. Radio {station}.",

            "I don't sleep, which sounds like a boast until you remember I "
            "also don't do anything else.",

            "The heating in here is set by somebody who has never had to sit "
            "in it. I've filed a complaint... which I'll be reviewing in the "
            "morning.",
        ],
        "plain": [
            "Right. Let's keep this going.",
            "Plenty more where that came from.",
            "Nothing much to report. Back to the music.",
            "Still here, still going.",
            "That's the way of it. On we go.",
            "Let's have another one.",
        ],
    },
}

# Segment types chosen by their position in a break rather than by rotation.
# intro only exists when the next track is known, so it is placed rather than
# drawn. The clock is handled entirely by bulletin.py.
POSITIONAL = ("intro",)

# Relative frequency of each opening segment. Naming the track that just played
# is the most common thing a presenter does, so it carries most of the weight.
# Idents and musings are the occasional ones, not equal partners.
WEIGHTS = {"track_back": 6, "filler": 2, "station_ident": 1}

# Types exempt from the anti repeat window. Saying what just played two breaks
# running is normal radio. With only three rotatable types, subjecting all of
# them to the window forces strict round robin and makes the weights above
# meaningless.
ALWAYS_AVAILABLE = ("track_back",)

# A segment type may not repeat until this many other breaks have aired. The
# effective window is capped at one less than the number of rotatable types,
# because a window as wide as the pool would leave nothing to choose from and
# silently fall back to allowing anything, including immediate repeats. It
# tightens on its own as more segment types are added.
SEGMENT_MEMORY = 3

# A specific line may not repeat until this many other lines have aired. The
# window spans every segment and both tiers, so it should stay comfortably below
# the size of the smallest tier. If it does not, that tier is exhausted on most
# breaks and the fallback below quietly permits repeats instead.
LINE_MEMORY = 12

TONES = ("witty", "plain")


def _merge(base, extra):
    """Fold a generated bank into the hand written one, tier by tier.

    The generated lines are appended rather than interleaved, so a pool always
    reads as the approved lines first and the bulk run after them. Weighting and
    anti repeat treat both the same, because once a line is in the bank its
    provenance stops mattering to the loop.
    """
    for segment, tiers in extra.items():
        target = base.setdefault(segment, {})
        for tone, lines in tiers.items():
            target.setdefault(tone, []).extend(lines)
    return base


if patter_bulk is not None:
    _merge(SEGMENTS, patter_bulk.SEGMENTS)


def _entry(item):
    """Split a pool entry into its line and its relative weight."""
    if isinstance(item, tuple):
        return item
    return item, 1.0


def _tier(segment, tone):
    """Return one tier of a pool, falling back to the other if it is empty.

    A segment with nothing written in the requested tone still has to say
    something, so the fallback keeps a half filled pool usable rather than
    making the loop handle an empty break.
    """
    pool = SEGMENTS[segment]
    entries = pool.get(tone) or []
    if entries:
        return entries
    other = "plain" if tone == "witty" else "witty"
    return pool.get(other) or []


def choose_segment(recent_types):
    """Pick the next segment type, avoiding anything used recently."""
    rotatable = [s for s in SEGMENTS if s not in POSITIONAL]
    occasional = [s for s in rotatable if s not in ALWAYS_AVAILABLE]
    window = max(0, min(SEGMENT_MEMORY, len(occasional)))
    blocked = set(recent_types[-window:]) if window else set()
    candidates = [
        s for s in rotatable if s in ALWAYS_AVAILABLE or s not in blocked
    ]
    weights = [WEIGHTS.get(s, 1) for s in candidates]
    return random.choices(candidates, weights=weights, k=1)[0]


def build_line(segment, tone, fields, recent_lines):
    """Return (template, rendered_text) for the given segment and tone."""
    pool = [_entry(item) for item in _tier(segment, tone)]
    window = recent_lines[-LINE_MEMORY:]
    candidates = [pair for pair in pool if pair[0] not in window]
    if not candidates:
        candidates = pool
    lines = [line for line, _ in candidates]
    weights = [weight for _, weight in candidates]
    template = random.choices(lines, weights=weights, k=1)[0]
    return template, template.format(**fields)


HOUR_WORDS = [
    "twelve", "one", "two", "three", "four", "five",
    "six", "seven", "eight", "nine", "ten", "eleven",
]


def time_phrase(now):
    """Spoken form of a clock time, for example 'half past ten'.

    Rounded to the nearest quarter. Sixty is included as a rounding target so
    that a time like 10:58 becomes eleven o'clock rather than quarter to eleven.
    Hours are spelled out because the text goes to a speech synthesiser, where a
    numeral is a guess about pronunciation.
    """
    targets = {
        0: ("{} o'clock", 0),
        15: ("quarter past {}", 0),
        30: ("half past {}", 0),
        45: ("quarter to {}", 1),
        60: ("{} o'clock", 1),
    }
    nearest = min(targets, key=lambda m: abs(m - now.minute))
    phrase, hour_offset = targets[nearest]
    hour = (now.hour + hour_offset) % 12
    return phrase.format(HOUR_WORDS[hour])

_ONES = ["", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"]
_TEENS = ["ten", "eleven", "twelve", "thirteen", "fourteen", "fifteen",
          "sixteen", "seventeen", "eighteen", "nineteen"]
_TENS = ["", "", "twenty", "thirty", "forty", "fifty",
         "sixty", "seventy", "eighty", "ninety"]


def _two_digits(n):
    if n < 10:
        return _ONES[n]
    if n < 20:
        return _TEENS[n - 10]
    tens, ones = divmod(n, 10)
    return _TENS[tens] + (" " + _ONES[ones] if ones else "")


def spoken_year(value):
    """Render a four digit year the way it is said aloud, not counted.

    A speech synthesiser reads 2026 as a cardinal number, which is the most
    obvious sign that nobody wrote the line. Years are split into pairs, with
    the two thousands as the exception because that decade genuinely is said in
    full. Anything that is not a four digit year is returned untouched.
    """
    text = str(value).strip()
    if len(text) != 4 or not text.isdigit():
        return text

    year = int(text)
    if 2000 <= year <= 2009:
        return "two thousand" if year == 2000 else "two thousand and " + _ONES[year - 2000]

    century, remainder = divmod(year, 100)
    spoken_century = _two_digits(century)
    if remainder == 0:
        return spoken_century + " hundred"
    if remainder < 10:
        return spoken_century + " oh " + _ONES[remainder]
    return spoken_century + " " + _two_digits(remainder)
