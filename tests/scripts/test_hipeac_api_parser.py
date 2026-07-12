import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "scripts" / "hipeac_api_parser.py"
SPEC = importlib.util.spec_from_file_location("hipeac_api_parser", MODULE_PATH)
parser = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(parser)


class HipeacApiParserTests(unittest.TestCase):
    def test_uses_explicit_structured_title_without_interpreting_author_tail(self):
        activity = {
            "title": "CoNST: Code Generator for Sparse Tensor Networks",
            "authors": ["Saurabh Raje", "P. Sadayappan"],
            "description": "CoNST: Code Generator for Sparse Tensor Networks, Ponnuswamy Sadayappan",
        }

        parsed = parser.parse_activity(activity)

        self.assertEqual(parsed["status"], "resolved")
        self.assertEqual(parsed["title"], "CoNST: Code Generator for Sparse Tensor Networks")
        self.assertEqual(parsed["authors"], ["Saurabh Raje", "P. Sadayappan"])
        self.assertEqual(parsed["display_tail"], "CoNST: Code Generator for Sparse Tensor Networks, Ponnuswamy Sadayappan")

    def test_rejects_description_only_input_instead_of_guessing_title_boundary(self):
        activity = {
            "description": "_CesASMe and Staticdeps: Static Detection of Memory-carried Dependencies for Code Analyzers, Hugo Pompougnac, INRIA"
        }

        parsed = parser.parse_activity(activity)

        self.assertEqual(parsed, {"status": "unresolved", "reason": "missing_explicit_title", "title": None, "authors": [], "display_tail": None})

    def test_preserves_commas_colons_and_newlines_in_explicit_title(self):
        title = "A title, with a colon: and a newline\nthat must remain intact"
        parsed = parser.parse_activity({"title": title, "authors": ["Ada Lovelace"]})

        self.assertEqual(parsed["status"], "resolved")
        self.assertEqual(parsed["title"], title)


if __name__ == "__main__":
    unittest.main()
