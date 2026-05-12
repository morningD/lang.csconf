"""Step 2d: Crawl OpenReview for conferences where DBLP has no data yet.

OpenReview (openreview.net) hosts paper data for several major AI/ML
conferences and often has accepted papers months before DBLP indexes them.
This step checks registered OpenReview venues and fills in missing years.

Also extracts acceptance rates when available.

Runs after step2c (SPARQL + gap filling) as a supplementary source.
"""

import json
from pathlib import Path

from pipeline.utils.openreview import (
    fetch_acceptance_stats,
    fetch_paper_count,
    fetch_papers,
    notes_to_raw_authors,
    registered_conferences,
)
from pipeline.utils.years import YEAR_FLOOR, year_ceiling

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
AUTHORS_DIR = RAW_DIR / "authors"
ACCEPT_RATES_FILE = RAW_DIR / "accept_rates.json"
CONFERENCES_FILE = RAW_DIR / "conferences.json"


def _load_conferences() -> list[dict]:
    if not CONFERENCES_FILE.exists():
        return []
    with open(CONFERENCES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _existing_years(conf_id: str) -> set[int]:
    """Years that already have raw author data (from any source)."""
    years: set[int] = set()
    safe_id = conf_id.replace("/", "-")
    for f in AUTHORS_DIR.glob(f"{safe_id}_*.json"):
        parts = f.stem.rsplit("_", 1)
        if len(parts) == 2:
            try:
                years.add(int(parts[1]))
            except ValueError:
                pass
    return years


def run(force: bool = False, conferences_filter: list[str] | None = None):
    """Run step 2d: crawl OpenReview for missing conference-year data.

    For each registered OpenReview conference, checks years from YEAR_FLOOR
    to year_ceiling() that don't already have raw author data, and fetches
    papers from OpenReview if available.

    If force=True, re-crawls all OpenReview-sourced data even if files exist.
    """
    import requests

    conferences = _load_conferences()
    conf_map = {c["id"]: c for c in conferences}

    or_confs = registered_conferences()
    if conferences_filter:
        or_confs = [c for c in or_confs if c in conferences_filter]

    if not or_confs:
        print("No OpenReview-registered conferences to process.")
        return

    print(f"Checking OpenReview for {len(or_confs)} conferences...")

    session = requests.Session()
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    session.mount("https://", HTTPAdapter(max_retries=retry))

    AUTHORS_DIR.mkdir(parents=True, exist_ok=True)

    filled = 0
    accept_rate_updates: dict[str, list[dict]] = {}

    for conf_id in or_confs:
        meta = conf_map.get(conf_id, {})
        dblp_key = meta.get("dblp", "")
        if isinstance(dblp_key, list):
            dblp_key = dblp_key[0]

        existing = _existing_years(conf_id)
        ceiling = year_ceiling()

        for year in range(YEAR_FLOOR, ceiling + 1):
            # When force=True, only re-crawl OpenReview-sourced files
            if force and year in existing:
                # Check if existing file is from OpenReview
                safe_id = conf_id.replace("/", "-")
                fpath = AUTHORS_DIR / f"{safe_id}_{year}.json"
                if fpath.exists():
                    with open(fpath) as f:
                        data = json.load(f)
                    if data.get("_source") != "openreview":
                        continue  # Don't overwrite SPARQL data
                else:
                    continue
            elif not force and year in existing:
                continue

            # Check if OpenReview has data for this year
            count = fetch_paper_count(conf_id, year, session=session)
            if count == 0:
                continue

            print(f"  {conf_id} {year}: {count} papers on OpenReview → crawling...")
            notes = fetch_papers(conf_id, year, session=session)
            if not notes:
                continue

            raw = notes_to_raw_authors(conf_id, dblp_key, year, notes)
            safe_id = conf_id.replace("/", "-")
            output_file = AUTHORS_DIR / f"{safe_id}_{year}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(raw, f, indent=2, ensure_ascii=False)

            print(f"    Saved {raw['total_papers']} papers ({len(raw['authors'])} authors)")
            filled += 1

            # Also fetch acceptance rate (only if submitted > accepted, i.e. meaningful)
            stats = fetch_acceptance_stats(conf_id, year, session=session)
            if stats and stats["submitted"] > stats["accepted"]:
                accept_rate_updates.setdefault(conf_id, []).append(stats)
                print(f"    Accept rate: {stats['accepted']}/{stats['submitted']} "
                      f"({stats['accepted']/stats['submitted']*100:.1f}%)")

    # Update accept_rates.json with OpenReview data
    if accept_rate_updates:
        existing_rates: dict = {}
        if ACCEPT_RATES_FILE.exists():
            with open(ACCEPT_RATES_FILE, "r", encoding="utf-8") as f:
                existing_rates = json.load(f)

        for conf_id, entries in accept_rate_updates.items():
            if conf_id not in existing_rates:
                existing_rates[conf_id] = []
            by_year = {e["year"]: e for e in existing_rates[conf_id]}
            for entry in entries:
                by_year[entry["year"]] = entry
            existing_rates[conf_id] = sorted(by_year.values(), key=lambda x: -x["year"])

        with open(ACCEPT_RATES_FILE, "w", encoding="utf-8") as f:
            json.dump(existing_rates, f, indent=2, ensure_ascii=False)

        total_rates = sum(len(v) for v in accept_rate_updates.values())
        print(f"Updated acceptance rates for {len(accept_rate_updates)} conferences ({total_rates} entries)")

    if filled:
        print(f"\nOpenReview: filled {filled} conference-year(s)")
        # Remove stale classified files so step3 re-classifies
        classified_dir = DATA_DIR / "classified" / "authors"
        if classified_dir.exists():
            removed = 0
            for conf_id in or_confs:
                safe_id = conf_id.replace("/", "-")
                for year in range(YEAR_FLOOR, year_ceiling() + 1):
                    cf = classified_dir / f"{safe_id}_{year}.json"
                    if cf.exists():
                        # Only remove if raw file is OpenReview-sourced
                        raw_file = AUTHORS_DIR / f"{safe_id}_{year}.json"
                        if raw_file.exists():
                            with open(raw_file) as f:
                                data = json.load(f)
                            if data.get("_source") == "openreview":
                                cf.unlink()
                                removed += 1
            if removed:
                print(f"Removed {removed} stale classified file(s) for re-classification")
    else:
        print("OpenReview: no new data to fill")


if __name__ == "__main__":
    run()
