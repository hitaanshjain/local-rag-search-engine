import tempfile
import unittest
from uuid import uuid4
from pathlib import Path
from unittest.mock import patch

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import FakeEmbeddings

from app.ingest import process_documents


class IngestTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
