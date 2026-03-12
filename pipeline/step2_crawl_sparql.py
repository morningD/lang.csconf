"""Step 2: Crawl DBLP via SPARQL for authors of each conference/year (2010-2025).

Stores all authors with their ordinal position (1 = first author, 2 = second, etc.).
Downstream steps (step3, step4) filter to first authors as needed.
"""

import json
import sys
import time
from pathlib import Path

from tqdm import tqdm

from pipeline.utils.dblp_sparql import fetch_batch_sparql

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
AUTHORS_DIR = RAW_DIR / "authors"
VENUES_DIR = RAW_DIR / "venues"
CONFERENCES_FILE = RAW_DIR / "conferences.json"

EXPECTED_YEARS = list(range(2010, 2027))
BATCH_SIZE = 5
MAX_RETRIES = 3


def _safe_filename(conf_id: str) -> str:
    """Replace path-unsafe characters in conference ID."""
    return conf_id.replace("/", "-")


def _chunks(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i : i + n]


def _extract_all_authors(papers: list[dict]) -> list[dict]:
    """Extract all authors with ordinal from each paper."""
    results = []
    for paper in papers:
        authors = paper.get("authors", [])
        for a in authors:
            results.append({
                "name": a["name"],
                "title": paper["title"],
                "ordinal": a["ordinal"],
            })
    return results


