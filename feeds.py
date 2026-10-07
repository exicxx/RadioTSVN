"""
Live content for the station's bulletins: news, weather and sport.

Every fetcher returns a list, and returns an empty one on failure or when there
is genuinely nothing to report. Nothing in here ever raises and nothing ever
produces a placeholder. A segment with no content is a segment the bulletin
leaves out, because a presenter announcing that there is no rugby news is worse
than a presenter who simply does not mention rugby.

Results are cached for a few minutes. A bulletin fires twice an hour, so there
is no reason to pull the same feeds on every poll, and the sources are free and
unauthenticated and should be treated accordingly.

What is covered is configured in .env, through NEWS_MIX, LOCAL_NEWS_FEED,
SPORTS and WEATHER_LOCATION. Nothing about the listener is assumed, so a setting
that is absent or empty switches its section off. setup_content.py asks for each
one and writes the answers to .env.

Sources, all free and without keys:
    BBC News and BBC Sport RSS, phys.org for space news
    Open-Meteo for weather and for resolving place names
    Squiggle for AFL results, AFL.com.au for AFL news
    ESPN's public scoreboard for Premiership rugby results and fixtures
"""

import datetime
import html
import json
import os
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

USER_AGENT = "RadioTSVN/0.1 (+https://github.com/exicxx/RadioTSVN; non-commercial)"
TIMEOUT_SECONDS = 15

# Feeds are polled far less often than they update, so a short cache is purely
# about not hammering the sources when a bulletin is regenerated.
CACHE_SECONDS = 300

# News categories that can be named in NEWS_MIX. "local" is not listed here,
# because its feed is whatever LOCAL_NEWS_FEED is set to. "space" uses phys.org
# rather than BBC, because BBC files science and environment together and that
# feed is dominated by the environment half.
NEWS_FEEDS = {
    "uk": "https://feeds.bbci.co.uk/news/uk/rss.xml",
    "world": "https://feeds.bbci.co.uk/news/world/rss.xml",
    "politics": "https://feeds.bbci.co.uk/news/politics/rss.xml",
    "business": "https://feeds.bbci.co.uk/news/business/rss.xml",
    "technology": "https://feeds.bbci.co.uk/news/technology/rss.xml",
    "health": "https://feeds.bbci.co.uk/news/health/rss.xml",
    "science": "https://feeds.bbci.co.uk/news/science_and_environment/rss.xml",
    "entertainment": "https://feeds.bbci.co.uk/news/entertainment_and_arts/rss.xml",
    "space": "https://phys.org/rss-feed/space-news/",
}

# Settings read from the environment. Each is read when a bulletin is built, so
# .env must be loaded first. A setting that is absent or empty switches its
# section off.
#
#     NEWS_MIX          categories and headline counts, in reading order
#     LOCAL_NEWS_FEED   RSS feed read as the "local" category
#     SPORTS            sports in reading order
#     WEATHER_LOCATION  place name, optionally with a two letter country code,
#                       or "latitude, longitude"

# Any BBC Sport section can be named in SPORTS by its address, for example
# cricket, football, formula1, golf, tennis, rugby-league, boxing, cycling or
# mixed-martial-arts. Each contributes this many headlines.
BBC_SPORT_URL = "https://feeds.bbci.co.uk/sport/{}/rss.xml"
BBC_SPORT_HEADLINES = 1

# BBC does not cover Australian rules, so AFL reporting comes from the league's
# own feed. Squiggle supplies the scores; this supplies the story around them,
# so the segment is not a bare list of numbers.
AFL_NEWS_URL = "https://www.afl.com.au/rss"

# BBC publishes all rugby union under one feed, so Premiership coverage has to
# be picked out by name. This is best effort and the odd international or URC
# story will pass through.
RUGBY_PREM_TERMS = ("premiership", "gallagher", "saracens", "harlequins",
                    "leicester", "bath", "northampton", "sale", "exeter",
                    "bristol", "gloucester", "newcastle")

SQUIGGLE_URL = "https://api.squiggle.com.au/"

# Premiership results and fixtures. BBC publishes rugby stories but no machine
# readable scores, so the numbers come from ESPN's public scoreboard, which
# needs no key and identifies the competition by the league id below. ESPN marks
# each side as home or away explicitly, which is what the fixtures are read
# from, so a match is never announced the wrong way round.
ESPN_PREM_URL = "https://site.api.espn.com/apis/site/v2/sports/rugby/267979/scoreboard"

