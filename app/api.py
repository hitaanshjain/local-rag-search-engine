import json
import logging
import os
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from app.answering import ABSTAIN, cited_claims, collect_conflict_candidates, detect_conflicts, format_scope, repair_answer, resolve_conflict, verify_answer
from app.engine import (
    LLM_MODEL, SearchIndexCache, bm25_search, get_vector_db, get_llm, get_rag_prompt,
    hybrid_search, needs_clarification, select_context,
)

app = FastAPI(title="Local RAG API", version="1.0")
logger = logging.getLogger(__name__)
DATA_DIR = Path(__file__).resolve().parents[1] / "data"

app.add_middleware(
    CORSMiddleware,
    allow_origins=[os.getenv("FRONTEND_ORIGIN", "http://localhost:3000")],
    allow_credentials=False,
    allow_methods=["POST"],
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


class QueryRequest(BaseModel):
    query: str


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


@app.post("/chat")
async def chat(request: QueryRequest):
    retrieval_started = perf_counter()
    index = await run_in_threadpool(search_index.get)
    index_ms = (perf_counter() - retrieval_started) * 1000
    stage_times = {}
    results = await run_in_threadpool(hybrid_search, request.query, db, k=3, index=index, timings=stage_times)
    clarification_started = perf_counter()
    clarify = await run_in_threadpool(needs_clarification, request.query, index)
    ambiguity_ms = (perf_counter() - clarification_started) * 1000
    context_started = perf_counter()
    keyword_leaders = (
        await run_in_threadpool(bm25_search, request.query, index, k=2)
        if results and not clarify else []
    )
    context_results = select_context(results, keyword_leaders, request.query)
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

            async def checked_draft(instruction: str) -> str:
                parts = []
                async for chunk in chain.astream({
                    "context": context_text, "question": request.query, "citation_instruction": instruction,
                }):
                    parts.append(chunk.content)
                candidate = "".join(parts).strip()
                if candidate != ABSTAIN and not await verify_answer(candidate, context_results, llm):
                    candidate = await repair_answer(candidate, context_results, llm) or ABSTAIN
                return candidate

            draft = await checked_draft(citation_instruction)
            if draft == ABSTAIN:
                draft = await checked_draft(
                    "Answer in the fewest words possible using the passage's exact terms and number spelling. "
                    "Do not infer extra processes or obligations. " + citation_instruction
                )

            shown_docs = list(context_results)
            claims = cited_claims(draft, len(context_results)) if draft != ABSTAIN else None
            primary_number = claims[0][1][0] if claims else 1
            primary_doc = context_results[primary_number - 1]
            conflict_notes = []
            unresolved = False
            if draft != ABSTAIN:
                keyword_candidates = bm25_search(request.query, index, k=30)
                candidate_docs = collect_conflict_candidates(primary_doc, results, keyword_candidates)
                conflicts = await detect_conflicts(request.query, primary_doc, candidate_docs, llm, draft)
                for conflict in conflicts:
                    decision = resolve_conflict(request.query, primary_doc, conflict.other)
                    if decision != "primary":
                        unresolved = True
                        break
                    if conflict.other not in shown_docs:
                        shown_docs.append(conflict.other)
                    other_number = shown_docs.index(conflict.other) + 1
                    main_section = primary_doc.metadata.get("section") or "the selected section"
                    other_section = conflict.other.metadata.get("section") or conflict.other.metadata.get("source") or "another source"
                    main_quote = " ".join(conflict.primary_quote.split())
                    other_quote = " ".join(conflict.other_quote.split())
                    conflict_notes.append(
                        f'Conflicting provisions: {main_section} states "{main_quote}" [{primary_number}]; '
                        f'{other_section} states "{other_quote}" [{other_number}]. '
                        f"The named {main_section} provision applies to this question [{primary_number}]."
                    )

            sources = [
                {"source": doc.metadata.get("source"), "page": doc.metadata.get("page"),
                 "excerpt": excerpt(doc.page_content)}
                for doc in shown_docs
            ]
            yield sse_event("sources", {"sources": sources})
            if unresolved:
                answer = "The retrieved provisions conflict. Which jurisdiction, district, or document version should I use?"
            elif draft == ABSTAIN:
                answer = ABSTAIN
            else:
                answer = f"{format_scope(primary_doc, request.query)}\n{draft}"
                if conflict_notes:
                    answer += "\n" + "\n".join(conflict_notes)
            yield sse_event("token", {"text": answer})
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
