from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from app.engine import get_vector_db, get_llm, get_rag_prompt

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

@app.post("/chat")
async def chat(request: QueryRequest):
    results = db.similarity_search(request.query, k=2)
    if not results:
        return {"answer": "I couldn't find any relevant information."}
    
    context_text = "\n\n".join([doc.page_content for doc in results])
    
    async def stream_generator():
        chain = prompt_template | llm
        async for chunk in chain.astream({"context": context_text, "question": request.query}):
            yield chunk.content

    return StreamingResponse(stream_generator(), media_type="text/event-stream")