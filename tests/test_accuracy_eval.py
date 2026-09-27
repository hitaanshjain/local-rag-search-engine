import unittest

from langchain_core.documents import Document

from app.engine import SearchIndex
from benchmarks.accuracy_eval import check_index_corpus, keyword_search_substring, load_and_validate_queries, score_ranking


class AccuracyMetricTests(unittest.TestCase):
    def test_corpus_check_allows_recorded_textless_pages_only(self):
        index = SearchIndex([
            Document(page_content="Rule", metadata={"source": "a.pdf", "page": 1}),
            Document(page_content="Rule", metadata={"source": "a.pdf", "page": 3}),
        ], None)
        check_index_corpus(index, {"a.pdf": 3}, {"a.pdf": {"pages": 3, "blank_pages": [2], "low_text_pages": []}})
        with self.assertRaises(ValueError):
            check_index_corpus(index, {"a.pdf": 3}, {})
        with self.assertRaises(ValueError):
            check_index_corpus(index, {"a.pdf": 4}, {"a.pdf": {"pages": 4, "blank_pages": [2], "low_text_pages": []}})

    def test_retrieval_eval_includes_verified_additional_questions(self):
        queries, _, _ = load_and_validate_queries()
        self.assertEqual(len(queries), 28)
        self.assertEqual(len({query["id"] for query in queries}), 28)
        self.assertIn("held_cha_02", {query["id"] for query in queries})

    def test_source_and_page_metrics_use_the_first_relevant_rank(self):
        results = [
            Document(page_content="other", metadata={"source": "other.pdf", "page": 1}),
            Document(page_content="wrong page", metadata={"source": "rules.pdf", "page": 2}),
            Document(page_content="answer", metadata={"source": "rules.pdf", "page": 7}),
        ]
        metrics = score_ranking(results, [{"source": "rules.pdf", "page": 7}])

        self.assertEqual(metrics["source"], {"hit@3": 1, "hit@5": 1, "mrr": 0.5})
        self.assertEqual(metrics["page"], {"hit@3": 1, "hit@5": 1, "mrr": 1 / 3})

    def test_substring_baseline_preserves_the_old_partial_word_match(self):
        index = SearchIndex(
            documents=[
                Document(id="parking", page_content="Parking is allowed."),
                Document(id="other", page_content="Fences are limited."),
            ],
            bm25=None,
        )

        self.assertEqual(keyword_search_substring("park", index, k=2)[0][0].id, "parking")


if __name__ == "__main__":
    unittest.main()
