import importlib.util
import io
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "audit_hipeac_crossref.py"
SPEC = importlib.util.spec_from_file_location("audit_hipeac_crossref", MODULE_PATH)
trial = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(trial)


class AuditHipeacCrossrefTests(unittest.TestCase):
    def test_evaluate_crossref_record_marks_strict_identity_with_affiliation(self):
        paper = {"title": "Sample Paper", "first_author": "Ada Lovelace"}
        message = {
            "title": ["Sample Paper"],
            "author": [{"given": "Ada", "family": "Lovelace", "affiliation": [{"name": "Analytical Engine Lab"}]}],
            "DOI": "10.1/example",
            "publisher": "ACM",
        }

        verdict = trial.evaluate_crossref_record(paper, "10.1/example", message, approved_repairs={})

        self.assertEqual(verdict["verdict"], "accepted_exact")
        self.assertEqual(verdict["first_author_affiliations"], ["Analytical Engine Lab"])

    def test_evaluate_crossref_record_marks_bookkeeping_match_without_affiliation(self):
        paper = {"title": "Sample Paper", "first_author": "Ada Lovelace"}
        message = {"title": ["Sample Paper"], "author": [{"given": "Ada", "family": "Lovelace"}]}

        self.assertEqual(
            trial.evaluate_crossref_record(paper, "10.1/a", message, approved_repairs={})["verdict"],
            "accepted_no_affiliation",
        )

    def test_evaluate_crossref_record_marks_only_approved_parser_tail(self):
        raw_title = "CoNST: Code Generator for Sparse Tensor Networks, Ponnuswamy Sadayappan"
        paper = {"title": raw_title, "first_author": "Saurabh Raje"}
        message = {
            "title": ["CoNST: Code Generator for Sparse Tensor Networks"],
            "author": [{"given": "Saurabh", "family": "Raje", "affiliation": [{"name": "Example University"}]}],
        }
        approved = {raw_title: "CoNST: Code Generator for Sparse Tensor Networks"}

        self.assertEqual(
            trial.evaluate_crossref_record(paper, "10.1145/3689342", message, approved_repairs=approved)["verdict"],
            "raw_title_has_parser_tail",
        )
        self.assertEqual(
            trial.evaluate_crossref_record(paper, "10.1145/3689342", message, approved_repairs={})["verdict"],
            "raw_title_unexplained_superstring",
        )

    def test_evaluate_crossref_record_rejects_author_mismatch(self):
        paper = {"title": "Sample Paper", "first_author": "Ada Lovelace"}
        message = {"title": ["Sample Paper"], "author": [{"given": "Grace", "family": "Hopper", "affiliation": [{"name": "Navy"}]}]}

        self.assertEqual(
            trial.evaluate_crossref_record(paper, "10.1/b", message, approved_repairs={})["verdict"],
            "crossref_first_author_mismatch",
        )

    def test_dry_run_never_writes_evidence_file(self):
        output = ROOT / "data" / "stats" / "affiliation_source_evidence" / "dry_run_test.json"
        output.unlink(missing_ok=True)
        stdout = io.StringIO()

        with patch.object(trial, "first_author_papers", return_value=[]), redirect_stdout(stdout):
            self.assertEqual(trial.main(["--dry-run"]), 0)

        self.assertFalse(output.exists())
        self.assertIn("do_not_automate", stdout.getvalue())

    def test_cli_rejects_dry_run_with_explicit_evidence_write(self):
        with self.assertRaises(SystemExit):
            trial.main(["--dry-run", "--write-evidence", "out.json"])

    def test_summarize_evidence_does_not_promote_parser_tail_to_write_candidate(self):
        entries = [{"verdict": "accepted_exact"} for _ in range(18)] + [{"verdict": "raw_title_has_parser_tail"} for _ in range(2)]
        summary = trial.summarize_evidence(entries)

        self.assertEqual(summary["accepted"], 18)
        self.assertEqual(summary["decision"], "do_not_automate")


if __name__ == "__main__":
    unittest.main()
