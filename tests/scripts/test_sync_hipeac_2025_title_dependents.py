import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "sync_hipeac_2025_title_dependents.py"
SPEC = importlib.util.spec_from_file_location("sync_hipeac_2025_title_dependents", MODULE_PATH)
syncer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(syncer)


OLD_A = "CoNST: Code Generator for Sparse Tensor Networks, Ponnuswamy Sadayappan"
NEW_A = "CoNST: Code Generator for Sparse Tensor Networks"
OLD_B = "_CesASMe and Staticdeps: Static Detection of Memory-carried Dependencies for Code Analyzers, Hugo Pompougnac, INRIA"
NEW_B = "CesASMe and Staticdeps: static detection of memory-carried dependencies for code analyzers"


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def raw_payload():
    return {
        "conference": "HIPEAC", "year": 2025, "total_papers": 2, "_source": "hipeac_api+crossref",
        "authors": [
            {"name": "Saurabh Raje", "title": NEW_A, "year": 2025, "ordinal": 1},
            {"name": "P. Sadayappan", "title": NEW_A, "year": 2025, "ordinal": 2},
            {"name": "Théophile Bastian", "title": NEW_B, "year": 2025, "ordinal": 1},
            {"name": "Hugo Pompougnac", "title": NEW_B, "year": 2025, "ordinal": 2},
        ],
    }


def classified_payload():
    payload = raw_payload()
    payload["authors"] = [
        {**row, "title": OLD_A if row["title"] == NEW_A else OLD_B, "nationality": "English", "language": "English", "confidence": 0.9}
        for row in payload["authors"]
    ]
    return payload


def affiliation_payload():
    return {
        "conference": "HIPEAC", "year": 2025, "total_papers": 2, "total_matched": 1,
        "total_with_affiliation": 1, "coverage_pct": 50.0, "source": "openalex",
        "papers": [
            {"title": OLD_A, "first_author": "Saurabh Raje", "matched": False, "institution": None},
            {"title": OLD_B, "first_author": "Théophile Bastian", "matched": True, "institution": "Example University", "openalex_id": "W1"},
        ],
    }


def manifest(raw_path):
    return {
        "schema_version": 1, "conference": "HIPEAC", "year": 2025,
        "target_file": str(raw_path), "expected_source": "hipeac_api+crossref",
        "expected_total_papers": 2, "expected_repair_count": 2,
        "repairs": [
            {"expected_bad_title": OLD_A, "replacement_title": NEW_A, "expected_first_author": "Saurabh Raje", "expected_author_rows": 2, "expected_ordinals": [1, 2]},
            {"expected_bad_title": OLD_B, "replacement_title": NEW_B, "expected_first_author": "Théophile Bastian", "expected_author_rows": 2, "expected_ordinals": [1, 2]},
        ],
    }


class SyncHipeacDependentsTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        root = Path(self.directory.name)
        self.raw_path = root / "raw.json"
        self.classified_path = root / "classified.json"
        self.affiliation_path = root / "affiliation.json"
        write_json(self.raw_path, raw_payload())
        write_json(self.classified_path, classified_payload())
        write_json(self.affiliation_path, affiliation_payload())
        self.manifest = manifest(self.raw_path)

    def tearDown(self):
        self.directory.cleanup()

    def test_prepare_sync_is_zero_write_and_only_changes_titles(self):
        before = {path: path.read_bytes() for path in (self.raw_path, self.classified_path, self.affiliation_path)}

        plan = syncer.prepare_sync(self.manifest, self.raw_path, self.classified_path, self.affiliation_path)

        self.assertEqual({path: path.read_bytes() for path in before}, before)
        self.assertEqual(plan["changed_classified_rows"], 4)
        self.assertEqual(plan["changed_affiliation_records"], 2)
        self.assertEqual([row["title"] for row in plan["classified_payload"]["authors"]], [NEW_A, NEW_A, NEW_B, NEW_B])
        self.assertEqual([paper["title"] for paper in plan["affiliation_payload"]["papers"]], [NEW_A, NEW_B])
        self.assertEqual(plan["affiliation_payload"]["papers"][1]["openalex_id"], "W1")
        self.assertEqual(plan["affiliation_payload"]["total_matched"], 1)

    def test_prepare_sync_rejects_first_author_mismatch_without_writing(self):
        payload = affiliation_payload()
        payload["papers"][0]["first_author"] = "Wrong Author"
        write_json(self.affiliation_path, payload)
        before = self.affiliation_path.read_bytes()

        with self.assertRaisesRegex(ValueError, "first author"):
            syncer.prepare_sync(self.manifest, self.raw_path, self.classified_path, self.affiliation_path)

        self.assertEqual(self.affiliation_path.read_bytes(), before)

    def test_apply_requires_force_confirmation_and_unchanged_inputs(self):
        plan = syncer.prepare_sync(self.manifest, self.raw_path, self.classified_path, self.affiliation_path)
        before = self.classified_path.read_bytes()

        with self.assertRaisesRegex(ValueError, "--force"):
            syncer.apply_sync(self.raw_path, self.classified_path, self.affiliation_path, plan, force=False, confirmation=syncer.CONFIRMATION)
        self.assertEqual(self.classified_path.read_bytes(), before)

        self.classified_path.write_text("changed", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "changed after preview"):
            syncer.apply_sync(self.raw_path, self.classified_path, self.affiliation_path, plan, force=True, confirmation=syncer.CONFIRMATION)


if __name__ == "__main__":
    unittest.main()