# Premiership stories and results per sport bulletin. Six results covers a full
# round.
PREM_STORIES = 2
PREM_RESULTS = 6

# The Premiership segment follows the week rather than running every day.
# Matches fall on a Friday, Saturday or Sunday, and there is little worth saying
# early in the week, so Monday to Wednesday are silent on rugby. Stories and a
# preview of the weekend's fixtures return on Thursday. From Friday the
# weekend's results are read as they come in, alongside whatever is still to be
# played. Days run Monday 0 to Sunday 6.
PREM_STORY_DAYS = frozenset({3, 4, 5, 6})
PREM_FIXTURE_DAYS = frozenset({3, 4, 5, 6})
PREM_RESULT_DAYS = frozenset({4, 5, 6})

GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"

# World Meteorological Organization codes, phrased the way a forecast is read.
WEATHER_CODES = {
    0: "clear", 1: "mostly clear", 2: "partly cloudy", 3: "overcast",
    45: "foggy", 48: "freezing fog",
    51: "light drizzle", 53: "drizzle", 55: "heavy drizzle",
    56: "freezing drizzle", 57: "freezing drizzle",
    61: "light rain", 63: "rain", 65: "heavy rain",
    66: "freezing rain", 67: "freezing rain",
    71: "light snow", 73: "snow", 75: "heavy snow", 77: "snow grains",
    80: "showers", 81: "heavy showers", 82: "violent showers",
    85: "snow showers", 86: "heavy snow showers",
    95: "thunderstorms", 96: "thunderstorms with hail",
    99: "thunderstorms with hail",
}

_cache = {}


def _get(url):
    """Fetch a URL, using a short lived cache. Returns bytes, or None."""
    entry = _cache.get(url)
    if entry and time.time() - entry[0] < CACHE_SECONDS:
        return entry[1]

    try:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        body = urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS).read()
    except Exception:
        # A dead feed is not an error worth stopping a radio station for. Serve
        # whatever is cached, however stale, and otherwise report nothing.
        return entry[1] if entry else None

    _cache[url] = (time.time(), body)
    return body


def _setting(name):
    """An environment setting, stripped, or an empty string if it is not set."""
    return (os.getenv(name) or "").strip()


def _names(text):
    """A comma separated list of names, lower cased, empties dropped."""
    return [part.strip().lower() for part in text.split(",") if part.strip()]


def news_mix():
    """The configured news categories as (name, count) pairs, in reading order.

    Written as "uk:2, local:1". A name without a count takes one headline, and
    a count that is not a whole number is treated as one.
    """
    mix = []
    for entry in _names(_setting("NEWS_MIX")):
        name, _, count = entry.partition(":")
        mix.append((name.strip(), int(count) if count.strip().isdigit() else 1))
    return mix


def sports():
    """The configured sports, in reading order."""
    return _names(_setting("SPORTS"))


_locations = {}


def weather_location():
    """Latitude, longitude and place name for the weather, or None.

    Accepts "latitude, longitude" directly. Otherwise the setting is a place
    name, optionally followed by a two letter country code to settle ambiguous
    names, such as "Paris, FR" against Paris, Texas. Names are
    resolved once through Open-Meteo's geocoding service and remembered for the
    life of the process. None means no weather, either because the setting is
    empty or because the place could not be found.
    """
    text = _setting("WEATHER_LOCATION")
    if not text:
        return None
    if text in _locations:
        return _locations[text]

    parts = [part.strip() for part in text.split(",")]
    try:
        latitude, longitude = float(parts[0]), float(parts[1])
        found = (latitude, longitude, text)
    except (ValueError, IndexError):
        params = {"name": parts[0], "count": 1}
        if len(parts) > 1 and len(parts[-1]) == 2 and parts[-1].isalpha():
            params["countryCode"] = parts[-1].upper()
        body = _get(GEOCODING_URL + "?" + urllib.parse.urlencode(params))
        try:
            place = json.loads(body)["results"][0]
            found = (place["latitude"], place["longitude"], place["name"])
        except (TypeError, ValueError, KeyError, IndexError):
            # Not remembered, so a transient failure is retried next bulletin.
            return None

    _locations[text] = found
    return found


def clean(text):
    """Flatten feed text into something a speech synthesiser can read."""
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&", " and ").replace("%", " percent")
    text = re.sub(r"\s+", " ", text).strip()
    # Feeds often end a truncated summary with an ellipsis, which reads as a
    # stumble rather than a pause.
    return text.rstrip(". ").strip() if text.endswith("...") else text


