"""Batch OpenAlex affiliation crawl for CCF-A conferences (2023-2025).

Features:
  - Resumable: skips completed batches, safe to re-run after interruption
  - Auto key rotation: cycles through all keys, pauses at UTC midnight if all exhausted
  - Hot-reload keys: re-reads openalex_keys.txt before each batch
  - Progress log: data/raw/affiliations/_crawl_log.txt

Usage:
    python scripts/openalex_batch_crawl.py                          # All CCF-A, 2023-2025
    python scripts/openalex_batch_crawl.py --conferences CHI SIGKDD  # Specific conferences
    python scripts/openalex_batch_crawl.py --force                   # Re-crawl existing
    python scripts/openalex_batch_crawl.py --years 2024 2025         # Custom years
    python scripts/openalex_batch_crawl.py --key-index 2             # Start with key #2
"""

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).parent.parent
AFFIL_DIR = ROOT / "data" / "raw" / "affiliations"
AUTHORS_DIR = ROOT / "data" / "raw" / "authors"
CONFERENCES_FILE = ROOT / "data" / "raw" / "conferences.json"
KEYS_FILE = Path(__file__).parent / "openalex_keys.txt"
LOG_FILE = AFFIL_DIR / "_crawl_log.txt"

sys.path.insert(0, str(ROOT))
from pipeline.utils.openalex_client import (
    extract_first_author_institution,
    search_work,
)


def log(msg: str):
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
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


class KeyManager:
    """Manages API keys with auto-rotation on 429 and wait-until-reset."""

    def __init__(self, start_index: int = 0):
        self._keys = load_keys()
        self._idx = start_index % len(self._keys)
        self._session = self._make_session()
        self._exhausted: set[int] = set()  # indices of keys that returned 429
        log(f"KeyManager: {len(self._keys)} key(s), starting with #{self._idx}")

    def _make_session(self):
        import requests
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry
        s = requests.Session()
        retry = Retry(total=2, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])
        s.mount("https://", HTTPAdapter(max_retries=retry))
        s.params = {"api_key": self._keys[self._idx]}
        return s

    def reload_keys(self):
        """Hot-reload keys from file."""
        new_keys = load_keys()
        if new_keys != self._keys:
            self._keys = new_keys
            self._idx = self._idx % len(self._keys)
            self._exhausted.clear()
            self._session = self._make_session()
            log(f"Keys hot-reloaded: {len(self._keys)} key(s)")

    @property
    def session(self):
        return self._session

    @property
    def current_key_tail(self) -> str:
        return self._keys[self._idx][-6:]

    def rotate(self) -> bool:
        """Rotate to next non-exhausted key. Returns False if all exhausted."""
        for _ in range(len(self._keys)):
            self._idx = (self._idx + 1) % len(self._keys)
            if self._idx not in self._exhausted:
                self._session = self._make_session()
                return True
        return False

    def mark_exhausted(self):
        """Mark current key as exhausted (429 budget depleted)."""
        self._exhausted.add(self._idx)
        log(f"Key #{self._idx} (...{self.current_key_tail}) exhausted "
            f"({len(self._exhausted)}/{len(self._keys)} exhausted)")

    def all_exhausted(self) -> bool:
        return len(self._exhausted) >= len(self._keys)

    def reset_exhausted(self):
        """Clear exhausted set after midnight reset."""
        self._exhausted.clear()
        log("All keys reset — exhausted flags cleared")

    def wait_for_reset(self):
        """Wait until UTC midnight, checking every 60s for new keys."""
        import urllib3
        urllib3.disable_warnings()
        now = datetime.now(timezone.utc)
        tomorrow = now.replace(hour=0, minute=0, second=5, microsecond=0)
        if tomorrow <= now:
            from datetime import timedelta
            tomorrow += timedelta(days=1)
        wait_secs = (tomorrow - now).total_seconds()
        log(f"All keys exhausted. Waiting {wait_secs/60:.0f} min until UTC midnight reset...")
        log(f"  (Add new keys to {KEYS_FILE} — checked every 60s)")

        # Poll: sleep in 60s chunks so we can detect new keys early
        deadline = time.time() + wait_secs
        while time.time() < deadline:
            time.sleep(min(60, deadline - time.time()))
            # Hot-reload: if new keys appeared, try them
            try:
                new_keys = load_keys()
            except SystemExit:
                continue
            if len(new_keys) > len(self._keys):
                log(f"Detected {len(new_keys) - len(self._keys)} new key(s)!")
                self._keys = new_keys
                self._idx = self._idx % len(self._keys)
                self._exhausted.clear()
                self._session = self._make_session()
                log(f"Resuming with {len(self._keys)} keys, starting with ...{self.current_key_tail}")
                return
        # Normal midnight reset
        self.reload_keys()
        self.reset_exhausted()
        log("Midnight reset — resuming...")


