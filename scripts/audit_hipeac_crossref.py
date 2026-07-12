#!/usr/bin/env python3
"""Audit bounded Crossref evidence for HIPEAC 2025 without changing affiliation data."""

from __future__ import annotations

import argparse
import json
import os
import re
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
AUTHORS_FILE = ROOT / "data" / "raw" / "authors" / "HIPEAC_2025.json"
DEFAULT_OUTPUT = ROOT / "data" / "stats" / "affiliation_source_evidence" / "hipeac_2025_crossref.json"
CROSSREF_API = "https://api.crossref.org/works"


def normalize_title(value: str) -> str:
    value = value.casefold()
    value = re.sub(r"[^\w\s]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_name(value: str) -> str:
    return re.sub(r"[^\w]", "", value.casefold())


def _crossref_author_name(author: dict[str, Any]) -> str:
    return " ".join(part for part in (author.get("given"), author.get("family")) if isinstance(part, str))


def _approved_repair_title(paper: dict[str, str], source_title: str, approved_repairs: dict[str, str]) -> bool:
    return approved_repairs.get(paper["title"]) == source_title


def evaluate_crossref_record(
    paper: dict[str, str], doi: str, message: dict[str, Any], approved_repairs: dict[str, str]
) -> dict[str, Any]:
    titles = message.get("title")
    source_title = titles[0] if isinstance(titles, list) and titles and isinstance(titles[0], str) else ""
    authors = message.get("author")
    authors = authors if isinstance(authors, list) else []
    first_author = authors[0] if authors and isinstance(authors[0], dict) else None
    base = {
        "title": paper["title"],
        "first_author": paper["first_author"],
        "doi": doi,
        "crossref_title": source_title,
        "crossref_first_author": _crossref_author_name(first_author) if first_author else "",
        "publisher": message.get("publisher"),
        "container_title": (message.get("container-title") or [None])[0],
    }
    if not first_author or normalize_name(paper["first_author"]) != normalize_name(_crossref_author_name(first_author)):
        return {**base, "verdict": "crossref_first_author_mismatch", "first_author_affiliations": []}

    title_matches = normalize_title(paper["title"]) == normalize_title(source_title)
    if not title_matches:
        raw_is_superstring = normalize_title(paper["title"]).startswith(normalize_title(source_title) + " ")
        if raw_is_superstring and _approved_repair_title(paper, source_title, approved_repairs):
            return {**base, "verdict": "raw_title_has_parser_tail", "first_author_affiliations": []}
        if raw_is_superstring:
            return {**base, "verdict": "raw_title_unexplained_superstring", "first_author_affiliations": []}
        return {**base, "verdict": "crossref_title_mismatch", "first_author_affiliations": []}

    affiliations = first_author.get("affiliation")
    names = [item["name"] for item in affiliations if isinstance(item, dict) and isinstance(item.get("name"), str)] if isinstance(affiliations, list) else []
    if not names:
        return {**base, "verdict": "accepted_no_affiliation", "first_author_affiliations": []}
    return {**base, "verdict": "accepted_exact", "first_author_affiliations": names}


def summarize_evidence(entries: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    for entry in entries:
        counts[entry["verdict"]] = counts.get(entry["verdict"], 0) + 1
    total = len(entries)
    accepted = counts.get("accepted_exact", 0)
    identity_problems = sum(
        counts.get(verdict, 0)
        for verdict in ("raw_title_has_parser_tail", "raw_title_unexplained_superstring", "crossref_title_mismatch", "crossref_first_author_mismatch")
    )
    rate = accepted / total if total else 0.0
    return {
        "sample_count": total,
        "accepted": accepted,
        "acceptance_pct": round(100 * rate, 1),
        "verdict_counts": {key: counts[key] for key in sorted(counts)},
        "multiple_affiliation_records": sum(len(entry.get("first_author_affiliations", [])) > 1 for entry in entries),
        "decision": "candidate_for_write_trial" if total >= 20 and rate >= 0.7 and identity_problems == 0 else "do_not_automate",
    }


def first_author_papers(path: Path) -> list[dict[str, str]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    papers: dict[str, dict[str, str]] = {}
    for author in payload.get("authors", []):
        if author.get("ordinal") == 1:
            papers.setdefault(author["title"], {"title": author["title"], "first_author": author["name"]})
    return list(papers.values())


def load_approved_repairs(path: Path | None) -> dict[str, str]:
    if path is None:
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    repairs = payload.get("repairs", [])
    if not isinstance(repairs, list):
        raise ValueError("approved repair manifest must contain a repairs list")
    return {
        repair["expected_bad_title"]: repair["replacement_title"]
        for repair in repairs
        if isinstance(repair, dict)
        and isinstance(repair.get("expected_bad_title"), str)
        and isinstance(repair.get("replacement_title"), str)
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bounded HIPEAC 2025 Crossref evidence audit")
    parser.add_argument("--conference", default="HIPEAC", choices=["HIPEAC"])
    parser.add_argument("--year", default=2025, type=int, choices=[2025])
    parser.add_argument("--limit", default=20, type=int)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--write-evidence", type=Path)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help=argparse.SUPPRESS)
    parser.add_argument("--approved-repairs", type=Path)
    args = parser.parse_args(argv)
    if not 1 <= args.limit <= 20:
        parser.error("--limit must be between 1 and 20")
    if args.dry_run and "--output" in (argv or []):
        parser.error("--output is only valid with --write-evidence")

    import requests

    papers = first_author_papers(AUTHORS_FILE)[:args.limit]
    approved_repairs = load_approved_repairs(args.approved_repairs)
    entries = []
    requests_made = 0
    for paper in papers:
        time.sleep(2 if requests_made else 0)
        response = requests.get(CROSSREF_API, params={"query.bibliographic": paper["title"], "rows": 1}, timeout=20)
        requests_made += 1
        if response.status_code != 200:
            entries.append({**paper, "verdict": f"http_{response.status_code}", "first_author_affiliations": []})
            if response.status_code in {403, 429} or response.status_code >= 500:
                break
            continue
        items = response.json().get("message", {}).get("items", [])
        if not items:
            entries.append({**paper, "verdict": "doi_not_found", "first_author_affiliations": []})
            continue
        message = items[0]
        doi = message.get("DOI", "")
        if not isinstance(doi, str) or not doi:
            entries.append({**paper, "verdict": "doi_not_found", "first_author_affiliations": []})
            continue
        time.sleep(2)
        response = requests.get(f"{CROSSREF_API}/{doi}", timeout=20)
        requests_made += 1
        if response.status_code != 200:
            entries.append({**paper, "doi": doi, "verdict": f"http_{response.status_code}", "first_author_affiliations": []})
            if response.status_code in {403, 429} or response.status_code >= 500:
                break
            continue
        entry = evaluate_crossref_record(paper, doi, response.json().get("message", {}), approved_repairs)
        entries.append({**entry, "crossref_url": f"{CROSSREF_API}/{doi}"})

    summary = summarize_evidence(entries)
    payload = {
        "scope": "crossref_evidence_audit",
        "mode": "dry_run" if args.dry_run else "write_evidence",
        "conference": "HIPEAC",
        "year": 2025,
        "limit": args.limit,
        "requests_made": requests_made,
        "summary": summary,
        "entries": entries,
    }
    if args.write_evidence:
        _write_json(args.write_evidence, payload)
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
