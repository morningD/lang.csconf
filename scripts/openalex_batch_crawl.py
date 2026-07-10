"""Batch OpenAlex affiliation crawl — hybrid batch+search edition.

Uses k API keys concurrently (one thread per key) for k× speedup.
Resumable, auto key rotation, waits for UTC midnight reset when all exhausted.

Optimizations:
  - Batch download via source ID (1 credit/page, 50 papers) when source is available
  - Falls back to title.search (10 credits/paper) for unmatched papers
  - _test_key uses list filter (1 credit) instead of search (10 credits)

Usage:
    python scripts/openalex_batch_crawl.py                          # All CCF-B, 2023-2025
    python scripts/openalex_batch_crawl.py --rank A                  # All CCF-A
    python scripts/openalex_batch_crawl.py --conferences CHI SIGKDD  # Specific conferences
    python scripts/openalex_batch_crawl.py --force                   # Re-crawl existing
    python scripts/openalex_batch_crawl.py --years 2010 2025         # Custom years
"""

import argparse
import json
import os
import queue
import re
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
AFFIL_DIR = ROOT / "data" / "raw" / "affiliations"
AUTHORS_DIR = ROOT / "data" / "raw" / "authors"
CONFERENCES_FILE = ROOT / "data" / "raw" / "conferences.json"
KEYS_FILE = Path(__file__).parent / "openalex_keys.txt"
LOG_FILE = AFFIL_DIR / "_crawl_log.txt"

sys.path.insert(0, str(ROOT))
from pipeline.utils.openalex_client import extract_first_author_institution

# Thread-safe logging
_log_lock = threading.Lock()


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    with _log_lock:
        print(line, flush=True)
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


def load_keys() -> list[str]:
    if not KEYS_FILE.exists():
        log(f"ERROR: API keys file not found: {KEYS_FILE}")
        sys.exit(1)
    keys = [line.strip() for line in KEYS_FILE.read_text().splitlines()
            if line.strip() and not line.startswith("#")]
    if not keys:
        log("ERROR: No API keys found in keys file")
        sys.exit(1)
    return keys


def make_session(api_key: str):
    import requests
    s = requests.Session()
    # NOTE: Do NOT use urllib3 Retry adapter — it hangs on 429 responses
    # in urllib3 2.3.0. We handle retries at the application level instead.
    s.params = {"api_key": api_key}
    return s


# ---------------------------------------------------------------------------
# Source discovery: find OpenAlex conference source for batch download
# ---------------------------------------------------------------------------

# Cache: (conf_id, year) -> source_id or None
_source_cache: dict[tuple[str, int], str | None] = {}


def _discover_source(conf_id: str, conf_title: str, year: int, session) -> str | None:
    """Try to find an OpenAlex conference source for this conference-year.

    Returns source OpenAlex ID (e.g. 'S4363608773') or None.
    Uses year-specific sources (e.g. '2022 IEEE ICME') which have ~50-400 papers each.
    """
    cache_key = (conf_id, year)
    if cache_key in _source_cache:
        return _source_cache[cache_key]

    import requests

    # Search sources for the conference name + year
    search_queries = [
        f"{conf_title} {year}",
        conf_title,
    ]
    for query in search_queries:
        try:
            r = session.get("https://api.openalex.org/sources", params={
                "search": query,
                "filter": "type:conference",
                "select": "id,display_name,works_count",
                "per_page": 10,
                "sort": "relevance_score:desc",
            }, timeout=15)
        except requests.RequestException:
            continue

        if r.status_code != 200:
            continue

        results = r.json().get("results", [])
        for src in results:
            name = src.get("display_name", "")
            src_id = src.get("id", "")
            works = src.get("works_count", 0)
            # Check if this source matches our conference and year
            if works < 10 or not src_id:
                continue
            # Verify year is in the source name (year-specific sources)
            if str(year) in name and _name_matches_conf(name, conf_id, conf_title):
                _source_cache[cache_key] = src_id
                return src_id

    # Also try: search a sample paper and check its locations[].source
    _source_cache[cache_key] = None
    return None


