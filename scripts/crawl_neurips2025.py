"""Crawl NeurIPS 2025 accepted papers from OpenReview v2 API.

DBLP has not yet indexed NeurIPS 2025 proceedings. This script fetches
paper titles and authors from OpenReview and saves them in the standard
raw author format used by the pipeline.

Usage:
    python scripts/crawl_neurips2025.py
"""

import json
import sys
import time
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://api2.openreview.net/notes"


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s
OUTPUT_FILE = Path(__file__).parent.parent / "data" / "raw" / "authors" / "NEURIPS_2025.json"


def fetch_all_papers() -> list[dict]:
    """Fetch all NeurIPS 2025 main conference papers from OpenReview."""
    session = _session()
    all_notes = []
    offset = 0
    limit = 1000

    while True:
        params = {
            "content.venueid": "NeurIPS.cc/2025/Conference",
            "limit": limit,
            "offset": offset,
        }
        print(f"  Fetching offset={offset}, limit={limit}...")
        resp = session.get(API_URL, params=params, timeout=60)
        resp.raise_for_status()
        data = resp.json()

        notes = data.get("notes", [])
        if not notes:
            break

        all_notes.extend(notes)
        print(f"    Got {len(notes)} papers (total: {len(all_notes)})")

        if len(notes) < limit:
            break

        offset += limit
        time.sleep(0.5)

    return all_notes


def main():
    print("Crawling NeurIPS 2025 papers from OpenReview...")
    notes = fetch_all_papers()
    print(f"Total papers fetched: {len(notes)}")

    # Convert to raw author format
    authors = []
    unique_titles: set[str] = set()

    for note in notes:
        content = note.get("content", {})
        title_field = content.get("title", {})
        title = title_field.get("value", "") if isinstance(title_field, dict) else str(title_field)
        if not title:
            continue

        authors_field = content.get("authors", {})
        author_list = authors_field.get("value", []) if isinstance(authors_field, dict) else authors_field
        if not author_list:
            continue

        norm_title = " ".join(title.lower().split())
        unique_titles.add(norm_title)

        for i, name in enumerate(author_list):
            if not name or name.startswith("LinkedIn:") or name.startswith("Twitter:"):
                continue
            authors.append({
                "name": name,
                "title": title,
                "year": 2025,
                "ordinal": i + 1,
            })

    result = {
        "conference": "NEURIPS",
        "dblp": "nips",
        "year": 2025,
        "total_papers": len(unique_titles),
        "_source": "openreview",
        "authors": authors,
    }

    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(unique_titles)} papers ({len(authors)} author entries) to {OUTPUT_FILE}")

    # Summary by acceptance type
    by_venue: dict[str, int] = {}
    for note in notes:
        content = note.get("content", {})
        venue_field = content.get("venue", {})
        venue = venue_field.get("value", "unknown") if isinstance(venue_field, dict) else str(venue_field)
        by_venue[venue] = by_venue.get(venue, 0) + 1
    print("\nBy acceptance type:")
    for v, c in sorted(by_venue.items()):
        print(f"  {v}: {c}")


if __name__ == "__main__":
    main()
