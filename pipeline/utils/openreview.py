"""OpenReview v2 API client — fetch papers and acceptance rates.

OpenReview (openreview.net) hosts paper submission/review for several major
AI/ML conferences.  It often has accepted-paper data months before DBLP
indexes the proceedings, making it a valuable supplementary data source.

This module provides:
  - A registry of known OpenReview venues (conf_id → venueid pattern)
  - Batch paper fetching with pagination and retry
  - Acceptance rate extraction from conference statistics
"""

from __future__ import annotations

import time
from collections import defaultdict
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://api2.openreview.net"

# ---------------------------------------------------------------------------
# Venue registry
# ---------------------------------------------------------------------------
# Maps our conference ID → OpenReview venue-id pattern.
# {year} placeholder is replaced at query time.
VENUE_REGISTRY: dict[str, str] = {
    "NEURIPS": "NeurIPS.cc/{year}/Conference",
    "ICLR":    "ICLR.cc/{year}/Conference",
    "ICML":    "ICML.cc/{year}/Conference",
    "AISTATS": "aistats.org/AISTATS/{year}/Conference",
    "CoRL":    "robot-learning.org/CoRL/{year}/Conference",
    "UAI":     "auai.org/UAI/{year}/Conference",
    "COLM":    "colmweb.org/COLM/{year}/Conference",
}


def registered_conferences() -> list[str]:
    """Conference IDs with OpenReview support."""
    return list(VENUE_REGISTRY.keys())


def venue_id(conf_id: str, year: int) -> str | None:
    """Return the OpenReview venue-id for a conference-year, or None."""
    pattern = VENUE_REGISTRY.get(conf_id)
    if pattern is None:
        return None
    return pattern.format(year=year)


# ---------------------------------------------------------------------------
# HTTP session
# ---------------------------------------------------------------------------

def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    return s


# ---------------------------------------------------------------------------
# Paper fetching
# ---------------------------------------------------------------------------

def fetch_paper_count(conf_id: str, year: int, *, session: requests.Session | None = None) -> int:
    """Return the number of accepted papers for a conference-year on OpenReview."""
    vid = venue_id(conf_id, year)
    if vid is None:
        return 0
    s = session or _session()
    resp = s.get(f"{API_URL}/notes", params={"content.venueid": vid, "limit": 1, "offset": 0}, timeout=30)
    if resp.status_code != 200:
        return 0
    return resp.json().get("count", 0) or 0


def fetch_papers(conf_id: str, year: int, *, session: requests.Session | None = None) -> list[dict]:
    """Fetch all accepted paper notes from OpenReview for a conference-year.

    Returns raw OpenReview note objects (dicts).
    """
    vid = venue_id(conf_id, year)
    if vid is None:
        return []

    s = session or _session()
    all_notes: list[dict] = []
    offset = 0
    limit = 1000

    while True:
        resp = s.get(
            f"{API_URL}/notes",
            params={"content.venueid": vid, "limit": limit, "offset": offset},
            timeout=60,
        )
        resp.raise_for_status()
        notes = resp.json().get("notes", [])
        if not notes:
            break
        all_notes.extend(notes)
        if len(notes) < limit:
            break
        offset += limit
        time.sleep(0.5)

    return all_notes


def notes_to_raw_authors(conf_id: str, dblp_key: str, year: int, notes: list[dict]) -> dict:
    """Convert OpenReview notes to our raw-author format.

    Returns a dict matching the standard raw author JSON schema:
      {conference, dblp, year, total_papers, _source, authors}
    """
    authors: list[dict] = []
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
                "year": year,
                "ordinal": i + 1,
            })

    return {
        "conference": conf_id,
        "dblp": dblp_key,
        "year": year,
        "total_papers": len(unique_titles),
        "_source": "openreview",
        "authors": authors,
    }


# ---------------------------------------------------------------------------
# Acceptance rate
# ---------------------------------------------------------------------------

def fetch_acceptance_stats(conf_id: str, year: int, *, session: requests.Session | None = None) -> dict | None:
    """Fetch acceptance statistics for a conference-year from OpenReview.

    Tries the /notes count for accepted papers and the conference group
    statistics for submission counts.

    Returns {"year": int, "submitted": int, "accepted": int} or None.
    """
    vid = venue_id(conf_id, year)
    if vid is None:
        return None

    s = session or _session()

    # Accepted paper count from notes API
    accepted = fetch_paper_count(conf_id, year, session=s)
    if accepted == 0:
        return None

    # Try to get submission count from conference invitation stats.
    # OpenReview tracks submitted/accepted via invitation counters.
    # The most reliable approach: check the group's stats page.
    submitted = _fetch_submission_count(s, conf_id, year)

    if submitted and submitted > 0:
        return {
            "year": year,
            "submitted": submitted,
            "accepted": accepted,
        }

    # Fallback: return with accepted only (submitted unknown)
    return None


def _fetch_submission_count(s: requests.Session, conf_id: str, year: int) -> int | None:
    """Try to get the total submission count for a conference-year.

    Checks multiple OpenReview API endpoints for submission statistics.
    """
    vid = venue_id(conf_id, year)
    if vid is None:
        return None

    # Approach 1: Check if there's a submitted paper invitation
    # The submission invitation typically follows the pattern:
    # {venue_id}/-/Submission
    invitation = f"{vid}/-/Submission"
    try:
        resp = s.get(
            f"{API_URL}/notes",
            params={"invitation": invitation, "limit": 1, "offset": 0},
            timeout=30,
        )
        if resp.status_code == 200:
            count = resp.json().get("count", 0)
            if count and count > 0:
                return count
    except Exception:
        pass

    # Approach 2: Check the Blinded_Submission invitation
    invitation2 = f"{vid}/-/Blinded_Submission"
    try:
        resp = s.get(
            f"{API_URL}/notes",
            params={"invitation": invitation2, "limit": 1, "offset": 0},
            timeout=30,
        )
        if resp.status_code == 200:
            count = resp.json().get("count", 0)
            if count and count > 0:
                return count
    except Exception:
        pass

    return None
