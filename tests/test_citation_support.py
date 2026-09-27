import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pymupdf

from benchmarks.citation_support import (
    OllamaJudge, PageTexts, calibrate, score_support, sentence_citations, split_sentences, summarize_support,
)

P54 = "e. Said guesthouse shall be limited to 900 square feet; and\nf. No kitchen shall be provided."
P38 = "A freestanding guest house shall not exceed 700 square feet of heated and finished floor area."
SOURCES = [{"source": "u.pdf", "page": 54}, {"source": "u.pdf", "page": 38}]


def pages(texts):
    return lambda source, page: texts.get((source, page))


class FakeJudge:
    def __init__(self, replies):
        self.replies = replies
        self.calls = []

    def __call__(self, sentence, page):
        self.calls.append((sentence, page))
        reply = self.replies[sentence]
        if isinstance(reply, Exception):
            raise reply
        return reply


class SplitTests(unittest.TestCase):
    def test_skips_scope_line_abstention_and_questions(self):
        answer = (
            "Jurisdiction: Union City, Georgia | District: R-2 | Source: u.pdf\n"
            "A guest house may be 900 square feet [1].\n"
            "Which district do you mean?\n"
            "I don't know based on these documents."
        )
        self.assertEqual(split_sentences(answer), ["A guest house may be 900 square feet [1]."])

    def test_keeps_citations_and_abbreviations_with_their_sentence(self):
        answer = (
            "The front yard is 10 ft. in combination with an A or R Zone [1]. "
            "Construction runs from 7 a.m. to 7 p.m. [2]. It is quiet. [1]"
        )
        self.assertEqual(split_sentences(answer), [
            "The front yard is 10 ft. in combination with an A or R Zone [1].",
            "Construction runs from 7 a.m. to 7 p.m. [2].",
            "It is quiet. [1]",
        ])

    def test_citation_groups(self):
        self.assertEqual(sentence_citations("Limits apply [1, 3] and [2]."), [1, 3, 2])


class ScoreTests(unittest.TestCase):
    def texts(self):
        return pages({("u.pdf", 54): P54, ("u.pdf", 38): P38})

    def test_supported_requires_the_quote_on_the_page(self):
        claim = "A guest house may be 900 square feet."
        good = FakeJudge({claim: {"verdict": "supported", "quote": "limited to 900 square feet"}})
        result = score_support(f"{claim[:-1]} [1].", SOURCES, self.texts(), good)
        self.assertEqual(result["sentences"][0]["label"], "supported")
        invented = FakeJudge({claim: {"verdict": "supported", "quote": "guest houses may be 900 square feet"}})
        result = score_support(f"{claim[:-1]} [1].", SOURCES, self.texts(), invented)
        self.assertEqual(result["sentences"][0]["label"], "unverified")

    def test_quote_normalization_and_minimum_length(self):
        claim = "No kitchen is allowed."
        curly = FakeJudge({claim: {"verdict": "supported", "quote": "“No  kitchen shall be provided.”"}})
        self.assertEqual(score_support("No kitchen is allowed [1].", SOURCES, self.texts(), curly)["sentences"][0]["label"], "supported")
        generic = FakeJudge({claim: {"verdict": "supported", "quote": "No kitchen"}})
        self.assertEqual(score_support("No kitchen is allowed [1].", SOURCES, self.texts(), generic)["sentences"][0]["label"], "unverified")

    def test_quote_matches_despite_word_spacing_differences(self):
        # The page says "guesthouse"; the judge quoted it as "guest house".
        claim = "A guest house may be 900 square feet."
        spaced = FakeJudge({claim: {"verdict": "supported", "quote": "Said guest house shall be limited to 900 square feet."}})
        self.assertEqual(score_support(f"{claim[:-1]} [1].", SOURCES, self.texts(), spaced)["sentences"][0]["label"], "supported")

    def test_multi_citation_sentence_is_judged_against_all_cited_pages(self):
        claim = "The R-2 limit is 900 square feet and the general limit is 700 square feet."
        judge = FakeJudge({claim: {"verdict": "supported", "quote": "shall not exceed 700 square feet"}})
        result = score_support(claim[:-1] + " [1, 2].", SOURCES, self.texts(), judge)
        self.assertEqual(result["sentences"][0]["label"], "supported")
        self.assertIn("=== u.pdf page 54 ===", judge.calls[0][1])
        self.assertIn("=== u.pdf page 38 ===", judge.calls[0][1])

    def test_partial_and_unsupported_verdicts(self):
        partial = "Guest houses may be 900 square feet with a kitchen."
        wrong = "Guest houses may be 1,200 square feet."
        judge = FakeJudge({
            partial: {"verdict": "partial", "quote": "limited to 900 square feet"},
            wrong: {"verdict": "unsupported", "quote": ""},
        })
        result = score_support(f"{partial[:-1]} [1]. {wrong[:-1]} [1].", SOURCES, self.texts(), judge)
        self.assertEqual([row["label"] for row in result["sentences"]], ["partial", "unsupported"])

    def test_uncited_factual_sentence_and_nonfactual_skip(self):
        result = score_support("The limit is 900 square feet. Thanks for asking.", SOURCES, self.texts(), FakeJudge({}))
        self.assertEqual([row["label"] for row in result["sentences"]], ["uncited"])
        self.assertEqual(result["scored"], 1)

    def test_out_of_range_judge_error_and_unreadable_pages_are_unverified(self):
        claim = "The limit is 900 square feet."
        broken = FakeJudge({claim: ValueError("bad json")})
        self.assertEqual(score_support("The limit is 900 square feet [5].", SOURCES, self.texts(), broken)["sentences"][0]["label"], "unverified")
        self.assertEqual(score_support("The limit is 900 square feet [1].", SOURCES, self.texts(), broken)["sentences"][0]["label"], "unverified")
        unreadable = pages({})
        self.assertEqual(score_support("The limit is 900 square feet [1].", SOURCES, unreadable, broken)["sentences"][0]["label"], "unverified")

    def test_unsupported_with_an_unreadable_cited_page_is_unverified(self):
        claim = "The limit is 900 square feet."
        judge = FakeJudge({claim: {"verdict": "unsupported", "quote": ""}})
        only_38 = pages({("u.pdf", 38): P38})
        result = score_support("The limit is 900 square feet [1, 2].", SOURCES, only_38, judge)
        self.assertEqual(result["sentences"][0]["label"], "unverified")


