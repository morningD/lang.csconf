"""Step 2b: Crawl DBLP HTML index pages for conference venue (city/country).

Instead of parsing long prose titles via SPARQL, this fetches the DBLP conference
index page (e.g. https://dblp.org/db/conf/eurosys/index.html) which has clean
<h2> headings like "EuroSys 2024: Athens, Greece".
"""

import json
import re
import sys
import time
from pathlib import Path

import requests
from tqdm import tqdm

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
VENUES_DIR = RAW_DIR / "venues"
CONFERENCES_FILE = RAW_DIR / "conferences.json"

DBLP_INDEX_URL = "https://dblp.org/db/conf/{dblp_key}/index.html"

# Mirror candidates to try if primary fails (in order)
DBLP_MIRRORS = [
    "https://dblp.org",
    "https://dblp.uni-trier.de",
    "https://dblp.dagstuhl.de",
]

HEADERS = {"User-Agent": "lang.csconf-venue-crawler/1.0 (research project)"}


def _parse_location(location: str) -> dict | None:
    """Parse a location string from a DBLP h2 heading into {city, country}.

    Handles patterns like:
      "Athens, Greece"
      "Philadelphia, PA, USA"
      "Vancouver, BC, Canada"
      "Changsha, Hunan, China"
      "Singapore"                        -> city-state
      "Virtual Event"
      "Virtual Event, UK"
      "Online"
      "Virtual Event / Yokohama, Japan"  -> prefers physical part
      "Tainan, Taiwan / Virtual Conference"
    """
    if not location:
        return None

    # Strip bracketed annotations like "[hybrid]", "[virtual]"
    location = re.sub(r"\s*\[.*?\]", "", location).strip()

    # Handle slash-separated dual venues (e.g. "Virtual / Tokyo, Japan")
    if " / " in location:
        parts = location.split(" / ")
        physical = next(
            (p for p in parts if not re.match(r"^(Virtual|Online)", p, re.I)), None
        )
        location = physical if physical else parts[0]

    location = location.strip()

    # Purely virtual/online
    if re.match(r"^(Virtual\s*(Event|Conference)?|Online)\s*$", location, re.I):
        return {"city": "Virtual", "country": None}

    parts = [p.strip() for p in location.split(",")]

    if not parts or not parts[0]:
        return None

    # Virtual event with country
    if re.match(r"^(Virtual|Online)", parts[0], re.I):
        country = parts[-1] if len(parts) > 1 else None
        return {"city": "Virtual", "country": country}

    city = parts[0]

    if len(parts) == 1:
        # City-state (Singapore, Monaco, etc.) — city == country
        return {"city": city, "country": city}

    # Last part is always the country (ignore intermediate state/province/region)
    country = parts[-1]
    return {"city": city, "country": country}


def _fetch_venues_from_html(dblp_key: str) -> dict[str, dict]:
    """Fetch venues for all years by scraping the DBLP conference index page.

    Returns {year: {city, country, h2_text}} dict.
    """
    last_exc = None
    for mirror in DBLP_MIRRORS:
        url = f"{mirror}/db/conf/{dblp_key}/index.html"
        try:
            resp = requests.get(url, headers=HEADERS, timeout=30)
            if resp.status_code == 404:
                return {}  # Conference not in DBLP under this key
            resp.raise_for_status()
            break
        except requests.RequestException as e:
            last_exc = e
            time.sleep(1)
    else:
        raise last_exc

    html = resp.text

    # Decode HTML entities before parsing
    import html as html_lib
    html = html_lib.unescape(html)

    # Extract all <h2> tags (may contain nested <a> tags)
    raw_h2s = re.findall(r"<h2[^>]*>(.*?)</h2>", html, re.DOTALL)

    venues: dict[str, dict] = {}
    for raw in raw_h2s:
        # Strip HTML tags to get plain text
        text = re.sub(r"<[^>]+>", "", raw).strip()

        # Must contain a 4-digit year
        year_match = re.search(r"\b(20\d{2})\b", text)
        if not year_match:
            continue

        year = year_match.group(1)

        # Location follows the colon: "EuroSys 2024: Athens, Greece"
        colon_idx = text.find(": ")
        if colon_idx == -1:
            continue
        location_str = text[colon_idx + 2:].strip()

        if not location_str:
            continue

        venue = _parse_location(location_str)
        if venue:
            venues[year] = {
                "city": venue["city"],
                "country": venue["country"],
                "h2_text": text,
            }

    return venues


def run(force: bool = False, conferences_filter: list[str] | None = None):
    """Run step 2b: crawl venue data from DBLP HTML index pages."""
    if not CONFERENCES_FILE.exists():
        print("No conferences.json found. Run step 1 first.")
        return

    with open(CONFERENCES_FILE, "r") as f:
        conferences = json.load(f)

    if conferences_filter:
        filter_set = {c.upper() for c in conferences_filter}
        conferences = [
            c for c in conferences
            if c["id"].upper() in filter_set or c["title"].upper() in filter_set
        ]

    VENUES_DIR.mkdir(parents=True, exist_ok=True)

    skipped = 0
    to_fetch = []

    for conf in conferences:
        dblp_value = conf.get("dblp")
        if not dblp_value or dblp_value == "NO DBLP":
            continue

        conf_id = conf["id"]
        output_file = VENUES_DIR / f"{conf_id}.json"
        if not force and output_file.exists():
            skipped += 1
            continue

        # For multi-key conferences, use the first key for venue info
        dblp_keys = dblp_value if isinstance(dblp_value, list) else [dblp_value]
        to_fetch.append((conf_id, dblp_keys[0]))

    print(f"Venue crawl: {len(to_fetch)} conferences to fetch, {skipped} already cached")

    if not to_fetch:
        print("Nothing to crawl.")
        return

    done = 0
    errors = 0

    for conf_id, dblp_key in tqdm(to_fetch, desc="Venue crawl"):
        try:
            venues = _fetch_venues_from_html(dblp_key)

            result = {
                "conference": conf_id,
                "dblp": dblp_key,
                "venues": venues,
            }

            output_file = VENUES_DIR / f"{conf_id}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            done += 1

        except Exception as e:
            print(f"\n  Error fetching {conf_id} ({dblp_key}): {e}")
            errors += 1

        # Be polite to DBLP servers
        time.sleep(0.5)

    print(f"Done: {done} saved, {errors} errors, {skipped} cached")


if __name__ == "__main__":
    force = "--force" in sys.argv
    conf_filter = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            conf_filter = arg.split(",")
    run(force=force, conferences_filter=conf_filter)
