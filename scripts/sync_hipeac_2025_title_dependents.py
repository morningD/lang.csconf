#!/usr/bin/env python3
"""Synchronize the two manifest-approved HIPEAC 2025 titles across dependent inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent.parent
CONFIRMATION = "HIPEAC-2025-dependent-title-sync"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _groups(rows: list[dict[str, Any]], title_key: str = "title") -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        title = row.get(title_key)
        if not isinstance(title, str):
            raise ValueError("every record must contain a string title")
        result.setdefault(title, []).append(row)
    return result


def _identity_set(rows: list[dict[str, Any]], first_author_key: str) -> set[tuple[str, str]]:
    return {(row["title"], row[first_author_key]) for row in rows}


def _raw_first_author_rows(raw: dict[str, Any]) -> list[dict[str, Any]]:
    authors = raw.get("authors")
    if not isinstance(authors, list):
        raise ValueError("raw payload must contain authors")
    rows = [row for row in authors if row.get("ordinal") == 1]
    if len(rows) != raw.get("total_papers"):
        raise ValueError("raw first-author count does not equal total_papers")
    return rows


def _validate_root(payload: dict[str, Any], *, source: str | None = None) -> None:
    if payload.get("conference") != "HIPEAC" or payload.get("year") != 2025:
        raise ValueError("payload must be HIPEAC 2025")
    if source is not None and payload.get("source") != source:
        raise ValueError("affiliation source must be openalex")


def _manifest_repairs(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != 1 or manifest.get("conference") != "HIPEAC" or manifest.get("year") != 2025:
        raise ValueError("manifest scope must be HIPEAC 2025 schema v1")
    repairs = manifest.get("repairs")
    if not isinstance(repairs, list) or len(repairs) != 2 or manifest.get("expected_repair_count") != 2:
        raise ValueError("manifest must have exactly two repairs")
    return repairs


def _verify_repair_group(rows: list[dict[str, Any]], repair: dict[str, Any]) -> None:
    if len(rows) != repair.get("expected_author_rows"):
        raise ValueError("author row count does not match manifest")
    first_authors = [row.get("name") for row in rows if row.get("ordinal") == 1]
    if first_authors != [repair.get("expected_first_author")]:
        raise ValueError("first author does not match manifest")
    if sorted(row.get("ordinal") for row in rows) != repair.get("expected_ordinals"):
        raise ValueError("ordinal set does not match manifest")


def _encoded_sha256(payload: dict[str, Any]) -> str:
    return hashlib.sha256((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")).hexdigest()


def prepare_sync(manifest: dict[str, Any], raw_path: Path, classified_path: Path, affiliation_path: Path) -> dict[str, Any]:
    """Validate and construct the dependent title candidates without writing files."""
    input_hashes = {"raw": _sha256(raw_path), "classified": _sha256(classified_path), "affiliation": _sha256(affiliation_path)}
    raw = _load(raw_path)
    classified = _load(classified_path)
    affiliation = _load(affiliation_path)
    _validate_root(raw)
    _validate_root(classified)
    _validate_root(affiliation, source="openalex")
    repairs = _manifest_repairs(manifest)
    if raw.get("_source") != manifest.get("expected_source") or raw.get("total_papers") != manifest.get("expected_total_papers"):
        raise ValueError("raw source or paper count does not match manifest")
    if affiliation.get("total_papers") != raw.get("total_papers"):
        raise ValueError("affiliation total_papers does not match raw")
    for field in ("total_matched", "total_with_affiliation", "coverage_pct"):
        if field not in affiliation:
            raise ValueError(f"affiliation payload missing {field}")

    raw_first = _raw_first_author_rows(raw)
    raw_groups = _groups(raw["authors"])
    classified_authors = classified.get("authors")
    papers = affiliation.get("papers")
    if not isinstance(classified_authors, list) or not isinstance(papers, list):
        raise ValueError("classified and affiliation payloads must contain list records")
    classified_groups = _groups(classified_authors)
    affiliation_groups = _groups(papers)
    classified_candidate = deepcopy(classified)
    affiliation_candidate = deepcopy(affiliation)
    changed_classified_rows = 0
    changed_affiliation_records = 0
    changes = []

    for repair in repairs:
        old = repair.get("expected_bad_title")
        new = repair.get("replacement_title")
        if not isinstance(old, str) or not isinstance(new, str):
            raise ValueError("repair titles must be exact strings")
        if old in raw_groups or new not in raw_groups:
            raise ValueError("raw must already have the replacement title and no old title")
        _verify_repair_group(raw_groups[new], repair)
        classified_rows = classified_groups.get(old)
        if not classified_rows:
            raise ValueError("classified expected old title not found")
        if new in classified_groups:
            raise ValueError("replacement title already belongs to classified paper")
        _verify_repair_group(classified_rows, repair)
        affiliation_rows = affiliation_groups.get(old)
        if not affiliation_rows or len(affiliation_rows) != 1:
            raise ValueError("affiliation expected old title must occur exactly once")
        paper = affiliation_rows[0]
        if paper.get("first_author") != repair.get("expected_first_author"):
            raise ValueError("affiliation first author does not match manifest")
        if new in affiliation_groups:
            raise ValueError("replacement title already belongs to affiliation paper")

        for row in classified_candidate["authors"]:
            if row["title"] == old:
                row["title"] = new
                changed_classified_rows += 1
        for candidate_paper in affiliation_candidate["papers"]:
            if candidate_paper["title"] == old:
                candidate_paper["title"] = new
                changed_affiliation_records += 1
        changes.append({"old_title": old, "new_title": new, "first_author": repair["expected_first_author"], "author_rows": len(classified_rows)})

    raw_ids = _identity_set(raw_first, "name")
    classified_first = [row for row in classified_candidate["authors"] if row.get("ordinal") == 1]
    classified_ids = _identity_set(classified_first, "name")
    affiliation_ids = _identity_set(affiliation_candidate["papers"], "first_author")
    if len(raw_ids) != raw.get("total_papers") or raw_ids != classified_ids or raw_ids != affiliation_ids:
        raise ValueError("raw, classified, and affiliation identities are not identical")
    if len(affiliation_candidate["papers"]) != affiliation.get("total_papers"):
        raise ValueError("affiliation paper count changed")
    for field in ("total_matched", "total_with_affiliation", "coverage_pct", "source"):
        if affiliation_candidate[field] != affiliation[field]:
            raise ValueError(f"affiliation {field} changed")
    return {
        "input_hashes": input_hashes,
        "output_hashes": {"classified": _encoded_sha256(classified_candidate), "affiliation": _encoded_sha256(affiliation_candidate)},
        "classified_payload": classified_candidate,
        "affiliation_payload": affiliation_candidate,
        "changed_papers": len(changes),
        "changed_classified_rows": changed_classified_rows,
        "changed_affiliation_records": changed_affiliation_records,
        "changes": changes,
    }


def _atomic_write(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def apply_sync(raw_path: Path, classified_path: Path, affiliation_path: Path, plan: dict[str, Any], *, force: bool, confirmation: str) -> None:
    if not force:
        raise ValueError("--force is required to apply dependent title sync")
    if confirmation != CONFIRMATION:
        raise ValueError(f"--confirm {CONFIRMATION} is required to apply dependent title sync")
    current = {"raw": _sha256(raw_path), "classified": _sha256(classified_path), "affiliation": _sha256(affiliation_path)}
    if current != plan["input_hashes"]:
        raise ValueError("one or more dependent inputs changed after preview; refusing promotion")
    _atomic_write(classified_path, plan["classified_payload"])
    _atomic_write(affiliation_path, plan["affiliation_payload"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Synchronize exact HIPEAC 2025 dependent titles")
    parser.add_argument("--manifest", type=Path, required=True)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true")
    mode.add_argument("--apply", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--confirm")
    args = parser.parse_args(argv)
    if args.dry_run and (args.force or args.confirm):
        parser.error("--dry-run cannot be combined with --force or --confirm")
    if args.apply and (not args.force or args.confirm != CONFIRMATION):
        parser.error(f"--apply requires --force --confirm {CONFIRMATION}")
    manifest = _load(args.manifest)
    raw_path = ROOT / manifest["target_file"]
    classified_path = ROOT / "data" / "classified" / "authors" / "HIPEAC_2025.json"
    affiliation_path = ROOT / "data" / "raw" / "affiliations" / "HIPEAC_2025.json"
    plan = prepare_sync(manifest, raw_path, classified_path, affiliation_path)
    summary = {key: value for key, value in plan.items() if key not in {"classified_payload", "affiliation_payload"}}
    if args.dry_run:
        print(json.dumps({"mode": "dry_run", **summary, "message": "NO FILES WRITTEN"}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    apply_sync(raw_path, classified_path, affiliation_path, plan, force=args.force, confirmation=args.confirm)
    print(json.dumps({"mode": "applied", **summary}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