def _name_matches_conf(source_name: str, conf_id: str, conf_title: str) -> bool:
    """Check if a source name likely refers to our conference."""
    sn = source_name.lower()
    # Check conference ID (common abbreviations)
    if conf_id.lower() in sn:
        return True
    # Check key words from conference title
    title_words = [w for w in conf_title.lower().split()
                   if len(w) > 3 and w not in ("international", "conference", "proceedings",
                                                 "annual", "acm", "ieee", "symposium")]
    if title_words and sum(1 for w in title_words if w in sn) >= min(2, len(title_words)):
        return True
    return False


def _batch_download(source_id: str, year: int, session) -> list[dict]:
    """Download all works from a source for a given year. Returns list of work dicts.

    Uses cursor pagination (1 credit per page of 50 papers).
    """
    import requests

    works = []
    cursor = "*"
    while cursor:
        try:
            r = session.get("https://api.openalex.org/works", params={
                "filter": f"locations.source.id:{source_id},publication_year:{year}",
                "select": "id,doi,title,authorships",
                "per_page": 50,
                "cursor": cursor,
            }, timeout=30)
        except requests.RequestException:
            break

        if r.status_code != 200:
            break

        data = r.json()
        results = data.get("results", [])
        works.extend(results)

        cursor = data.get("meta", {}).get("next_cursor")
        if not results:
            break

    return works


# ---------------------------------------------------------------------------
# Individual paper search (10 credits each)
# ---------------------------------------------------------------------------

def _fetch_one(title: str, year: int, session) -> dict | None:
    """Fetch a single work from OpenAlex. Returns work dict, None (no match), or status dict."""
    import requests

    try:
        r = session.get("https://api.openalex.org/works", params={
            "filter": f"title.search:{title[:200]},publication_year:{year}",
            "select": "id,doi,title,authorships",
            "per_page": 10,
            "sort": "relevance_score:desc",
        }, timeout=(5, 15))
    except requests.RequestException:
        return {"_status": "network_error"}

    if r.status_code == 200:
        results = r.json().get("results", [])
        if not results:
            return None
        proceedings = [w for w in results
                       if w.get("doi") and "arxiv" not in (w.get("doi") or "")]
        work = (proceedings[0] if proceedings else results[0])
        work["_status"] = "ok"
        return work

    if r.status_code == 429:
        return {"_status": "429"}

    return {"_status": "error"}


def _test_key(api_key: str) -> bool:
    """Quick test if a key still has budget. Uses list filter (1 credit, not 10)."""
    import requests
    try:
        r = requests.get("https://api.openalex.org/works", params={
            "filter": "publication_year:2025",
            "api_key": api_key, "per_page": 1,
        }, timeout=10)
        return r.status_code == 200
    except Exception:
        return False


def _wait_for_key_reset(keys: list[str], timeout: int = 86400) -> list[str]:
    """Wait until at least one key has budget again. Returns live keys."""
    log(f"  All keys exhausted, waiting for UTC midnight reset...")
    log(f"  (Add new keys to {KEYS_FILE} — checked every 60s)")

    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(60)
        # Hot-reload keys from file
        new_keys = load_keys()
        live = [k for k in new_keys if _test_key(k)]
        if live:
            log(f"  {len(live)} key(s) available, resuming!")
            return live
    return []


# ---------------------------------------------------------------------------
# Title normalization for matching
# ---------------------------------------------------------------------------

