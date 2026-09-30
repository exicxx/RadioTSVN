"""
Turning catalogue text into something a speech synthesiser can read aloud.

Spotify titles carry information meant for a shop listing rather than for a
presenter. A remaster year, a deluxe edition marker and a bonus track note are
all facts about which copy of a recording is being played, and no presenter has
ever read one out. They are removed rather than softened, because a half spoken
edition marker is worse than none at all.

Punctuation is the other half of the problem. A synthesiser reads a slash as the
word "slash", so AC/DC arrives as "A C slash D C". The generic rules below cover
the common cases, and PRONUNCIATION exists for the ones they cannot, since how a
band name should be said is a question for the ear rather than for a rule.
"""

import re

# Exact text replaced before any other rule runs. Keys are matched without
# regard to case. This is the escape hatch for anything the generic rules get
# wrong, and it is expected to grow as the station is listened to.
PRONUNCIATION = {
    "AC/DC": "A C D C",
}

# Words that mark a chunk as being about the edition rather than the music. A
# bracketed or dash suffixed chunk containing any of these is dropped whole.
EDITION_TERMS = (
    "remaster", "remastered", "deluxe", "edition", "anniversary", "expanded",
    "reissue", "bonus track", "mono", "stereo", "original recording",
    "digitally remastered", "re-master",
)

_TERMS = "|".join(re.escape(term) for term in EDITION_TERMS)

# A bracketed chunk anywhere in the string, for example "(2011 Remaster)".
_BRACKETED = re.compile(
    r"\s*[\(\[][^)\]]*\b(?:" + _TERMS + r")\b[^)\]]*[\)\]]",
    re.IGNORECASE,
)

# A trailing chunk introduced by a dash, for example " - 2003 Remaster".
_DASH_SUFFIX = re.compile(
    r"\s+[-–]\s+[^-–]*\b(?:" + _TERMS + r")\b[^-–]*$",
    re.IGNORECASE,
)

_WHITESPACE = re.compile(r"\s{2,}")

# A featured credit, in its bracketed and bare forms. "feat." and "ft." are shop
# listing shorthand that a synthesiser reads as the syllable "feet". The
# bracketed form becomes a spoken aside, since "Song, featuring X" is how a
# presenter says it and "Song featuring X" run together is not.
_FEATURE_BRACKETED = re.compile(
    r"\s*[\(\[]\s*(?:feat|ft|featuring)\b\.?\s*([^)\]]+)[\)\]]",
    re.IGNORECASE,
)
_FEATURE_BARE = re.compile(r"\b(?:feat|ft)\b\.?", re.IGNORECASE)


def strip_edition(text):
    """Remove remaster, deluxe and edition markers from a title or album."""
    cleaned = _BRACKETED.sub("", text)
    cleaned = _DASH_SUFFIX.sub("", cleaned)
    return cleaned.strip(" -–")


def for_speech(text):
    """Prepare catalogue text to be read aloud.

    Named pronunciations win over every rule, because they exist precisely for
    the cases the rules handle badly. Everything else is emptied of edition
    markers and then relieved of the punctuation a synthesiser reads as a word.
    """
    if not text:
        return text

    for written, spoken in PRONUNCIATION.items():
        if written.lower() in text.lower():
            pattern = re.compile(re.escape(written), re.IGNORECASE)
            text = pattern.sub(spoken, text)

    text = strip_edition(text)

    text = _FEATURE_BRACKETED.sub(lambda m: ", featuring " + m.group(1).strip(), text)
    text = _FEATURE_BARE.sub("featuring", text)

    # A slash is read as a word. Between two pieces of text it is a separator
    # and a pause serves better, so it becomes a comma.
    text = re.sub(r"\s*/\s*", ", ", text)

    return _WHITESPACE.sub(" ", text).strip()


# Currency written for the page rather than the ear. A synthesiser reads
# "\u00a3400K" as "pound four hundred k", because it speaks the symbol where it
# stands and the suffix as a letter. Said aloud the symbol goes last and the
# suffix becomes a word.
_CURRENCY = {"\u00a3": ("pound", "pounds"), "$": ("dollar", "dollars"),
             "\u20ac": ("euro", "euros")}
_MAGNITUDE = {"k": "thousand", "m": "million", "b": "billion", "bn": "billion",
              "thousand": "thousand", "million": "million", "billion": "billion"}
_AMOUNT = re.compile(
    r"([\u00a3$\u20ac])\s?(\d[\d,]*(?:\.\d+)?)"
    r"(?:\s?(bn|thousand|million|billion|k|m|b)\b)?",
    re.IGNORECASE,
)


def amounts(text):
    """Rewrite sums of money the way they are spoken.

    "\u00a3400K" becomes "400 thousand pounds", "\u00a31.5m" becomes "1.5
    million pounds" and "\u00a32.50" becomes "2 pounds 50". The digits are left
    as digits, since the synthesiser reads numbers well and only the symbol and
    the suffix trip it.
    """
    def spoken(match):
        symbol, number, magnitude = match.groups()
        one, many = _CURRENCY[symbol]
        number = number.replace(",", "")
        if magnitude:
            return "{} {} {}".format(number, _MAGNITUDE[magnitude.lower()], many)
        if "." in number:
            whole, fraction = number.split(".", 1)
            if set(fraction) == {"0"}:
                number = whole
            elif len(fraction) == 2:
                unit = one if whole == "1" else many
                return "{} {} {}".format(whole, unit, int(fraction))
        return "{} {}".format(number, one if number == "1" else many)

    return _AMOUNT.sub(spoken, text)
