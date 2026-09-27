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

    def test_first_question_needs_no_rewrite(self):
        llm = RecordingLLM()
        self.assertEqual(asyncio.run(contextualize_query("What is the setback?", [], llm)), "What is the setback?")
        self.assertIsNone(llm.prompt)


if __name__ == "__main__":
    unittest.main()
