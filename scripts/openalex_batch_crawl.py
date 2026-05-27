"""Batch OpenAlex affiliation crawl — parallel edition.

Uses k API keys concurrently (one thread per key) for k× speedup.
Resumable, auto key rotation, waits for UTC midnight reset when all exhausted.

Usage:
    python scripts/openalex_batch_crawl.py                          # All CCF-A, 2023-2025
    python scripts/openalex_batch_crawl.py --conferences CHI SIGKDD  # Specific conferences
    python scripts/openalex_batch_crawl.py --force                   # Re-crawl existing
    python scripts/openalex_batch_crawl.py --years 2024 2025         # Custom years
"""

import argparse
import json
import random
import sys
import threading
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry
    s = requests.Session()
    retry = Retry(total=1, backoff_factor=0.3, status_forcelist=[500, 502, 503, 504])
    s.mount("https://", HTTPAdapter(max_retries=retry))
    s.params = {"api_key": api_key}
    return s




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
    """Quick test if a key still has budget."""
    import requests
    try:
        r = requests.get("https://api.openalex.org/works", params={
            "filter": "title.search:test,publication_year:2024",
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
            with _exhausted_lock:
                _exhausted_keys.clear()
            return live
    return []


def crawl_conference_year_parallel(conf_id: str, year: int, keys: list[str],
                                    delay: float = 0.11) -> dict:
    """Crawl one conference-year using k parallel threads (one per key).

    If keys run out mid-batch, saves what we have and returns partial results.
    The caller can retry later or wait for key reset.
    """

    raw_file = AUTHORS_DIR / f"{conf_id}_{year}.json"
    if not raw_file.exists():
        return {"status": "no_data", "total": 0, "matched": 0, "affil": 0}

    with open(raw_file, encoding="utf-8") as f:
        data = json.load(f)

    papers = {}
    for a in data.get("authors", []):
        if a.get("ordinal") == 1:
            title = a["title"]
            if title not in papers:
                papers[title] = {"title": title, "first_author": a["name"]}
    papers = list(papers.values())

    if not papers:
        return {"status": "no_papers", "total": 0, "matched": 0, "affil": 0}

    # Test keys, only use live ones
    live_keys = [k for k in keys if _test_key(k)]
    if not live_keys:
        live_keys = _wait_for_key_reset(keys)
        if not live_keys:
            return {"status": "no_keys", "total": len(papers), "matched": 0, "affil": 0}

    # Per-key exhausted tracking (local to this batch)
    local_exhausted: set[int] = set()
    local_lock = threading.Lock()

    n_workers = len(live_keys)
    sessions = [make_session(k) for k in live_keys]
    if n_workers < len(keys):
        log(f"  Using {n_workers}/{len(keys)} keys (others exhausted)")

    results: list[dict | None] = [None] * len(papers)
    matched = 0
    has_affil = 0
    errors = 0
    lock = threading.Lock()
    progress = [0]

    def process_paper(paper_idx: int, paper: dict, key_idx: int):
        nonlocal matched, has_affil, errors
        title = paper["title"]
        first_author = paper["first_author"]

        # Try assigned key first, then find any live key
        s_idx = key_idx
        with local_lock:
            if s_idx in local_exhausted:
                for alt in range(n_workers):
                    if alt not in local_exhausted:
                        s_idx = alt
                        break
                else:
                    # All local keys dead — mark as failed, caller will retry
                    results[paper_idx] = {"title": title, "first_author": first_author,
                                          "matched": False, "institution": None}
                    with lock:
                        progress[0] += 1
                    return

        work = _fetch_one(title, year, sessions[s_idx])
        status = work.get("_status", "no_match") if work else "no_match"

        if status == "429":
            with local_lock:
                local_exhausted.add(s_idx)
                all_dead = len(local_exhausted) >= n_workers
            if all_dead:
                log(f"  {conf_id} {year}: all keys exhausted at {progress[0]}/{len(papers)}")
            results[paper_idx] = {"title": title, "first_author": first_author,
                                  "matched": False, "institution": None}
            with lock:
                progress[0] += 1
            return

        if status == "ok":
            del work["_status"]
            inst = extract_first_author_institution(work)
            entry = {
                "title": title,
                "first_author": first_author,
                "matched": True,
                "openalex_id": work.get("id"),
                "doi": work.get("doi"),
            }
            if inst:
                with lock:
                    has_affil += 1
                entry["institution"] = inst["name"]
                entry["institution_country"] = inst.get("country")
                if inst.get("ror"):
                    entry["institution_ror"] = inst["ror"]
                if inst.get("raw"):
                    entry["raw_affiliation"] = inst["raw"]
            else:
                entry["institution"] = None
            with lock:
                matched += 1
            results[paper_idx] = entry
        else:
            if status == "network_error":
                with lock:
                    errors += 1
            results[paper_idx] = {"title": title, "first_author": first_author,
                                  "matched": False, "institution": None}

        with lock:
            progress[0] += 1
            done = progress[0]
            if done % 100 == 0 or done == len(papers):
                pct = 100 * has_affil / done if done > 0 else 0
                log(f"  {conf_id} {year}: {done}/{len(papers)} "
                    f"(affil={has_affil}, {pct:.0f}%, err={errors})")

    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = []
        for paper_idx, paper in enumerate(papers):
            key_idx = paper_idx % n_workers
            futures.append(executor.submit(process_paper, paper_idx, paper, key_idx))

        for f in as_completed(futures):
            try:
                f.result()
            except Exception as e:
                log(f"  Thread error: {e}")
                with lock:
                    errors += 1

    # Check if partial: use actual key exhaustion, not match rate
    # (low match rate is normal for some conferences like CRYPTO/ACL)
    none_count = sum(1 for r in results if r is None)
    key_exhausted = len(local_exhausted) >= n_workers  # all keys died
    partial = key_exhausted or none_count > len(papers) * 0.1  # >10% unprocessed = key issue

    # Fill None results with unmatched entries
    for i, r in enumerate(results):
        if r is None:
            results[i] = {"title": papers[i]["title"], "first_author": papers[i]["first_author"],
                          "matched": False, "institution": None}

    # Only save if not a partial failure due to key exhaustion
    if not partial:
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
        out_file = AFFIL_DIR / f"{conf_id}_{year}.json"
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2, ensure_ascii=False)

    return {
        "status": "partial" if partial else "ok",
        "total": len(papers),
        "matched": matched,
        "affil": has_affil,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description="Parallel OpenAlex affiliation crawl")
    parser.add_argument("--conferences", nargs="+", help="Specific conference IDs")
    parser.add_argument("--years", nargs="+", type=int, default=[2023, 2024, 2025],
                        help="Year range (default: 2023 2024 2025)")
    parser.add_argument("--force", action="store_true",
                        help="Re-crawl even if affiliation file exists")
    parser.add_argument("--delay", type=float, default=0.11,
                        help="Seconds between API calls per thread (default: 0.11)")
    args = parser.parse_args()

    with open(CONFERENCES_FILE, encoding="utf-8") as f:
        all_confs = json.load(f)

    if args.conferences:
        target_ids = set(args.conferences)
    else:
        target_ids = {c["id"] for c in all_confs if c.get("rank") == "A"}

    keys = load_keys()
    log(f"Loaded {len(keys)} API key(s) → {len(keys)} parallel workers")

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
    log(f"Estimated: ~${total_papers * 0.001:.0f}, "
        f"~{total_papers * args.delay / 3600 / len(keys):.0f}h with {len(keys)} workers")

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

        log(f"START {conf_id} {year} ({expected} papers, {len(keys)} workers)")
        t1 = time.time()
        result = crawl_conference_year_parallel(conf_id, year, keys, delay=args.delay)
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
        elif result["status"] == "partial":
            # Keys ran out — wait for reset then retry this batch
            done_papers += result["matched"]
            grand_total += result["total"]
            grand_affil += result["affil"]
            grand_errors += result["errors"]
            pct = round(100 * result["affil"] / max(result["total"], 1), 1)
            log(f"PARTIAL {conf_id} {year}: {result['affil']}/{result['total']} "
                f"({pct}%) in {elapsed:.0f}s — waiting for key reset...")
            # Wait for key reset, then retry from this batch
            live = _wait_for_key_reset(keys)
            if live:
                keys = load_keys()
                log(f"RETRY {conf_id} {year} with {len(keys)} keys")
                t1 = time.time()
                result2 = crawl_conference_year_parallel(conf_id, year, keys, delay=args.delay)
                elapsed += time.time() - t1
                if result2["status"] == "ok":
                    done += 1
                    done_papers += result2["total"] - result["total"]
                    grand_total += result2["total"] - result["total"]
                    grand_affil += result2["affil"] - result["affil"]
                    pct = round(100 * result2["affil"] / max(result2["total"], 1), 1)
                    log(f"DONE  {conf_id} {year} (retry): {result2['affil']}/{result2['total']} "
                        f"({pct}%) in {elapsed:.0f}s total")
                else:
                    log(f"RETRY FAILED {conf_id} {year}: {result2['status']}, will try next run")
            else:
                log(f"NO KEYS after wait, stopping.")
                break
        else:
            log(f"SKIP  {conf_id} {year}: {result['status']}")

        if done > 0 and done % 5 == 0 and grand_total > 0:
            remaining = total_papers - done_papers
            elapsed = time.time() - t0
            rate = done_papers / elapsed if elapsed > 0 else 0
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
