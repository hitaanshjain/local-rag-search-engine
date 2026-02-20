from fastapi import FastAPI
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
    results = db.similarity_search(request.query, k=5)
    if not results:
        return {"answer": "I couldn't find any relevant information.", "sources": []}
        
    context_text = "\n\n".join([doc.page_content for doc in results])
    
    chain = prompt_template | llm
    response = chain.invoke({"context": context_text, "question": request.query})
    
    return {"answer": response.content, "sources": [doc.metadata for doc in results]}