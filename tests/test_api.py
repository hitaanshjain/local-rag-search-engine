import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document

from app.api import QueryRequest, chat


class FakeChain:
    async def astream(self, values):
        yield SimpleNamespace(content="First ")
        yield SimpleNamespace(content="answer")


class FakePrompt:
    def __or__(self, llm):
        return FakeChain()


async def response_events(response):
    parts = [
        part.decode() if isinstance(part, bytes) else part
        async for part in response.body_iterator
    ]
    body = "".join(parts)
    events = []
    for frame in body.strip().split("\n\n"):
        fields = dict(line.split(": ", 1) for line in frame.splitlines())
        events.append((fields["event"], json.loads(fields["data"])))
    return events


class ChatEventsTests(unittest.TestCase):
    def test_sources_are_sent_before_tokens_with_file_and_page(self):
        docs = [
            Document(page_content="A", metadata={"source": "zoning.pdf", "page": 2}),
            Document(page_content="B", metadata={"source": "rules.pdf", "page": 7}),
        ]
        with patch("app.api.hybrid_search", return_value=docs), patch(
            "app.api.prompt_template", FakePrompt()
        ):
            response = asyncio.run(chat(QueryRequest(query="What applies?")))
            events = asyncio.run(response_events(response))

        self.assertEqual(response.media_type, "text/event-stream")
        retrieval_timing = response.headers.get("server-timing", "")
        self.assertTrue(retrieval_timing.startswith("retrieval;dur="))
        self.assertGreaterEqual(float(retrieval_timing.split("=", 1)[1]), 0)
        self.assertEqual(
            events,
            [
                ("sources", {"sources": [{"source": "zoning.pdf", "page": 2}, {"source": "rules.pdf", "page": 7}]}),
                ("token", {"text": "First "}),
                ("token", {"text": "answer"}),
                ("done", {}),
            ],
        )

    def test_empty_search_uses_the_same_event_protocol(self):
        with patch("app.api.hybrid_search", return_value=[]):
            response = asyncio.run(chat(QueryRequest(query="missing")))
            events = asyncio.run(response_events(response))

        self.assertEqual(response.media_type, "text/event-stream")
        self.assertEqual(
            events,
            [
                ("sources", {"sources": []}),
                ("token", {"text": "I couldn't find any relevant information."}),
                ("done", {}),
            ],
        )


if __name__ == "__main__":
    unittest.main()
