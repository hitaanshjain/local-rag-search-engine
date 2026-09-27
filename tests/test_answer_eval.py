import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from benchmarks.answer_eval import load_queries, parse_sse, read_chat, run_answer_benchmark, score_answer


class AnswerScoringTests(unittest.TestCase):
    def test_final_holdout_has_random_page_items_and_a_category_stratum(self):
        rows = load_queries()
        original = [row for row in rows if row["id"].startswith("h2_")]
        counts = {kind: sum(row["kind"] == kind for row in original) for kind in ("answerable", "unanswerable", "ambiguous")}
        self.assertEqual(counts, {"answerable": 20, "unanswerable": 4, "ambiguous": 2})
        stratum = [row for row in rows if not row["id"].startswith("h2_")]
        self.assertEqual({category: sum(row.get("category") == category for row in stratum)
                          for category in ("conflict", "table", "exception", "outdated")},
                         {"conflict": 4, "table": 4, "exception": 4, "outdated": 4})
        self.assertEqual(len(stratum), 16)
        self.assertEqual(len({row["id"] for row in rows}), len(rows))

    def test_coverage_development_set_has_four_per_category(self):
        rows = load_queries("coverage_development_queries.json")
        self.assertEqual(sorted(row["category"] for row in rows), sorted(["conflict", "table", "exception", "outdated"] * 4))

    def test_holdout_shares_no_questions_or_pages_with_tuned_sets(self):
        holdout = load_queries()
        tuned = (load_queries("regression_queries.json") + load_queries("development_queries.json")
                 + load_queries("coverage_development_queries.json"))

        def pages(rows):
            return {
                (row["source"], page)
                for row in rows if row["kind"] == "answerable"
                for page in [row["page"], *row.get("additional_relevant_pages", [])]
            }

        self.assertFalse({row["query"] for row in holdout} & {row["query"] for row in tuned})
        self.assertFalse({(row["source"], row["page"]) for row in holdout if row["kind"] == "answerable"} & pages(tuned))

    def test_answer_requires_expected_fact_and_matching_page_citation(self):
        row = {
            "kind": "answerable",
            "accepted_answers": ["10 acres", "ten acres"],
            "source": "rules.pdf",
            "page": 3,
        }
        sources = [{"source": "wrong.pdf", "page": 3}, {"source": "rules.pdf", "page": 3}]
        self.assertEqual(score_answer(row, "The minimum is 10 acres [2].", sources), {
            "fact_match": True,
            "citation_match": True,
            "citation_refs_valid": True,
            "pass": True,
        })
        self.assertFalse(score_answer(row, "The minimum is 10 acres [1].", sources)["pass"])
        self.assertFalse(score_answer(row, "The minimum is 10 acres [9].", sources)["citation_refs_valid"])

    def test_unanswerable_question_requires_abstention(self):
        row = {"kind": "unanswerable"}
        self.assertTrue(score_answer(row, "I don't know based on these documents.", [])["pass"])
        self.assertFalse(score_answer(row, "The answer is 42 [1].", [{"source": "x", "page": 1}])["pass"])

    def test_expected_yes_is_not_satisfied_by_a_no_answer_using_permitted_word(self):
        row = {
            "kind": "answerable", "source": "rules.pdf", "page": 2,
            "accepted_answers": ["yes", "permitted"], "forbidden_answers": ["no"],
        }
        sources = [{"source": "rules.pdf", "page": 2}]
        self.assertFalse(score_answer(row, "No, the use is not permitted [1].", sources)["pass"])

    def test_combined_citation_checks_every_reference(self):
        row = {"kind": "answerable", "accepted_answers": ["10 acres"], "source": "rules.pdf", "page": 2}
        sources = [{"source": "rules.pdf", "page": 2}]
        score = score_answer(row, "The limit is 10 acres [1, 4].", sources)
        self.assertFalse(score["citation_refs_valid"])
        self.assertFalse(score["pass"])

    def test_another_verified_page_can_support_the_same_fact(self):
        row = {
            "kind": "answerable", "accepted_answers": ["30 feet"],
            "source": "rules.pdf", "page": 406, "additional_relevant_pages": [405],
        }
        sources = [{"source": "rules.pdf", "page": 405}]
        self.assertTrue(score_answer(row, "The minimum is 30 feet [1].", sources)["pass"])

    def test_read_chat_reports_model_named_by_the_server(self):
        class FakeResponse:
            headers = {"X-LLM-Model": "served-model:1b"}

            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def raise_for_status(self):
                pass

            def iter_content(self, chunk_size=None):
                yield b'event: sources\ndata: {"sources": []}\n\nevent: token\ndata: {"text": "Hi"}\n\nevent: timing\ndata: {"check_calls": 2}\n\nevent: done\ndata: {}\n\n'

        class FakeSession:
            def post(self, *args, **kwargs):
                return FakeResponse()

        meta = {}
        answer, sources = read_chat("Hello?", session=FakeSession(), meta=meta)
        self.assertEqual((answer, sources, meta), ("Hi", [], {"llm": "served-model:1b", "timing": {"check_calls": 2}}))


