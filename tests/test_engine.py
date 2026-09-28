import unittest
import tempfile
from pathlib import Path
from uuid import uuid4
from unittest.mock import patch

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_core.embeddings import FakeEmbeddings

from app.engine import (
    SearchIndex, SearchIndexCache, bm25_search, build_search_index, fuse_results,
    get_vector_db, hybrid_search, needs_clarification, select_context,
)


class OfflineConfigurationTests(unittest.TestCase):
    def test_production_chroma_client_disables_telemetry(self):
        with patch("app.engine.Chroma") as chroma:
            get_vector_db()
        self.assertFalse(chroma.call_args.kwargs["client_settings"].anonymized_telemetry)


class StoredDB:
    """Minimal stand-in for Chroma's get() used to build a keyword index.

    Unrelated filler chunks keep BM25Okapi term weights positive, as in the real corpus;
    in a two- or three-chunk corpus a shared word gets a zero or negative weight.
    """

    def __init__(self, docs):
        self.docs = docs + [
            Document(id=f"filler-{number}", page_content=f"unrelated parking signage rule {number}", metadata={"source": "filler.pdf"})
            for number in range(10)
        ]

    def get(self, include):
        return {
            "ids": [doc.id for doc in self.docs],
            "documents": [doc.page_content for doc in self.docs],
            "metadatas": [doc.metadata for doc in self.docs],
        }


class RetrievalTests(unittest.TestCase):
    def test_document_scope_filters_keyword_and_vector_candidates(self):
        city_a = Document(id="a", page_content="guest house 700 square feet", metadata={"source": "a.pdf"})
        city_b = Document(id="b", page_content="guest house 900 square feet", metadata={"source": "b.pdf"})
        city_c = Document(id="c", page_content="shed 800 square feet", metadata={"source": "c.pdf"})
        index = build_search_index(StoredDB([city_a, city_b, city_c]))
        self.assertEqual([doc.metadata["source"] for doc, _ in bm25_search("guest house", index, sources={"b.pdf"})], ["b.pdf"])

        class FilteredDB:
            def similarity_search_with_score(self, query, k, filter=None):
                self.last_filter = filter
                return [(city_b, 0.1)]

        db = FilteredDB()
        self.assertEqual(hybrid_search("guest house", db, k=2, index=index, sources={"b.pdf"}), [city_b])
        self.assertEqual(db.last_filter, {"source": "b.pdf"})
        hybrid_search("guest house", db, k=2, index=index, sources={"b.pdf", "a.pdf"})
        self.assertEqual(db.last_filter, {"source": {"$in": ["a.pdf", "b.pdf"]}})

    def test_scoped_keyword_scores_match_unscoped_scores(self):
        docs = [
            Document(id=str(number), page_content=text, metadata={"source": source})
            for number, (text, source) in enumerate([
                ("guest house limited to 900 square feet", "a.pdf"),
                ("guest house limited to 700 square feet", "b.pdf"),
                ("fence height limited to four feet", "b.pdf"),
                ("sign area limited to 32 square feet", "c.pdf"),
            ])
        ]
        index = build_search_index(StoredDB(docs))
        unscoped = {doc.id: score for doc, score in bm25_search("guest house square feet", index, k=10)}
        scoped = bm25_search("guest house square feet", index, k=10, sources={"b.pdf"})
        self.assertEqual({doc.metadata["source"] for doc, _ in scoped}, {"b.pdf"})
        self.assertTrue(all(score == unscoped[doc.id] for doc, score in scoped))

    def test_named_district_passage_precedes_a_general_rule(self):
        general = Document(id="general", page_content="Guest house: 700 square feet.")
        district = Document(
            id="district", page_content="Guest house: 900 square feet.",
            metadata={"section": "6-2 R-2 Residential."},
        )
        other = Document(
            id="other", page_content="Guest house: 800 square feet.",
            metadata={"section": "6-3 R-3 Residential."},
        )
        class FixedScores:
            def get_scores(self, words):
                return [10.0, 9.0, 9.5]

        class FixedVectorDB:
            def similarity_search_with_score(self, query, k):
                return [(general, 0.01), (other, 0.5), (district, 0.6)]

        index = SearchIndex(documents=[general, other, district], bm25=FixedScores())
        self.assertEqual(
            hybrid_search("In the R-2 district, how large may a guest house be?", FixedVectorDB(), k=3, index=index),
            [district, general, other],
        )
        self.assertEqual(
            hybrid_search("How large may a guest house be?", FixedVectorDB(), k=3, index=index),
            [general, district, other],
        )

    def test_district_specific_guest_house_rule_outranks_general_and_other_districts(self):
        db = Chroma(
            collection_name=f"retrieval_test_{uuid4().hex}",
            embedding_function=FakeEmbeddings(size=16),
        )
        db.add_documents(
            [
                Document(page_content="Guest houses. Maximum size: 700 square feet.", metadata={"source": "rules.pdf", "page": 1}),
                Document(page_content="Guest house. Maximum size: 900 square feet.", metadata={"source": "rules.pdf", "page": 2, "section": "6-2 R-2 Residential."}),
                Document(page_content="Guest house. Maximum size: 800 square feet.", metadata={"source": "rules.pdf", "page": 3, "section": "6-3 R-3 Residential."}),
                *[Document(page_content=f"Unrelated zoning topic {n}.", metadata={"source": "rules.pdf", "page": n + 4}) for n in range(8)],
            ],
            ids=[str(n) for n in range(11)],
        )
        index = build_search_index(db)
        hits = bm25_search("In the R-2 district, how large may a guest house be?", index, k=3)
        self.assertEqual(hits[0][0].metadata["page"], 2)

    def test_section_heading_does_not_create_hits_for_ordinary_queries(self):
        db = Chroma(
            collection_name=f"retrieval_test_{uuid4().hex}",
            embedding_function=FakeEmbeddings(size=16),
        )
        db.add_documents(
            [
                Document(page_content="Fence height limit.", metadata={"source": "rules.pdf", "page": 1, "section": "6-2 Guest house rules."}),
                Document(page_content="Guest house size limit.", metadata={"source": "rules.pdf", "page": 2}),
                Document(page_content="Parking space rules.", metadata={"source": "rules.pdf", "page": 3}),
                Document(page_content="Setback rules.", metadata={"source": "rules.pdf", "page": 4}),
                Document(page_content="Tree canopy rules.", metadata={"source": "rules.pdf", "page": 5}),
                Document(page_content="Lighting rules.", metadata={"source": "rules.pdf", "page": 6}),
                Document(page_content="Sign height rules.", metadata={"source": "rules.pdf", "page": 7}),
            ],
            ids=["section-only", "answer", "parking", "setback", "trees", "lighting", "sign"],
        )
        hits = bm25_search("guest house", build_search_index(db), k=4)
        self.assertEqual([doc.id for doc, _ in hits], ["answer"])

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

        class ModeratelyCloseScores:
            def get_scores(self, words):
                return [10.0, 9.2]

        relevant.bm25 = ModeratelyCloseScores()
        self.assertTrue(needs_clarification("What is the maximum fence height?", relevant))

        named = SearchIndex(
            documents=[
                Document(page_content="Union City maximum fence height", metadata={"source": "union.pdf"}),
                Document(page_content="Other City maximum fence height", metadata={"source": "other.pdf"}),
            ],
            bm25=ModeratelyCloseScores(),
        )
        self.assertFalse(needs_clarification("What is the Union City maximum fence height?", named))

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
