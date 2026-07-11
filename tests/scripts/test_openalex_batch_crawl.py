import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "openalex_batch_crawl.py"
SPEC = importlib.util.spec_from_file_location("openalex_batch_crawl", MODULE_PATH)
crawler = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(crawler)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class OpenAlexBatchCrawlTests(unittest.TestCase):
    def test_audit_plan_accepts_only_current_openalex_match_gap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authors_dir = root / "authors"
            affiliations_dir = root / "affiliations"
            audit_path = root / "audit.json"
            write_json(authors_dir / "SAFE_2024.json", {"authors": [
                {"title": "One", "name": "Alice", "ordinal": 1},
                {"title": "Two", "name": "Bob", "ordinal": 1},
            ]})
            write_json(affiliations_dir / "SAFE_2024.json", {
                "source": "openalex", "total_papers": 2,
                "total_matched": 1, "total_with_affiliation": 1,
                "papers": [
                    {"title": "One", "first_author": "Alice", "matched": True, "institution": "U"},
                    {"title": "Two", "first_author": "Bob", "matched": False, "institution": None},
                ],
            })
            write_json(authors_dir / "OTHER_2024.json", {"authors": [
                {"title": "Other", "name": "Carol", "ordinal": 1},
            ]})
            write_json(affiliations_dir / "OTHER_2024.json", {
                "source": "papercopilot", "papers": [],
            })
            write_json(audit_path, {"openalex_match_gap_candidates": [
                {"conference": "SAFE", "year": 2024, "total": 2, "matched": 1,
                 "with_institution": 1, "unmatched": 1, "coverage_pct": 50.0,
                 "coverage_band": "50_or_more", "priority_rank": 1},
                {"conference": "OTHER", "year": 2024, "total": 1, "matched": 0,
                 "with_institution": 0, "unmatched": 1, "priority_rank": 2},
            ]})

            plan = crawler.build_audit_retry_plan(audit_path, authors_dir, affiliations_dir)

        self.assertEqual(plan["accepted"], [{
            "conference": "SAFE", "year": 2024, "total": 2, "matched": 1,
            "with_institution": 1, "unmatched": 1, "coverage_pct": 50.0,
            "coverage_band": "50_or_more", "priority_rank": 1,
        }])
        self.assertEqual(plan["rejected"], [{
            "conference": "OTHER", "year": 2024,
            "reason": "source_guard:papercopilot",
        }])

    def test_retry_merge_preserves_old_matches_and_requires_improvement(self):
        old = {
            "conference": "SAFE", "year": 2024, "source": "openalex",
            "papers": [
                {"title": "One", "first_author": "Alice", "matched": True, "institution": "U"},
                {"title": "Two", "first_author": "Bob", "matched": False, "institution": None},
            ],
        }
        raw = [
            {"title": "One", "first_author": "Alice"},
            {"title": "Two", "first_author": "Bob"},
        ]
        result = crawler.merge_retry_results(old, raw, {
            "Two": {"title": "Two", "first_author": "Bob", "matched": True, "institution": "V"},
        })

        self.assertTrue(result["improved"])
        self.assertEqual(result["payload"]["total_matched"], 2)
        self.assertEqual(result["payload"]["total_with_affiliation"], 2)
        self.assertEqual(result["payload"]["papers"][0], old["papers"][0])

    def test_strict_title_match_rejects_normalized_mismatch(self):
        self.assertTrue(crawler._is_strict_title_match("A Study", {"title": "A Study"}))
        self.assertFalse(crawler._is_strict_title_match("A Study", {"title": "A Different Study"}))

    def test_build_title_filter_uses_exact_for_wildcards_and_quotes_commas(self):
        self.assertEqual(
            crawler._title_filter("Does It Work?"),
            'title.search.exact:"Does It Work?"',
        )
        self.assertEqual(
            crawler._title_filter("Small-Step, Operational Approach"),
            'title.search:"Small-Step, Operational Approach"',
        )
        self.assertEqual(crawler._title_filter("Plain Title"), "title.search:Plain Title")

    def test_promote_retry_requires_unchanged_source_file_and_improvement(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "SAFE_2024.json"
            old = {
                "conference": "SAFE", "year": 2024, "source": "openalex",
                "papers": [
                    {"title": "One", "first_author": "Alice", "matched": True, "institution": "U"},
                    {"title": "Two", "first_author": "Bob", "matched": False, "institution": None},
                ],
            }
            write_json(path, old)
            original_hash = crawler._file_sha256(path)
            result = crawler.merge_retry_results(old, [
                {"title": "One", "first_author": "Alice"},
                {"title": "Two", "first_author": "Bob"},
            ], {"Two": {"title": "Two", "first_author": "Bob", "matched": True, "institution": "V"}})

            self.assertTrue(crawler.promote_retry_result(path, original_hash, result))
            self.assertEqual(json.loads(path.read_text())["total_with_affiliation"], 2)
            self.assertFalse(crawler.promote_retry_result(path, original_hash, result))

    def test_retry_execution_never_promotes_without_improvement(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authors = root / "authors"
            affiliations = root / "affiliations"
            write_json(authors / "SAFE_2024.json", {"authors": [
                {"title": "One", "name": "Alice", "ordinal": 1},
                {"title": "Two", "name": "Bob", "ordinal": 1},
            ]})
            path = affiliations / "SAFE_2024.json"
            old = {
                "conference": "SAFE", "year": 2024, "source": "openalex",
                "total_papers": 2, "total_matched": 1, "total_with_affiliation": 1,
                "papers": [
                    {"title": "One", "first_author": "Alice", "matched": True, "institution": "U"},
                    {"title": "Two", "first_author": "Bob", "matched": False, "institution": None},
                ],
            }
            write_json(path, old)
            original = path.read_bytes()
            previous_authors, previous_affiliations = crawler.AUTHORS_DIR, crawler.AFFIL_DIR
            crawler.AUTHORS_DIR, crawler.AFFIL_DIR = authors, affiliations
            try:
                result = crawler._retry_unmatched_only("SAFE", "SAFE", 2024, [], 0)
            finally:
                crawler.AUTHORS_DIR, crawler.AFFIL_DIR = previous_authors, previous_affiliations

        self.assertEqual(result, {"status": "rejected", "reason": "no_live_keys"})
        self.assertEqual(path.read_bytes() if path.exists() else original, original)