def _rss_items(url, limit=20):
    """Parse an RSS feed into title and summary pairs."""
    body = _get(url)
    if body is None:
        return []
    try:
        root = ET.fromstring(body)
    except ET.ParseError:
        return []

    items = []
    for node in root.findall(".//item")[:limit]:
        title = clean(node.findtext("title"))
        summary = clean(node.findtext("description"))
        if title:
            items.append({"title": title, "summary": summary})
    return items


def _as_sentence(text):
    """Ensure a fragment ends in a full stop so the synthesiser pauses."""
    text = text.strip()
    if not text:
        return ""
    return text if text[-1] in ".!?" else text + "."


# Words too common to count as shared content between a headline and its
# summary.
_STOPWORDS = frozenset(
    "a an and the of to in on for with at by from is was his her their its as "
    "has have be been are it this that after over into new but".split()
)

# When at least this share of a headline's content words reappear in its
# summary, the summary is taken to be restating the headline, and only the
# summary is read. BBC summaries often do exactly that, and reading both made
# stories sound as though they were being announced twice. Below the threshold
# the two carry different information, such as a fee that appears only in the
# headline, and both are kept.
RESTATEMENT_THRESHOLD = 0.6


def _content_words(text):
    """Distinctive words, cut to five letters as a crude stem.

    The cut is what lets "retires" match "retirement" and "internationals"
    match "international" without pulling in a stemming library.
    """
    words = re.findall(r"[a-z0-9\u00a3$\u20ac]+", text.lower())
    return {w[:5] for w in words if len(w) > 1 and w not in _STOPWORDS}


# Markers of rolling coverage rather than a story. A live blog has no reportable
# content of its own, it is a page asking the reader to keep refreshing, so read
# aloud it becomes "follow our live coverage" with nothing attached. Skipping
# these is what stops the Australian rules segment collapsing into scores alone.
_ROLLING = (
    "live:", "follow live", "live coverage", "as it happened", "live reaction",
    "live updates", "follow our live", "minute-by-minute", "watch live",
    "live stream", "blog:",
)


def _is_rolling(item):
    """True if the item is a live blog or stream rather than a written story."""
    haystack = (item["title"] + " " + item["summary"]).lower()
    return any(marker in haystack for marker in _ROLLING)


def _first_story(url, seen):
    """The first item on a feed that is a real story and has not been used."""
    for item in _rss_items(url):
        if item["title"] in seen or _is_rolling(item):
            continue
        return item
    return None


def _story(item):
    """Speech for one story, without saying the same thing twice."""
    title, summary = item["title"], item["summary"]
    if not summary:
        return _as_sentence(title)
    head = _content_words(title)
    if head and len(head & _content_words(summary)) / len(head) >= RESTATEMENT_THRESHOLD:
        return _as_sentence(summary)
    return _as_sentence(title) + " " + _as_sentence(summary)


def news(mix=None):
    """Headlines across categories, each with its one line of context.

    Returns a list of dicts with category, title, summary and speech. An empty
    list means nothing could be fetched, and the bulletin should omit news
    rather than announce its absence.
    """
    stories = []
    seen = set()
    local_feed = _setting("LOCAL_NEWS_FEED")
    for category, wanted in (mix or news_mix()):
        url = local_feed if category == "local" else NEWS_FEEDS.get(category)
        if not url:
            continue
        taken = 0
        for item in _rss_items(url):
            if taken >= wanted:
                break
            if item["title"] in seen or _is_rolling(item):
                continue
            seen.add(item["title"])
            taken += 1
            stories.append({
                "category": category,
                "title": item["title"],
                "summary": item["summary"],
                "speech": _story(item),
            })
    return stories


