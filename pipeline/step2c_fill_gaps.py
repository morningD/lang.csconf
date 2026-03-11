"""Step 2c: Fill SPARQL indexing gaps using DBLP Search API fallback.

Some conference-years have proceedings in DBLP but are not indexed in the
SPARQL RDF stream. This step detects those gaps and fills them via the
DBLP Search API + proceedings page cross-referencing.
"""

import json
import re
import sys
from pathlib import Path

from tqdm import tqdm

from pipeline.utils.dblp_search_api import (
    check_proceedings_years,
    discover_venue_keyword,
    fetch_papers_from_html,
    fetch_papers_search_api,
    fetch_proceedings_data,
)
from pipeline.utils.filters import is_proceedings_volume

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
AUTHORS_DIR = RAW_DIR / "authors"
VENUES_DIR = RAW_DIR / "venues"
CONFERENCES_FILE = RAW_DIR / "conferences.json"

EXPECTED_YEARS = list(range(2010, 2027))

# Gap detection thresholds
# If SPARQL returned fewer than this many papers AND proceedings page has more
# than MIN_EXPECTED, it's a gap.
MAX_SPARQL_FOR_GAP = 20
MIN_EXPECTED_FOR_GAP = 30


def _safe_filename(conf_id: str) -> str:
    return conf_id.replace("/", "-")


def _load_conferences(conferences_filter: list[str] | None = None) -> list[dict]:
    with open(CONFERENCES_FILE, "r") as f:
        conferences = json.load(f)

    if conferences_filter:
        filter_set = {c.upper() for c in conferences_filter}
        conferences = [
            c for c in conferences
            if c["id"].upper() in filter_set or c["title"].upper() in filter_set
        ]

    return conferences


def _get_venue_years(conf_id: str) -> set[int]:
    """Get years for which we have venue data (i.e., conference happened)."""
    venue_file = VENUES_DIR / f"{conf_id}.json"
    if not venue_file.exists():
        return set()
    with open(venue_file, "r") as f:
        data = json.load(f)
    return {int(y) for y in data.get("venues", {}).keys()}


