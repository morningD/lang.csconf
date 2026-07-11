import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "audit_affiliation_coverage.py"
SPEC = importlib.util.spec_from_file_location("audit_affiliation_coverage", MODULE_PATH)
audit = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(audit)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


class AuditAffiliationCoverageTests(unittest.TestCase):
    def test_openalex_record_separates_matching_and_metadata_gaps(self):
        payload = {
            "source": "openalex",
            "total_papers": 3,
            "total_matched": 2,
            "total_with_affiliation": 1,
            "papers": [
                {"matched": True, "institution": "Example University"},
                {"matched": True, "institution": None},
                {"matched": False, "institution": None},
            ],
        }

        result = audit.analyze_affiliation_file("CONF", 2024, 3, payload)

        self.assertEqual(result["matched"], 2)
        self.assertEqual(result["with_institution"], 1)
        self.assertEqual(result["coverage_pct"], 33.3)
        self.assertEqual(result["coverage_band"], "10_to_50")
        self.assertEqual(result["diagnosis"], "openalex_metadata_gap")
        self.assertEqual(result["integrity_issues"], [])

    def test_audit_uses_raw_author_files_as_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authors_dir = root / "authors"
            affiliations_dir = root / "affiliations"
            conferences = [
                {"id": "BCONF", "rank": "B"},
                {"id": "ACONF", "rank": "A"},
            ]
            write_json(authors_dir / "BCONF_2024.json", {
                "authors": [
                    {"title": "One", "ordinal": 1},
                    {"title": "One", "ordinal": 2},
                    {"title": "Two", "ordinal": 1},
                ],
            })
            write_json(authors_dir / "BCONF_2025.json", {
                "authors": [{"title": "Three", "ordinal": 1}],
            })
            write_json(authors_dir / "ACONF_2024.json", {
                "authors": [{"title": "Ignored", "ordinal": 1}],
            })
            write_json(affiliations_dir / "BCONF_2024.json", {
                "source": "papercopilot",
                "total_papers": 2,
                "total_matched": 2,
                "total_with_affiliation": 1,
                "papers": [
                    {"matched": True, "institution": "Example University"},
                    {"matched": True, "institution": None},
                ],
            })

            report = audit.audit_affiliation_data(
                conferences, authors_dir, affiliations_dir
            )

        self.assertEqual(report["summary"]["eligible_conference_years"], 2)
        self.assertEqual(report["summary"]["affiliation_files_found"], 1)
        self.assertEqual(report["summary"]["missing_affiliation_files"], 1)
        self.assertEqual(report["records"][0]["diagnosis"], "non_openalex")
        self.assertEqual(report["priority"]["zero"], [{"conference": "BCONF", "year": 2025}])
        self.assertEqual(report["integrity_issues"], [
            {"conference": "BCONF", "year": 2025, "issue": "missing_affiliation_file"},
        ])

    def test_main_writes_stable_sorted_json_report(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            conferences_path = root / "conferences.json"
            authors_dir = root / "authors"
            affiliations_dir = root / "affiliations"
            output_path = root / "stats" / "audit.json"
            write_json(conferences_path, [{"id": "BCONF", "rank": "B"}])
            write_json(authors_dir / "BCONF_2024.json", {
                "authors": [{"title": "One", "ordinal": 1}],
            })
            write_json(affiliations_dir / "BCONF_2024.json", {
                "source": "openalex",
                "total_papers": 1,
                "total_matched": 1,
                "total_with_affiliation": 1,
                "papers": [{"matched": True, "institution": "Example University"}],
            })
            argv = [
                "--conferences", str(conferences_path),
                "--authors-dir", str(authors_dir),
                "--affiliations-dir", str(affiliations_dir),
                "--output", str(output_path),
            ]

            self.assertEqual(audit.main(argv), 0)
            first = output_path.read_bytes()
            self.assertEqual(audit.main(argv), 0)
            self.assertEqual(output_path.read_bytes(), first)
            report = json.loads(first)

        self.assertEqual(report["records"][0]["diagnosis"], "openalex_complete")
        self.assertTrue(first.endswith(b"\n"))

    def test_audit_excludes_conference_metadata_from_raw_denominator(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authors_dir = root / "authors"
            affiliations_dir = root / "affiliations"
            conferences = [{
                "id": "UAI",
                "rank": "B",
                "title": "UAI",
                "description": "Conference on Uncertainty in Artificial Intelligence",
            }]
            write_json(authors_dir / "UAI_2024.json", {
                "authors": [
                    {"title": "A Paper", "ordinal": 1},
                    {
                        "title": (
                            "Conference on Uncertainty in Artificial Intelligence, "
                            "15-19 July 2024, Barcelona, Spain."
                        ),
                        "ordinal": 1,
                    },
                ],
            })
            write_json(affiliations_dir / "UAI_2024.json", {
                "source": "openreview",
                "total_papers": 1,
                "total_matched": 1,
                "total_with_affiliation": 1,
                "papers": [{"matched": True, "institution": "Example University"}],
            })

            report = audit.audit_affiliation_data(
                conferences, authors_dir, affiliations_dir
            )

        record = report["records"][0]
        self.assertEqual(record["total"], 1)
        self.assertEqual(record["excluded_conference_metadata"], 1)
        self.assertEqual(record["integrity_issues"], [])
        self.assertEqual(report["summary"]["excluded_conference_metadata"], 1)

    def test_audit_keeps_metadata_when_affiliation_file_contains_it(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authors_dir = root / "authors"
            affiliations_dir = root / "affiliations"
            conferences = [{
                "id": "UAI",
                "rank": "B",
                "description": "Conference on Uncertainty in Artificial Intelligence",
            }]
            write_json(authors_dir / "UAI_2023.json", {
                "authors": [
                    {"title": "A Paper", "ordinal": 1},
                    {
                        "title": (
                            "Uncertainty in Artificial Intelligence, UAI 2023, "
                            "July 31 - 4 August 2023, Pittsburgh, PA, USA."
                        ),
                        "ordinal": 1,
                    },
                ],
            })
            write_json(affiliations_dir / "UAI_2023.json", {
                "source": "papercopilot",
                "total_papers": 2,
                "total_matched": 2,
                "total_with_affiliation": 1,
                "papers": [
                    {
                        "matched": True,
                        "institution": "Example University",
                        "title": "A Paper",
                    },
                    {
                        "matched": True,
                        "institution": None,
                        "title": (
                            "Uncertainty in Artificial Intelligence, UAI 2023, "
                            "July 31 - 4 August 2023, Pittsburgh, PA, USA."
                        ),
                    },
                ],
            })

            report = audit.audit_affiliation_data(
                conferences, authors_dir, affiliations_dir
            )

        record = report["records"][0]
        self.assertEqual(record["total"], 2)
        self.assertEqual(record["excluded_conference_metadata"], 0)
        self.assertEqual(record["integrity_issues"], [])
        self.assertEqual(report["summary"]["excluded_conference_metadata"], 0)

    def test_audit_exposes_only_safe_openalex_match_gap_candidates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            authors_dir = root / "authors"
            affiliations_dir = root / "affiliations"
            conferences = [
                {"id": "MATCH", "rank": "B"},
                {"id": "META", "rank": "B"},
                {"id": "OTHER", "rank": "B"},
            ]
            for conf_id in ("MATCH", "META", "OTHER"):
                write_json(authors_dir / f"{conf_id}_2024.json", {
                    "authors": [
                        {"title": "One", "ordinal": 1},
                        {"title": "Two", "ordinal": 1},
                        {"title": "Three", "ordinal": 1},
                    ],
                })
            write_json(affiliations_dir / "MATCH_2024.json", {
                "source": "openalex", "total_papers": 3,
                "total_matched": 1, "total_with_affiliation": 1,
                "papers": [
                    {"title": "One", "matched": True, "institution": "University"},
                    {"title": "Two", "matched": False, "institution": None},
                    {"title": "Three", "matched": False, "institution": None},
                ],
            })
            write_json(affiliations_dir / "META_2024.json", {
                "source": "openalex", "total_papers": 3,
                "total_matched": 2, "total_with_affiliation": 1,
                "papers": [
                    {"title": "One", "matched": True, "institution": "University"},
                    {"title": "Two", "matched": True, "institution": None},
                    {"title": "Three", "matched": False, "institution": None},
                ],
            })
            write_json(affiliations_dir / "OTHER_2024.json", {
                "source": "papercopilot", "total_papers": 2,
                "papers": [
                    {"title": "One", "matched": False, "institution": None},
                    {"title": "Two", "matched": False, "institution": None},
                ],
            })

            report = audit.audit_affiliation_data(
                conferences, authors_dir, affiliations_dir
            )

        self.assertEqual(report["openalex_match_gap_candidates"], [{
            "conference": "MATCH", "year": 2024, "total": 3, "matched": 1,
            "with_institution": 1, "unmatched": 2, "coverage_pct": 33.3,
            "coverage_band": "10_to_50", "priority_rank": 1,
        }])
        self.assertEqual(report["openalex_retry_skips"], [
            {"conference": "META", "year": 2024, "reason": "openalex_metadata_gap"},
            {"conference": "OTHER", "year": 2024, "reason": "non_openalex_source:papercopilot"},
        ])
