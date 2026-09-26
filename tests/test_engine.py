import unittest
import tempfile
from pathlib import Path
from uuid import uuid4

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import FakeEmbeddings

from app.engine import SearchIndex, SearchIndexCache, bm25_search, build_search_index, needs_clarification, select_context, fuse_results, hybrid_search


class RetrievalTests(unittest.TestCase):
    def test_strong_keyword_lead_uses_only_its_matching_top_passage(self):
        first = Document(id="one", page_content="specific rule")
        second = Document(id="two", page_content="unrelated")
        self.assertEqual(select_context([first, second], [(first, 14.0), (second, 10.0)]), [first])
        self.assertEqual(select_context([first, second], [(first, 13.0), (second, 10.0)]), [first, second])
        self.assertEqual(select_context([first, second], [(second, 14.0), (first, 10.0)]), [first, second])

    def test_clarification_requires_competing_source_matches_to_query_terms(self):
        class FixedScores:
            def get_scores(self, words):
                return [10.0, 9.8]

        relevant = SearchIndex(
            documents=[
                Document(page_content="maximum fence height", metadata={"source": "city-a.pdf"}),
                Document(page_content="maximum fence height", metadata={"source": "city-b.pdf"}),
            ],
            bm25=FixedScores(),
        )
        unrelated = SearchIndex(
            documents=[
                Document(page_content="floor area", metadata={"source": "city-a.pdf"}),
                Document(page_content="permit capacity", metadata={"source": "city-b.pdf"}),
            ],
            bm25=FixedScores(),
        )
        self.assertTrue(needs_clarification("What is the maximum fence height?", relevant))
        self.assertFalse(needs_clarification("What is the Tesla battery capacity?", unrelated))

    def test_hybrid_search_reports_vector_keyword_and_fusion_times(self):
        db = Chroma(
            collection_name=f"retrieval_test_{uuid4().hex}",
            embedding_function=FakeEmbeddings(size=16),
        )
        db.add_documents(
            [Document(page_content="A zoning setback applies.", metadata={"source": "rules.pdf", "page": 1})],
            ids=["one"],
        )
        timings = {}
        hybrid_search("setback", db, index=build_search_index(db), timings=timings)
        self.assertEqual(set(timings), {"vector", "keyword", "fusion"})
        self.assertTrue(all(value >= 0 for value in timings.values()))

    def test_cached_keyword_index_refreshes_only_after_ingestion_marker_changes(self):
        class StoredCorpus:
            def __init__(self):
                self.calls = 0
                self.text = "First rule"

            def get(self, include):
                self.calls += 1
                return {
                    "ids": ["one"],
                    "documents": [self.text],
                    "metadatas": [{"source": "rules.pdf", "page": 1}],
                }

        with tempfile.TemporaryDirectory() as temporary_dir:
            marker = Path(temporary_dir) / "index.version"
            corpus = StoredCorpus()
            cache = SearchIndexCache(corpus, marker)
            self.assertIs(cache.get(), cache.get())
            self.assertEqual(corpus.calls, 1)

            corpus.text = "Updated rule"
            marker.write_text("new-version", encoding="utf-8")
            self.assertEqual(cache.get().documents[0].page_content, "Updated rule")
            self.assertEqual(corpus.calls, 2)

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