def weather():
    """Current conditions and today's range for the configured place.

    Returns a dict, or None if weather is switched off or unavailable. The
    forecast day is the place's own, since Open-Meteo is asked to use the local
    timezone of the coordinates.
    """
    location = weather_location()
    if location is None:
        return None
    latitude, longitude, _ = location
    query = urllib.parse.urlencode({
        "latitude": latitude,
        "longitude": longitude,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max",
        "timezone": "auto",
        "forecast_days": 1,
    })
    body = _get(FORECAST_URL + "?" + query)
    if body is None:
        return None
    try:
        data = json.loads(body)
        current = data["current"]
        daily = data["daily"]
    except (ValueError, KeyError):
        return None

    now_c = round(current["temperature_2m"])
    description = WEATHER_CODES.get(current["weather_code"], "unsettled")
    high = round(daily["temperature_2m_max"][0])
    low = round(daily["temperature_2m_min"][0])
    rain_chance = daily["precipitation_probability_max"][0]

    speech = "It's {} and {} degrees out there".format(description, now_c)
    if high != now_c:
        speech += ", topping out at {}".format(high)
    speech += ", down to {} overnight".format(low)
    if rain_chance is not None and rain_chance >= 40:
        speech += ", and a {} percent chance of rain".format(int(rain_chance))
    speech += "."

    return {
        "now_c": now_c, "high_c": high, "low_c": low,
        "description": description, "rain_chance": rain_chance,
        "speech": speech,
    }


def _afl_results(limit=3):
    """Most recently completed AFL matches, newest last. Empty in the off season."""
    year = time.gmtime().tm_year
    url = SQUIGGLE_URL + "?" + urllib.parse.urlencode(
        {"q": "games", "year": year, "complete": 100}
    ).replace("&", ";")
    body = _get(url)
    if body is None:
        return []
    try:
        games = json.loads(body).get("games") or []
    except ValueError:
        return []

    games = [g for g in games if g.get("hscore") is not None]
    games.sort(key=lambda g: g.get("date") or "")
    recent = games[-limit:]
    return [{
        "speech": "{} {}, {} {}.".format(
            g.get("hteam"), g.get("hscore"), g.get("ateam"), g.get("ascore")
        )
    } for g in recent]


def _club(name):
    """A club's name as a presenter says it.

    ESPN uses the formal names, so Bath, Gloucester and Bristol arrive as "Bath
    Rugby", "Gloucester Rugby" and "Bristol Rugby". Nobody says the word "Rugby"
    in a rugby bulletin, where it goes without saying, so it is dropped.
    """
    return re.sub(r"\s*\bRugby\b\s*", " ", name or "").strip()


def _prem_day(day):
    """Every Premiership match ESPN lists for one date. Empty on any failure.

    The endpoint rejects a date range and answers one day at a time, so a
    window is built by asking for each day in turn.
    """
    stamp = day.strftime("%Y%m%d")
    body = _get(ESPN_PREM_URL + "?" + urllib.parse.urlencode({"dates": stamp}))
    if body is None:
        return []
    try:
        events = json.loads(body).get("events") or []
    except ValueError:
        return []

    matches = []
    for event in events:
        competitions = event.get("competitions") or []
        if not competitions:
            continue
        competition = competitions[0]
        sides = {c.get("homeAway"): c for c in competition.get("competitors") or []}
        home, away = sides.get("home"), sides.get("away")
        if home is None or away is None:
            continue
        try:
            kickoff = datetime.datetime.fromisoformat(
                event["date"].replace("Z", "+00:00")
            ).astimezone()
        except (KeyError, ValueError):
            continue
        matches.append({
            "id": event.get("id"),
            "state": competition.get("status", {}).get("type", {}).get("state"),
            "kickoff": kickoff,
            "home": _club(home.get("team", {}).get("displayName")),
            "away": _club(away.get("team", {}).get("displayName")),
            "home_score": home.get("score"),
            "away_score": away.get("score"),
        })
    return matches


def _prem_weekend(now):
    """Every Premiership match from this week's Thursday to its Sunday.

    Kept by event id, because a match near midnight is returned by both of the
    days it borders. Sorted by kick off.
    """
    thursday = now.date() - datetime.timedelta(days=now.weekday() - 3)
    seen, matches = set(), []
    for offset in range(4):
        for match in _prem_day(thursday + datetime.timedelta(days=offset)):
            if match["id"] in seen:
                continue
            seen.add(match["id"])
            matches.append(match)
    matches.sort(key=lambda match: match["kickoff"])
    return matches


def _day_phrase(kickoff, now):
    """When a match is, the way a presenter would put it."""
    days = (kickoff.date() - now.date()).days
    if days == 0:
        return "tonight" if kickoff.hour >= 17 else "later today"
    if days == 1:
        return "tomorrow"
    return "on " + kickoff.strftime("%A")


def _listed(phrases):
    """Join phrases as spoken, "a, b and c", without a comma before the and."""
    if len(phrases) < 2:
        return "".join(phrases)
    return ", ".join(phrases[:-1]) + " and " + phrases[-1]


