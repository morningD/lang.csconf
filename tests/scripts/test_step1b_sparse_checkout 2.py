import importlib.util
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import call, patch


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "pipeline" / "step1b_parse_accept_rates.py"
SPEC = importlib.util.spec_from_file_location("step1b_parse_accept_rates", MODULE_PATH)
step1b = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(step1b)


class SparseCheckoutTests(unittest.TestCase):
    def test_sparse_clone_configures_only_requested_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            with patch.object(step1b.subprocess, "run") as run:
                step1b._clone_or_pull("https://example.test/source.git", destination, sparse_paths=("/data.csv",))

        self.assertEqual(
            run.call_args_list,
            [
                call(
                    ["git", "clone", "--depth", "1", "--no-checkout", "https://example.test/source.git", str(destination)],
                    check=True, capture_output=True,
                ),
                call(
                    ["git", "sparse-checkout", "init", "--no-cone"],
                    cwd=destination, check=True, capture_output=True,
                ),
                call(
                    ["git", "sparse-checkout", "set", "--no-cone", "/data.csv"],
                    cwd=destination, check=True, capture_output=True,
                ),
                call(
                    ["git", "checkout"],
                    cwd=destination, check=True, capture_output=True,
                ),
            ],
        )

    def test_existing_sparse_cache_is_configured_before_pull(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            destination.mkdir()
            with patch.object(step1b.subprocess, "run") as run:
                step1b._clone_or_pull("https://example.test/source.git", destination, sparse_paths=("/data.csv",))

        self.assertEqual(
            run.call_args_list,
            [
                call(
                    ["git", "sparse-checkout", "init", "--no-cone"],
                    cwd=destination, check=True, capture_output=True,
                ),
                call(
                    ["git", "sparse-checkout", "set", "--no-cone", "/data.csv"],
                    cwd=destination, check=True, capture_output=True,
                ),
                call(
                    ["git", "pull", "--ff-only"],
                    cwd=destination, check=False, capture_output=True,
                ),
            ],
        )

    def test_full_clone_retains_existing_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / "source"
            with patch.object(step1b.subprocess, "run") as run:
                step1b._clone_or_pull("https://example.test/source.git", destination)

        run.assert_called_once_with(
            ["git", "clone", "--depth", "1", "https://example.test/source.git", str(destination)],
            check=True, capture_output=True,
        )

    def test_real_sparse_checkout_excludes_claude_md_after_update(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            origin = root / "origin"
            cache = root / "cache"
            origin.mkdir()
            subprocess.run(["git", "init", "-q"], cwd=origin, check=True)
            subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=origin, check=True)
            subprocess.run(["git", "config", "user.name", "Test User"], cwd=origin, check=True)
            (origin / "csconferences.csv").write_text("Conference,Year\nTEST,2026\n", encoding="utf-8")
            (origin / "CLAUDE.md").write_text("external instructions\n", encoding="utf-8")
            subprocess.run(["git", "add", "."], cwd=origin, check=True)
            subprocess.run(["git", "commit", "-qm", "initial"], cwd=origin, check=True)

            step1b._clone_or_pull(str(origin), cache, sparse_paths=("/csconferences.csv",))
            self.assertTrue((cache / "csconferences.csv").exists())
            self.assertFalse((cache / "CLAUDE.md").exists())

            (origin / "csconferences.csv").write_text("Conference,Year\nTEST,2027\n", encoding="utf-8")
            subprocess.run(["git", "add", "csconferences.csv"], cwd=origin, check=True)
            subprocess.run(["git", "commit", "-qm", "update"], cwd=origin, check=True)
            step1b._clone_or_pull(str(origin), cache, sparse_paths=("/csconferences.csv",))

            self.assertEqual((cache / "csconferences.csv").read_text(encoding="utf-8"), "Conference,Year\nTEST,2027\n")
            self.assertFalse((cache / "CLAUDE.md").exists())
            status = subprocess.run(
                ["git", "status", "--short"], cwd=cache, check=True, capture_output=True, text=True,
            )
            self.assertEqual(status.stdout, "")


if __name__ == "__main__":
    unittest.main()
