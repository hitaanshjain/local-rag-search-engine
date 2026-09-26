import unittest

from benchmarks.answer_eval import load_queries, read_chat, score_answer


class AnswerScoringTests(unittest.TestCase):
    def test_final_holdout_has_excerpt_verified_answerable_items(self):
        rows = load_queries()
        self.assertEqual(len(rows), 10)
        self.assertEqual(len({row["id"] for row in rows}), len(rows))

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
                yield b'event: sources\ndata: {"sources": []}\n\nevent: token\ndata: {"text": "Hi"}\n\nevent: done\ndata: {}\n\n'

        class FakeSession:
            def post(self, *args, **kwargs):
                return FakeResponse()

        meta = {}
        answer, sources = read_chat("Hello?", session=FakeSession(), meta=meta)
        self.assertEqual((answer, sources, meta), ("Hi", [], {"llm": "served-model:1b"}))


if __name__ == "__main__":
    unittest.main()