def _prem_results_speech(matches):
    """The weekend's finished matches, home side first."""
    played = [m for m in matches if m["state"] == "post"][-PREM_RESULTS:]
    if not played:
        return None
    return "The latest from the Premiership. " + " ".join(
        "{} {}, {} {}.".format(m["home"], m["home_score"], m["away"], m["away_score"])
        for m in played
    )


def _prem_fixtures_speech(matches, now, after_results):
    """The weekend's matches still to be played, grouped by day."""
    pending = [m for m in matches if m["state"] == "pre" and m["kickoff"] > now]
    if not pending:
        return None
    groups = []
    for match in pending:
        phrase = _day_phrase(match["kickoff"], now)
        if not groups or groups[-1][0] != phrase:
            groups.append((phrase, []))
        groups[-1][1].append("{} host {}".format(match["home"], match["away"]))
    opener = ("Still to come this weekend in the Premiership."
              if after_results else "Coming up this weekend in the Premiership.")
    sentences = [
        "{}, {}.".format(phrase[0].upper() + phrase[1:], _listed(games))
        for phrase, games in groups
    ]
    return opener + " " + " ".join(sentences)


def _premiership(now, seen):
    """Premiership rugby union results, stories and fixtures, by day of the week.

    The segment follows the week rather than running every day. Results lead
    from Friday, because the scores are what is most wanted, then stories, then
    whatever is still to be played, since "still to come" is a natural way to
    leave a segment.
    """
    weekday = now.weekday()
    if weekday not in (PREM_STORY_DAYS | PREM_FIXTURE_DAYS | PREM_RESULT_DAYS):
        return []
    items = []
    weekend = _prem_weekend(now)

    results = (_prem_results_speech(weekend)
               if weekday in PREM_RESULT_DAYS else None)
    if results:
        items.append({"source": "rugby-scores", "speech": results})

    taken = 0
    for item in (_rss_items(BBC_SPORT_URL.format("rugby-union"))
                 if weekday in PREM_STORY_DAYS else []):
        if taken >= PREM_STORIES:
            break
        if item["title"] in seen or _is_rolling(item):
            continue
        haystack = (item["title"] + " " + item["summary"]).lower()
        if any(term in haystack for term in RUGBY_PREM_TERMS):
            seen.add(item["title"])
            taken += 1
            items.append({"source": "rugby", "speech": _story(item)})

    fixtures = (_prem_fixtures_speech(weekend, now, bool(results))
                if weekday in PREM_FIXTURE_DAYS else None)
    if fixtures:
        items.append({"source": "rugby-fixtures", "speech": fixtures})
    return items


def _afl(seen):
    """AFL reporting followed by the latest scores.

    Reporting comes first, so the segment reads as news with a results round up
    rather than a list of numbers with nothing around it. The segment falls
    silent on its own in the off season, since both sources go quiet.
    """
    items = []
    story = _first_story(AFL_NEWS_URL, seen)
    if story is not None:
        seen.add(story["title"])
        items.append({"source": "afl-news", "speech": _story(story)})

    results = _afl_results()
    if results:
        items.append({
            "source": "afl-scores",
            "speech": "And the latest from the A F L. "
                      + " ".join(r["speech"] for r in results),
        })
    return items


def _bbc_sport(section, seen):
    """Headlines from one BBC Sport section, named by its address."""
    items = []
    for item in _rss_items(BBC_SPORT_URL.format(section)):
        if len(items) >= BBC_SPORT_HEADLINES:
            break
        if item["title"] in seen or _is_rolling(item):
            continue
        seen.add(item["title"])
        items.append({"source": section, "speech": _story(item)})
    return items


def sport(chosen=None, now=None):
    """Sport items for the configured sports, in the order they are listed.

    "rugby-premiership" and "afl" have dedicated segments with scores and
    fixtures. Any other name is read as a BBC Sport section. A sport with
    nothing to report is simply absent.

    A story is read once however many feeds carry it, because BBC files the
    same item under more than one sport.
    """
    now = now or datetime.datetime.now().astimezone()
    items = []
    seen = set()
    for name in (sports() if chosen is None else chosen):
        if name == "rugby-premiership":
            items.extend(_premiership(now, seen))
        elif name == "afl":
            items.extend(_afl(seen))
        else:
            items.extend(_bbc_sport(name, seen))
    return items
