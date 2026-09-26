import json
import os
from pathlib import Path
from time import perf_counter

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from app.engine import (
    LLM_MODEL, SearchIndexCache, bm25_search, get_vector_db, get_llm, get_rag_prompt,
    hybrid_search, needs_clarification, select_context,
)

app = FastAPI(title="Local RAG API", version="1.0")
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
    context_results = select_context(results, keyword_leaders)
    context_ms = (perf_counter() - context_started) * 1000
    retrieval_ms = (perf_counter() - retrieval_started) * 1000

    async def stream_generator():
        sources = [
            {"source": doc.metadata.get("source"), "page": doc.metadata.get("page"),
             "excerpt": excerpt(doc.page_content)}
            for doc in context_results
        ]
        yield sse_event("sources", {"sources": [] if clarify else sources})
        if clarify:
            yield sse_event("token", {"text": "Which city or document do you mean?"})
            yield sse_event("done", {})
            return
        if not context_results:
            yield sse_event("token", {"text": "I don't know based on these documents."})
            yield sse_event("done", {})
            return

        context_text = "\n\n".join(
            f"[{number}] {doc.metadata.get('source')}, page {doc.metadata.get('page')}\n{doc.page_content}"
            for number, doc in enumerate(context_results, start=1)
        )
        chain = prompt_template | llm
        try:
            async for chunk in chain.astream(
                {"context": context_text, "question": request.query}
            ):
                yield sse_event("token", {"text": chunk.content})
        except Exception:
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
