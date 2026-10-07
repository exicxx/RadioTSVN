"""
Choose what the station's bulletins cover.

Asks for a weather location, the news categories and the sports to hear, checks
each answer against the live source, and writes the result to .env. Nothing is
assumed about the listener, so a bulletin only contains what is chosen here.
Running it again replaces the earlier answers and leaves every other line of
.env alone.

Usage
    .venv/bin/python setup_content.py
"""

import os
import shutil
import sys

import feeds

HERE = os.path.dirname(os.path.abspath(__file__))
ENV_PATH = os.path.join(HERE, ".env")
EXAMPLE_PATH = os.path.join(HERE, ".env.example")

NEWS_CATEGORIES = (
    ("uk", "BBC News, UK"),
    ("world", "BBC News, world"),
    ("politics", "BBC News, politics"),
    ("business", "BBC News, business"),
    ("technology", "BBC News, technology"),
    ("health", "BBC News, health"),
    ("science", "BBC News, science and environment"),
    ("entertainment", "BBC News, entertainment and arts"),
    ("space", "phys.org, space news"),
    ("local", "any RSS feed of your choice, such as a regional BBC feed"),
)

# Sports with a segment of their own, then the BBC Sport sections most often
# wanted. Any other BBC Sport section can still be typed by its URL name.
DEDICATED_SPORTS = (
    ("rugby-premiership", "Premiership rugby, with results and fixtures"),
    ("afl", "Australian rules, with results and news"),
)
BBC_SPORTS = (
    "athletics", "boxing", "cricket", "cycling", "football", "formula1", "golf",
    "mixed-martial-arts", "rugby-league", "tennis",
)


def ask(prompt):
    """Read one line, treating the end of input as a request to stop."""
    try:
        return input(prompt).strip()
    except EOFError:
        sys.exit("\nStopped without saving.")


def choose_weather():
    """Ask for a location until it resolves, or is left blank for no weather."""
    print("\nWeather")
    print("  A place name with an optional two letter country code, such as")
    print("  'Paris, FR', or coordinates such as '48.85, 2.35'. Leave blank for")
    print("  no weather.")
    while True:
        text = ask("  Location: ")
        if not text:
            return ""
        os.environ["WEATHER_LOCATION"] = text
        feeds._locations.clear()
        found = feeds.weather_location()
        if found is None:
            print("  Could not find that place. Try adding a country code.")
            continue
        answer = ask("  Found {} ({:.2f}, {:.2f}). Use it? [Y/n] ".format(
            found[2], found[0], found[1])).lower()
        if answer in ("", "y", "yes"):
            return text


def choose_local_feed():
    """Ask for the feed behind the local category, checking it returns stories."""
    print("\n  Local news reads an RSS feed that you choose. Regional BBC feeds")
    print("  follow https://feeds.bbci.co.uk/news/england/<region>/rss.xml and")
    print("  any other RSS feed works. Leave blank to drop the local category.")
    while True:
        url = ask("  Local feed: ")
        if not url:
            return ""
        if feeds._rss_items(url, limit=1):
            return url
        print("  That address returned no stories. Check it and try again.")


def choose_news():
    """Ask for the categories and counts, returning (news_mix, local_feed)."""
    print("\nNews")
    for name, description in NEWS_CATEGORIES:
        print("  {:<14}{}".format(name, description))
    print("  List the categories in reading order, each with a headline count.")
    print("  For example 'uk:2, world:1, space:1'. A name alone gives one")
    print("  headline. Leave blank for no news.")
    known = {name for name, _ in NEWS_CATEGORIES}
    while True:
        text = ask("  News: ")
        if not text:
            return "", ""
        os.environ["NEWS_MIX"] = text
        mix = feeds.news_mix()
        unknown = [name for name, _ in mix if name not in known]
        if unknown:
            print("  Not a category: {}.".format(", ".join(unknown)))
            continue
        local_feed = ""
        if any(name == "local" for name, _ in mix):
            local_feed = choose_local_feed()
            if not local_feed:
                mix = [(name, count) for name, count in mix if name != "local"]
        return ", ".join("{}:{}".format(name, count) for name, count in mix), local_feed


def choose_sport():
    """Ask for sports until every one of them is available."""
    print("\nSport")
    for name, description in DEDICATED_SPORTS:
        print("  {:<20}{}".format(name, description))
    print("  Or a BBC Sport section, one headline each. Common ones are")
    print("  {}.".format(", ".join(BBC_SPORTS)))
    print("  List them in reading order. Leave blank for no sport.")
    dedicated = {name for name, _ in DEDICATED_SPORTS}
    while True:
        text = ask("  Sport: ")
        if not text:
            return ""
        names = [part.strip().lower() for part in text.split(",") if part.strip()]
        missing = [
            name for name in names
            if name not in dedicated
            and not feeds._rss_items(feeds.BBC_SPORT_URL.format(name), limit=1)
        ]
        if missing:
            print("  No BBC Sport feed for {}. Check the spelling.".format(
                ", ".join(missing)))
            continue
        return ", ".join(names)


def write_settings(settings):
    """Set each key in .env, replacing an existing line or adding a new one."""
    if not os.path.exists(ENV_PATH):
        shutil.copyfile(EXAMPLE_PATH, ENV_PATH)
    with open(ENV_PATH) as handle:
        lines = handle.read().splitlines()

    pending = dict(settings)
    for index, line in enumerate(lines):
        key = line.split("=", 1)[0].strip()
        if "=" in line and not line.lstrip().startswith("#") and key in pending:
            lines[index] = "{}={}".format(key, pending.pop(key))
    for key, value in pending.items():
        lines.append("{}={}".format(key, value))

    with open(ENV_PATH, "w") as handle:
        handle.write("\n".join(lines) + "\n")


def main():
    print("Choose what the bulletins cover. Each answer is checked as you go.")
    weather = choose_weather()
    news, local_feed = choose_news()
    sport = choose_sport()

    settings = {
        "WEATHER_LOCATION": weather,
        "NEWS_MIX": news,
        "LOCAL_NEWS_FEED": local_feed,
        "SPORTS": sport,
    }
    print("\nThese will be written to .env")
    for key, value in settings.items():
        print("  {}={}".format(key, value or "(off)"))
    if ask("Save? [Y/n] ").lower() not in ("", "y", "yes"):
        sys.exit("Nothing saved.")
    write_settings(settings)
    print("Saved to {}".format(ENV_PATH))


if __name__ == "__main__":
    main()
