import unittest
from uuid import uuid4

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import FakeEmbeddings

from app.engine import bm25_search, build_search_index, fuse_results


class RetrievalTests(unittest.TestCase):
    def test_bm25_ranks_whole_word_match_and_ignores_substrings(self):
        db = Chroma(
            collection_name=f"retrieval_test_{uuid4().hex}",
            embedding_function=FakeEmbeddings(size=16),
        )
        db.add_documents(
            [
                Document(page_content="Parking spaces are required.", metadata={"source": "a.pdf", "page": 1}),
                Document(page_content="A setback permit is required.", metadata={"source": "b.pdf", "page": 2}),
                Document(page_content="Fences have height limits.", metadata={"source": "c.pdf", "page": 3}),
            ],
            ids=["a", "b", "c"],
        )
        index = build_search_index(db)

        self.assertEqual(bm25_search("setback", index, k=3)[0][0].id, "b")
        self.assertEqual(bm25_search("park", index, k=3), [])

    def test_fusion_keeps_keyword_only_document_and_respects_weights(self):
        vector_doc = Document(id="vector", page_content="vector text", metadata={"source": "a.pdf", "page": 1})
        keyword_doc = Document(id="keyword", page_content="keyword text", metadata={"source": "b.pdf", "page": 2})
        vector = [(vector_doc, 0.1)]
        keyword = [(keyword_doc, 2.0)]

        vector_favored = fuse_results(vector, keyword, k=2, vector_weight=0.8, keyword_weight=0.2)
        keyword_favored = fuse_results(vector, keyword, k=2, vector_weight=0.2, keyword_weight=0.8)

        self.assertEqual([doc.id for doc in vector_favored], ["vector", "keyword"])
        self.assertEqual([doc.id for doc in keyword_favored], ["keyword", "vector"])


if __name__ == "__main__":
    unittest.main()
