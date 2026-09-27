import asyncio
import unittest
from types import SimpleNamespace

from langchain_core.documents import Document

from app.answering import cited_claims, collect_conflict_candidates, detect_conflicts, format_scope, repair_answer, resolve_conflict, verify_answer


class FixedLLM:
    def __init__(self, *responses):
        self.responses = responses
        self.index = 0

    async def ainvoke(self, prompt):
        response = self.responses[min(self.index, len(self.responses) - 1)]
        self.index += 1
        return SimpleNamespace(content=response)


class AnswerVerificationTests(unittest.TestCase):
    def test_conflict_candidates_keep_distinct_pages_in_same_jurisdiction_across_files(self):
        primary = Document(id="a", page_content="The R-2 rule.", metadata={"source": "old.pdf", "page": 54, "jurisdiction": "Union City"})
        same_page = Document(id="b", page_content="Another chunk on page 54.", metadata={"source": "old.pdf", "page": 54, "jurisdiction": "Union City"})
        general = Document(id="c", page_content="The general rule.", metadata={"source": "old.pdf", "page": 38, "jurisdiction": "Union City"})
        newer = Document(id="d", page_content="The new version.", metadata={"source": "new.pdf", "page": 2, "jurisdiction": "Union City"})
        other_city = Document(id="e", page_content="Another city's rule.", metadata={"source": "other.pdf", "page": 7, "jurisdiction": "Charleston"})
        candidates = collect_conflict_candidates(primary, [same_page, other_city], [(general, 8.0), (newer, 7.0)])
        self.assertEqual(candidates, [primary, general, newer])

    def test_evidence_excerpt_tolerates_pdf_spacing_but_not_changed_numbers(self):
        passage = Document(page_content="Said guesthouse shall be limited to 900 square feet.")
        spacing = FixedLLM('{"supported": true, "quote": "Said guest house shall be limited to 900 square feet."}')
        self.assertTrue(asyncio.run(verify_answer("The limit is 900 square feet [1].", [passage], spacing)))
        wrong_number = FixedLLM('{"supported": true, "quote": "Said guest house shall be limited to 700 square feet."}')
        self.assertFalse(asyncio.run(verify_answer("The limit is 700 square feet [1].", [passage], wrong_number)))

    def test_claim_requires_valid_citation_and_exact_supporting_excerpt(self):
        passage = Document(
            page_content="Said guesthouse shall be limited to 900 square feet.",
            metadata={"source": "rules.pdf", "page": 54, "section": "6-2 R-2 Residential."},
        )
        valid = FixedLLM('{"supported": true, "quote": "Said guesthouse shall be limited to 900 square feet."}')
        self.assertTrue(asyncio.run(verify_answer("A guest house is limited to 900 square feet [1].", [passage], valid)))
        invalid_quote = FixedLLM('{"supported": true, "quote": "The limit is 700 square feet."}')
        self.assertFalse(asyncio.run(verify_answer("The limit is 700 square feet [1].", [passage], invalid_quote)))
        self.assertFalse(asyncio.run(verify_answer("The limit is 900 square feet [2].", [passage], FixedLLM())))
        self.assertFalse(asyncio.run(verify_answer("The limit is 900 square feet.", [passage], FixedLLM())))

    def test_every_cited_claim_is_checked_before_acceptance(self):
        passage = Document(page_content="The limit is 900 square feet. One guest house is allowed.")
        llm = FixedLLM(
            '{"supported": true, "quote": "The limit is 900 square feet."}',
            '{"supported": false, "quote": ""}',
        )
        answer = "The limit is 900 square feet [1]. Two guest houses are allowed [1]."
        self.assertFalse(asyncio.run(verify_answer(answer, [passage], llm)))
        self.assertIsNone(cited_claims("The limit is 900 feet. Two units are allowed [1].", 1))

    def test_false_negative_is_rechecked_against_the_validated_quote(self):
        passage = Document(page_content="Front yard setback, as measured from the right-of-way: 15 feet.")
        llm = FixedLLM(
            '{"supported": false, "quote": "Front yard setback, as measured from the right-of-way: 15 feet."}',
            '{"supported": true, "quote": "Front yard setback, as measured from the right-of-way: 15 feet."}',
        )
        self.assertTrue(asyncio.run(verify_answer("The front-yard setback is 15 feet [1].", [passage], llm)))

    def test_repair_moves_a_claim_only_to_a_confirmed_supporting_passage(self):
        five = Document(page_content="No more than five vehicle visits per day.")
        ten = Document(page_content="No more than 10 visits per day.")
        llm = FixedLLM(
            '{"supported": true, "quote": "No more than five vehicle visits per day."}',
            '{"supported": false, "quote": "No more than 10 visits per day."}',
            '{"supported": false, "quote": "No more than 10 visits per day."}',
        )
        repaired = asyncio.run(repair_answer("No more than five vehicle visits per day are permitted [2].", [five, ten], llm))
        self.assertEqual(repaired, "No more than five vehicle visits per day are permitted [1].")

    def test_repair_drops_invalid_extra_citation_and_moves_leading_citation_after_check(self):
        passage = Document(page_content="A cemetery must contain at least ten acres.")
        llm = FixedLLM('{"supported": true, "quote": "A cemetery must contain at least ten acres."}')
        extra = asyncio.run(repair_answer("A cemetery must contain at least ten acres [1] and [4].", [passage], llm))
        self.assertEqual(extra, "A cemetery must contain at least ten acres [1].")
        leading = asyncio.run(repair_answer("[1] A cemetery must contain at least ten acres.", [passage], llm))
        self.assertEqual(leading, "A cemetery must contain at least ten acres [1].")

    def test_conflict_uses_exact_quotes_and_named_section_scope(self):
        specific = Document(
            id="specific", page_content="Said guesthouse shall be limited to 900 square feet.",
            metadata={"source": "rules.pdf", "page": 54, "section": "6-2 R-2 Residential.", "jurisdiction": "Union City, Georgia", "version": "August 20, 2024, Rev."},
        )
        general = Document(
            id="general", page_content="A freestanding guest house shall not exceed 700 square feet.",
            metadata={"source": "rules.pdf", "page": 38, "section": "5-11 Guest houses.", "jurisdiction": "Union City, Georgia", "version": "August 20, 2024, Rev."},
        )
        llm = FixedLLM('{"conflicts": [{"candidate": 2, "primary_quote": "Said guesthouse shall be limited to 900 square feet.", "other_quote": "A freestanding guest house shall not exceed 700 square feet."}]}')
        conflicts = asyncio.run(detect_conflicts("In R-2, how large may a guest house be?", specific, [specific, general], llm))
        self.assertEqual(len(conflicts), 1)
        self.assertIs(conflicts[0].other, general)
        self.assertEqual(resolve_conflict("In R-2, how large may a guest house be?", specific, general), "primary")
        self.assertIn("Union City, Georgia", format_scope(specific, "In R-2, how large may a guest house be?"))
        self.assertIn("August 20, 2024, Rev.", format_scope(specific, "In R-2, how large may a guest house be?"))
        cottage = Document(page_content="Cottage home courts: 15 feet.", metadata={"section": "6-7 RM Residential Multi-family.", "jurisdiction": "Union City, Georgia", "version": "2024"})
        self.assertIn("District: RM", format_scope(cottage, "What is the cottage court setback?"))

    def test_numeric_conflict_finds_different_limits_without_model_and_ignores_other_uses(self):
        specific = Document(page_content="Said guesthouse shall be limited to 900 square feet.", metadata={"section": "6-2 R-2 Residential.", "jurisdiction": "Union City, Georgia"})
        general = Document(page_content="A freestanding guest house shall not exceed 700 square feet of heated and finished floor area.", metadata={"section": "5-11 Guest houses.", "jurisdiction": "Union City, Georgia"})
        other_use = Document(page_content="Townhouses have a 15-foot front yard setback; cottage home courts need one acre.", metadata={"section": "6-7 RM Residential.", "jurisdiction": "Union City, Georgia"})
        from app.answering import numeric_rule_conflicts
        found = numeric_rule_conflicts("In Union City's R-2 district, how large may a guest house be?", "A guest house may be 900 square feet [1].", specific, [specific, general])
        self.assertEqual(len(found), 1)
        self.assertIs(found[0].other, general)
        checked = asyncio.run(detect_conflicts("In Union City's R-2 district, how large may a guest house be?", specific, [specific, general], FixedLLM('{"conflicts": []}'), "A guest house may be 900 square feet [1]."))
        self.assertEqual(len(checked), 1)
        cottage = Document(page_content="Cottage home courts: Front yard setback: 15 feet.", metadata={"jurisdiction": "Union City, Georgia"})
        self.assertEqual(numeric_rule_conflicts("What front-yard setback applies to cottage home courts in Union City?", "The front yard setback is 15 feet [1].", cottage, [cottage, other_use]), [])

    def test_conflict_parser_accepts_json_surrounded_by_model_explanation(self):
        primary = Document(page_content="The limit is 900 square feet.")
        other = Document(page_content="The limit is 700 square feet.")
        llm = FixedLLM('Comparison follows.\n{"conflicts": [{"candidate": 2, "primary_quote": "900 square feet", "other_quote": "700 square feet"}]}\nThese differ.')
        conflicts = asyncio.run(detect_conflicts("What is the limit?", primary, [primary, other], llm))
        self.assertEqual(len(conflicts), 1)

    def test_conflict_parser_retries_a_prose_only_empty_result(self):
        primary = Document(page_content="One unit per lot.")
        other = Document(page_content="Unrelated parking standard.")
        llm = FixedLLM(
            "I could not format the result.",
            '{"conflicts": []}',
        )
        self.assertEqual(asyncio.run(detect_conflicts("How many units per lot?", primary, [primary, other], llm)), [])

    def test_explicit_no_conflict_prose_is_an_empty_result(self):
        primary = Document(page_content="One unit per lot.")
        other = Document(page_content="Unrelated parking standard.")
        llm = FixedLLM("There are no rules about the same subject, so the output is an empty array.")
        self.assertEqual(asyncio.run(detect_conflicts("How many units per lot?", primary, [primary, other], llm)), [])

    def test_malformed_or_heading_only_conflicts_are_not_reported(self):
        primary = Document(page_content="Cottage home courts: front yard setback is 15 feet.")
        other = Document(page_content="Townhouses: front yard setback is 25 feet.")
        malformed = FixedLLM('["conflicts": []]', '["conflicts": []]')
        self.assertEqual(asyncio.run(detect_conflicts("Cottage court front yard setback?", primary, [primary, other], malformed)), [])
        heading = FixedLLM('{"conflicts": [{"candidate": 2, "primary_quote": "Cottage home courts:", "other_quote": "Townhouses: front yard setback is 25 feet."}]}')
        self.assertEqual(asyncio.run(detect_conflicts("Cottage court front yard setback?", primary, [primary, other], heading)), [])

    def test_unresolved_document_version_conflict_does_not_choose_a_rule(self):
        first = Document(page_content="Limit: 900 feet.", metadata={"source": "old.pdf", "section": "6-2 R-2 Residential.", "jurisdiction": "Union City", "version": "2024"})
        second = Document(page_content="Limit: 700 feet.", metadata={"source": "new.pdf", "section": "6-2 R-2 Residential.", "jurisdiction": "Union City", "version": "2025"})
        self.assertIsNone(resolve_conflict("What is the R-2 limit?", first, second))


if __name__ == "__main__":
    unittest.main()
