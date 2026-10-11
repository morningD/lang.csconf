#!/usr/bin/env python3
"""Build a local, read-only feasibility matrix for affiliation sources."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_AUDIT = ROOT / "data" / "stats" / "affiliation_coverage_audit.json"
DEFAULT_NOTES = ROOT / "pipeline" / "conference_year_notes.json"
DEFAULT_OUTPUT = ROOT / "data" / "stats" / "affiliation_source_feasibility.json"

REPRESENTATIVE_SMALL = {
    ("GROUP", 2023),
    ("ECSCW", 2025),
    ("CIDR", 2023),
    ("CIDR", 2024),
    ("VMCAI", 2024),
}
HIGH_IMPACT_FAMILY = {("ICASSP", 2016)}
JOURNAL_MODEL_CONFERENCES = {"FSE-CRYPTO", "HIPEAC"}


def _note_for(notes: dict[str, Any], conference: str, year: int) -> dict[str, Any]:
    value = notes.get(f"{conference}_{year}", {})
    return value if isinstance(value, dict) else {}


def _entry(record: dict[str, Any], notes: dict[str, Any]) -> dict[str, Any]:
    conference = record["conference"]
    year = record["year"]
    note = _note_for(notes, conference, year)
    source = record.get("source", "unknown")
    diagnosis = record.get("diagnosis", "unknown")
    paper_source = note.get("paper_source", "sparql")
    base = {
        "conference": conference,
        "year": year,
        "current_source": source,
        "total": record.get("total", 0),
        "matched": record.get("matched", 0),
        "with_institution": record.get("with_institution", 0),
        "unmatched": record.get("total", 0) - record.get("matched", 0),
        "diagnosis": diagnosis,
        "paper_source": paper_source,
    }
    note_text = str(note.get("note", "")).lower()
    is_journal_modeled = (
        paper_source == "journal_scrape"
        or conference in JOURNAL_MODEL_CONFERENCES
        or "journal" in note_text
    )
    if diagnosis == "openalex_metadata_gap":
        return {**base, "priority_group": "excluded", "recommendation": "excluded_metadata_gap"}
    if source != "openalex":
        return {**base, "priority_group": "excluded", "recommendation": "preserve_existing_source"}
    if diagnosis == "openalex_complete":
        return {**base, "priority_group": "excluded", "recommendation": "already_openalex_complete"}
    if is_journal_modeled:
        return {**base, "priority_group": "source_specific", "recommendation": "source_specific_needed"}
    if (conference, year) in REPRESENTATIVE_SMALL:
        return {**base, "priority_group": "representative_small", "recommendation": "publisher_or_event_feasibility"}
    if (conference, year) in HIGH_IMPACT_FAMILY:
        return {**base, "priority_group": "high_impact_family", "recommendation": "ieee_source_or_doi_feasibility"}
    return {**base, "priority_group": "deferred", "recommendation": "historical_openalex_limit"}


def _identity(item: Any) -> tuple[str, int] | None:
    if not isinstance(item, dict):
        return None
    conference = item.get("conference")
    year = item.get("year")
    if not isinstance(conference, str) or not isinstance(year, int):
        return None
    return conference, year


def _missing_affiliation_identities(audit: dict[str, Any]) -> list[tuple[str, int]]:
    priority = audit.get("priority", {})
    zero_priority = priority.get("zero", []) if isinstance(priority, dict) else []
    zero_ids = {identity for item in zero_priority if (identity := _identity(item)) is not None}
    missing_ids = {
        identity
        for item in audit.get("integrity_issues", [])
        if isinstance(item, dict)
        and item.get("issue") == "missing_affiliation_file"
        and (identity := _identity(item)) is not None
    }
    record_ids = {
        identity for item in audit.get("records", []) if (identity := _identity(item)) is not None
    }
    return sorted((zero_ids & missing_ids) - record_ids)


def _missing_entry(conference: str, year: int, notes: dict[str, Any]) -> dict[str, Any]:
    note = _note_for(notes, conference, year)
    return {
        "conference": conference,
        "year": year,
        "current_source": "missing",
        "total": 0,
        "matched": 0,
        "with_institution": 0,
        "unmatched": 0,
        "diagnosis": "missing_affiliation_file",
        "paper_source": note.get("paper_source", "sparql"),
        "priority_group": "missing",
        "recommendation": "create_affiliation_file",
    }


def build_feasibility_matrix(audit: dict[str, Any], notes: dict[str, Any]) -> dict[str, Any]:
    entries = [_entry(record, notes) for record in audit.get("records", [])]
    entries.extend(
        _missing_entry(conference, year, notes)
        for conference, year in _missing_affiliation_identities(audit)
    )
    priority = {
        "missing": 0,
        "representative_small": 1,
        "high_impact_family": 2,
        "source_specific": 3,
        "deferred": 4,
        "excluded": 5,
    }
    entries.sort(key=lambda item: (priority[item["priority_group"]], item["conference"], item["year"]))
    summaries: dict[str, int] = {}
    for entry in entries:
        key = entry["recommendation"]
        summaries[key] = summaries.get(key, 0) + 1
    return {
        "scope": "local_only_no_network_no_affiliation_writes",
        "entries": entries,
        "recommendation_counts": {key: summaries[key] for key in sorted(summaries)},
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a local affiliation-source feasibility matrix")
    parser.add_argument("--audit-report", type=Path, default=DEFAULT_AUDIT)
    parser.add_argument("--notes", type=Path, default=DEFAULT_NOTES)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    audit = json.loads(args.audit_report.read_text(encoding="utf-8"))
    notes = json.loads(args.notes.read_text(encoding="utf-8"))
    matrix = build_feasibility_matrix(audit, notes)
    _write_json(args.output, matrix)
    print(f"Wrote {args.output}: {len(matrix['entries'])} entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
