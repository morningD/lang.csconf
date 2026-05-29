#!/usr/bin/env python3
"""Crawl first-author affiliations from ACL Anthology XML data.

ACL Anthology publishes structured XML on GitHub with <affiliation> tags
for each author. This script downloads the XML, extracts first-author
affiliations, and matches them against our raw author data.

Usage:
    python scripts/crawl_acl_anthology_affiliations.py                        # All ACL conferences
    python scripts/crawl_acl_anthology_affiliations.py --conferences ACL       # Specific conference
    python scripts/crawl_acl_anthology_affiliations.py --force                 # Overwrite existing files
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

# ACL Anthology XML base URL
ANTHOLOGY_XML_BASE = ("https://raw.githubusercontent.com/acl-org/"
                      "acl-anthology/master/data/xml")

# Conference ID → XML file mapping
# Each entry: (primary_xml, [(findings_xml, findings_volume_id), ...])
CONF_XML_MAP = {
    "ACL": {
        "xml_files": ["2025.acl.xml", "2025.findings.xml"],
        "findings_volume": "acl",  # volume id within findings XML
    },
    "EMNLP": {
        "xml_files": ["2025.emnlp.xml", "2025.findings.xml"],
        "findings_volume": "emnlp",
    },
    "NAACL": {
        "xml_files": ["2025.naacl.xml", "2025.findings.xml"],
        "findings_volume": "naacl",
    },
    "COLING": {
        "xml_files": ["2025.coling.xml"],
        "findings_volume": None,
    },
}


def _norm_title(title: str) -> str:
    """Normalize title for fuzzy matching."""
    t = title.lower().strip()
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t)
    return t


def _strip_fixed_case(text: str) -> str:
    """Remove <fixed-case> tags from ACL Anthology titles."""
    return re.sub(r'</?fixed-case>', '', text)


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


def _fetch_xml(filename: str) -> str | None:
    """Download an XML file from ACL Anthology GitHub."""
    url = f"{ANTHOLOGY_XML_BASE}/{filename}"
    try:
        r = requests.get(url, timeout=120)
        if r.status_code == 404:
            return None
        r.raise_for_status()
        return r.text
    except requests.RequestException as e:
        print(f"  ERROR fetching {url}: {e}")
        return None


def _parse_papers_from_xml(xml_text: str, volume_filter: str | None = None) -> list[dict]:
    """Parse paper titles and first-author affiliations from ACL Anthology XML."""
    papers = []

    # If volume_filter, extract only that volume
    if volume_filter:
        idx = xml_text.find(f'<volume id="{volume_filter}"')
        if idx < 0:
            return []
        end_idx = xml_text.find('</volume>', idx)
        if end_idx < 0:
            return []
        xml_text = xml_text[idx:end_idx]

    # Find all paper elements
    paper_blocks = re.findall(r'<paper[^>]*>(.*?)</paper>', xml_text, re.DOTALL)

    for ptext in paper_blocks:
        # Title (strip <fixed-case> tags)
        title_m = re.search(r'<title>(.*?)</title>', ptext, re.DOTALL)
        if not title_m:
            continue
        title = _strip_fixed_case(title_m.group(1)).strip()

        # First author (first <author> element)
        first_author_block = re.search(r'<author[^>]*>(.*?)</author>', ptext, re.DOTALL)
        if not first_author_block:
            continue

        block = first_author_block.group(1)
        first_m = re.search(r'<first>(.*?)</first>', block)
        last_m = re.search(r'<last>(.*?)</last>', block)
        name = f"{first_m.group(1)} {last_m.group(1)}" if first_m and last_m else ""

        # First author's affiliation
        aff_m = re.search(r'<affiliation>(.*?)</affiliation>', block)
        affiliation = aff_m.group(1).strip() if aff_m else None

        if affiliation:
            papers.append({
                "title": title,
                "first_author": name,
                "institution": affiliation,
            })

    return papers


def _save_affiliation_file(conf_id: str, year: int, papers: list[dict],
                           raw_papers: dict[str, dict], source_label: str) -> tuple[int, int]:
    """Save affiliation data merged with raw author data.

    Merges with existing file if present (preserves data from other sources).
    """
    # Build lookup from Anthology data
    anth_lookup = {}
    for p in papers:
        norm = _norm_title(p["title"])
        if norm:
            anth_lookup[norm] = p

    # Load existing file to preserve non-Anthology data
    affil_file = AFFIL_DIR / f"{conf_id}_{year}.json"
    existing = {}
    if affil_file.exists():
        with open(affil_file) as f:
            old = json.load(f)
        for p in old.get("papers", []):
            norm = _norm_title(p["title"])
            if norm:
                existing[norm] = p

    # Build merged result
    results = []
    has_affil = 0
    for norm_title, raw_info in raw_papers.items():
        entry = {
            "title": raw_info["title"],
            "first_author": raw_info["first_author"],
            "matched": False,
            "institution": None,
        }

        # Prefer Anthology data, fall back to existing data
        if norm_title in anth_lookup:
            info = anth_lookup[norm_title]
            entry["matched"] = True
            entry["institution"] = info["institution"]
            entry["imported_from"] = source_label
            has_affil += 1
        elif norm_title in existing and existing[norm_title].get("institution"):
            old_entry = existing[norm_title]
            entry["matched"] = old_entry.get("matched", False)
            entry["institution"] = old_entry["institution"]
            if "imported_from" in old_entry:
                entry["imported_from"] = old_entry["imported_from"]
            has_affil += 1

        results.append(entry)

    output = {
        "conference": conf_id,
        "year": year,
        "total_papers": len(results),
        "total_matched": has_affil,
        "total_with_affiliation": has_affil,
        "coverage_pct": round(100 * has_affil / max(len(results), 1), 1),
        "source": source_label,
        "papers": results,
    }

    AFFIL_DIR.mkdir(parents=True, exist_ok=True)
    with open(affil_file, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    return has_affil, len(results)


def main():
    parser = argparse.ArgumentParser(description="Crawl ACL Anthology affiliations")
    parser.add_argument("--conferences", nargs="+", help="Specific conference IDs")
    parser.add_argument("--force", action="store_true", help="Overwrite existing files")
    parser.add_argument("--year", type=int, default=2025, help="Year to crawl (default: 2025)")
    args = parser.parse_args()

    target_confs = args.conferences or list(CONF_XML_MAP.keys())
    year = args.year

    # Load conferences to get configured years
    confs_data = json.load(open(RAW_DIR / "conferences.json"))
    conf_years = {c["id"]: c.get("years", []) for c in confs_data}

    # XML cache to avoid re-downloading
    xml_cache: dict[str, str] = {}

    total_imported = 0
    total_papers = 0
    total_with_affil = 0

    for conf_id in sorted(target_confs):
        if conf_id not in CONF_XML_MAP:
            print(f"Unknown conference: {conf_id}")
            continue

        if year not in conf_years.get(conf_id, []):
            print(f"{conf_id} {year}: not in configured years, skipping")
            continue

        affil_file = AFFIL_DIR / f"{conf_id}_{year}.json"
        if not args.force and affil_file.exists():
            d = json.load(open(affil_file))
            pct = d.get("coverage_pct", 0)
            if pct >= 80:
                print(f"{conf_id} {year}: already {pct:.0f}% coverage, skipping")
                continue
            print(f"{conf_id} {year}: exists but only {pct:.0f}%, re-crawling...")

        info = CONF_XML_MAP[conf_id]
        raw_papers = _load_raw_first_authors(conf_id, year)
        if not raw_papers:
            print(f"{conf_id} {year}: no raw author data, skipping")
            continue

        # Collect papers from all XML files
        all_anth_papers = []
        source_parts = []

        for xml_file in info["xml_files"]:
            if xml_file not in xml_cache:
                print(f"  Downloading {xml_file}...", end=" ", flush=True)
                xml = _fetch_xml(xml_file)
                if xml:
                    xml_cache[xml_file] = xml
                    paper_count = xml.count("<paper ")
                    print(f"{paper_count} papers")
                else:
                    print("not found")
                    continue

            xml_text = xml_cache[xml_file]

            # For findings XML, filter to the conference's volume
            if "findings" in xml_file and info.get("findings_volume"):
                parsed = _parse_papers_from_xml(xml_text, volume_filter=info["findings_volume"])
            else:
                parsed = _parse_papers_from_xml(xml_text)

            all_anth_papers.extend(parsed)
            if parsed:
                source_parts.append("acl_anthology")

        if not all_anth_papers:
            print(f"{conf_id} {year}: no papers found in Anthology XML")
            continue

        source_label = " + ".join(dict.fromkeys(source_parts)) if source_parts else "acl_anthology"
        has_affil, total = _save_affiliation_file(
            conf_id, year, all_anth_papers, raw_papers, source_label)
        pct = round(100 * has_affil / max(total, 1), 1)
        print(f"{conf_id} {year}: {has_affil}/{total} = {pct:.0f}% "
              f"({len(all_anth_papers)} Anthology papers)")

        total_imported += 1
        total_papers += total
        total_with_affil += has_affil

    print(f"\nACL Anthology import complete: {total_imported} conf-years, "
          f"{total_with_affil}/{total_papers} papers "
          f"({round(100*total_with_affil/max(total_papers,1),1)}%)")


if __name__ == "__main__":
    main()
