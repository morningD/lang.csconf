#!/usr/bin/env python3
"""Audit existing CCF-B affiliation coverage without network access."""

from __future__ import annotations

import argparse
import json
import os
import re
from collections import defaultdict
from pathlib import Path
from typing import Any


COVERAGE_BANDS = (
    (0.0, "zero"),
    (10.0, "under_10"),
    (50.0, "10_to_50"),
)


def classify_coverage(total: int, with_institution: int) -> str:
    """Return the priority band for a conference-year's coverage."""
    pct = 100 * with_institution / total if total else 0.0
    if pct == 0:
        return "zero"
    if pct < 10:
        return "under_10"
    if pct < 50:
        return "10_to_50"
    return "50_or_more"


def _count_papers(papers: list[dict[str, Any]]) -> tuple[int, int]:
    matched = sum(bool(paper.get("matched")) for paper in papers)
    with_institution = sum(bool(paper.get("institution")) for paper in papers)
    return matched, with_institution


def analyze_affiliation_file(
    conf_id: str, year: int, raw_total: int, payload: dict[str, Any]
) -> dict[str, Any]:
    """Analyze one existing affiliation payload without mutating it."""
    source = str(payload.get("source") or "unknown")
    papers = payload.get("papers")
    integrity_issues: list[str] = []
    if not isinstance(papers, list):
        papers = []
        integrity_issues.append("papers_not_list")

    file_total = payload.get("total_papers")
    if not isinstance(file_total, int):
        file_total = len(papers)
        integrity_issues.append("total_papers_missing_or_invalid")
    if file_total != raw_total:
        integrity_issues.append("raw_total_mismatch")

    if source == "openalex":
        matched, with_institution = _count_papers(papers)
        declared_matched = payload.get("total_matched")
        declared_with_institution = payload.get("total_with_affiliation")
        if declared_matched != matched:
            integrity_issues.append("total_matched_mismatch")
        if declared_with_institution != with_institution:
            integrity_issues.append("total_with_affiliation_mismatch")
        if with_institution > matched:
            integrity_issues.append("institution_exceeds_matched")
        if matched > raw_total:
            integrity_issues.append("matched_exceeds_raw_total")
        if with_institution < matched:
            diagnosis = "openalex_metadata_gap"
        elif matched < raw_total:
            diagnosis = "openalex_match_gap"
        else:
            diagnosis = "openalex_complete"
    else:
        matched, with_institution = _count_papers(papers)
        diagnosis = "non_openalex"

    coverage_pct = round(100 * with_institution / raw_total, 1) if raw_total else 0.0
    return {
        "conference": conf_id,
        "year": year,
        "source": source,
        "total": raw_total,
        "matched": matched,
        "with_institution": with_institution,
        "coverage_pct": coverage_pct,
        "coverage_band": classify_coverage(raw_total, with_institution),
        "diagnosis": diagnosis,
        "integrity_issues": sorted(integrity_issues),
    }


AUTHOR_FILENAME = re.compile(
    r"^(?P<conference>[A-Za-z0-9+&.\-]+)_(?P<year>\d{4})\.json$"
)


def _conference_metadata_prefixes(conference: dict[str, Any]) -> tuple[str, ...]:
    description = conference.get("description")
    if not isinstance(description, str) or not description.strip():
        return ()
    normalized = description.strip().casefold()
    prefixes = [normalized]
    generic_prefix = "conference on "
    if normalized.startswith(generic_prefix):
        prefixes.append(normalized.removeprefix(generic_prefix))
    return tuple(prefixes)