def _local_median(year_counts: dict[int, tuple[int, dict]], venue_years: set[int],
                   target_year: int, window: int = 3) -> int:
    """Compute median paper count using a ±window year range around target_year.

    Only considers years with venue data (conference actually happened).
    Falls back to global median if the window has fewer than 2 data points.
    """
    window_counts = sorted(
        c for y, (c, _) in year_counts.items()
        if y in venue_years and abs(y - target_year) <= window
    )
    if len(window_counts) < 2:
        # Fall back to global median if window too small
        window_counts = sorted(
            c for y, (c, _) in year_counts.items() if y in venue_years
        )
    if not window_counts:
        return 0
    return window_counts[len(window_counts) // 2]


def detect_gaps(
    conferences: list[dict],
    force: bool = False,
) -> list[dict]:
    """Detect conference-years where SPARQL returned much fewer papers than expected.

    A gap is detected when:
    - We have venue data for that year (conference happened)
    - SPARQL returned < MAX_SPARQL_FOR_GAP papers (or no raw file exists)
    - The ±3-year local median paper count is >= MIN_EXPECTED_FOR_GAP
      (adapts to conferences with growing/shrinking paper counts)
    - DBLP has actual proceedings links for that year (not just a heading)
      (distinguishes "indexing gap" from "not yet indexed")
    - The gap hasn't already been filled (unless force=True)

    Returns list of dicts: {conf_id, year, dblp_keys, conf, sparql_papers, median_papers}
    """
    gaps = []

    for conf in conferences:
        dblp_value = conf.get("dblp")
        if not dblp_value or dblp_value == "NO DBLP":
            continue

        conf_id = conf["id"]
        safe_id = _safe_filename(conf_id)
        dblp_keys = dblp_value if isinstance(dblp_value, list) else [dblp_value]
        venue_years = _get_venue_years(conf_id)

        # Collect paper counts for years the conference actually happened
        # (has venue data), to compute a meaningful median
        year_counts: dict[int, tuple[int, dict]] = {}  # year -> (total_papers, json_data)
        for year in EXPECTED_YEARS:
            raw_file = AUTHORS_DIR / f"{safe_id}_{year}.json"
            if not raw_file.exists():
                continue
            with open(raw_file, "r") as f:
                data = json.load(f)
            year_counts[year] = (data.get("total_papers", 0), data)

        if not year_counts:
            continue

        # Identify candidate gap years before doing any network calls
        candidate_years: list[tuple[int, int, int, dict]] = []  # (year, total, median, data)
        for year in EXPECTED_YEARS:
            if year not in venue_years:
                continue

            # Case 1: Raw file exists but has very few papers
            if year in year_counts:
                total_papers, data = year_counts[year]
                if total_papers >= MAX_SPARQL_FOR_GAP:
                    continue
                # Check if already filled by a previous run
                if not force and data.get("_source") == "search_api":
                    continue
            else:
                # Case 2: No raw file at all (SPARQL returned 0, file not saved)
                total_papers = 0
                data = {}

            # Use ±3-year local median to adapt to growing/shrinking conferences
            median_papers = _local_median(year_counts, venue_years, year)

            if median_papers < MIN_EXPECTED_FOR_GAP:
                continue

            candidate_years.append((year, total_papers, median_papers, data))

        if not candidate_years:
            continue

        # Check which years actually have proceedings on DBLP (one HTTP request per conf)
        # This filters out "not yet indexed" false positives
        proceedings_years: set[int] = set()
        for dblp_key in dblp_keys:
            proceedings_years.update(check_proceedings_years(dblp_key))

        for year, total_papers, median_papers, data in candidate_years:
            if year not in proceedings_years:
                continue

            gaps.append({
                "conf_id": conf_id,
                "year": year,
                "dblp_keys": dblp_keys,
                "conf": conf,
                "sparql_papers": total_papers,
                "median_papers": median_papers,
            })

    return gaps


def fill_gap(gap: dict) -> dict | None:
    """Fill a single SPARQL gap using the DBLP Search API.

    1. Fetch proceedings page(s) for each dblp_key → extract paper keys
    2. Reverse-search a sample paper key → discover venue keyword
    3. Batch-fetch all papers via Search API using venue keyword
    4. Filter to only papers on the proceedings page
    5. Return result dict in step2 output format
    """
    conf_id = gap["conf_id"]
    year = gap["year"]
    dblp_keys = gap["dblp_keys"]

    all_proc_keys: set[str] = set()
    all_proc_urls: list[str] = []
    all_sample_titles: list[str] = []
    all_html_pages: list[str] = []
    venue_keyword = None

    for dblp_key in dblp_keys:
        proc_keys, proc_urls, sample_titles, html_pages = fetch_proceedings_data(dblp_key, year)
        if not proc_keys:
            continue
        all_proc_keys.update(proc_keys)
        all_proc_urls.extend(proc_urls)
        all_sample_titles.extend(sample_titles)
        all_html_pages.extend(html_pages)

        # Try to discover venue keyword from proceedings page titles
        if venue_keyword is None:
            kw = discover_venue_keyword(dblp_key, proc_urls, sample_titles)
            if kw:
                venue_keyword = kw

    if not all_proc_keys:
        print(f"    No proceedings pages found for {conf_id} {year}")
        return None

    # Cross-filing check: if the MAJORITY of paper keys belong to a different
    # conference (e.g., ECAI 2022 papers are under conf/ijcai/), and that
    # conference already has data, skip to avoid double-counting.
    own_keys_set = set(dblp_keys)
    key_conf_counts: dict[str, int] = {}  # conf_key → count of paper keys
    for pk in all_proc_keys:
        parts = pk.split("/")
        if len(parts) >= 3 and parts[0] == "conf":
            key_conf_counts[parts[1]] = key_conf_counts.get(parts[1], 0) + 1

    if key_conf_counts:
        dominant_conf = max(key_conf_counts, key=key_conf_counts.get)
        if dominant_conf not in own_keys_set:
            # Most papers are under a different conference
            dominant_count = key_conf_counts[dominant_conf]
            total_keys = sum(key_conf_counts.values())
            if dominant_count > total_keys * 0.5:
                # Check if that conference already has data for this year
                for check_file in AUTHORS_DIR.glob(f"*_{year}.json"):
                    with open(check_file, "r") as f:
                        check_data = json.load(f)
                    check_dblp = check_data.get("dblp", "")
                    check_dblp_keys = check_dblp if isinstance(check_dblp, list) else [check_dblp]
                    if dominant_conf in check_dblp_keys and check_data.get("total_papers", 0) >= MIN_EXPECTED_FOR_GAP:
                        print(f"    Skipping: {dominant_count}/{total_keys} papers are under '{dominant_conf}' which already has {check_data['total_papers']} papers")
                        return None

    print(f"    {len(all_proc_keys)} proceedings keys, venue keyword: '{venue_keyword}'")

    papers = []

    # Try Search API first if we have a venue keyword
    if venue_keyword:
        papers = fetch_papers_search_api(
            venue_keyword=venue_keyword,
            year=year,
            valid_keys=all_proc_keys,
        )

    # Fallback: scrape papers directly from proceedings HTML
    if not papers and all_html_pages:
        print(f"    Search API unavailable, falling back to HTML scraping...")
        papers = fetch_papers_from_html(all_html_pages)

    if not papers:
        print(f"    No papers found for {conf_id} {year}")
        return None

    # Convert to step2 output format with deduplication
    seen: set[tuple[str, str]] = set()
    unique_authors: list[dict] = []
    unique_titles: set[str] = set()

    for paper in papers:
        # Skip proceedings volume editor entries (not real papers)
        if is_proceedings_volume(paper["title"]):
            continue
        for author in paper["authors"]:
            norm_title = " ".join(paper["title"].lower().split())
            key = (norm_title, author["name"])
            if key not in seen:
                seen.add(key)
                unique_authors.append({
                    "name": author["name"],
                    "title": paper["title"],
                    "year": year,
                    "ordinal": author["ordinal"],
                })
                unique_titles.add(norm_title)

    dblp_value = dblp_keys[0] if len(dblp_keys) == 1 else dblp_keys
    result = {
        "conference": conf_id,
        "dblp": dblp_value,
        "year": year,
        "total_papers": len(unique_titles),
        "authors": unique_authors,
        "_source": "search_api",
    }

    return result


def run(force: bool = False, conferences_filter: list[str] | None = None):
    """Run step 2c: detect and fill SPARQL indexing gaps."""
    if not CONFERENCES_FILE.exists():
        print("No conferences.json found. Run step 1 first.")
        return

    conferences = _load_conferences(conferences_filter)
    gaps = detect_gaps(conferences, force=force)

    if not gaps:
        print("No SPARQL gaps detected.")
        return

    print(f"Detected {len(gaps)} SPARQL gap(s):")
    for g in gaps:
        print(f"  {g['conf_id']} {g['year']}: {g['sparql_papers']} papers from SPARQL")

    filled = 0
    errors = 0

    for gap in tqdm(gaps, desc="Filling gaps"):
        conf_id = gap["conf_id"]
        year = gap["year"]
        safe_id = _safe_filename(conf_id)

        print(f"\n  Filling {conf_id} {year}...")
        try:
            result = fill_gap(gap)
            if result is None:
                errors += 1
                continue

            output_file = AUTHORS_DIR / f"{safe_id}_{year}.json"

            # If SPARQL had some data, merge: keep all existing authors + add new ones
            if output_file.exists():
                with open(output_file, "r") as f:
                    existing = json.load(f)
                existing_authors = existing.get("authors", [])
                existing_keys = {
                    (" ".join(a["title"].lower().split()), a["name"])
                    for a in existing_authors
                }

                new_authors = [
                    a for a in result["authors"]
                    if (" ".join(a["title"].lower().split()), a["name"]) not in existing_keys
                ]
                merged_authors = existing_authors + new_authors
                merged_titles = {" ".join(a["title"].lower().split()) for a in merged_authors}
                result["authors"] = merged_authors
                result["total_papers"] = len(merged_titles)

            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            print(f"    Saved: {result['total_papers']} papers ({result['total_papers'] - gap['sparql_papers']} new)")
            filled += 1

        except Exception as e:
            print(f"    Error filling {conf_id} {year}: {e}")
            errors += 1

    print(f"\nDone: {filled} gaps filled, {errors} errors")

    # Post-process: merge files where yearOfPublication != conference year
    from pipeline.step2_crawl_sparql import merge_publication_year_splits
    merge_publication_year_splits(conferences_filter)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Fill SPARQL indexing gaps")
    parser.add_argument("--force", action="store_true", help="Re-fill already filled gaps")
    parser.add_argument("--conferences", type=str, help="Comma-separated conference IDs")
    args = parser.parse_args()
    conf_filter = args.conferences.split(",") if args.conferences else None
    run(force=args.force, conferences_filter=conf_filter)
