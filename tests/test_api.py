import asyncio
import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from langchain_core.documents import Document
from fastapi.testclient import TestClient
from fastapi import HTTPException

from app.api import QueryRequest, app, chat
from app.answering import Conflict, detect_conflicts, verify_answer
from app.engine import SearchIndex


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


def event_data(events, name):
    return next(data for event, data in events if event == name)


class ChatEventsTests(unittest.TestCase):
    def setUp(self):
        clarification = patch("app.api.needs_clarification", return_value=False)
        clarification.start()
        self.addCleanup(clarification.stop)
        keyword = patch("app.api.bm25_search", return_value=[])
        keyword.start()
        self.addCleanup(keyword.stop)
        verifier = patch("app.api.verify_answer", new_callable=AsyncMock, return_value=True)
        verifier.start()
        self.addCleanup(verifier.stop)
        conflicts = patch("app.api.detect_conflicts", new_callable=AsyncMock, return_value=[])
        conflicts.start()
        self.addCleanup(conflicts.stop)

    def test_ambiguous_source_returns_clarification_without_model_answer(self):
        with patch("app.api.hybrid_search", return_value=[Document(page_content="fence", metadata={"source": "city-a.pdf", "page": 1})]), patch(
            "app.api.needs_clarification", return_value=True
        ):
            response = asyncio.run(chat(QueryRequest(query="What is the maximum fence height?")))
            events = asyncio.run(response_events(response))
        self.assertEqual([name for name, _ in events], ["status", "sources", "token", "timing", "done"])
        self.assertEqual(events[0][1]["stage"], "searching")
        self.assertEqual(event_data(events, "sources"), {"sources": []})
        self.assertEqual(event_data(events, "token"), {"text": "Which city or document do you mean?"})
        self.assertEqual(event_data(events, "timing")["drafts"], 0)

    def test_unverified_claim_is_not_sent_to_the_client(self):
        class DraftChain:
            async def astream(self, values):
                yield SimpleNamespace(content="The limit is 700 square feet [1].")

        class DraftPrompt:
            def __or__(self, llm):
                return DraftChain()

        class RejectingLLM:
            async def ainvoke(self, prompt):
                return SimpleNamespace(content='{"supported": false, "quote": ""}')

        doc = Document(page_content="The limit is 900 square feet.", metadata={"source": "rules.pdf", "page": 1})
        with patch("app.api.hybrid_search", return_value=[doc]), patch("app.api.prompt_template", DraftPrompt()), patch("app.api.llm", RejectingLLM()), patch("app.api.verify_answer", verify_answer):
            response = asyncio.run(chat(QueryRequest(query="What is the limit?")))
            events = asyncio.run(response_events(response))

        tokens = "".join(data["text"] for name, data in events if name == "token")
        self.assertEqual(tokens, "I don't know based on these documents.")

    def test_unverified_draft_can_be_replaced_by_a_verified_extractive_retry(self):
        class RetryChain:
            def __init__(self):
                self.calls = 0

            async def astream(self, values):
                self.calls += 1
                text = "The limit is 700 square feet [1]." if self.calls == 1 else "The limit is 900 square feet [1]."
                yield SimpleNamespace(content=text)

        chain = RetryChain()

        class RetryPrompt:
            def __or__(self, llm):
                return chain

        doc = Document(page_content="The limit is 900 square feet.", metadata={"source": "rules.pdf", "page": 1})
        with patch("app.api.hybrid_search", return_value=[doc]), patch("app.api.prompt_template", RetryPrompt()), patch("app.api.verify_answer", new_callable=AsyncMock, side_effect=[False, True]), patch("app.api.repair_answer", new_callable=AsyncMock, return_value=None):
            response = asyncio.run(chat(QueryRequest(query="What is the limit?")))
            events = asyncio.run(response_events(response))
        answer = "".join(data["text"] for name, data in events if name == "token")
        self.assertEqual(chain.calls, 2)
        self.assertIn("900 square feet [1]", answer)
        self.assertNotIn("700 square feet", answer)

    def test_named_district_explains_conflicting_general_rule_with_scope(self):
        class DraftChain:
            async def astream(self, values):
                yield SimpleNamespace(content="The guest house limit is 900 square feet [1].")

        class DraftPrompt:
            def __or__(self, llm):
                return DraftChain()

        class CheckingLLM:
            def __init__(self):
                self.responses = iter([
                    '{"supported": true, "quote": "Said guesthouse shall be limited to 900 square feet."}',
                    '{"conflicts": [{"candidate": 2, "primary_quote": "Said guesthouse shall be limited to 900 square feet.", "other_quote": "A freestanding guest house shall not exceed 700 square feet."}]}',
                ])

            async def ainvoke(self, prompt):
                return SimpleNamespace(content=next(self.responses))

        specific = Document(
            id="specific", page_content="Said guesthouse shall be limited to 900 square feet.",
            metadata={"source": "rules.pdf", "page": 54, "section": "6-2 R-2 Residential.", "jurisdiction": "Union City, Georgia", "version": "August 20, 2024, Rev."},
        )
        general = Document(
            id="general", page_content="A freestanding guest house shall not exceed 700 square feet.",
            metadata={"source": "rules.pdf", "page": 38, "section": "5-11 Guest houses.", "jurisdiction": "Union City, Georgia", "version": "August 20, 2024, Rev."},
        )
        with patch("app.api.hybrid_search", return_value=[specific, general]), patch(
            "app.api.bm25_search", return_value=[(specific, 28.0), (general, 26.0)]
        ), patch("app.api.prompt_template", DraftPrompt()), patch("app.api.llm", CheckingLLM()), patch("app.api.verify_answer", verify_answer), patch("app.api.detect_conflicts", detect_conflicts):
            response = asyncio.run(chat(QueryRequest(query="In R-2, how large may a guest house be?")))
            events = asyncio.run(response_events(response))

        self.assertEqual([source["page"] for source in event_data(events, "sources")["sources"]], [54, 38])
        answer = "".join(data["text"] for name, data in events if name == "token")
        self.assertIn("900 square feet", answer)
        self.assertIn("700 square feet", answer)
        self.assertIn("Jurisdiction: Union City, Georgia", answer)
        self.assertIn("District: R-2", answer)
        self.assertIn("Document version: August 20, 2024, Rev.", answer)

    def test_wrong_citation_is_repaired_only_after_support_check(self):
        class DraftChain:
            async def astream(self, values):
                yield SimpleNamespace(content="No more than five vehicle visits per day are permitted [2].")

        class DraftPrompt:
            def __or__(self, llm):
                return DraftChain()

        class CheckingLLM:
            def __init__(self):
                self.responses = iter([
                    '{"supported": false, "quote": "No more than 10 visits per day."}',
                    '{"supported": false, "quote": "No more than 10 visits per day."}',
                    '{"supported": true, "quote": "No more than five vehicle visits per day."}',
                    '{"supported": false, "quote": "No more than 10 visits per day."}',
                    '{"supported": false, "quote": "No more than 10 visits per day."}',
                ])

            async def ainvoke(self, prompt):
                return SimpleNamespace(content=next(self.responses))

        docs = [
            Document(id="five", page_content="No more than five vehicle visits per day.", metadata={"source": "rules.pdf", "page": 1}),
            Document(id="ten", page_content="No more than 10 visits per day.", metadata={"source": "rules.pdf", "page": 2}),
        ]
        with patch("app.api.hybrid_search", return_value=docs), patch("app.api.prompt_template", DraftPrompt()), patch("app.api.llm", CheckingLLM()), patch("app.api.verify_answer", verify_answer):
            response = asyncio.run(chat(QueryRequest(query="How many vehicle visits per day?")))
            events = asyncio.run(response_events(response))

        answer = "".join(data["text"] for name, data in events if name == "token")
        self.assertIn("five vehicle visits per day are permitted [1]", answer)
        self.assertNotIn("permitted [2]", answer)

    def test_scope_uses_the_passage_cited_by_the_verified_answer(self):
        class DraftChain:
            async def astream(self, values):
                yield SimpleNamespace(content="The limit is 900 square feet [2].")

        class DraftPrompt:
            def __or__(self, llm):
                return DraftChain()

        docs = [
            Document(id="wrong", page_content="The limit is 700 square feet.", metadata={"source": "general.pdf", "page": 1, "jurisdiction": "Other City"}),
            Document(id="right", page_content="The limit is 900 square feet.", metadata={"source": "district.pdf", "page": 2, "jurisdiction": "Union City", "section": "6-2 R-2 Residential.", "version": "2024"}),
        ]
        with patch("app.api.hybrid_search", return_value=docs), patch("app.api.select_context", return_value=docs), patch("app.api.prompt_template", DraftPrompt()):
            response = asyncio.run(chat(QueryRequest(query="R-2 limit?")))
            events = asyncio.run(response_events(response))
        answer = "".join(data["text"] for name, data in events if name == "token")
        self.assertIn("Jurisdiction: Union City | District: R-2 | Document version: 2024 | Source: district.pdf", answer)

    def test_different_document_versions_require_clarification_when_unresolved(self):
        class DraftChain:
            async def astream(self, values):
                yield SimpleNamespace(content="The limit is 900 square feet [1].")

        class DraftPrompt:
            def __or__(self, llm):
                return DraftChain()

        older = Document(id="old", page_content="The limit is 900 square feet.", metadata={"source": "old.pdf", "page": 1, "section": "6-2 R-2 Residential.", "jurisdiction": "Union City", "version": "2024"})
        newer = Document(id="new", page_content="The limit is 700 square feet.", metadata={"source": "new.pdf", "page": 1, "section": "6-2 R-2 Residential.", "jurisdiction": "Union City", "version": "2025"})
        with patch("app.api.hybrid_search", return_value=[older]), patch("app.api.bm25_search", return_value=[(newer, 8.0)]), patch("app.api.prompt_template", DraftPrompt()), patch("app.api.detect_conflicts", new_callable=AsyncMock, return_value=[Conflict(newer, "900 square feet", "700 square feet")]):
            response = asyncio.run(chat(QueryRequest(query="What is the R-2 limit?")))
            events = asyncio.run(response_events(response))
        answer = "".join(data["text"] for name, data in events if name == "token")
        self.assertIn("Which jurisdiction, district, or document version", answer)
        self.assertNotIn("900 square feet", answer)

    def test_conflict_is_answered_from_the_other_passage_when_the_question_names_its_section(self):
        class DraftChain:
            async def astream(self, values):
                yield SimpleNamespace(content="The limit is 700 square feet [1].")

        class DraftPrompt:
            def __or__(self, llm):
                return DraftChain()

        general = Document(id="gen", page_content="Guest houses are limited to 700 square feet.", metadata={"source": "code.pdf", "page": 38, "section": "5-4 Accessory Uses", "jurisdiction": "Union City"})
        district = Document(id="r2", page_content="In R-2, guest houses are limited to 900 square feet.", metadata={"source": "code.pdf", "page": 54, "section": "6-3 R-2 Residential", "jurisdiction": "Union City"})
        conflict = Conflict(district, "Guest houses are limited to 700 square feet", "In R-2, guest houses are limited to 900 square feet")
        with patch("app.api.hybrid_search", return_value=[general]), patch("app.api.bm25_search", return_value=[(district, 8.0)]), patch("app.api.prompt_template", DraftPrompt()), patch("app.api.detect_conflicts", new_callable=AsyncMock, return_value=[conflict]):
            response = asyncio.run(chat(QueryRequest(query="What is the guest house limit in R-2?")))
            events = asyncio.run(response_events(response))
        sources = event_data(events, "sources")["sources"]
        answer = "".join(data["text"] for name, data in events if name == "token")
        self.assertEqual([(source["source"], source["page"]) for source in sources], [("code.pdf", 38), ("code.pdf", 54)])
        self.assertTrue(answer.startswith("Jurisdiction: Union City | District: R-2"))
        self.assertIn('6-3 R-2 Residential states "In R-2, guest houses are limited to 900 square feet" [2].', answer)
        self.assertIn("The named 6-3 R-2 Residential provision applies to this question [2].", answer)
        self.assertNotIn("Which jurisdiction", answer)

    def test_progress_status_precedes_sources_and_timing_precedes_done(self):
        docs = [Document(page_content="Rule [1].", metadata={"source": "rules.pdf", "page": 1})]
        with patch("app.api.hybrid_search", return_value=docs), patch("app.api.prompt_template", FakePrompt()):
            events = asyncio.run(response_events(asyncio.run(chat(QueryRequest(query="What is the rule?")))))
        names = [event for event, _ in events]
        self.assertEqual(names, ["status", "status", "status", "status", "sources", "token", "timing", "done"])
        self.assertEqual([data["stage"] for event, data in events if event == "status"], ["searching", "drafting", "checking", "comparing"])
        self.assertTrue(all(data["text"] for event, data in events if event == "status"))

    def test_timing_reports_stage_durations_and_model_calls(self):
        class CallingLLM:
            async def ainvoke(self, prompt):
                return SimpleNamespace(content="{}")

        async def verify(answer, passages, llm):
            await llm.ainvoke("check one")
            await llm.ainvoke("check two")
            return True

        docs = [Document(page_content="Rule [1].", metadata={"source": "rules.pdf", "page": 1})]
        with patch("app.api.hybrid_search", return_value=docs), patch("app.api.prompt_template", FakePrompt()), patch(
            "app.api.llm", CallingLLM()
        ), patch("app.api.verify_answer", verify):
            events = asyncio.run(response_events(asyncio.run(chat(QueryRequest(query="What is the rule?")))))
        timing = event_data(events, "timing")
        self.assertEqual(set(timing), {
            "index_ms", "rewrite_ms", "retrieval_ms", "vector_ms", "keyword_ms", "fusion_ms", "ambiguity_ms",
            "context_ms", "draft_ms", "check_ms", "conflict_ms", "answer_ms", "drafts", "check_calls",
        })
        self.assertEqual((timing["drafts"], timing["check_calls"]), (1, 2))
        self.assertTrue(all(timing[key] >= 0 for key in ("draft_ms", "check_ms", "conflict_ms", "answer_ms")))

    def test_search_failure_is_sent_as_an_error_event(self):
        with patch("app.api.hybrid_search", side_effect=ConnectionError("embedding service down")):
            response = asyncio.run(chat(QueryRequest(query="What is the rule?")))
            events = asyncio.run(response_events(response))
        self.assertEqual([name for name, _ in events], ["status", "error"])
        self.assertEqual(events[-1][1]["message"], "Answer generation failed.")

    def test_conflict_keyword_search_runs_off_the_event_loop(self):
        import threading

        threads = []

        def keyword_search(query, index, k=5, sources=None):
            threads.append((k, threading.current_thread() is threading.main_thread()))
            return []

        docs = [Document(page_content="Rule [1].", metadata={"source": "rules.pdf", "page": 1})]
        with patch("app.api.hybrid_search", return_value=docs), patch("app.api.bm25_search", keyword_search), patch("app.api.prompt_template", FakePrompt()):
            asyncio.run(response_events(asyncio.run(chat(QueryRequest(query="What is the rule?")))))
        self.assertIn((30, False), threads)

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
        self.assertEqual(len(event_data(events, "sources")["sources"]), 1)
        self.assertNotIn("Unrelated rule", observed["context"])

    def test_named_section_sends_its_keyword_leader_without_conflicting_passages(self):
        district = Document(
            id="district", page_content="Guest house: 900 square feet.",
            metadata={"source": "rules.pdf", "page": 2, "section": "6-2 R-2 Residential."},
        )
        general = Document(
            id="general", page_content="Guest house: 700 square feet.",
            metadata={"source": "rules.pdf", "page": 1},
        )
        other = Document(
            id="other", page_content="Guest house: 800 square feet.",
            metadata={"source": "rules.pdf", "page": 3, "section": "6-3 R-3 Residential."},
        )
        observed = {}

        class RecordingChain:
            async def astream(self, values):
                observed.update(values)
                yield SimpleNamespace(content="900 square feet [1].")

        class RecordingPrompt:
            def __or__(self, llm):
                return RecordingChain()

        with patch("app.api.hybrid_search", return_value=[district, general, other]), patch(
            "app.api.bm25_search", return_value=[(district, 28.0), (other, 26.0)]
        ), patch("app.api.prompt_template", RecordingPrompt()):
            response = asyncio.run(chat(QueryRequest(query="In R-2, how large may a guest house be?")))
            events = asyncio.run(response_events(response))

        self.assertEqual([(source["page"]) for source in event_data(events, "sources")["sources"]], [2])
        self.assertIn("900 square feet", observed["context"])
        self.assertNotIn("700 square feet", observed["context"])

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
        self.assertIn("only valid citation labels for this answer are: [1]", observed.get("citation_instruction", ""))
        self.assertEqual(event_data(events, "sources")["sources"][0]["excerpt"], "No fence may exceed four feet.")

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

    def test_document_catalog_reports_low_text_pages(self):
        docs = [
            Document(page_content="Some text", metadata={"source": "a.pdf", "page": 1, "low_text": True}),
            Document(page_content="More text", metadata={"source": "a.pdf", "page": 2, "low_text": False}),
            Document(page_content="Other", metadata={"source": "b.pdf", "page": 3}),
        ]
        with tempfile.TemporaryDirectory() as temporary_dir:
            report = Path(temporary_dir) / "pages.json"
            with patch("app.api.search_index.get", return_value=SearchIndex(docs, None)), patch("app.api.PAGE_REPORT_PATH", report):
                with TestClient(app) as client:
                    without_report = client.get("/documents").json()
                    # The ingestion report also covers unreadable pages that produced no chunks.
                    report.write_text(json.dumps({"a.pdf": {"pages": 4, "low_text_pages": [1, 4], "blank_pages": [3]}}), encoding="utf-8")
                    with_report = client.get("/documents").json()
        self.assertEqual(without_report, {"documents": [
            {"name": "a.pdf", "pages": 2, "low_text_pages": [1]},
            {"name": "b.pdf", "pages": 3, "low_text_pages": []},
        ]})
        self.assertEqual(with_report, {"documents": [
            {"name": "a.pdf", "pages": 4, "low_text_pages": [1, 4]},
            {"name": "b.pdf", "pages": 3, "low_text_pages": []},
        ]})

    def test_selected_documents_scope_search_and_conflict_candidates(self):
        one = Document(id="one", page_content="One rule", metadata={"source": "a.pdf", "page": 1})
        two = Document(id="two", page_content="Two rule", metadata={"source": "b.pdf", "page": 1})
        index = SearchIndex([one, two], None)
        with patch("app.api.search_index.get", return_value=index), patch("app.api.hybrid_search", return_value=[two]) as search, patch("app.api.prompt_template", FakePrompt()), patch("app.api.bm25_search", return_value=[]) as keyword:
            events = asyncio.run(response_events(asyncio.run(chat(QueryRequest(query="Which rule?", documents=["b.pdf"])))))
        self.assertEqual(event_data(events, "sources")["sources"][0]["source"], "b.pdf")
        self.assertEqual(search.call_args.kwargs["sources"], {"b.pdf"})
        # One shared keyword index is scored, then filtered to the selection.
        self.assertIs(search.call_args.kwargs["index"], index)
        self.assertTrue(keyword.call_args_list)
        self.assertTrue(all(call.kwargs["sources"] == {"b.pdf"} for call in keyword.call_args_list))

        with patch("app.api.search_index.get", return_value=index):
            with self.assertRaises(HTTPException) as error:
                asyncio.run(chat(QueryRequest(query="Which rule?", documents=["missing.pdf"])))
        self.assertEqual(error.exception.status_code, 422)

    def test_follow_up_uses_history_for_search_and_generation(self):
        doc = Document(page_content="R-2 permits 900 square feet.", metadata={"source": "rules.pdf", "page": 1})
        seen = {}

        class RecordingChain:
            async def astream(self, values):
                seen.update(values)
                yield SimpleNamespace(content="900 square feet [1].")

        class RecordingPrompt:
            def __or__(self, llm):
                return RecordingChain()

        with patch("app.api.contextualize_query", new_callable=AsyncMock, return_value="R-2 guest house size") as rewrite, patch("app.api.hybrid_search", return_value=[doc]) as search, patch("app.api.prompt_template", RecordingPrompt()):
            response = asyncio.run(chat(QueryRequest(query="How large?", history=[{"role": "user", "text": "What about R-2 guest houses?"}, {"role": "assistant", "text": "R-2 permits them."}])))
            asyncio.run(response_events(response))
        self.assertEqual(search.call_args.args[0], "R-2 guest house size")
        self.assertIn("What about R-2 guest houses?", seen["history"])
        self.assertEqual(seen["question"], "How large?")
        rewrite.assert_awaited_once()

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
        timing = event_data(events, "timing")
        self.assertTrue(all(timing[f"{stage}_ms"] >= 0 for stage in ("retrieval", "index", "vector", "keyword", "fusion")))
        self.assertGreaterEqual(timing["retrieval_ms"], timing["index_ms"])
        self.assertEqual(
            [(event, data) for event, data in events if event not in {"status", "timing"}],
            [
                ("sources", {"sources": [{"source": "zoning.pdf", "page": 2, "excerpt": "A"}, {"source": "rules.pdf", "page": 7, "excerpt": "B"}]}),
                ("token", {"text": "Jurisdiction: not identified | District: not specified | Document version: not identified | Source: zoning.pdf\nFirst answer"}),
                ("done", {}),
            ],
        )

    def test_empty_search_uses_the_same_event_protocol(self):
        with patch("app.api.hybrid_search", return_value=[]):
            response = asyncio.run(chat(QueryRequest(query="missing")))
            events = asyncio.run(response_events(response))

        self.assertEqual(response.media_type, "text/event-stream")
        self.assertEqual([name for name, _ in events], ["status", "sources", "token", "timing", "done"])
        self.assertEqual(event_data(events, "sources"), {"sources": []})
        self.assertEqual(event_data(events, "token"), {"text": "I don't know based on these documents."})

    def test_excerpt_drops_only_the_source_header(self):
        docs = [
            Document(page_content="Source: rules.pdf | Page: 7\nFirst line.\nSecond line.", metadata={"source": "rules.pdf", "page": 7}),
            Document(page_content="Continued fact.\nMore text.", metadata={"source": "rules.pdf", "page": 7}),
        ]
        with patch("app.api.hybrid_search", return_value=docs), patch("app.api.prompt_template", FakePrompt()):
            response = asyncio.run(chat(QueryRequest(query="Fence limit?")))
            events = asyncio.run(response_events(response))

        excerpts = [source["excerpt"] for source in event_data(events, "sources")["sources"]]
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
