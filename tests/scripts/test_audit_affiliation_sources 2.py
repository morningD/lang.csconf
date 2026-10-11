import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "audit_affiliation_sources.py"
SPEC = importlib.util.spec_from_file_location("audit_affiliation_sources", MODULE_PATH)
sources = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(sources)


class AuditAffiliationSourcesTests(unittest.TestCase):
    def test_matrix_prioritizes_representatives_and_journal_models(self):
        audit = {
            "records": [
                {"conference": "GROUP", "year": 2023, "source": "openalex", "total": 27,
                 "matched": 0, "with_institution": 0, "diagnosis": "openalex_match_gap"},
                {"conference": "ICASSP", "year": 2016, "source": "openalex", "total": 1322,
                 "matched": 0, "with_institution": 0, "diagnosis": "openalex_match_gap"},
                {"conference": "HIPEAC", "year": 2024, "source": "openalex", "total": 20,
                 "matched": 1, "with_institution": 1, "diagnosis": "openalex_match_gap"},
                {"conference": "CODES+ISSS", "year": 2023, "source": "openalex", "total": 30,
                 "matched": 1, "with_institution": 1, "diagnosis": "openalex_match_gap"},
                {"conference": "META", "year": 2024, "source": "openalex", "total": 20,
                 "matched": 10, "with_institution": 1, "diagnosis": "openalex_metadata_gap"},
            ]
        }
        notes = {
            "HIPEAC_2024": {"paper_source": "journal_scrape", "note": "ACM TACO journal"},
            "CODES+ISSS_2023": {"paper_source": "journal_scrape", "note": "provenance fixture"},
        }

        matrix = sources.build_feasibility_matrix(audit, notes)

        entries = {(item["conference"], item["year"]): item for item in matrix["entries"]}
        self.assertEqual(entries[("GROUP", 2023)]["recommendation"], "publisher_or_event_feasibility")
        self.assertEqual(entries[("GROUP", 2023)]["priority_group"], "representative_small")
        self.assertEqual(entries[("ICASSP", 2016)]["recommendation"], "ieee_source_or_doi_feasibility")
        self.assertEqual(entries[("ICASSP", 2016)]["priority_group"], "high_impact_family")
        self.assertEqual(entries[("HIPEAC", 2024)]["recommendation"], "source_specific_needed")
        self.assertEqual(entries[("CODES+ISSS", 2023)]["recommendation"], "source_specific_needed")
        self.assertEqual(entries[("META", 2024)]["recommendation"], "excluded_metadata_gap")

    def test_matrix_excludes_complete_openalex_records(self):
        audit = {
            "records": [
                {"conference": "COMPLETE", "year": 2024, "source": "openalex", "total": 10,
                 "matched": 10, "with_institution": 10, "diagnosis": "openalex_complete"},
                {"conference": "JOURNAL", "year": 2024, "source": "openalex", "total": 10,
                 "matched": 10, "with_institution": 10, "diagnosis": "openalex_complete"},
            ]
        }
        notes = {"JOURNAL_2024": {"paper_source": "journal_scrape"}}

        matrix = sources.build_feasibility_matrix(audit, notes)
        entries = {(item["conference"], item["year"]): item for item in matrix["entries"]}

        self.assertEqual(entries[("COMPLETE", 2024)]["recommendation"], "already_openalex_complete")
        self.assertEqual(entries[("JOURNAL", 2024)]["recommendation"], "already_openalex_complete")
        self.assertEqual(entries[("JOURNAL", 2024)]["priority_group"], "excluded")

    def test_matrix_includes_confirmed_missing_affiliation_files(self):
        audit = {
            "records": [
                {"conference": "ZERO", "year": 2024, "source": "openalex", "total": 12,
                 "matched": 0, "with_institution": 0, "diagnosis": "openalex_match_gap"},
            ],
            "priority": {
                "zero": [
                    {"conference": "MISSING", "year": 2024},
                    {"conference": "ZERO", "year": 2024},
                ],
            },
            "integrity_issues": [
                {"conference": "MISSING", "year": 2024, "issue": "missing_affiliation_file"},
            ],
        }
        notes = {"MISSING_2024": {"paper_source": "journal_scrape"}}

        matrix = sources.build_feasibility_matrix(audit, notes)
        entries = {(item["conference"], item["year"]): item for item in matrix["entries"]}

        self.assertEqual(entries[("MISSING", 2024)]["current_source"], "missing")
        self.assertEqual(entries[("MISSING", 2024)]["diagnosis"], "missing_affiliation_file")
        self.assertEqual(entries[("MISSING", 2024)]["priority_group"], "missing")
        self.assertEqual(entries[("MISSING", 2024)]["recommendation"], "create_affiliation_file")
        self.assertEqual(entries[("MISSING", 2024)]["paper_source"], "journal_scrape")
        self.assertEqual(len([item for item in matrix["entries"] if item["conference"] == "ZERO"]), 1)

    def test_main_writes_stable_local_matrix(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            audit_path = root / "audit.json"
            notes_path = root / "notes.json"
            output_path = root / "matrix.json"
            audit_path.write_text(json.dumps({"records": []}), encoding="utf-8")
            notes_path.write_text(json.dumps({}), encoding="utf-8")
            argv = ["--audit-report", str(audit_path), "--notes", str(notes_path), "--output", str(output_path)]

            self.assertEqual(sources.main(argv), 0)
            first = output_path.read_bytes()
            self.assertEqual(sources.main(argv), 0)
            self.assertEqual(output_path.read_bytes(), first)

        self.assertTrue(first.endswith(b"\n"))
