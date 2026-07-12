#!/usr/bin/env python3
"""Preview or atomically apply an exact, manifest-backed raw-title repair."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Any


CONFIRMATION = "HIPEAC-2025-title-repair"
REQUIRED_VERDICT = "raw_title_has_parser_tail"
ROOT = Path(__file__).resolve().parent.parent


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _paper_groups(authors: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    for row in authors:
        title = row.get("title")
        if not isinstance(title, str):
            raise ValueError("every author row must have a string title")
        groups.setdefault(title, []).append(row)
    return groups


def _first_author(rows: list[dict[str, Any]]) -> str:
    first = [row.get("name") for row in rows if row.get("ordinal") == 1]
    if len(first) != 1 or not isinstance(first[0], str):
        raise ValueError("each repaired paper must have exactly one string-named ordinal-1 author")
    return first[0]


def _validate_manifest(manifest: dict[str, Any], target: Path, payload: dict[str, Any]) -> list[dict[str, Any]]:
    if manifest.get("schema_version") != 1:
        raise ValueError("manifest schema_version must be 1")
    if manifest.get("conference") != "HIPEAC" or manifest.get("year") != 2025:
        raise ValueError("manifest scope must be HIPEAC 2025")
    if manifest.get("target_file") not in {str(target), "data/raw/authors/HIPEAC_2025.json"}:
        raise ValueError("manifest target_file does not match target")
    if payload.get("conference") != "HIPEAC" or payload.get("year") != 2025:
        raise ValueError("target payload is not HIPEAC 2025")
    if payload.get("_source") != manifest.get("expected_source"):
        raise ValueError("target _source does not match manifest")
    if payload.get("total_papers") != manifest.get("expected_total_papers"):
        raise ValueError("target total_papers does not match manifest")

    repairs = manifest.get("repairs")
    if not isinstance(repairs, list) or len(repairs) != 2 or manifest.get("expected_repair_count") != 2:
        raise ValueError("manifest must contain exactly two repairs")
    old_titles = [repair.get("expected_bad_title") for repair in repairs if isinstance(repair, dict)]
    new_titles = [repair.get("replacement_title") for repair in repairs if isinstance(repair, dict)]
    if len(old_titles) != 2 or len(new_titles) != 2 or len(set(old_titles)) != 2 or len(set(new_titles)) != 2:
        raise ValueError("repair titles must be two unique exact strings")
    if any(not isinstance(title, str) or not title for title in old_titles + new_titles):
        raise ValueError("repair titles must be non-empty strings")
    if any(repair.get("crossref_verdict") != REQUIRED_VERDICT for repair in repairs):
        raise ValueError(f"each repair crossref_verdict must be {REQUIRED_VERDICT}")
    return repairs


def prepare_repair(manifest: dict[str, Any], target: Path) -> dict[str, Any]:
    """Validate an exact repair and return an in-memory candidate without writing files."""
    before_sha256 = file_sha256(target)
    expected_sha256 = manifest.get("expected_sha256")
    if before_sha256 != expected_sha256:
        raise ValueError("target SHA-256 does not match manifest")
    payload = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("authors"), list):
        raise ValueError("target payload must contain an authors list")
    repairs = _validate_manifest(manifest, target, payload)
    groups = _paper_groups(payload["authors"])
    candidate = deepcopy(payload)
    changed_rows = 0
    changes = []

    for repair in repairs:
        old_title = repair["expected_bad_title"]
        new_title = repair["replacement_title"]
        rows = groups.get(old_title)
        if not rows:
            raise ValueError(f"expected bad title not found: {old_title!r}")
        if new_title in groups and new_title != old_title:
            raise ValueError(f"replacement title already belongs to another paper: {new_title!r}")
        if len(rows) != repair.get("expected_author_rows"):
            raise ValueError("author row count does not match manifest")
        if _first_author(rows) != repair.get("expected_first_author"):
            raise ValueError("first author does not match manifest")
        if sorted(row.get("ordinal") for row in rows) != repair.get("expected_ordinals"):
            raise ValueError("ordinal set does not match manifest")
        if not isinstance(repair.get("crossref_doi"), str) or not isinstance(repair.get("approved_tail"), str):
            raise ValueError("repair must retain exact Crossref DOI and approved tail evidence")
        for row in candidate["authors"]:
            if row["title"] == old_title:
                row["title"] = new_title
                changed_rows += 1
        changes.append({
            "old_title": old_title,
            "new_title": new_title,
            "first_author": repair["expected_first_author"],
            "author_rows": len(rows),
            "ordinals": sorted(row["ordinal"] for row in rows),
            "crossref_doi": repair["crossref_doi"],
        })

    candidate_groups = _paper_groups(candidate["authors"])
    if len(candidate_groups) != len(groups) or len(candidate["authors"]) != len(payload["authors"]):
        raise ValueError("repair changed paper or author-row count")
    for before, after in zip(payload["authors"], candidate["authors"], strict=True):
        if {key: value for key, value in before.items() if key != "title"} != {key: value for key, value in after.items() if key != "title"}:
            raise ValueError("repair changed a non-title author field")

    encoded = json.dumps(candidate, ensure_ascii=False, indent=2) + "\n"
    return {
        "payload": candidate,
        "before_sha256": before_sha256,
        "after_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
        "changed_papers": len(changes),
        "changed_author_rows": changed_rows,
        "changes": changes,
    }


def apply_repair(target: Path, plan: dict[str, Any], *, force: bool, confirmation: str) -> None:
    """Atomically replace target only after explicit confirmation and unchanged-input verification."""
    if not force:
        raise ValueError("--force is required to apply a raw title repair")
    if confirmation != CONFIRMATION:
        raise ValueError(f"--confirm {CONFIRMATION} is required to apply a raw title repair")
    if file_sha256(target) != plan["before_sha256"]:
        raise ValueError("target changed after preview; refusing promotion")
    temporary = target.with_suffix(target.suffix + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as handle:
            json.dump(plan["payload"], handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Preview or atomically apply an exact HIPEAC 2025 raw-title repair")
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

    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    target = ROOT / manifest["target_file"]
    plan = prepare_repair(manifest, target)
    summary = {key: value for key, value in plan.items() if key != "payload"}
    if args.dry_run:
        print(json.dumps({"mode": "dry_run", **summary, "message": "NO FILES WRITTEN"}, ensure_ascii=False, indent=2, sort_keys=True))
        return 0
    apply_repair(target, plan, force=args.force, confirmation=args.confirm)
    print(json.dumps({"mode": "applied", **summary}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
