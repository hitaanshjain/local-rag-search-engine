import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from langchain_core.documents import Document
from fastapi.testclient import TestClient

from app.api import QueryRequest, app, chat


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
    def setUp(self):
        clarification = patch("app.api.needs_clarification", return_value=False)
        clarification.start()
        self.addCleanup(clarification.stop)
        keyword = patch("app.api.bm25_search", return_value=[])
        keyword.start()
        self.addCleanup(keyword.stop)

    def test_ambiguous_source_returns_clarification_without_model_answer(self):
        with patch("app.api.hybrid_search", return_value=[Document(page_content="fence", metadata={"source": "city-a.pdf", "page": 1})]), patch(
            "app.api.needs_clarification", return_value=True
        ):
            response = asyncio.run(chat(QueryRequest(query="What is the maximum fence height?")))
            events = asyncio.run(response_events(response))
        self.assertEqual(events, [
            ("sources", {"sources": []}),
            ("token", {"text": "Which city or document do you mean?"}),
            ("done", {}),
        ])

    def test_source_list_contains_only_passages_sent_to_model(self):
        first = Document(id="one", page_content="The direct answer.", metadata={"source": "a.pdf", "page": 1})
        second = Document(id="two", page_content="Unrelated rule.", metadata={"source": "b.pdf", "page": 2})
        observed = {}

        class RecordingChain:
            async def astream(self, values):
                observed.update(values)
                yield SimpleNamespace(content="Answer [1].")

        class RecordingPrompt:
            def __or__(self, llm):
                return RecordingChain()

        with patch("app.api.hybrid_search", return_value=[first, second]), patch(
            "app.api.bm25_search", return_value=[(first, 14.0), (second, 10.0)]
        ), patch("app.api.prompt_template", RecordingPrompt()):
            response = asyncio.run(chat(QueryRequest(query="Direct answer?")))
            events = asyncio.run(response_events(response))
        self.assertEqual(len(events[0][1]["sources"]), 1)
        self.assertNotIn("Unrelated rule", observed["context"])

    def test_answer_context_has_numbered_sources_and_stream_shows_excerpts(self):
        observed = {}

        class RecordingChain:
            async def astream(self, values):
                observed.update(values)
                yield SimpleNamespace(content="The limit is four feet [1].")

        class RecordingPrompt:
            def __or__(self, llm):
                return RecordingChain()

        docs = [Document(page_content="No fence may exceed four feet.", metadata={"source": "rules.pdf", "page": 7})]
        with patch("app.api.hybrid_search", return_value=docs), patch("app.api.prompt_template", RecordingPrompt()):
            response = asyncio.run(chat(QueryRequest(query="Fence limit?")))
            events = asyncio.run(response_events(response))

        self.assertIn("[1] rules.pdf, page 7", observed["context"])
        self.assertEqual(events[0][1]["sources"][0]["excerpt"], "No fence may exceed four feet.")

    def test_pdf_page_endpoint_serves_only_files_in_data_directory(self):
        with tempfile.TemporaryDirectory() as temporary_dir:
            root = Path(temporary_dir)
            (root / "rules.pdf").write_bytes(b"%PDF-1.4\n")
            with patch("app.api.DATA_DIR", root):
                with TestClient(app) as client:
                    found = client.get("/documents/rules.pdf")
                    missing = client.get("/documents/secret.pdf")

        self.assertEqual(found.status_code, 200)
        self.assertEqual(found.headers["content-type"], "application/pdf")
        self.assertEqual(missing.status_code, 404)

    def test_generation_error_is_sent_as_an_event(self):
        class BrokenChain:
            async def astream(self, values):
                raise RuntimeError("ollama unavailable")
                yield

        class BrokenPrompt:
            def __or__(self, llm):
                return BrokenChain()

        docs = [Document(page_content="Rule", metadata={"source": "rules.pdf", "page": 1})]
        with patch("app.api.hybrid_search", return_value=docs), patch("app.api.prompt_template", BrokenPrompt()):
            response = asyncio.run(chat(QueryRequest(query="What is the rule?")))
            events = asyncio.run(response_events(response))

        self.assertEqual(events[-1][0], "error")
        self.assertEqual(events[-1][1]["message"], "Answer generation failed.")

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
        self.assertGreaterEqual(float(retrieval_timing.split(",", 1)[0].split("=", 1)[1]), 0)
        self.assertIn("index;dur=", retrieval_timing)
        self.assertIn("vector;dur=", retrieval_timing)
        self.assertEqual(
            events,
            [
                ("sources", {"sources": [{"source": "zoning.pdf", "page": 2, "excerpt": "A"}, {"source": "rules.pdf", "page": 7, "excerpt": "B"}]}),
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
                ("token", {"text": "I don't know based on these documents."}),
                ("done", {}),
            ],
        )

    def test_excerpt_drops_only_the_source_header(self):
        docs = [
            Document(page_content="Source: rules.pdf | Page: 7\nFirst line.\nSecond line.", metadata={"source": "rules.pdf", "page": 7}),
            Document(page_content="Continued fact.\nMore text.", metadata={"source": "rules.pdf", "page": 7}),
        ]
        with patch("app.api.hybrid_search", return_value=docs), patch("app.api.prompt_template", FakePrompt()):
            response = asyncio.run(chat(QueryRequest(query="Fence limit?")))
            events = asyncio.run(response_events(response))

        excerpts = [source["excerpt"] for source in events[0][1]["sources"]]
        self.assertEqual(excerpts, ["First line.\nSecond line.", "Continued fact.\nMore text."])

    def test_response_reports_the_serving_llm_model(self):
        docs = [Document(page_content="Rule", metadata={"source": "rules.pdf", "page": 1})]
        with patch("app.api.hybrid_search", return_value=docs), patch("app.api.prompt_template", FakePrompt()), patch(
            "app.api.LLM_MODEL", "served-model:1b"
        ):
            response = asyncio.run(chat(QueryRequest(query="What is the rule?")))
        self.assertEqual(response.headers["X-LLM-Model"], "served-model:1b")


if __name__ == "__main__":
    unittest.main()
