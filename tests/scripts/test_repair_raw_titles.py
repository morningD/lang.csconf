import copy
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "repair_raw_titles.py"
SPEC = importlib.util.spec_from_file_location("repair_raw_titles", MODULE_PATH)
repairer = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(repairer)


OLD_A = "CoNST: Code Generator for Sparse Tensor Networks, Ponnuswamy Sadayappan"
NEW_A = "CoNST: Code Generator for Sparse Tensor Networks"
OLD_B = "_CesASMe and Staticdeps: Static Detection of Memory-carried Dependencies for Code Analyzers, Hugo Pompougnac, INRIA"
NEW_B = "CesASMe and Staticdeps: Static Detection of Memory-carried Dependencies for Code Analyzers"


def payload():
    return {
        "conference": "HIPEAC",
        "year": 2025,
        "total_papers": 2,
        "_source": "hipeac_api+crossref",
        "authors": [
            {"name": "Saurabh Raje", "title": OLD_A, "year": 2025, "ordinal": 1},
            {"name": "P. Sadayappan", "title": OLD_A, "year": 2025, "ordinal": 2},
            {"name": "Théophile Bastian", "title": OLD_B, "year": 2025, "ordinal": 1},
            {"name": "Hugo Pompougnac", "title": OLD_B, "year": 2025, "ordinal": 2},
        ],
    }


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def manifest(path, data):
    return {
        "schema_version": 1,
        "conference": "HIPEAC",
        "year": 2025,
        "target_file": str(path),
        "expected_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "expected_source": "hipeac_api+crossref",
        "expected_total_papers": 2,
        "expected_repair_count": 2,
        "repairs": [
            {
                "expected_bad_title": OLD_A,
                "replacement_title": NEW_A,
                "expected_first_author": "Saurabh Raje",
                "expected_author_rows": 2,
                "expected_ordinals": [1, 2],
                "crossref_doi": "10.1145/3689342",
                "crossref_verdict": "raw_title_has_parser_tail",
                "approved_tail": ", Ponnuswamy Sadayappan",
            },
            {
                "expected_bad_title": OLD_B,
                "replacement_title": NEW_B,
                "expected_first_author": "Théophile Bastian",
                "expected_author_rows": 2,
                "expected_ordinals": [1, 2],
                "crossref_doi": "10.1145/3715125",
                "crossref_verdict": "raw_title_has_parser_tail",
                "approved_tail": ", Hugo Pompougnac, INRIA",
            },
        ],
    }


class RepairRawTitlesTests(unittest.TestCase):
    def test_preview_is_zero_write_and_replaces_all_author_rows_per_paper(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "HIPEAC_2025.json"
            write_json(target, payload())
            source_bytes = target.read_bytes()

            plan = repairer.prepare_repair(manifest(target, payload()), target)

            self.assertEqual(target.read_bytes(), source_bytes)
            self.assertEqual(plan["changed_papers"], 2)
            self.assertEqual(plan["changed_author_rows"], 4)
            repaired = plan["payload"]
            self.assertEqual([row["title"] for row in repaired["authors"]], [NEW_A, NEW_A, NEW_B, NEW_B])
            self.assertEqual([row["name"] for row in repaired["authors"]], [row["name"] for row in payload()["authors"]])
            self.assertNotEqual(plan["before_sha256"], plan["after_sha256"])

    def test_rejects_wrong_input_hash_without_mutating_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "HIPEAC_2025.json"
            write_json(target, payload())
            source_bytes = target.read_bytes()
            invalid = manifest(target, payload())
            invalid["expected_sha256"] = "0" * 64

            with self.assertRaisesRegex(ValueError, "SHA-256"):
                repairer.prepare_repair(invalid, target)

            self.assertEqual(target.read_bytes(), source_bytes)

    def test_rejects_title_collision_without_mutating_file(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "HIPEAC_2025.json"
            collision = payload()
            collision["total_papers"] = 3
            collision["authors"].append({"name": "Other", "title": NEW_A, "year": 2025, "ordinal": 1})
            write_json(target, collision)
            source_bytes = target.read_bytes()
            invalid = manifest(target, collision)
            invalid["expected_total_papers"] = 3

            with self.assertRaisesRegex(ValueError, "already belongs"):
                repairer.prepare_repair(invalid, target)

            self.assertEqual(target.read_bytes(), source_bytes)

    def test_rejects_non_approved_crossref_verdict(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "HIPEAC_2025.json"
            write_json(target, payload())
            invalid = manifest(target, payload())
            invalid["repairs"][0]["crossref_verdict"] = "accepted_exact"

            with self.assertRaisesRegex(ValueError, "crossref_verdict"):
                repairer.prepare_repair(invalid, target)

    def test_apply_requires_confirmation_and_preserves_atomic_preconditions(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "HIPEAC_2025.json"
            write_json(target, payload())
            source_bytes = target.read_bytes()
            plan = repairer.prepare_repair(manifest(target, payload()), target)

            with self.assertRaisesRegex(ValueError, "--force"):
                repairer.apply_repair(target, plan, force=False, confirmation="HIPEAC-2025-title-repair")
            self.assertEqual(target.read_bytes(), source_bytes)

            target.write_text("changed concurrently", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "changed after preview"):
                repairer.apply_repair(target, plan, force=True, confirmation="HIPEAC-2025-title-repair")


if __name__ == "__main__":
    unittest.main()
