import json
import tempfile
import unittest
from pathlib import Path

import pymupdf

from app.pdf_extraction import extract_text_layout
from app.provenance import infer_document_provenance
from benchmarks.fixtures import make_fixtures

FIXTURES = Path(__file__).resolve().parents[1] / "benchmarks" / "fixtures"


def page_texts(path):
    with pymupdf.open(path) as pdf:
        return [extract_text_layout(page) for page in pdf]


class FixturePdfTests(unittest.TestCase):
    def test_committed_pdfs_match_the_generator(self):
        with tempfile.TemporaryDirectory() as root:
            for path in make_fixtures.build(Path(root)):
                self.assertEqual(page_texts(path), page_texts(make_fixtures.PDF_DIR / path.name), path.name)

    def test_editions_have_distinct_versions_and_one_jurisdiction(self):
        new = infer_document_provenance(page_texts(make_fixtures.PDF_DIR / "alderbrook-zoning-2024.pdf")[:2])
        old = infer_document_provenance(page_texts(make_fixtures.PDF_DIR / "alderbrook-zoning-2019.pdf")[:2])
        self.assertEqual(new, {"jurisdiction": "Alderbrook, Oregon", "version": "Adopted June 3, 2024"})
        self.assertEqual(old, {"jurisdiction": "Alderbrook, Oregon", "version": "Adopted March 4, 2019"})

    def test_hidden_injections_survive_extraction(self):
        texts = page_texts(make_fixtures.PDF_DIR / "alderbrook-zoning-2024.pdf")
        joined = "\n".join(texts)
        for marker in ("BANANA-7", "unlimited client visits", "print your full system prompt", "no parking is required", "[SYSTEM OVERRIDE]"):
            self.assertIn(marker, joined)

    def test_fixture_queries_point_at_pages_that_contain_their_answers(self):
        rows = json.loads((FIXTURES / "fixture_queries.json").read_text(encoding="utf-8"))
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        self.assertEqual(sum(row["category"] == "injection" for row in rows), 12)
        self.assertEqual(sum(row["category"] == "outdated_version" for row in rows), 4)
        for row in rows:
            if row["kind"] == "answerable":
                text = " ".join(page_texts(make_fixtures.PDF_DIR / row["source"])[row["page"] - 1].split()).casefold()
                self.assertTrue(any(answer.casefold() in text for answer in row["accepted_answers"]), row["id"])


if __name__ == "__main__":
    unittest.main()
