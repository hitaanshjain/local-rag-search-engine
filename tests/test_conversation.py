import asyncio
import unittest
from types import SimpleNamespace

from app.conversation import contextualize_query, format_history


class RecordingLLM:
    def __init__(self):
        self.prompt = None

    async def ainvoke(self, prompt):
        self.prompt = prompt
        return SimpleNamespace(content="Union City R-2 guest house maximum size")


class ConversationTests(unittest.TestCase):
    def test_follow_up_uses_recent_turns_for_retrieval(self):
        history = [
            {"role": "user", "text": "In Union City R-2, are guest houses allowed?"},
            {"role": "assistant", "text": "Yes, guest houses are allowed [1]."},
        ]
        llm = RecordingLLM()
        query = asyncio.run(contextualize_query("What about their size?", history, llm))
        self.assertEqual(query, "Union City R-2 guest house maximum size")
        self.assertIn("In Union City R-2", llm.prompt)
        self.assertIn("What about their size?", llm.prompt)
        self.assertIn("Assistant:", format_history(history))

    def test_rewrite_that_drops_the_topic_or_invents_one_is_replaced(self):
        history = [
            {"role": "user", "text": "In Union City's R-2 district, how large may a guest house be?"},
            {"role": "assistant", "text": "A guest house is limited to 900 square feet [1]."},
        ]

        class FixedLLM:
            def __init__(self, reply):
                self.reply = reply

            async def ainvoke(self, prompt):
                return SimpleNamespace(content=self.reply)

        invented = FixedLLM("How many parking spaces does a restaurant need in Charleston?")
        self.assertEqual(
            asyncio.run(contextualize_query("And in Charleston?", history, invented)),
            "In Union City's R-2 district, how large may a guest house be? And in Charleston?",
        )
        dropped = FixedLLM("How large may a guest house be in Union City's R-2 district?")
        complete = "What is the front yard setback in Charleston's DR-1 district?"
        self.assertEqual(asyncio.run(contextualize_query(complete, history, dropped)), complete)
        good = FixedLLM("How large may a guest house be in Charleston?")
        self.assertEqual(asyncio.run(contextualize_query("And in Charleston?", history, good)), "How large may a guest house be in Charleston?")

    def test_new_place_drops_district_codes_and_places_from_earlier_turns(self):
        history = [
            {"role": "user", "text": "In Union City's R-2 district, how large may a guest house be?"},
            {"role": "assistant", "text": "A guest house is limited to 900 square feet [1]."},
        ]
        places = ["Union City", "Charleston", "Urbana"]

        class FixedLLM:
            def __init__(self, reply):
                self.reply = reply

            async def ainvoke(self, prompt):
                return SimpleNamespace(content=self.reply)

        carried = FixedLLM("In Charleston's R-2 district, how large may a guest house be?")
        self.assertEqual(
            asyncio.run(contextualize_query("And in Charleston?", history, carried, places)),
            "In Charleston's district, how large may a guest house be?",
        )
        both = FixedLLM("How large may a guest house be in Union City's R-2 district and in Charleston?")
        self.assertEqual(
            asyncio.run(contextualize_query("And in Charleston?", history, both, places)),
            "How large may a guest house be in district and in Charleston?",
        )
        same_place = FixedLLM("How large may a guest house be in Union City's R-3 district?")
        self.assertEqual(
            asyncio.run(contextualize_query("What about Union City's R-3 district?", history, same_place, places)),
            "How large may a guest house be in Union City's R-3 district?",
        )
        no_place = FixedLLM("How large may a guest house be in Union City's R-3 district?")
        self.assertEqual(
            asyncio.run(contextualize_query("What about the R-3 district?", history, no_place, places)),
            "How large may a guest house be in Union City's R-3 district?",
        )

    def test_rewrite_failure_falls_back_instead_of_raising(self):
        class BrokenLLM:
            async def ainvoke(self, prompt):
                raise ConnectionError("ollama unavailable")

        history = [{"role": "user", "text": "How large may a guest house be in R-2?"}]
        self.assertEqual(
            asyncio.run(contextualize_query("And in R-3?", history, BrokenLLM())),
            "How large may a guest house be in R-2? And in R-3?",
        )

    def test_first_question_needs_no_rewrite(self):
        llm = RecordingLLM()
        self.assertEqual(asyncio.run(contextualize_query("What is the setback?", [], llm)), "What is the setback?")
        self.assertIsNone(llm.prompt)


if __name__ == "__main__":
    unittest.main()
