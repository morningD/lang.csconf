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
CONFERENCES_FILE = RAW_DIR / "conferences.json"

EXPECTED_YEARS = list(range(2010, 2026))
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
                conf = pair_to_conf.get(pair)
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

    print(f"Done: {done} saved, {errors} errors, {skipped} cached")


if __name__ == "__main__":
    # Accept --force flag and optional --conferences filter
    force = "--force" in sys.argv
    conf_filter = None
    for arg in sys.argv[1:]:
        if not arg.startswith("--"):
            conf_filter = arg.split(",")
    run(force=force, conferences_filter=conf_filter)
