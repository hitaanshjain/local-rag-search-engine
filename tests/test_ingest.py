import tempfile
import unittest
from uuid import uuid4
from pathlib import Path
from unittest.mock import patch

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import FakeEmbeddings

from app.ingest import assign_sections, process_documents, publish_index_version


class IngestTests(unittest.TestCase):
    def test_district_heading_carries_to_provisions_on_following_page(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            data_dir = Path(temporary_dir)
            (data_dir / "rules.pdf").touch()
            db = Chroma(
                collection_name=f"ingest_test_{uuid4().hex}",
                embedding_function=FakeEmbeddings(size=16),
            )
            pages = [
                Document(page_content="August 20, 2024, Rev. Page 1\nUnion City, Georgia\n6-2 R-2 Residential.\nPermitted uses.", metadata={"page": 0}),
                Document(page_content="3. Guest house. Limit: 900 square feet.", metadata={"page": 1}),
                Document(page_content="6-3 R-3 Residential.\nPermitted uses.", metadata={"page": 2}),
                Document(page_content="3. Guest house. Limit: 800 square feet.", metadata={"page": 3}),
                Document(page_content="7-1 Definitions.\nA separate topic.", metadata={"page": 4}),
            ]
            with patch("app.ingest.PyPDFLoader") as loader:
                loader.return_value.load.return_value = pages
                process_documents(data_dir=data_dir, db=db)

            stored = db.get(include=["documents", "metadatas"])
            by_page = {
                metadata["page"]: metadata.get("section")
                for metadata in stored["metadatas"]
            }
            self.assertEqual(by_page[2], "6-2 R-2 Residential.")
            self.assertEqual(by_page[4], "6-3 R-3 Residential.")
            self.assertEqual(by_page[5], "7-1 Definitions.")
            self.assertTrue(all(item.get("jurisdiction") == "Union City, Georgia" for item in stored["metadatas"]))
            self.assertTrue(all(item.get("version") == "August 20, 2024, Rev." for item in stored["metadatas"]))

    def test_ingestion_publishes_new_index_version_after_corpus_change(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            marker = root / "index.version"
            db = Chroma(
                collection_name=f"ingest_test_{uuid4().hex}",
                embedding_function=FakeEmbeddings(size=16),
            )
            process_documents(data_dir=root, db=db, marker_path=marker)
            first_version = marker.read_text(encoding="utf-8")
            self.assertTrue(first_version)

            db.add_documents([Document(page_content="temporary")], ids=["temporary"])
            process_documents(data_dir=root, db=db, marker_path=marker)
            self.assertNotEqual(marker.read_text(encoding="utf-8"), first_version)

    def test_empty_data_directory_clears_the_previous_corpus(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            data_dir = Path(temporary_dir)
            db = Chroma(
                collection_name=f"ingest_test_{uuid4().hex}",
                embedding_function=FakeEmbeddings(size=16),
            )
            db.add_documents(
                [Document(page_content="old", metadata={"source": "removed.pdf", "page": 1})],
                ids=["stale"],
            )

            process_documents(data_dir=data_dir, db=db)

            self.assertEqual(db.get(include=[])["ids"], [])

    def test_reingest_replaces_stale_chunks_and_preserves_page_metadata(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            data_dir = root / "data"
            data_dir.mkdir()
            (data_dir / "sample.pdf").touch()
            db = Chroma(
                collection_name=f"ingest_test_{uuid4().hex}",
                embedding_function=FakeEmbeddings(size=16),
            )
            db.add_documents(
                [Document(page_content="old", metadata={"source": "removed.pdf", "page": 1})],
                ids=["stale"],
            )

            def load_pages():
                return [
                    Document(page_content="First page has a permit rule. " * 60, metadata={"page": 0}),
                    Document(page_content="Second page has a setback rule.", metadata={"page": 1}),
                ]

            with patch("app.ingest.PyPDFLoader") as loader:
                loader.return_value.load.side_effect = load_pages
                process_documents(data_dir=data_dir, db=db)
                first = db.get(include=["documents", "metadatas"])
                process_documents(data_dir=data_dir, db=db)

            stored = db.get(include=["documents", "metadatas"])
            self.assertGreater(len(stored["ids"]), 2)
            self.assertEqual(len(stored["ids"]), len(first["ids"]))
            self.assertEqual(set(stored["ids"]), set(first["ids"]))
            self.assertEqual(stored["documents"], first["documents"])
            self.assertEqual(
                {(item["source"], item["page"]) for item in stored["metadatas"]},
                {("sample.pdf", 1), ("sample.pdf", 2)},
            )
            self.assertNotIn("stale", stored["ids"])

    def test_version_publish_retries_while_marker_is_briefly_locked(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            marker = Path(temporary_dir) / "index.version"
            real_replace = Path.replace
            calls = []

            def flaky_replace(self, target):
                calls.append(target)
                if len(calls) < 3:
                    raise PermissionError("marker is open in another process")
                return real_replace(self, target)

            with patch.object(Path, "replace", flaky_replace), patch("app.ingest.sleep"):
                publish_index_version(marker)

            self.assertEqual(len(calls), 3)
            self.assertTrue(marker.read_text(encoding="utf-8"))
            self.assertEqual(list(Path(temporary_dir).glob("*.tmp")), [])


class SectionLabelTests(unittest.TestCase):
    def label(self, *texts):
        chunks = [Document(page_content=text, metadata={"source": "code.pdf"}) for text in texts]
        assign_sections(chunks)
        return [chunk.metadata.get("section") for chunk in chunks]

    def test_numbered_and_sec_prefixed_headings_become_sections(self):
        self.assertEqual(
            self.label(
                "6-15 TCMU Town Center Mixed Use\nRules.",
                "Source: code.pdf | Page: 2\nSec. 54-269.  Design Review Board created; composition\nText.",
            ),
            ["6-15 TCMU Town Center Mixed Use", "Sec. 54-269. Design Review Board created; composition"],
        )

    def test_cross_references_years_and_contents_lines_are_not_headings(self):
        self.assertEqual(
            self.label(
                "Sec. 54-100.  Purpose\nText.",
                "1995-160 on May 9, 1995; and amended by\n"
                "54-348 in areas of the required buffer\n"
                "2013-2014 South Carolina General Assembly on June 19\n"
                "54-203 Permitted principal uses . . . . . . . 2-12.1",
            ),
            ["Sec. 54-100. Purpose", "Sec. 54-100. Purpose"],
        )

    def test_appendix_heading_ends_the_previous_section(self):
        self.assertEqual(
            self.label("Sec. 54-1060.  Design and construction requirements.\nText.", "APPENDIX C\nRules of procedure."),
            ["Sec. 54-1060. Design and construction requirements.", "APPENDIX C"],
        )

    def test_chunk_takes_the_section_covering_most_of_its_text(self):
        r1_rules = "The R-1 minimum lot area is 10,000 square feet. " * 6
        self.assertEqual(
            self.label(
                "6-2 R-1 Residential\nIntro.",
                f"{r1_rules}\n6-3 R-2 Residential\nShort.",
                "The R-2 minimum lot area is 7,500 square feet.",
            ),
            ["6-2 R-1 Residential", "6-2 R-1 Residential", "6-3 R-2 Residential"],
        )


if __name__ == "__main__":
    unittest.main()
