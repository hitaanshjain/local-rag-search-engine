import json

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from app.engine import get_vector_db, get_llm, get_rag_prompt, hybrid_search

app = FastAPI(title="Local RAG API", version="1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = get_vector_db()
llm = get_llm()
prompt_template = get_rag_prompt()


class QueryRequest(BaseModel):
    query: str


def sse_event(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.post("/chat")
async def chat(request: QueryRequest):
    results = hybrid_search(request.query, db, k=3)

    async def stream_generator():
        sources = [
            {"source": doc.metadata.get("source"), "page": doc.metadata.get("page")}
            for doc in results
        ]
        yield sse_event("sources", {"sources": sources})
        if not results:
            yield sse_event("token", {"text": "I couldn't find any relevant information."})
            yield sse_event("done", {})
            return

        context_text = "\n\n".join(doc.page_content for doc in results)
        chain = prompt_template | llm
        async for chunk in chain.astream(
            {"context": context_text, "question": request.query}
        ):
            yield sse_event("token", {"text": chunk.content})
        yield sse_event("done", {})

    return StreamingResponse(
        stream_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache"},
    )