class AnswerEvalExtensionTests(unittest.TestCase):
    def test_parse_sse_handles_split_frames_and_requires_done(self):
        chunks = [b'event: sources\ndata: {"sources": [{"source": "a.pdf", "page": 1}]}\n', b'\nevent: token\ndata: {"text": "Hi [1]."}\n\nevent: done\ndata: {}\n\n']
        self.assertEqual(parse_sse(chunks), ("Hi [1].", [{"source": "a.pdf", "page": 1}]))
        with self.assertRaises(ValueError):
            parse_sse([b'event: token\ndata: {"text": "Hi"}\n\n'])

    def test_holdout_requires_the_final_run_flag(self):
        with self.assertRaisesRegex(ValueError, "--final-holdout"):
            run_answer_benchmark("heldout_queries.json", "x", support=False)

    def test_results_record_support_and_categories_without_changing_pass(self):
        rows = [
            {"id": "t1", "kind": "answerable", "category": "table", "query": "Q1?", "source": "a.pdf", "page": 1, "accepted_answers": ["10 feet"]},
            {"id": "t2", "kind": "unanswerable", "query": "Q2?"},
        ]
        replies = {"Q1?": ("The yard is 10 feet [1].", [{"source": "a.pdf", "page": 1}]),
                   "Q2?": ("I don't know based on these documents.", [])}

        def fake_read_chat(query, session=None, meta=None):
            meta["llm"] = "served:3b"
            return replies[query]

        class Judge:
            model = "judge:7b"

            def __call__(self, sentence, page):
                return {"verdict": "supported", "quote": "yard is 10 feet"}

        with patch("benchmarks.answer_eval.load_queries", return_value=rows), \
             patch("benchmarks.answer_eval.read_chat", side_effect=fake_read_chat), \
             patch("benchmarks.answer_eval.write_results"):
            result = run_answer_benchmark("development_queries.json", "x", judge=Judge(),
                                          page_text=lambda source, page: "The front yard is 10 feet.")
        self.assertEqual(result["passed"], 2)
        self.assertEqual(result["queries"][0]["citation_support"]["counts"], {"supported": 1})
        self.assertNotIn("citation_support", result["queries"][1])
        self.assertEqual(result["citation_support"]["judge_model"], "judge:7b")
        self.assertEqual(result["citation_support"]["by_category"]["table"]["support_rate"], 1.0)
        self.assertEqual(result["category_pass"], {"table": {"passed": 1, "total": 1}, "general": {"passed": 1, "total": 1}})

    def test_unknown_category_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            path = Path(root) / "bad.json"
            path.write_text(json.dumps([{"id": "b", "kind": "unanswerable", "query": "Q?", "category": "misc"}]), encoding="utf-8")
            with patch("benchmarks.answer_eval.HERE", Path(root)):
                with self.assertRaisesRegex(ValueError, "Unknown category"):
                    load_queries("bad.json")


if __name__ == "__main__":
    unittest.main()