def _normalize_title(title: str) -> str:
    """Normalize title for matching: lowercase, strip punctuation, collapse whitespace."""
    t = title.lower()
    t = re.sub(r'[^a-z0-9\s]', ' ', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


# ---------------------------------------------------------------------------
# Main crawl logic
# ---------------------------------------------------------------------------

def _process_work(title: str, first_author: str, work: dict) -> dict:
    """Convert an OpenAlex work into a result entry."""
    inst = extract_first_author_institution(work)
    entry = {
        "title": title,
        "first_author": first_author,
        "matched": True,
        "openalex_id": work.get("id"),
        "doi": work.get("doi"),
    }
    if inst:
        entry["institution"] = inst["name"]
        entry["institution_country"] = inst.get("country")
        if inst.get("ror"):
            entry["institution_ror"] = inst["ror"]
        if inst.get("raw"):
            entry["raw_affiliation"] = inst["raw"]
    else:
        entry["institution"] = None
    return entry


def crawl_conference_year_hybrid(conf_id: str, conf_title: str, year: int,
                                  keys: list[str], delay: float = 0.11) -> dict:
    """Crawl one conference-year using hybrid batch+search strategy.

    Final affiliation files are written only when every first-author paper has
    received a definitive response. A 429 or network interruption therefore
    returns a partial status instead of creating a result that future
    incremental runs would silently skip.
    """
    raw_file = AUTHORS_DIR / f"{conf_id}_{year}.json"
    if not raw_file.exists():
        return {"status": "no_data", "total": 0, "matched": 0, "affil": 0, "errors": 0}

    with open(raw_file, encoding="utf-8") as f:
        data = json.load(f)

    papers_by_title = {}
    for author in data.get("authors", []):
        if author.get("ordinal") == 1:
            papers_by_title.setdefault(author["title"], {
                "title": author["title"], "first_author": author["name"],
            })
    papers = list(papers_by_title.values())
    if not papers:
        return {"status": "no_papers", "total": 0, "matched": 0, "affil": 0, "errors": 0}

    live_keys = [key for key in keys if _test_key(key)]
    if not live_keys:
        live_keys = _wait_for_key_reset(keys)
        if not live_keys:
            return {"status": "no_keys", "total": len(papers), "matched": 0, "affil": 0, "errors": 0}

    if len(live_keys) < len(keys):
        log(f"  Using {len(live_keys)}/{len(keys)} keys (others exhausted)")
    sessions = [make_session(key) for key in live_keys]
    entries_by_idx: dict[int, dict] = {}
    unmatched = list(enumerate(papers))
    source_matches = 0

    # Phase 1: batch download is only an optimization. Any miss still receives
    # the definitive title-search treatment below.
    source_id = _discover_source(conf_id, conf_title, year, sessions[0])
    if source_id:
        log(f"  Batch download: source={source_id}")
        batch_works = _batch_download(source_id, year, sessions[0])
        if batch_works:
            log(f"  Downloaded {len(batch_works)} works from source")
            batch_index = {
                _normalize_title(work.get("title", "")): work
                for work in batch_works if _normalize_title(work.get("title", ""))
            }
            unmatched = []
            for original_idx, paper in enumerate(papers):
                work = batch_index.get(_normalize_title(paper["title"]))
                if work:
                    entries_by_idx[original_idx] = _process_work(
                        paper["title"], paper["first_author"], work)
                    source_matches += 1
                else:
                    unmatched.append((original_idx, paper))

    search_completed = 0
    exhausted_workers = 0
    network_errors = 0
    if unmatched:
        log(f"  Search fallback: {len(unmatched)} papers")
        work_queue: queue.Queue[tuple[int, int, dict]] = queue.Queue()
        for unmatched_idx, (original_idx, paper) in enumerate(unmatched):
            work_queue.put((unmatched_idx, original_idx, paper))

        result_lock = threading.Lock()
        progress_lock = threading.Lock()
        progress = 0

        def worker(session) -> str:
            nonlocal search_completed, network_errors, progress
            while True:
                try:
                    _, original_idx, paper = work_queue.get_nowait()
                except queue.Empty:
                    return "complete"

                # The delay is per API key, rather than a global throttle.
                time.sleep(delay)
                work = _fetch_one(paper["title"], year, session)
                status = work.get("_status", "no_match") if work else "no_match"
                if status == "429":
                    work_queue.put((0, original_idx, paper))
                    return "exhausted"

                entry = (
                    _process_work(paper["title"], paper["first_author"], work)
                    if status == "ok"
                    else {"title": paper["title"], "first_author": paper["first_author"],
                          "matched": False, "institution": None}
                )
                with result_lock:
                    entries_by_idx[original_idx] = entry
                    search_completed += 1
                    if status == "network_error":
                        network_errors += 1
                with progress_lock:
                    progress += 1
                    if progress % 100 == 0 or progress == len(unmatched):
                        matched_now = sum(1 for value in entries_by_idx.values() if value.get("matched"))
                        affil_now = sum(1 for value in entries_by_idx.values() if value.get("institution"))
                        log(f"  {conf_id} {year}: search {progress}/{len(unmatched)} "
                            f"(matched={matched_now}, affil={affil_now})")

        with ThreadPoolExecutor(max_workers=len(sessions)) as executor:
            statuses = list(executor.map(worker, sessions))
        exhausted_workers = sum(status == "exhausted" for status in statuses)

    unprocessed = len(papers) - len(entries_by_idx)
    matched = sum(1 for entry in entries_by_idx.values() if entry.get("matched"))
    has_affil = sum(1 for entry in entries_by_idx.values() if entry.get("institution"))
    errors = network_errors + exhausted_workers

    if unprocessed:
        status = "partial_key_exhausted" if exhausted_workers else "partial_incomplete"
        log(f"  {conf_id} {year}: status={status}, source={source_matches}, "
            f"search={search_completed}/{len(unmatched)}, exhausted={exhausted_workers}, "
            f"unprocessed={unprocessed}")
        return {"status": status, "total": len(papers), "matched": matched,
                "affil": has_affil, "errors": errors, "unprocessed": unprocessed}
    if network_errors:
        status = "partial_network_failure"
        log(f"  {conf_id} {year}: status={status}, source={source_matches}, "
            f"search={search_completed}/{len(unmatched)}, network_errors={network_errors}")
        return {"status": status, "total": len(papers), "matched": matched,
                "affil": has_affil, "errors": errors, "unprocessed": 0}

    results = [entries_by_idx[index] for index in range(len(papers))]
    output = {
        "conference": conf_id,
        "year": year,
        "total_papers": len(papers),
        "total_matched": matched,
        "total_with_affiliation": has_affil,
        "coverage_pct": round(100 * has_affil / len(papers), 1),
        "source": "openalex",
        "papers": results,
    }
    AFFIL_DIR.mkdir(parents=True, exist_ok=True)
    out_file = AFFIL_DIR / f"{conf_id}_{year}.json"
    tmp_file = out_file.with_suffix(out_file.suffix + ".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp_file, out_file)
    log(f"  {conf_id} {year}: status=ok, source={source_matches}, "
        f"search={search_completed}/{len(unmatched)}, exhausted=0, unprocessed=0")
    return {"status": "ok", "total": len(papers), "matched": matched,
            "affil": has_affil, "errors": 0, "unprocessed": 0}


def main():
    parser = argparse.ArgumentParser(description="Hybrid OpenAlex affiliation crawl")
    parser.add_argument("--conferences", nargs="+", help="Specific conference IDs")
    parser.add_argument("--rank", default="B", help="CCF rank filter (default: B)")
    parser.add_argument("--years", nargs="+", type=int, default=[2023, 2024, 2025],
                        help="Year range (default: 2023 2024 2025)")
    parser.add_argument("--force", action="store_true",
                        help="Re-crawl even if affiliation file exists")
    parser.add_argument("--delay", type=float, default=0.11,
                        help="Seconds between API calls per thread (default: 0.11)")
    args = parser.parse_args()

    with open(CONFERENCES_FILE, encoding="utf-8") as f:
        all_confs = json.load(f)

    # Build conf_id → title map
    conf_titles = {c["id"]: c.get("title", c["id"]) for c in all_confs}

    if args.conferences:
        target_ids = set(args.conferences)
    else:
        target_ids = {c["id"] for c in all_confs if c.get("rank") == args.rank}

    keys = load_keys()
    log(f"Loaded {len(keys)} API key(s) → {len(keys)} parallel workers")
    log(f"Target: CCF-{args.rank}, years={args.years}, {len(target_ids)} conferences")

    # Build work queue
    queue = []
    for conf_id in sorted(target_ids):
        for year in args.years:
            out_file = AFFIL_DIR / f"{conf_id}_{year}.json"
            if not args.force and out_file.exists():
                continue
            raw_file = AUTHORS_DIR / f"{conf_id}_{year}.json"
            if not raw_file.exists():
                continue
            with open(raw_file, encoding="utf-8") as f:
                data = json.load(f)
            n = len({a["title"] for a in data.get("authors", []) if a.get("ordinal") == 1})
            if n > 0:
                queue.append((conf_id, year, n))

    if not queue:
        log("Nothing to crawl — all targets already have affiliation files.")
        return

    total_papers = sum(n for _, _, n in queue)
    log(f"Work queue: {len(queue)} batches, {total_papers} papers")
    # Cost estimate: assume ~10% batchable (1 credit/50), rest search (10 credits/paper)
    search_papers = total_papers * 0.9
    batch_pages = (total_papers * 0.1) / 50
    est_credits = int(search_papers * 10 + batch_pages)
    log(f"Estimated: ~{est_credits:,} credits (~${est_credits * 0.0001:.1f}), "
        f"~{est_credits / (len(keys) * 10000):.1f} days with {len(keys)} workers")

    done = 0
    done_papers = 0
    grand_total = 0
    grand_affil = 0
    grand_errors = 0
    t0 = time.time()

    for conf_id, year, expected in queue:
        # Hot-reload keys
        new_keys = load_keys()
        if new_keys != keys:
            keys = new_keys
            log(f"Keys updated: now {len(keys)} key(s)")

        out_file = AFFIL_DIR / f"{conf_id}_{year}.json"
        if not args.force and out_file.exists():
            log(f"SKIP {conf_id} {year} (file exists)")
            done += 1
            continue

        conf_title = conf_titles.get(conf_id, conf_id)
        log(f"START {conf_id} {year} ({expected} papers, {len(keys)} workers)")
        t1 = time.time()
        result = crawl_conference_year_hybrid(conf_id, conf_title, year, keys, delay=args.delay)
        elapsed = time.time() - t1

        if result["status"] == "ok":
            done += 1
            done_papers += result["total"]
            grand_total += result["total"]
            grand_affil += result["affil"]
            grand_errors += result["errors"]
            pct = round(100 * result["affil"] / max(result["total"], 1), 1)
            log(f"DONE  {conf_id} {year}: {result['affil']}/{result['total']} "
                f"({pct}%) in {elapsed:.0f}s, err={result['errors']}")
        elif result["status"].startswith("partial_"):
            done_papers += result["matched"]
            grand_total += result["total"]
            grand_affil += result["affil"]
            grand_errors += result["errors"]
            pct = round(100 * result["affil"] / max(result["total"], 1), 1)
            log(f"PARTIAL {conf_id} {year}: {result['affil']}/{result['total']} "
                f"({pct}%) in {elapsed:.0f}s, status={result['status']}, "
                f"unprocessed={result.get('unprocessed', 0)} — waiting for key reset...")
            # The crawler never persisted this partial result. Retry only after
            # at least one API key has recovered.
            live = _wait_for_key_reset(keys)
            if live:
                keys = load_keys()
                log(f"RETRY {conf_id} {year} with {len(keys)} keys")
                t1 = time.time()
                result2 = crawl_conference_year_hybrid(
                    conf_id, conf_title, year, keys, delay=args.delay)
                elapsed += time.time() - t1
                if result2["status"] == "ok":
                    done += 1
                    done_papers += result2["total"]
                    grand_total += result2["total"]
                    grand_affil += result2["affil"]
                    grand_errors += result2["errors"]
                    pct = round(100 * result2["affil"] / max(result2["total"], 1), 1)
                    log(f"DONE  {conf_id} {year} (retry): {result2['affil']}/{result2['total']} "
                        f"({pct}%) in {elapsed:.0f}s total")
                else:
                    log(f"RETRY FAILED {conf_id} {year}: {result2['status']}, will try next run")
            else:
                log("NO KEYS after wait, stopping.")
                break
        else:
            log(f"SKIP  {conf_id} {year}: {result['status']}")

        if done > 0 and done % 5 == 0 and grand_total > 0:
            remaining = total_papers - done_papers
            elapsed_total = time.time() - t0
            rate = done_papers / elapsed_total if elapsed_total > 0 else 0
            eta_h = remaining / rate / 3600 if rate > 0 else 0
            log(f"--- Progress: {done}/{len(queue)} batches, "
                f"{done_papers}/{total_papers} papers, "
                f"{grand_affil} affil ({100*grand_affil/grand_total:.0f}%), "
                f"ETA ~{eta_h:.1f}h ---")

    elapsed_total = time.time() - t0
    log(f"\n{'='*60}")
    log(f"CRAWL COMPLETE: {done}/{len(queue)} batches in {elapsed_total/3600:.1f}h")
    if grand_total > 0:
        log(f"Papers: {grand_affil}/{grand_total} with affiliations "
            f"({100*grand_affil/grand_total:.1f}%)")
    log(f"Errors: {grand_errors}")
    log(f"{'='*60}")


if __name__ == "__main__":
    main()
