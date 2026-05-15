"""Import first-author affiliation data from pre-compiled datasets.

Sources:
  1. martenlienen/icml-neurips-iclr-dataset (CSV)
     - NeurIPS 2006-2024, ICML 2017-2024, ICLR 2018-2024
     - ~100% affiliation coverage for first authors
     - URL: https://github.com/martenlienen/icml-neurips-iclr-dataset

  2. papercopilot/paperlists (JSON)
     - ICLR 2013-2026, NeurIPS 2020-2024, ICML 2017-2024, CoRL, etc.
     - Has `aff` field with semicolon-separated affiliations per author
     - URL: https://github.com/papercopilot/paperlists

Usage:
  python scripts/import_affiliations.py --source martenlienen
  python scripts/import_affiliations.py --source papercopilot
  python scripts/import_affiliations.py --source martenlienen --force  # overwrite existing
  python scripts/import_affiliations.py --source martenlienen --conferences NEURIPS ICML
"""

import argparse
import csv
import io
import json
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
AFFIL_DIR = RAW_DIR / "affiliations"
AUTHORS_DIR = RAW_DIR / "authors"

# Conference name mapping from external datasets to our IDs
NAME_TO_ID = {
    "NeurIPS": "NEURIPS",
    "NIPS": "NEURIPS",
    "ICML": "ICML",
    "ICLR": "ICLR",
    "AISTATS": "AISTATS",
    "CoRL": "CoRL",
    "UAI": "UAI",
    "COLM": "COLM",
}


def _normalize_title(title: str) -> str:
    """Normalize title for fuzzy matching: lowercase, strip punctuation."""
    t = title.lower().strip()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t


