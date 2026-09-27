import json
import logging
import os
from pathlib import Path
from time import perf_counter
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
from app.answering import ABSTAIN, cited_claims, collect_conflict_candidates, detect_conflicts, format_scope, repair_answer, resolve_conflict, verify_answer
from app.conversation import contextualize_query, format_history
from app.engine import (
    LLM_MODEL, SearchIndexCache, bm25_search, get_vector_db, get_llm, get_rag_prompt,
    hybrid_search, needs_clarification, select_context, filter_search_index,
)

app = FastAPI(title="Local RAG API", version="1.0")
logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    expose_headers=["Server-Timing"],
)

db = get_vector_db()
search_index = SearchIndexCache(db)
llm = get_llm()
prompt_template = get_rag_prompt()


def excerpt(text: str) -> str:
    if text.startswith("Source: "):
        text = text.split("\n", 1)[-1]
    return text.strip()[:500]


STATUS_TEXT = {
    "drafting": "Drafting an answer…",
    "checking": "Checking each claim against its cited passage…",
    "comparing": "Comparing related rules…",
}


def status_event(stage: str) -> str:
    return sse_event("status", {"stage": stage, "text": STATUS_TEXT[stage]})


class CountingLLM:
    """Count the model calls made while checking one answer."""

    def __init__(self, llm):
        self.llm = llm
        self.calls = 0

    async def ainvoke(self, *args, **kwargs):
        self.calls += 1
        return await self.llm.ainvoke(*args, **kwargs)


class ChatTurn(BaseModel):
    role: Literal["user", "assistant"]
    text: str = Field(max_length=4000)


class QueryRequest(BaseModel):
    query: str
    documents: list[str] | None = None
    history: list[ChatTurn] = Field(default_factory=list, max_length=12)


def sse_event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/documents/{filename}")
def document(filename: str):
    if filename != Path(filename).name or not filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=404)
    root = DATA_DIR.resolve()
    path = (root / filename).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404)
    return FileResponse(path, media_type="application/pdf", content_disposition_type="inline")


@app.get("/documents")
async def list_documents():
    index = await run_in_threadpool(search_index.get)
    catalog = {}
    for doc in index.documents:
        name = doc.metadata.get("source")
        if not name:
            continue
        entry = catalog.setdefault(name, {"name": name, "pages": 0, "low_text_pages": set()})
        page = doc.metadata.get("page")
        if isinstance(page, int):
            entry["pages"] = max(entry["pages"], page)
            if doc.metadata.get("low_text"):
                entry["low_text_pages"].add(page)
    return {"documents": [
        {**entry, "low_text_pages": sorted(entry["low_text_pages"])}
        for _, entry in sorted(catalog.items())
    ]}


