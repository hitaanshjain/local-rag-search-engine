import unittest

from benchmarks.citation_support import (
    score_support, sentence_citations, split_sentences, summarize_support,
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


if __name__ == "__main__":
    unittest.main()