def _raw_paper_total(
    path: Path,
    conference: dict[str, Any],
    affiliation_titles: set[str],
) -> tuple[int, int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    authors = payload.get("authors") if isinstance(payload, dict) else payload
    if not isinstance(authors, list):
        raise ValueError("authors_not_list")

    metadata_prefixes = _conference_metadata_prefixes(conference)
    seen_titles: set[str] = set()
    untitled_count = 0
    excluded_metadata = 0
    for author in authors:
        if not isinstance(author, dict) or author.get("ordinal") != 1:
            continue
        title = author.get("title")
        if isinstance(title, str) and title.strip():
            normalized_title = title.strip().casefold()
            if (
                any(normalized_title.startswith(prefix) for prefix in metadata_prefixes)
                and title not in affiliation_titles
            ):
                excluded_metadata += 1
                continue
            seen_titles.add(title.strip())
        else:
            untitled_count += 1
    return len(seen_titles) + untitled_count, excluded_metadata


def _eligible_raw_files(
    conferences: list[dict[str, Any]],
    authors_dir: Path,
    year_floor: int,
    year_ceiling: int,
) -> list[tuple[str, int, Path, dict[str, Any]]]:
    ccf_b_conferences = {
        str(item.get("id")): item for item in conferences if item.get("rank") == "B"
    }
    eligible: list[tuple[str, int, Path, dict[str, Any]]] = []
    for path in sorted(authors_dir.glob("*.json")):
        match = AUTHOR_FILENAME.fullmatch(path.name)
        if not match:
            continue
        conf_id = match.group("conference")
        year = int(match.group("year"))
        if conf_id in ccf_b_conferences and year_floor <= year <= year_ceiling:
            eligible.append((conf_id, year, path, ccf_b_conferences[conf_id]))
    return eligible


def _source_summary(records: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    summary: dict[str, dict[str, int]] = defaultdict(lambda: {
        "conference_years": 0,
        "total": 0,
        "matched": 0,
        "with_institution": 0,
    })
    for record in records:
        source = record["source"]
        summary[source]["conference_years"] += 1
        for key in ("total", "matched", "with_institution"):
            summary[source][key] += record[key]
    return {source: summary[source] for source in sorted(summary)}


def _openalex_retry_lists(
    records: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    candidates = []
    skips = []
    for record in records:
        identity = {"conference": record["conference"], "year": record["year"]}
        if record["source"] != "openalex":
            skips.append({**identity, "reason": f"non_openalex_source:{record['source']}"})
        elif record["integrity_issues"]:
            skips.append({**identity, "reason": "integrity_issues"})
        elif record["coverage_band"] not in {"zero", "under_10", "10_to_50"}:
            skips.append({**identity, "reason": f"coverage_band:{record['coverage_band']}"})
        elif record["diagnosis"] == "openalex_metadata_gap":
            skips.append({**identity, "reason": "openalex_metadata_gap"})
        elif record["diagnosis"] != "openalex_match_gap":
            skips.append({**identity, "reason": record["diagnosis"]})
        else:
            candidates.append({
                **identity,
                "total": record["total"],
                "matched": record["matched"],
                "with_institution": record["with_institution"],
                "unmatched": record["total"] - record["matched"],
                "coverage_pct": record["coverage_pct"],
                "coverage_band": record["coverage_band"],
            })
    band_rank = {"zero": 0, "under_10": 1, "10_to_50": 2, "50_or_more": 3}
    candidates.sort(key=lambda item: (
        band_rank[item["coverage_band"]], -item["unmatched"], item["conference"], item["year"]
    ))
    for rank, candidate in enumerate(candidates, start=1):
        candidate["priority_rank"] = rank
    skips.sort(key=lambda item: (item["conference"], item["year"], item["reason"]))
    return candidates, skips


def audit_affiliation_data(
    conferences: list[dict[str, Any]],
    authors_dir: Path,
    affiliations_dir: Path,
    year_floor: int = 2010,
    year_ceiling: int = 2026,
) -> dict[str, Any]:
    """Return a deterministic offline audit for eligible CCF-B conference-years."""
    records: list[dict[str, Any]] = []
    integrity_issues: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    invalid = 0

    for conf_id, year, raw_path, conference in _eligible_raw_files(
        conferences, authors_dir, year_floor, year_ceiling
    ):
        affiliation_path = affiliations_dir / f"{conf_id}_{year}.json"
        if not affiliation_path.exists():
            item = {"conference": conf_id, "year": year}
            missing.append(item)
            integrity_issues.append({**item, "issue": "missing_affiliation_file"})
            continue

        try:
            payload = json.loads(affiliation_path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("payload_not_object")
        except (OSError, ValueError, json.JSONDecodeError) as error:
            invalid += 1
            integrity_issues.append({
                "conference": conf_id,
                "year": year,
                "issue": f"invalid_affiliation_file:{error}",
            })
            continue

        papers = payload.get("papers")
        affiliation_titles = {
            paper["title"]
            for paper in papers if isinstance(paper, dict) and isinstance(paper.get("title"), str)
        } if isinstance(papers, list) else set()
        try:
            raw_total, excluded_metadata = _raw_paper_total(
                raw_path, conference, affiliation_titles
            )
        except (OSError, ValueError, json.JSONDecodeError) as error:
            integrity_issues.append({
                "conference": conf_id,
                "year": year,
                "issue": f"invalid_raw_file:{error}",
            })
            continue

        record = analyze_affiliation_file(conf_id, year, raw_total, payload)
        record["excluded_conference_metadata"] = excluded_metadata
        records.append(record)
        integrity_issues.extend(
            {"conference": conf_id, "year": year, "issue": issue}
            for issue in record["integrity_issues"]
        )

    records.sort(key=lambda item: (item["conference"], item["year"]))
    integrity_issues.sort(key=lambda item: (item["conference"], item["year"], item["issue"]))
    priority = {
        band: [
            {"conference": item["conference"], "year": item["year"]}
            for item in records
            if item["coverage_band"] == band
        ]
        for band in ("zero", "under_10", "10_to_50")
    }
    priority["zero"].extend(missing)
    priority["zero"].sort(key=lambda item: (item["conference"], item["year"]))
    openalex_candidates, openalex_retry_skips = _openalex_retry_lists(records)
    return {
        "scope": {"rank": "B", "year_floor": year_floor, "year_ceiling": year_ceiling},
        "summary": {
            "eligible_conference_years": len(records) + len(missing) + invalid,
            "affiliation_files_found": len(records),
            "missing_affiliation_files": len(missing),
            "invalid_affiliation_files": invalid,
            "excluded_conference_metadata": sum(
                record["excluded_conference_metadata"] for record in records
            ),
        },
        "by_source": _source_summary(records),
        "records": records,
        "priority": priority,
        "openalex_match_gap_candidates": openalex_candidates,
        "openalex_retry_skips": openalex_retry_skips,
        "integrity_issues": integrity_issues,
    }


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFERENCES = ROOT / "data" / "raw" / "conferences.json"
DEFAULT_AUTHORS_DIR = ROOT / "data" / "raw" / "authors"
DEFAULT_AFFILIATIONS_DIR = ROOT / "data" / "raw" / "affiliations"
DEFAULT_OUTPUT = ROOT / "data" / "stats" / "affiliation_coverage_audit.json"


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Offline audit for CCF-B first-author affiliation coverage"
    )
    parser.add_argument("--conferences", type=Path, default=DEFAULT_CONFERENCES)
    parser.add_argument("--authors-dir", type=Path, default=DEFAULT_AUTHORS_DIR)
    parser.add_argument("--affiliations-dir", type=Path, default=DEFAULT_AFFILIATIONS_DIR)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--year-floor", type=int, default=2010)
    parser.add_argument("--year-ceiling", type=int, default=2026)
    args = parser.parse_args(argv)

    conferences = json.loads(args.conferences.read_text(encoding="utf-8"))
    if not isinstance(conferences, list):
        raise ValueError("conferences JSON must be an array")
    report = audit_affiliation_data(
        conferences,
        args.authors_dir,
        args.affiliations_dir,
        args.year_floor,
        args.year_ceiling,
    )
    _write_json(args.output, report)
    summary = report["summary"]
    print(
        "CCF-B affiliation audit: "
        f"eligible={summary['eligible_conference_years']}, "
        f"files={summary['affiliation_files_found']}, "
        f"missing={summary['missing_affiliation_files']}, "
        f"invalid={summary['invalid_affiliation_files']}"
    )
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