@app.post("/chat")
async def chat(request: QueryRequest):
    retrieval_started = perf_counter()
    index = await run_in_threadpool(search_index.get)
    index_ms = (perf_counter() - retrieval_started) * 1000
    selected = None
    if request.documents is not None:
        selected = set(request.documents)
        available = {doc.metadata.get("source") for doc in index.documents}
        if not selected or not selected <= available:
            raise HTTPException(status_code=422, detail="Select one or more indexed documents.")
        if selected == available:
            selected = None
    scoped_index = await run_in_threadpool(filter_search_index, index, selected) if selected is not None else index
    history = [turn.model_dump() for turn in request.history]
    search_query = await contextualize_query(request.query, history, llm) if history else request.query
    stage_times = {}
    results = await run_in_threadpool(hybrid_search, search_query, db, k=3, index=scoped_index, timings=stage_times, sources=selected)
    clarification_started = perf_counter()
    clarify = await run_in_threadpool(needs_clarification, search_query, scoped_index)
    ambiguity_ms = (perf_counter() - clarification_started) * 1000
    context_started = perf_counter()
    keyword_leaders = (
        await run_in_threadpool(bm25_search, search_query, scoped_index, k=2)
        if results and not clarify else []
    )
    context_results = select_context(results, keyword_leaders, search_query)
    context_ms = (perf_counter() - context_started) * 1000
    retrieval_ms = (perf_counter() - retrieval_started) * 1000

    async def stream_generator():
        if clarify:
            yield sse_event("sources", {"sources": []})
            yield sse_event("token", {"text": "Which city or document do you mean?"})
            yield sse_event("done", {})
            return
        if not context_results:
            yield sse_event("sources", {"sources": []})
            yield sse_event("token", {"text": ABSTAIN})
            yield sse_event("done", {})
            return

        context_text = "\n\n".join(
            f"[{number}] {doc.metadata.get('source')}, page {doc.metadata.get('page')}"
            f"{', section ' + doc.metadata['section'] if doc.metadata.get('section') else ''}\n"
            f"{doc.page_content}"
            for number, doc in enumerate(context_results, start=1)
        )
        chain = prompt_template | llm
        try:
            citation_instruction = (
                "Give a short answer using only facts explicitly supported by the numbered passages. "
                "The only valid citation labels for this answer are: [1]. Cite the label of the supporting "
                "passage immediately after each factual sentence. Numbers inside a passage are part of its "
                "text, not citation labels. Never cite a passage that does not state the answer."
                if len(context_results) == 1 else
                "Give a short answer using only facts explicitly supported by the numbered passages. "
                "Add the number of the passage that states the answer in square brackets immediately after "
                "each factual sentence, for example [1]. Never cite a passage that does not state the answer."
            )

            answer_started = perf_counter()
            checker = CountingLLM(llm)
            timing = {"draft_ms": 0.0, "check_ms": 0.0, "conflict_ms": 0.0, "drafts": 0}

            async def write_draft(instruction: str) -> str:
                started = perf_counter()
                parts = []
                async for chunk in chain.astream({
                    "context": context_text, "question": request.query, "history": format_history(history), "citation_instruction": instruction,
                }):
                    parts.append(chunk.content)
                timing["draft_ms"] += (perf_counter() - started) * 1000
                timing["drafts"] += 1
                return "".join(parts).strip()

            async def check_draft(candidate: str) -> str:
                started = perf_counter()
                if candidate != ABSTAIN and not await verify_answer(candidate, context_results, checker):
                    candidate = await repair_answer(candidate, context_results, checker) or ABSTAIN
                timing["check_ms"] += (perf_counter() - started) * 1000
                return candidate

            yield status_event("drafting")
            candidate = await write_draft(citation_instruction)
            yield status_event("checking")
            draft = await check_draft(candidate)
            if draft == ABSTAIN:
                yield status_event("drafting")
                candidate = await write_draft(
                    "Answer in the fewest words possible using the passage's exact terms and number spelling. "
                    "Do not infer extra processes or obligations. " + citation_instruction
                )
                yield status_event("checking")
                draft = await check_draft(candidate)

            shown_docs = list(context_results)
            claims = cited_claims(draft, len(context_results)) if draft != ABSTAIN else None
            primary_number = claims[0][1][0] if claims else 1
            primary_doc = context_results[primary_number - 1]
            conflict_notes = []
            unresolved = False
            scope_doc = primary_doc
            if draft != ABSTAIN:
                yield status_event("comparing")
                started = perf_counter()
                keyword_candidates = await run_in_threadpool(bm25_search, search_query, scoped_index, k=30)
                candidate_docs = collect_conflict_candidates(primary_doc, results, keyword_candidates)
                conflicts = await detect_conflicts(search_query, primary_doc, candidate_docs, checker, draft)
                timing["conflict_ms"] = (perf_counter() - started) * 1000
                for conflict in conflicts:
                    decision = resolve_conflict(search_query, primary_doc, conflict.other)
                    if decision is None:
                        unresolved = True
                        break
                    if conflict.other not in shown_docs:
                        shown_docs.append(conflict.other)
                    other_number = shown_docs.index(conflict.other) + 1
                    main_section = primary_doc.metadata.get("section") or "the selected section"
                    other_section = conflict.other.metadata.get("section") or conflict.other.metadata.get("source") or "another source"
                    main_quote = " ".join(conflict.primary_quote.split())
                    other_quote = " ".join(conflict.other_quote.split())
                    notes = (
                        f'Conflicting provisions: {main_section} states "{main_quote}" [{primary_number}]; '
                        f'{other_section} states "{other_quote}" [{other_number}]. '
                    )
                    if decision == "other":
                        # The question names the other passage's scope, so answer from its verified quote.
                        scope_doc = conflict.other
                        draft = f'{other_section} states "{other_quote}" [{other_number}].'
                        conflict_notes = [notes + f"The named {other_section} provision applies to this question [{other_number}]."]
                        break
                    conflict_notes.append(
                        notes + f"The named {main_section} provision applies to this question [{primary_number}]."
                    )

            sources = [
                {"source": doc.metadata.get("source"), "page": doc.metadata.get("page"),
                 "excerpt": excerpt(doc.page_content),
                 **({"low_text": True} if doc.metadata.get("low_text") else {}),
                 **({"extraction_method": doc.metadata["extraction_method"]} if doc.metadata.get("extraction_method") else {})}
                for doc in shown_docs
            ]
            yield sse_event("sources", {"sources": sources})
            if unresolved:
                answer = "The retrieved provisions conflict. Which jurisdiction, district, or document version should I use?"
            elif draft == ABSTAIN:
                answer = ABSTAIN
            else:
                answer = f"{format_scope(scope_doc, search_query)}\n{draft}"
                if conflict_notes:
                    answer += "\n" + "\n".join(conflict_notes)
            yield sse_event("token", {"text": answer})
            timing["answer_ms"] = (perf_counter() - answer_started) * 1000
            timing["check_calls"] = checker.calls
            logger.info("Answer timing: %s", timing)
            yield sse_event("timing", timing)
        except Exception:
            logger.exception("Chat answer verification or conflict check failed")
            yield sse_event("error", {"message": "Answer generation failed."})
            return
        yield sse_event("done", {})

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-LLM-Model": LLM_MODEL,
            "Server-Timing": ", ".join(
                [f"retrieval;dur={retrieval_ms:.3f}", f"index;dur={index_ms:.3f}"]
                + [f"{stage};dur={stage_times.get(stage, 0):.3f}" for stage in ("vector", "keyword", "fusion")]
                + [f"ambiguity;dur={ambiguity_ms:.3f}"]
                + [f"context;dur={context_ms:.3f}"]
            ),
        },
    )