class SummaryTests(unittest.TestCase):
    def test_support_rate_overall_and_by_category(self):
        a = {"counts": {"supported": 2, "unsupported": 1}, "scored": 3, "supported": 2}
        b = {"counts": {"uncited": 1}, "scored": 1, "supported": 0}
        empty = {"counts": {}, "scored": 0, "supported": 0}
        summary = summarize_support([("table", a), ("general", b), ("general", empty)])
        self.assertEqual(summary["overall"]["support_rate"], 0.5)
        self.assertAlmostEqual(summary["by_category"]["table"]["support_rate"], 2 / 3)
        self.assertEqual(summary["by_category"]["general"]["counts"], {"uncited": 1})


class PageTextsTests(unittest.TestCase):
    def test_reads_a_page_and_returns_none_for_missing_file_or_page(self):
        with tempfile.TemporaryDirectory() as root:
            pdf = pymupdf.open()
            page = pdf.new_page()
            page.insert_textbox(pymupdf.Rect(72, 72, 540, 300), "4-2 Accessory Dwelling Units.\n\nAn accessory dwelling unit shall not exceed 800 square feet of floor area.", fontsize=11)
            pdf.save(Path(root) / "town.pdf")
            pdf.close()
            texts = PageTexts([Path(root) / "missing-dir", Path(root)])
            self.assertIn("800 square feet", texts("town.pdf", 1))
            self.assertIsNone(texts("town.pdf", 2))
            self.assertIsNone(texts("other.pdf", 1))
            self.assertIsNone(texts("town.pdf", None))


class OllamaJudgeTests(unittest.TestCase):
    class FakeLLM:
        def __init__(self, content):
            self.content = content

        def invoke(self, prompt):
            self.prompt = prompt
            return SimpleNamespace(content=self.content)

    def test_parses_verdict_and_rejects_unknown_verdicts(self):
        llm = self.FakeLLM('{"verdict": "supported", "quote": "limited to 900 square feet"}')
        judge = OllamaJudge(model="judge:7b", llm=llm)
        self.assertEqual(judge("The limit is 900 square feet.", "page text"), {"verdict": "supported", "quote": "limited to 900 square feet"})
        self.assertIn("The limit is 900 square feet.", llm.prompt)
        with self.assertRaises(ValueError):
            OllamaJudge(model="judge:7b", llm=self.FakeLLM('{"verdict": "maybe"}'))("x", "y")

    def test_check_available_names_the_pull_command(self):
        response = SimpleNamespace(json=lambda: {"models": [{"name": "llama3.2:3b"}]}, raise_for_status=lambda: None)
        with patch("benchmarks.citation_support.requests.get", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "ollama pull judge:7b"):
                OllamaJudge(model="judge:7b", llm=self.FakeLLM("{}")).check_available()


class CalibrationTests(unittest.TestCase):
    def test_agreement_by_expected_label(self):
        rows = [
            {"id": "c1", "sentence": "The limit is 900 square feet.", "source": "u.pdf", "page": 54, "expected": "supported"},
            {"id": "c2", "sentence": "The limit is 700 square feet.", "source": "u.pdf", "page": 54, "expected": "unsupported"},
        ]
        judge = FakeJudge({
            "The limit is 900 square feet.": {"verdict": "supported", "quote": "limited to 900 square feet"},
            "The limit is 700 square feet.": {"verdict": "supported", "quote": "limited to 900 square feet"},
        })
        judge.model = "fake"
        result = calibrate(rows, judge, pages({("u.pdf", 54): P54}))
        self.assertEqual(result["agreement"]["overall"], 0.5)
        self.assertEqual(result["agreement"]["by_expected"], {"supported": 1.0, "unsupported": 0.0})
        self.assertEqual([row["label"] for row in result["rows"]], ["supported", "supported"])

    def test_calibration_file_is_well_formed(self):
        path = Path(__file__).resolve().parents[1] / "benchmarks" / "judge_calibration.json"
        rows = json.loads(path.read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(rows), 20)
        self.assertEqual(len({row["id"] for row in rows}), len(rows))
        self.assertEqual({row["expected"] for row in rows}, {"supported", "partial", "unsupported"})
        texts = PageTexts([Path(__file__).resolve().parents[1] / "data"])
        for row in rows:
            self.assertIsNotNone(texts(row["source"], row["page"]), row["id"])


if __name__ == "__main__":
    unittest.main()