def _load_raw_paper_titles(conf_id: str, year: int) -> dict[str, dict]:
    """Load raw author file and return {normalized_title: {title, first_author}}."""
    safe_id = conf_id.replace("/", "-")
    raw_file = AUTHORS_DIR / f"{safe_id}_{year}.json"
    if not raw_file.exists():
        return {}

    with open(raw_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    papers = {}
    for a in data.get("authors", []):
        if a.get("ordinal") == 1:
            title = a["title"]
            norm = _normalize_title(title)
            if norm and norm not in papers:
                papers[norm] = {"title": title, "first_author": a["name"]}
    return papers


def _save_affiliation_file(conf_id: str, year: int, papers: list[dict],
                            source: str):
    """Save affiliation data in our standard format."""
    has_affil = sum(1 for p in papers if p.get("institution"))
    total = len(papers)

    output = {
        "conference": conf_id,
        "year": year,
        "total_papers": total,
        "total_matched": has_affil,
        "total_with_affiliation": has_affil,
        "coverage_pct": round(100 * has_affil / max(total, 1), 1),
        "source": source,
        "papers": papers,
    }

    safe_id = conf_id.replace("/", "-")
    affil_file = AFFIL_DIR / f"{safe_id}_{year}.json"
    AFFIL_DIR.mkdir(parents=True, exist_ok=True)
    with open(affil_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return has_affil, total


def _import_martenlienen(force: bool = False,
                         conferences_filter: set[str] | None = None):
    """Import affiliations from martenlienen CSV dataset."""
    import requests

    url = "https://raw.githubusercontent.com/martenlienen/icml-neurips-iclr-dataset/master/papers.csv"
    print(f"Downloading martenlienen dataset from {url}...")
    for attempt in range(3):
        try:
            resp = requests.get(url, timeout=120)
            resp.raise_for_status()
            csv_data = resp.text
            break
        except Exception as e:
            print(f"  Attempt {attempt+1}/3 failed: {e}")
            if attempt == 2:
                print("  All attempts failed. Aborting.")
                return
            time.sleep(2)

    reader = csv.DictReader(io.StringIO(csv_data))

    # Group by (conference, year) — collect first-author affiliation per title
    conf_year_data = defaultdict(lambda: defaultdict(dict))  # conf_year -> {norm_title -> affiliation}

    for row in reader:
        conf_name = row["Conference"]
        conf_id = NAME_TO_ID.get(conf_name)
        if not conf_id:
            continue
        if conferences_filter and conf_id not in conferences_filter:
            continue

        year = int(row["Year"])
        title = row["Title"]
        author = row["Author"]
        affil = (row.get("Affiliation") or "").strip()

        # Only store first author's affiliation (first row per title)
        norm = _normalize_title(title)
        key = (conf_id, year)
        if norm and norm not in conf_year_data[key]:
            conf_year_data[key][norm] = {
                "title": title,
                "author": author,
                "affiliation": affil,
            }

    print(f"Loaded {len(conf_year_data)} conference-years from CSV")

    total_imported = 0
    total_skipped = 0
    total_papers = 0
    total_with_affil = 0

    for (conf_id, year), csv_papers in sorted(conf_year_data.items()):
        safe_id = conf_id.replace("/", "-")
        affil_file = AFFIL_DIR / f"{safe_id}_{year}.json"

        if not force and affil_file.exists():
            total_skipped += 1
            continue

        # Load our raw paper titles for matching
        raw_papers = _load_raw_paper_titles(conf_id, year)
        if not raw_papers:
            continue

        results = []
        matched = 0
        unmatched = 0

        for norm_title, raw_info in raw_papers.items():
            entry = {
                "title": raw_info["title"],
                "first_author": raw_info["first_author"],
                "matched": False,
                "institution": None,
            }

            if norm_title in csv_papers:
                csv_info = csv_papers[norm_title]
                affil = csv_info["affiliation"]
                if affil:
                    entry["matched"] = True
                    entry["institution"] = affil
                    entry["imported_from"] = "martenlienen"
                    matched += 1
                else:
                    unmatched += 1

            results.append(entry)

        if not results:
            continue

        has_affil, total = _save_affiliation_file(
            conf_id, year, results, "martenlienen")
        total_imported += 1
        total_papers += total
        total_with_affil += has_affil
        pct = round(100 * has_affil / max(total, 1), 1)
        print(f"  ✅ {conf_id} {year}: {has_affil}/{total} ({pct}%) "
              f"[{unmatched} without affiliation]")

    print(f"\nmartenlienen import complete: {total_imported} imported, "
          f"{total_skipped} skipped")
    if total_papers > 0:
        print(f"Overall: {total_with_affil}/{total_papers} papers "
              f"({100 * total_with_affil / total_papers:.1f}%)")


def _import_papercopilot(force: bool = False,
                         conferences_filter: set[str] | None = None):
    """Import affiliations from papercopilot JSON datasets."""
    import urllib.request

    # Conference files available in papercopilot
    PAPERCOPILOT_FILES = {
        ("ICLR", year): f"iclr/iclr{year}.json"
        for year in range(2013, 2027)
    }
    PAPERCOPILOT_FILES.update({
        ("NEURIPS", year): f"neurips/neurips{year}.json"
        for year in range(2020, 2025)
    })
    PAPERCOPILOT_FILES.update({
        ("ICML", year): f"icml/icml{year}.json"
        for year in range(2017, 2025)
    })
    # Add CoRL
    PAPERCOPILOT_FILES.update({
        ("CoRL", year): f"corl/corl{year}.json"
        for year in range(2021, 2025)
    })

    base_url = "https://raw.githubusercontent.com/papercopilot/paperlists/main/"

    total_imported = 0
    total_skipped = 0
    total_papers = 0
    total_with_affil = 0

    for (conf_id, year), filename in sorted(PAPERCOPILOT_FILES.items()):
        if conferences_filter and conf_id not in conferences_filter:
            continue

        safe_id = conf_id.replace("/", "-")
        affil_file = AFFIL_DIR / f"{safe_id}_{year}.json"

        if not force and affil_file.exists():
            total_skipped += 1
            continue

        url = base_url + filename
        print(f"  Downloading {filename}...", end=" ", flush=True)

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as e:
            print(f"FAILED ({e})")
            continue

        if not isinstance(data, list):
            print(f"SKIPPED (not a list)")
            continue

        print(f"{len(data)} papers", end=" ", flush=True)

        # Filter to accepted papers only
        _ACCEPT_STATUSES = {
            "accept", "accepted", "accept (oral)", "accept (spotlight)",
            "accept (poster)", "poster", "spotlight", "talk", "oral",
        }
        accepted = []
        for p in data:
            status = p.get("status", "").lower().strip()
            if status in _ACCEPT_STATUSES or status.startswith("accept"):
                accepted.append(p)

        if not accepted:
            # Try all papers (some datasets don't have status)
            accepted = data

        print(f"({len(accepted)} accepted)", end=" ", flush=True)

        # Build affiliation lookup: first-author affiliation per paper
        affil_lookup = {}
        for p in accepted:
            title = p.get("title", "").strip()
            if not title:
                continue
            authors_str = p.get("author", "")
            affs_str = p.get("aff", "")

            authors = authors_str.split(";") if authors_str else []
            affs = affs_str.split(";") if affs_str else []

            first_author = authors[0].strip() if authors else ""
            first_aff = affs[0].strip() if affs else ""

            if first_aff:
                norm = _normalize_title(title)
                affil_lookup[norm] = {
                    "first_author": first_author,
                    "affiliation": first_aff,
                }

        # Match against our raw data
        raw_papers = _load_raw_paper_titles(conf_id, year)
        if not raw_papers:
            print("no raw data")
            continue

        results = []
        has_affil = 0
        for norm_title, raw_info in raw_papers.items():
            entry = {
                "title": raw_info["title"],
                "first_author": raw_info["first_author"],
                "matched": False,
                "institution": None,
            }

            if norm_title in affil_lookup:
                info = affil_lookup[norm_title]
                if info["affiliation"]:
                    entry["matched"] = True
                    entry["institution"] = info["affiliation"]
                    entry["imported_from"] = "papercopilot"
                    has_affil += 1

            results.append(entry)

        if not results:
            print("no matches")
            continue

        n_affil, n_total = _save_affiliation_file(
            conf_id, year, results, "papercopilot")
        total_imported += 1
        total_papers += n_total
        total_with_affil += n_affil
        pct = round(100 * n_affil / max(n_total, 1), 1)
        print(f"→ {n_affil}/{n_total} ({pct}%)")

    print(f"\npapercopilot import complete: {total_imported} imported, "
          f"{total_skipped} skipped")
    if total_papers > 0:
        print(f"Overall: {total_with_affil}/{total_papers} papers "
              f"({100 * total_with_affil / total_papers:.1f}%)")


def main():
    parser = argparse.ArgumentParser(
        description="Import affiliation data from pre-compiled datasets")
    parser.add_argument("--source", choices=["martenlienen", "papercopilot", "all"],
                        default="all", help="Data source to import from")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing affiliation files")
    parser.add_argument("--conferences", nargs="*", default=None,
                        help="Only import these conference IDs (e.g. NEURIPS ICML)")
    args = parser.parse_args()

    conf_filter = set(args.conferences) if args.conferences else None

    if args.source in ("martenlienen", "all"):
        print("=== Importing from martenlienen/icml-neurips-iclr-dataset ===")
        _import_martenlienen(force=args.force, conferences_filter=conf_filter)
        print()

    if args.source in ("papercopilot", "all"):
        print("=== Importing from papercopilot/paperlists ===")
        _import_papercopilot(force=args.force, conferences_filter=conf_filter)


if __name__ == "__main__":
    main()