def search_work_auto_rotate(title: str, year: int, km: KeyManager) -> dict | None:
    """Search OpenAlex with automatic key rotation on 429.

    Returns work dict, None (no match), or raises if all keys exhausted.
    """
    import requests

    while True:
        try:
            r = km.session.get("https://api.openalex.org/works", params={
                "filter": f"title.search:{title[:200]},publication_year:{year}",
                "select": "id,doi,title,authorships",
                "per_page": 10,
                "sort": "relevance_score:desc",
            }, timeout=15)
        except requests.RequestException:
            return None

        if r.status_code == 200:
            results = r.json().get("results", [])
            if not results:
                return None
            proceedings = [w for w in results
                           if w.get("doi") and "arxiv" not in (w.get("doi") or "")]
            return proceedings[0] if proceedings else results[0]

        if r.status_code == 429:
            km.mark_exhausted()
            if km.all_exhausted():
                km.wait_for_reset()
                continue  # retry with reset keys
            else:
                km.rotate()
                log(f"Rotated to key ...{km.current_key_tail}")
                continue  # retry with new key

        # Other errors
        return None


def crawl_conference_year(conf_id: str, year: int, km: KeyManager,
                          delay: float = 0.11) -> dict:
    """Crawl one conference-year via OpenAlex. Returns summary dict."""
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

    results = []
    matched = 0
    has_affil = 0
    errors = 0

    for i, paper in enumerate(papers):
        title = paper["title"]
        first_author = paper["first_author"]

        try:
            work = search_work_auto_rotate(title, year, km)
        except Exception as e:
            errors += 1
            results.append({"title": title, "first_author": first_author,
                            "matched": False, "institution": None})
            if errors <= 3:
                log(f"  ERROR on paper {i+1}: {e}")
            continue

        if work is None:
            results.append({"title": title, "first_author": first_author,
                            "matched": False, "institution": None})
            time.sleep(delay)
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
        time.sleep(delay)

        if (i + 1) % 50 == 0:
            pct = 100 * has_affil / (i + 1)
            log(f"  {conf_id} {year}: {i+1}/{len(papers)} "
                f"(affil={has_affil}, {pct:.0f}%, err={errors})")

    # Save output
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
        "status": "ok",
        "total": len(papers),
        "matched": matched,
        "affil": has_affil,
        "errors": errors,
    }


def main():
    parser = argparse.ArgumentParser(description="Batch OpenAlex affiliation crawl")
    parser.add_argument("--conferences", nargs="+", help="Specific conference IDs")
    parser.add_argument("--years", nargs="+", type=int, default=[2023, 2024, 2025],
                        help="Year range (default: 2023 2024 2025)")
    parser.add_argument("--force", action="store_true",
                        help="Re-crawl even if affiliation file exists")
    parser.add_argument("--delay", type=float, default=0.11,
                        help="Seconds between API calls (default: 0.11)")
    parser.add_argument("--key-index", type=int, default=0,
                        help="Start with this key index (0-based)")
    args = parser.parse_args()

    with open(CONFERENCES_FILE, encoding="utf-8") as f:
        all_confs = json.load(f)

    if args.conferences:
        target_ids = set(args.conferences)
    else:
        target_ids = {c["id"] for c in all_confs if c.get("rank") == "A"}

    km = KeyManager(start_index=args.key_index)

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
        f"~{total_papers * args.delay / 3600:.0f}h at {1/args.delay:.0f} RPS")

    done = 0
    done_papers = 0
    grand_total = 0
    grand_affil = 0
    grand_errors = 0
    t0 = time.time()

    for conf_id, year, expected in queue:
        km.reload_keys()

        out_file = AFFIL_DIR / f"{conf_id}_{year}.json"
        if not args.force and out_file.exists():
            log(f"SKIP {conf_id} {year} (file exists)")
            done += 1
            continue

        log(f"START {conf_id} {year} ({expected} papers) [key ...{km.current_key_tail}]")
        t1 = time.time()
        result = crawl_conference_year(conf_id, year, km, delay=args.delay)
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
        else:
            log(f"SKIP  {conf_id} {year}: {result['status']}")

        if done > 0 and done % 5 == 0 and grand_total > 0:
            remaining = total_papers - done_papers
            rate = done_papers / (time.time() - t0) if (time.time() - t0) > 0 else 0
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
