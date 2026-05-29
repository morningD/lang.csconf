#!/usr/bin/env python3
"""Crawl first-author affiliations from USENIX conference proceedings pages.

USENIX conferences (NSDI, OSDI, Security, FAST, ATC) are not indexed by
OpenAlex.  Their proceedings pages at usenix.org list every accepted paper
with author names and affiliations in structured HTML (<em> tags).

Usage:
    python scripts/crawl_usenix_affiliations.py                        # All USENIX, all years
    python scripts/crawl_usenix_affiliations.py --conferences NSDI OSDI  # Specific conferences
    python scripts/crawl_usenix_affiliations.py --force                 # Overwrite existing files
"""

import argparse
import json
import os
import re
import sys
import time
from html import unescape
from pathlib import Path

import requests

DATA_DIR = Path(__file__).parent.parent / "data"
RAW_DIR = DATA_DIR / "raw"
AFFIL_DIR = RAW_DIR / "affiliations"
AUTHORS_DIR = RAW_DIR / "authors"

# Conference ID → USENIX URL key + year range
USENIX_CONFERENCES = {
    "NSDI":            {"url_key": "nsdi",            "biennial": False},
    "OSDI":            {"url_key": "osdi",            "biennial": True, "even": True},
    "USENIXSECURITY":  {"url_key": "usenixsecurity",  "biennial": False},
    "FAST":            {"url_key": "fast",            "biennial": False},
    "USENIXATC":       {"url_key": "atc",             "biennial": False},
}


def _norm_title(title: str) -> str:
    """Normalize title for fuzzy matching."""
    t = title.lower().strip()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t


def _load_raw_first_authors(conf_id: str, year: int) -> dict[str, dict]:
    """Load raw author file and return {normalized_title: {title, first_author}}."""
    raw_file = AUTHORS_DIR / f"{conf_id}_{year}.json"
    if not raw_file.exists():
        return {}
    with open(raw_file) as f:
        data = json.load(f)
    papers = {}
    for a in data.get("authors", []):
        if a.get("ordinal") == 1:
            norm = _norm_title(a["title"])
            if norm and norm not in papers:
                papers[norm] = {"title": a["title"], "first_author": a["name"]}
    return papers


def _fetch_technical_sessions(url_key: str, year: int) -> str | None:
    """Fetch the technical-sessions page HTML."""
    yy = str(year)[2:]
    url = f"https://www.usenix.org/conference/{url_key}{yy}/technical-sessions"
    try:
        r = requests.get(url, timeout=60, headers={"User-Agent": "Mozilla/5.0"})
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        print(f"  ERROR fetching {url}: {e}")
        return None


def _parse_papers(html: str) -> list[dict]:
    """Parse all paper blocks from a technical-sessions page."""
    papers = []

    article_blocks = re.findall(
        r'<article[^>]*class="[^"]*node-paper[^"]*"[^>]*>(.*?)</article>',
        html, re.DOTALL,
    )

    for block in article_blocks:
        # Title
        title_m = re.search(r'<h2[^>]*>.*?<a[^>]*>(.*?)</a>', block, re.DOTALL)
        if not title_m:
            continue
        title = unescape(title_m.group(1).strip())

        # People/affiliations
        people_m = re.search(
            r'field-paper-people-text[^>]*>\s*<div[^>]*>\s*<div[^>]*>\s*<p>(.*?)</p>',
            block, re.DOTALL,
        )
        if not people_m:
            continue

        people_html = people_m.group(1)

        # Extract first <em> tag content = first author's affiliation
        em_m = re.search(r'<em>(.*?)</em>', people_html, re.DOTALL)
        if not em_m:
            continue

        affiliation = unescape(em_m.group(1).strip().rstrip(';').strip())
        if not affiliation:
            continue

        # Extract first author name (text before first comma or "and" before <em>)
        # Format: "Name1 and Name2, <em>Affil</em>; Name3, <em>Affil2</em>"
        # First author = text before the first comma that precedes the first <em>
        raw_text = re.sub(r'<[^>]+>', '', people_html)
        # Split by comma to find author block
        first_author = ""
        if raw_text:
            first_author = raw_text.split(',')[0].strip()
            # Remove "and Name2" if present (co-first authors sharing affiliation)
            if ' and ' in first_author:
                first_author = first_author.split(' and ')[0].strip()

        papers.append({
            "title": title,
            "first_author": first_author,
            "institution": affiliation,
        })

    return papers


