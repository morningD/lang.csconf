"""Step 2e: Fetch first-author affiliation data from OpenAlex + OpenReview.

For each conference-year:
  - OpenReview conferences (NeurIPS, ICLR, ICML, etc.): fetch first-author
    profile institutions directly — no title matching needed, ~76% coverage.
  - Other conferences: match paper titles against OpenAlex to extract
    first-author institutions. Coverage depends on publisher — IEEE/ACM/Springer
    70-90%; arXiv/Curran Associates near-zero.

Stores results in data/raw/affiliations/.
Incremental: skips conference-years that already have affiliation files.
Use --force to re-crawl all.
"""

import json
import time
from pathlib import Path

from pipeline.utils.openalex_client import (
    extract_first_author_institution,
    search_work,
    _session as _openalex_session,
)
from pipeline.utils.openreview import (
    registered_conferences,
    fetch_papers as openreview_fetch_papers,
    _session as _openreview_session,
)
from pipeline.utils.years import YEAR_FLOOR, year_ceiling

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
AFFIL_DIR = RAW_DIR / "affiliations"
AUTHORS_DIR = RAW_DIR / "authors"
CONFERENCES_FILE = RAW_DIR / "conferences.json"
PROFILE_CACHE_FILE = AFFIL_DIR / "_profile_cache.json"

_global_profile_cache: dict | None = None


def _load_profile_cache() -> dict:
    """Load persistent profile cache from disk."""
    global _global_profile_cache
    if _global_profile_cache is not None:
        return _global_profile_cache
    if PROFILE_CACHE_FILE.exists():
        with open(PROFILE_CACHE_FILE, "r", encoding="utf-8") as f:
            _global_profile_cache = json.load(f)
    else:
        _global_profile_cache = {}
    return _global_profile_cache


def _save_profile_cache():
    """Save persistent profile cache to disk."""
    global _global_profile_cache
    if _global_profile_cache is None:
        return
    AFFIL_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROFILE_CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(_global_profile_cache, f, ensure_ascii=False)