def merge_publication_year_splits(conferences_filter: list[str] | None = None):
    """Merge files where SPARQL yearOfPublication differs from real conference year.

    Two passes:
    1. Non-venue-year merge: When year Y is NOT a venue year but Y-1 IS, merge
       Y's papers into Y-1 and delete Y. (Publication year lag for non-venue years.)
    2. Cross-year dedup: When both Y and Y+1 are venue years but share ≥50%
       paper titles, remove duplicates from Y+1. (Publication year lag where
       both years are valid venue years, e.g., ICONIP 2023/2024, SIGMETRICS.)

    Also deletes stale classified files so step3 re-classifies the merged data.
    """
    import re
    _valid = re.compile(r"^[A-Za-z0-9+&.\-]+_\d{4}\.json$")
    classified_dir = DATA_DIR / "classified" / "authors"

    # Load venue years
    venue_years: dict[str, set[int]] = {}
    if VENUES_DIR.exists():
        for f in VENUES_DIR.glob("*.json"):
            with open(f) as fh:
                data = json.load(fh)
            conf_id = data.get("conference", "")
            venue_years[conf_id] = {int(y) for y in data.get("venues", {}).keys()}

    if not venue_years:
        return

    # Group files by conference
    conf_files: dict[str, dict[int, Path]] = {}
    for f in AUTHORS_DIR.glob("*.json"):
        if not _valid.match(f.name):
            continue
        parts = f.stem.rsplit("_", 1)
        if len(parts) != 2:
            continue
        conf_id, year_str = parts
        conf_files.setdefault(conf_id, {})[int(year_str)] = f

    if conferences_filter:
        filter_set = {c.upper() for c in conferences_filter}
        conf_files = {k: v for k, v in conf_files.items() if k.upper() in filter_set}

    # Pass 1: Non-venue-year merge (year NOT in venue_years → merge into year-1)
    merged_count = 0
    for conf_id, year_files in sorted(conf_files.items()):
        if conf_id not in venue_years:
            continue
        vy = venue_years[conf_id]

        for year in sorted(year_files):
            target_year = year - 1
            if year in vy or target_year not in vy or target_year < 2010:
                continue

            target_file = year_files.get(target_year)
            source_file = year_files[year]

            if target_file is None:
                target_path = AUTHORS_DIR / f"{_safe_filename(conf_id)}_{target_year}.json"
                with open(source_file) as f:
                    data = json.load(f)
                data["year"] = target_year
                for a in data.get("authors", []):
                    a["year"] = target_year
                with open(target_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                source_file.unlink()
                for cls_name in [f"{_safe_filename(conf_id)}_{year}.json",
                                 f"{_safe_filename(conf_id)}_{target_year}.json"]:
                    cls_file = classified_dir / cls_name
                    if cls_file.exists():
                        cls_file.unlink()
                print(f"  Renamed {conf_id}_{year} → {target_year} (publication year lag)")
                merged_count += 1
                continue

            with open(target_file) as f:
                target_data = json.load(f)
            with open(source_file) as f:
                source_data = json.load(f)

            existing_keys = set()
            for a in target_data.get("authors", []):
                norm_title = " ".join(a.get("title", "").lower().split())
                existing_keys.add((norm_title, a.get("name", "")))

            new_authors = []
            for a in source_data.get("authors", []):
                norm_title = " ".join(a.get("title", "").lower().split())
                key = (norm_title, a.get("name", ""))
                if key not in existing_keys:
                    existing_keys.add(key)
                    a_copy = dict(a)
                    a_copy["year"] = target_year
                    new_authors.append(a_copy)

            if new_authors:
                target_data["authors"].extend(new_authors)
                all_titles = {" ".join(a["title"].lower().split()) for a in target_data["authors"]}
                target_data["total_papers"] = len(all_titles)
                with open(target_file, "w", encoding="utf-8") as f:
                    json.dump(target_data, f, indent=2, ensure_ascii=False)

            source_file.unlink()
            for cls_name in [f"{_safe_filename(conf_id)}_{year}.json",
                             f"{_safe_filename(conf_id)}_{target_year}.json"]:
                cls_file = classified_dir / cls_name
                if cls_file.exists():
                    cls_file.unlink()
            new_titles = len({" ".join(a["title"].lower().split()) for a in new_authors})
            print(f"  Merged {conf_id}_{year} into {target_year}: {new_titles} new papers, deleted {year} file")
            merged_count += 1

    if merged_count:
        print(f"  Publication year splits: {merged_count} file(s) merged")

    # Pass 2: Cross-year dedup (both years are venue years but share papers)
    # Re-scan files since pass 1 may have deleted/modified some
    conf_files.clear()
    for f in AUTHORS_DIR.glob("*.json"):
        if not _valid.match(f.name):
            continue
        parts = f.stem.rsplit("_", 1)
        if len(parts) != 2:
            continue
        conf_id, year_str = parts
        conf_files.setdefault(conf_id, {})[int(year_str)] = f

    if conferences_filter:
        conf_files = {k: v for k, v in conf_files.items() if k.upper() in filter_set}

    dedup_count = 0
    for conf_id, year_files in sorted(conf_files.items()):
        years = sorted(year_files.keys())
        deleted_years: set[int] = set()
        for i in range(len(years) - 1):
            y1, y2 = years[i], years[i + 1]
            if y2 - y1 != 1 or y1 in deleted_years:
                continue
            if not year_files[y1].exists() or not year_files[y2].exists():
                continue

            with open(year_files[y1]) as f:
                d1 = json.load(f)
            with open(year_files[y2]) as f:
                d2 = json.load(f)

            titles_1 = {" ".join(a["title"].lower().split())
                        for a in d1.get("authors", []) if a.get("ordinal", 1) == 1}
            titles_2 = {" ".join(a["title"].lower().split())
                        for a in d2.get("authors", []) if a.get("ordinal", 1) == 1}

            overlap = titles_1 & titles_2
            min_size = min(len(titles_1), len(titles_2))
            if min_size < 5 or len(overlap) / min_size < 0.5:
                continue

            # Remove overlapping papers from the later-year file
            new_authors = [a for a in d2["authors"]
                           if " ".join(a["title"].lower().split()) not in overlap]

            if not new_authors:
                year_files[y2].unlink()
                deleted_years.add(y2)
                cls_file = classified_dir / year_files[y2].name
                if cls_file.exists():
                    cls_file.unlink()
                print(f"  Deleted {conf_id}_{y2}: 100% overlap with {y1} ({len(overlap)} papers)")
            else:
                remaining_titles = {" ".join(a["title"].lower().split()) for a in new_authors}
                d2["authors"] = new_authors
                d2["total_papers"] = len(remaining_titles)
                with open(year_files[y2], "w", encoding="utf-8") as f:
                    json.dump(d2, f, indent=2, ensure_ascii=False)
                cls_file = classified_dir / year_files[y2].name
                if cls_file.exists():
                    cls_file.unlink()
                print(f"  Deduped {conf_id}_{y2}: removed {len(overlap)} papers shared with {y1}, {d2['total_papers']} remain")
            dedup_count += 1

    if dedup_count:
        print(f"  Cross-year dedup: {dedup_count} file(s) cleaned")


def run(force: bool = False, conferences_filter: list[str] | None = None):
    """Run step 2: SPARQL-based crawl of DBLP for authors."""
    if not CONFERENCES_FILE.exists():
        print("No conferences.json found. Run step 1 first.")
        return

    with open(CONFERENCES_FILE, "r") as f:
        conferences = json.load(f)

    if conferences_filter:
        filter_set = {c.upper() for c in conferences_filter}

        def _matches_filter(c):
            if c["id"].upper() in filter_set or c["title"].upper() in filter_set:
                return True
            dblp = c.get("dblp")
            if not dblp:
                return False
            dblp_keys = dblp if isinstance(dblp, list) else [dblp]
            return any(k.upper() in filter_set for k in dblp_keys)

        conferences = [c for c in conferences if _matches_filter(c)]

    AUTHORS_DIR.mkdir(parents=True, exist_ok=True)

    # Build (dblp_key, year) pairs, keyed back to conf metadata
    # A conference with multiple dblp keys produces multiple pairs for the same year
    pair_to_conf: dict[tuple[str, int], dict] = {}
    pairs: list[tuple[str, int]] = []
    # Track which (conf_id, year) combos need fetching (for multi-key merge)
    pending_conf_years: set[tuple[str, int]] = set()
    skipped = 0

    for conf in conferences:
        dblp_value = conf.get("dblp")
        if not dblp_value or dblp_value == "NO DBLP":
            continue
        # Normalize to list of keys
        dblp_keys = dblp_value if isinstance(dblp_value, list) else [dblp_value]
        conf_id = conf["id"]
        safe_id = _safe_filename(conf_id)
        for year in EXPECTED_YEARS:
            output_file = AUTHORS_DIR / f"{safe_id}_{year}.json"
            if not force and output_file.exists():
                skipped += 1
                continue
            for dblp_key in dblp_keys:
                pair = (dblp_key, year)
                pair_to_conf[pair] = conf
                pairs.append(pair)
            pending_conf_years.add((conf_id, year))

    total = len(pairs)
    print(f"SPARQL crawl: {total} pairs to fetch, {skipped} already cached")

    if not pairs:
        print("Nothing to crawl.")
        return

    done = 0
    errors = 0
    # Accumulate authors per (conf_id, year) for multi-key merging
    accumulated: dict[tuple[str, int], list[dict]] = {}

    with tqdm(total=total, desc="SPARQL crawl") as pbar:
        for batch in _chunks(pairs, BATCH_SIZE):
            pbar.set_postfix_str(
                f"{batch[0][0]}/{batch[0][1]}..{batch[-1][0]}/{batch[-1][1]}"
            )

            # Retry logic for transient failures
            results = None
            for attempt in range(MAX_RETRIES):
                try:
                    results = fetch_batch_sparql(batch)
                    break
                except Exception as e:
                    if attempt < MAX_RETRIES - 1:
                        wait = 2 ** (attempt + 1)
                        print(f"\n  Batch error (attempt {attempt+1}): {e}, retrying in {wait}s...")
                        time.sleep(wait)
                    else:
                        print(f"\n  Batch failed after {MAX_RETRIES} attempts: {e}")
                        errors += len(batch)
                        pbar.update(len(batch))

            if results is None:
                continue

            for pair, papers in results.items():
                dblp_key, year = pair
                # The SPARQL result may re-bucket papers to a different year
                # (e.g., DBLP tags ACL 2024 Findings as yearOfPublication=2014).
                # Look up conf metadata from the queried pair first, then fall
                # back to the same dblp_key with the corrected year.
                conf = pair_to_conf.get(pair)
                if conf is None:
                    # Paper was re-bucketed to a year we didn't query for this key;
                    # find conf metadata from any pair with the same dblp_key.
                    conf = next(
                        (c for (k, _), c in pair_to_conf.items() if k == dblp_key),
                        None,
                    )
                if conf is None:
                    pbar.update(1)
                    continue

                conf_id = conf["id"]
                authors = _extract_all_authors(papers)
                acc_key = (conf_id, year)
                accumulated.setdefault(acc_key, []).extend(authors)
                pbar.update(1)

            # Small delay between batches to be polite
            time.sleep(0.2)

    # Write accumulated results, deduplicating by (normalized title, name)
    for (conf_id, year), authors in accumulated.items():
        # Skip out-of-range years (caused by URI year extraction bugs, e.g. 2089)
        if year < 2010 or year > 2026:
            continue

        safe_id = _safe_filename(conf_id)
        seen: set[tuple[str, str]] = set()
        unique_authors = []
        unique_titles: set[str] = set()
        for a in authors:
            norm_title = " ".join(a["title"].lower().split())
            key = (norm_title, a["name"])
            if key not in seen:
                seen.add(key)
                unique_authors.append(a)
                unique_titles.add(norm_title)

        # Skip empty results (all papers filtered out by workshop/proceedings filters)
        if not unique_authors:
            continue

        dblp_value = next(
            c["dblp"] for c in conferences if c["id"] == conf_id
        )
        result = {
            "conference": conf_id,
            "dblp": dblp_value,
            "year": year,
            "total_papers": len(unique_titles),
            "authors": [
                {"name": a["name"], "title": a["title"], "year": year, "ordinal": a["ordinal"]}
                for a in unique_authors
            ],
        }

        output_file = AUTHORS_DIR / f"{safe_id}_{year}.json"
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        done += 1

    # Clean up stale files: if force-crawl returned empty results for a
    # (conf_id, year) that previously had data, delete the old file.
    if force:
        stale_deleted = 0
        classified_dir = DATA_DIR / "classified" / "authors"
        for conf_id, year in pending_conf_years:
            if (conf_id, year) in accumulated:
                continue  # has new data, already written above
            safe_id = _safe_filename(conf_id)
            for d in [AUTHORS_DIR, classified_dir]:
                old_file = d / f"{safe_id}_{year}.json"
                if old_file.exists():
                    old_file.unlink()
                    stale_deleted += 1
        if stale_deleted:
            print(f"Cleaned {stale_deleted} stale file(s) (empty after re-crawl)")

    print(f"Done: {done} saved, {errors} errors, {skipped} cached")

    # Post-process: merge files where yearOfPublication != conference year
    merge_publication_year_splits(conferences_filter)


if __name__ == "__main__":
    # Accept --force flag and optional --conferences filter
    force = "--force" in sys.argv
    conf_filter = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            conf_filter = arg.split(",")
    run(force=force, conferences_filter=conf_filter)
