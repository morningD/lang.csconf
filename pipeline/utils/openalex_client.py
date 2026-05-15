"""OpenAlex API client — fetch paper affiliation data.

OpenAlex (openalex.org) provides structured institution data (ROR IDs,
display names, raw affiliation strings) for scholarly works. Coverage
depends on publisher: IEEE/ACM/Springer papers typically have 70-90%
affiliation coverage; arXiv/Curran Associates papers have near-zero.

Rate limit: 10 req/sec in the polite pool (with mailto parameter).
"""

from __future__ import annotations

import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

API_URL = "https://api.openalex.org"
MAILTO = "morningd.github@gmail.com"

# Fields we need from the works endpoint
_WORK_FIELDS = "id,doi,title,authorships"


def _session() -> requests.Session:
    s = requests.Session()
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.params = {"mailto": MAILTO}
    return s


def search_work(title: str, year: int, *, session: requests.Session | None = None) -> dict | None:
    """Search OpenAlex for a single work by title + year.

    Returns the top match with authorships, or None if not found.
    Prefers proceedings versions (non-arXiv DOI) over preprints.
    """
    s = session or _session()
    try:
        r = s.get(f"{API_URL}/works", params={
            "filter": f"title.search:{title[:200]},publication_year:{year}",
            "select": _WORK_FIELDS,
            "per_page": 10,
            "sort": "relevance_score:desc",
        }, timeout=15)
        if r.status_code != 200:
            return None

        results = r.json().get("results", [])
        if not results:
            return None

        # Prefer proceedings version (non-arXiv DOI) over arXiv preprint
        proceedings = [w for w in results
                       if w.get("doi") and "arxiv" not in (w.get("doi") or "")]
        return proceedings[0] if proceedings else results[0]
    except requests.RequestException:
        return None


def search_works_batch(titles: list[tuple[str, int]],
                       *, session: requests.Session | None = None,
                       delay: float = 0.11) -> list[dict | None]:
    """Search OpenAlex for multiple works by title + year.

    Args:
        titles: list of (title, year) tuples.
        delay: seconds between requests (default ~9 RPS).

    Returns:
        list of work dicts or None, aligned with input order.
    """
    s = session or _session()
    results: list[dict | None] = []
    for title, year in titles:
        results.append(search_work(title, year, session=s))
        time.sleep(delay)
    return results


def extract_first_author_institution(work: dict) -> dict | None:
    """Extract first author's institution from an OpenAlex work.

    Returns {"name": str, "ror": str|None, "country": str|None, "raw": str|None}
    or None if no affiliation data.
    """
    authorships = work.get("authorships", [])
    if not authorships:
        return None

    # Find first author
    first = next((a for a in authorships if a.get("author_position") == "first"), authorships[0])

    # Try structured institution data first
    institutions = first.get("institutions", [])
    if institutions:
        inst = institutions[0]
        return {
            "name": inst.get("display_name", ""),
            "ror": inst.get("ror", ""),
            "country": inst.get("country_code", ""),
            "raw": None,
        }

    # Fallback to raw affiliation strings
    raw_affils = first.get("raw_affiliation_strings", [])
    if raw_affils:
        return {
            "name": raw_affils[0],
            "ror": None,
            "country": None,
            "raw": raw_affils[0],
        }

    return None