def _save_affiliation_file(conf_id: str, year: int, papers: list[dict],
                           raw_papers: dict[str, dict]) -> tuple[int, int]:
    """Save affiliation data merged with raw author data."""
    # Build lookup from USENIX data
    usenix_lookup = {}
    for p in papers:
        norm = _norm_title(p["title"])
        if norm:
            usenix_lookup[norm] = p

    # Merge: for each raw paper, check if we have USENIX affiliation
    results = []
    has_affil = 0
    for norm_title, raw_info in raw_papers.items():
        entry = {
            "title": raw_info["title"],
            "first_author": raw_info["first_author"],
            "matched": False,
            "institution": None,
        }
        if norm_title in usenix_lookup:
            info = usenix_lookup[norm_title]
            entry["matched"] = True
            entry["institution"] = info["institution"]
            entry["imported_from"] = "usenix_website"
            has_affil += 1
        results.append(entry)

    output = {
        "conference": conf_id,
        "year": year,
        "total_papers": len(results),
        "total_matched": has_affil,
        "total_with_affiliation": has_affil,
        "coverage_pct": round(100 * has_affil / max(len(results), 1), 1),
        "source": "usenix_website",
        "papers": results,
    }

    AFFIL_DIR.mkdir(parents=True, exist_ok=True)
    out_file = AFFIL_DIR / f"{conf_id}_{year}.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return has_affil, len(results)


def main():
    parser = argparse.ArgumentParser(description="Crawl USENIX affiliations")
    parser.add_argument("--conferences", nargs="+", help="Specific conference IDs")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--delay", type=float, default=1.0, help="Seconds between requests")
    args = parser.parse_args()

    target_confs = args.conferences or list(USENIX_CONFERENCES.keys())

    # Load conferences to get configured years
    confs_data = json.load(open(RAW_DIR / "conferences.json"))
    conf_years = {c["id"]: c.get("years", []) for c in confs_data}

    total_imported = 0
    total_papers = 0
    total_with_affil = 0

    for conf_id in sorted(target_confs):
        if conf_id not in USENIX_CONFERENCES:
            print(f"Unknown conference: {conf_id}")
            continue

        info = USENIX_CONFERENCES[conf_id]
        url_key = info["url_key"]
        years = conf_years.get(conf_id, [])

        if not years:
            print(f"No years configured for {conf_id}")
            continue

        print(f"\n=== {conf_id} ({url_key}) ===")

        for year in years:
            affil_file = AFFIL_DIR / f"{conf_id}_{year}.json"

            if not args.force and affil_file.exists():
                # Skip if already has decent coverage
                d = json.load(open(affil_file))
                pct = d.get("coverage_pct", 0)
                if pct >= 50:
                    print(f"  {year}: already {pct:.0f}% coverage, skipping")
                    continue
                print(f"  {year}: exists but only {pct:.0f}% coverage, re-crawling...")

            # Load raw papers
            raw_papers = _load_raw_first_authors(conf_id, year)
            if not raw_papers:
                print(f"  {year}: no raw author data, skipping")
                continue

            # Fetch USENIX page
            html = _fetch_technical_sessions(url_key, year)
            if html is None:
                print(f"  {year}: no technical-sessions page (404)")
                continue

            # Parse papers
            usenix_papers = _parse_papers(html)
            if not usenix_papers:
                print(f"  {year}: no papers found on page")
                continue

            # Save
            has_affil, total = _save_affiliation_file(conf_id, year, usenix_papers, raw_papers)
            pct = round(100 * has_affil / max(total, 1), 1)
            print(f"  {year}: {has_affil}/{total} = {pct:.0f}% ({len(usenix_papers)} USENIX papers)")

            total_imported += 1
            total_papers += total
            total_with_affil += has_affil

            time.sleep(args.delay)

    print(f"\nUSENIX import complete: {total_imported} conf-years, "
          f"{total_with_affil}/{total_papers} papers "
          f"({round(100*total_with_affil/max(total_papers,1),1)}%)")


if __name__ == "__main__":
    main()