def _load_conferences() -> list[dict]:
    if not CONFERENCES_FILE.exists():
        return []
    with open(CONFERENCES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _get_paper_titles(raw_file: Path) -> list[dict]:
    """Extract unique papers with first-author names from a raw author file."""
    with open(raw_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    papers = {}  # title → {title, first_author}
    for a in data.get("authors", []):
        if a.get("ordinal") == 1:
            title = a["title"]
            if title not in papers:
                papers[title] = {"title": title, "first_author": a["name"]}

    return list(papers.values())


def _fetch_profile_institution(session, profile_id: str) -> dict | None:
    """Fetch institution from an OpenReview profile.

    Returns {"name": str, "country": str} or None.
    Uses urllib with socket-level timeout to survive SSL hangs.
    """
    if not profile_id or not profile_id.startswith("~"):
        return None

    import urllib.request
    import urllib.parse
    import socket
    import ssl

    try:
        old_timeout = socket.getdefaulttimeout()
        socket.setdefaulttimeout(15)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

        url = f"https://api2.openreview.net/profiles?id={urllib.parse.quote(profile_id)}"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        socket.setdefaulttimeout(old_timeout)

        profiles = data.get("profiles", [])
        if not profiles:
            return None
        history = profiles[0].get("content", {}).get("history", [])
        if not history:
            return None
        inst = history[0].get("institution", {})
        name = inst.get("name", "")
        if not name or name.lower() in ("independent", "independent researcher"):
            return None
        return {"name": name, "country": inst.get("country", "")}
    except Exception:
        return None


def _process_openreview(conf_id: str, year: int, session,
                        force: bool = False) -> int | None:
    """Fetch affiliations from OpenReview profiles for a conference-year.

    Returns number of papers with affiliations, or None if skipped.
    """
    safe_id = conf_id.replace("/", "-")
    raw_file = AUTHORS_DIR / f"{safe_id}_{year}.json"
    affil_file = AFFIL_DIR / f"{safe_id}_{year}.json"

    if not raw_file.exists():
        return None
    if not force and affil_file.exists():
        return None

    # Fetch notes from OpenReview
    notes = openreview_fetch_papers(conf_id, year, session=session)
    if not notes:
        return None

    results = []
    has_affil = 0
    profile_cache = _load_profile_cache()
    cache_hits = 0
    cache_misses = 0

    print(f"    Fetching {len(notes)} notes from OpenReview... "
          f"(profile cache: {len(profile_cache)} entries)", flush=True)

    for i, note in enumerate(notes):
        content = note.get("content", {})
        title_field = content.get("title", {})
        title = title_field.get("value", "") if isinstance(title_field, dict) else str(title_field)
        if not title:
            continue

        authors_field = content.get("authors", {})
        author_list = authors_field.get("value", []) if isinstance(authors_field, dict) else authors_field
        authorids_field = content.get("authorids", {})
        authorid_list = authorids_field.get("value", []) if isinstance(authorids_field, dict) else authorids_field

        first_author = author_list[0] if author_list else ""
        first_authorid = authorid_list[0] if authorid_list else ""

        entry = {
            "title": title,
            "first_author": first_author,
            "matched": False,
            "institution": None,
        }

        if first_authorid and first_authorid.startswith("~"):
            # Check cache: use if cached_year >= current crawl year,
            # or if cached_year is 0 (legacy, assume fresh enough for current year)
            cached = profile_cache.get(first_authorid)
            use_cache = False
            if cached:
                cached_year = cached.get("year", 0)
                if cached_year >= year or cached_year == 0:
                    use_cache = True

            if use_cache:
                inst = {"name": cached["name"], "country": cached.get("country", "")}
                cache_hits += 1
            else:
                time.sleep(0.3)  # ~3 RPS for profile API
                inst = _fetch_profile_institution(session, first_authorid)
                if inst:
                    inst["year"] = year
                profile_cache[first_authorid] = inst
                cache_misses += 1

            if inst:
                has_affil += 1
                entry["matched"] = True
                entry["institution"] = inst["name"]
                entry["institution_country"] = inst.get("country", "")
                entry["openreview_profile"] = first_authorid

        results.append(entry)

        if (i + 1) % 20 == 0:
            print(f"    ...{i + 1}/{len(notes)} notes processed "
                  f"({has_affil} with affiliations, cache: {cache_hits} hits / {cache_misses} misses)",
                  flush=True)

    # Persist cache after each conference-year
    _save_profile_cache()

    total = len(results)
    output = {
        "conference": conf_id,
        "year": year,
        "total_papers": total,
        "total_matched": has_affil,
        "total_with_affiliation": has_affil,
        "coverage_pct": round(100 * has_affil / max(total, 1), 1),
        "source": "openreview",
        "papers": results,
    }

    AFFIL_DIR.mkdir(parents=True, exist_ok=True)
    with open(affil_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return has_affil


def _process_openalex(conf_id: str, year: int, session,
                      force: bool = False) -> int | None:
    """Fetch affiliations from OpenAlex for a conference-year.

    Returns the number of papers with affiliations, or None if skipped.
    """
    safe_id = conf_id.replace("/", "-")
    raw_file = AUTHORS_DIR / f"{safe_id}_{year}.json"
    affil_file = AFFIL_DIR / f"{safe_id}_{year}.json"

    if not raw_file.exists():
        return None

    if not force and affil_file.exists():
        return None

    papers = _get_paper_titles(raw_file)
    if not papers:
        return None

    results = []
    matched = 0
    has_affil = 0

    for i, paper in enumerate(papers):
        title = paper["title"]
        first_author = paper["first_author"]

        work = search_work(title, year, session=session)
        if work is None:
            results.append({
                "title": title,
                "first_author": first_author,
                "matched": False,
                "institution": None,
            })
            continue

        matched += 1
        inst = extract_first_author_institution(work)

        entry = {
            "title": title,
            "first_author": first_author,
            "matched": True,
            "openalex_id": work.get("id"),
            "doi": work.get("doi"),
        }
        if inst:
            has_affil += 1
            entry["institution"] = inst["name"]
            entry["institution_country"] = inst.get("country")
            if inst.get("ror"):
                entry["institution_ror"] = inst["ror"]
            if inst.get("raw"):
                entry["raw_affiliation"] = inst["raw"]
        else:
            entry["institution"] = None

        results.append(entry)

        # Rate limiting: ~9 RPS
        time.sleep(0.11)

        # Progress indicator every 100 papers
        if (i + 1) % 100 == 0:
            print(f"    ...{i + 1}/{len(papers)} papers processed "
                  f"({has_affil} with affiliations)")

    # Save results
    output = {
        "conference": conf_id,
        "year": year,
        "total_papers": len(papers),
        "total_matched": matched,
        "total_with_affiliation": has_affil,
        "coverage_pct": round(100 * has_affil / len(papers), 1) if papers else 0,
        "source": "openalex",
        "papers": results,
    }

    AFFIL_DIR.mkdir(parents=True, exist_ok=True)
    with open(affil_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return has_affil


def run(force: bool = False, conferences_filter: list[str] | None = None):
    """Run step 2e: fetch affiliations from OpenReview + OpenAlex.

    OpenReview conferences use profile-based lookup (no title matching).
    Other conferences use OpenAlex title matching.
    """
    conferences = _load_conferences()
    if conferences_filter:
        conferences = [c for c in conferences if c["id"] in conferences_filter]

    if not conferences:
        print("No conferences to process.")
        return

    or_session = _openreview_session()
    oa_session = _openalex_session()
    or_confs = set(registered_conferences())

    total_conf_years = 0
    total_papers_with_affil = 0
    total_papers = 0
    skipped = 0

    ceiling = year_ceiling()

    for conf in conferences:
        conf_id = conf["id"]
        years = conf.get("years", [])
        if not years:
            years = list(range(YEAR_FLOOR, ceiling + 1))

        use_openreview = conf_id in or_confs

        for year in years:
            safe_id = conf_id.replace("/", "-")
            affil_file = AFFIL_DIR / f"{safe_id}_{year}.json"
            raw_file = AUTHORS_DIR / f"{safe_id}_{year}.json"

            if not raw_file.exists():
                continue
            if not force and affil_file.exists():
                skipped += 1
                continue

            source = "OpenReview" if use_openreview else "OpenAlex"
            print(f"  {conf_id} {year} [{source}]...")

            if use_openreview:
                result = _process_openreview(conf_id, year, or_session, force=force)
            else:
                result = _process_openalex(conf_id, year, oa_session, force=force)

            if result is not None:
                total_conf_years += 1
                with open(affil_file) as f:
                    d = json.load(f)
                total_papers += d["total_papers"]
                total_papers_with_affil += d["total_with_affiliation"]
                pct = d["coverage_pct"]
                print(f"  → {conf_id} {year}: {d['total_with_affiliation']}/{d['total_papers']} "
                      f"({pct}%) [{d['source']}]")

    print(f"\nStep 2e complete: {total_conf_years} conference-years processed, "
          f"{skipped} skipped (already exist)")
    if total_papers > 0:
        print(f"Overall: {total_papers_with_affil}/{total_papers} papers with affiliations "
              f"({100 * total_papers_with_affil / total_papers:.1f}%)")


if __name__ == "__main__":
    run()
