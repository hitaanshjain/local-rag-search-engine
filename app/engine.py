import os
import re
from dataclasses import dataclass
from typing import Any

from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DB_PATH = "./chroma_db"
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = "llama3.2:1b"


def get_vector_db() -> Chroma:
    """Initializes and returns the Chroma vector database connection."""
    print("Initializing Vector DB...")
    embedding_function = OllamaEmbeddings(
        model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL
    )
    return Chroma(persist_directory=DB_PATH, embedding_function=embedding_function)


def get_llm() -> ChatOllama:
    """Initializes and returns the local LLM connection."""
    print("Initializing LLM...")
    return ChatOllama(model=LLM_MODEL, base_url=OLLAMA_BASE_URL)


def get_rag_prompt() -> ChatPromptTemplate:
    """Returns the standardized prompt template for RAG queries."""
    return ChatPromptTemplate.from_template("""
    You are a helpful AI assistant. You are given a context that may contain information from multiple different documents.
    Your goal is to answer the user's question accurately.

    Instructions:
    1. Look for the specific answer in the context below.
    2. If the context contains information about different topics (e.g., different games or subjects), ONLY use the part that is relevant to the user's question.
    3. Do not mention "the provided context" or "documents" in your answer. Just answer the question directly.

    Context:
    {context}

    Question: {question}
    """)


def tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


@dataclass
class SearchIndex:
    documents: list[Document]
    bm25: Any | None


def build_search_index(db: Chroma) -> SearchIndex:
    stored = db.get(include=["documents", "metadatas"])
    documents = [
        Document(id=chunk_id, page_content=content, metadata=metadata or {})
        for chunk_id, content, metadata in zip(
            stored["ids"], stored["documents"], stored["metadatas"]
        )
        if content is not None
    ]
    bm25 = BM25Okapi([tokenize(doc.page_content) for doc in documents]) if documents else None
    return SearchIndex(documents=documents, bm25=bm25)


def bm25_search(query: str, index: SearchIndex, k: int = 5) -> list[tuple[Document, float]]:
    if index.bm25 is None or not tokenize(query):
        return []
    scores = index.bm25.get_scores(tokenize(query))
    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
    return [(index.documents[i], float(score)) for i, score in ranked[:k] if score > 0]


def fuse_results(
    vector_results: list[tuple[Document, float]],
    keyword_results: list[tuple[Document, float]],
    k: int = 5,
    vector_weight: float = 0.5,
    keyword_weight: float = 0.5,
) -> list[Document]:
    if vector_weight < 0 or keyword_weight < 0 or vector_weight + keyword_weight == 0:
        raise ValueError("Retrieval weights must be nonnegative and at least one must be positive")

    fused: dict[str, dict[str, Any]] = {}
    max_distance = max((distance for _, distance in vector_results), default=1)
    for doc, distance in vector_results:
        key = doc.id or f"{doc.metadata}:{doc.page_content}"
        fused[key] = {
            "doc": doc,
            "vector_score": 1 - distance / max(max_distance, 1),
            "keyword_score": 0.0,
        }

    max_keyword_score = max((score for _, score in keyword_results), default=0)
    for doc, score in keyword_results:
        key = doc.id or f"{doc.metadata}:{doc.page_content}"
        item = fused.setdefault(
            key, {"doc": doc, "vector_score": 0.0, "keyword_score": 0.0}
        )
        item["keyword_score"] = score / max_keyword_score if max_keyword_score > 0 else 0.0

    ranked = sorted(
        fused.values(),
        key=lambda item: item["vector_score"] * vector_weight
        + item["keyword_score"] * keyword_weight,
        reverse=True,
    )
    return [item["doc"] for item in ranked[:k]]


def hybrid_search(
    query: str,
    db: Chroma,
    k: int = 5,
    vector_weight: float = 0.5,
    keyword_weight: float = 0.5,
    index: SearchIndex | None = None,
) -> list[Document]:
    index = index if index is not None else build_search_index(db)
    vector_results = db.similarity_search_with_score(query, k=k * 2)
    keyword_results = bm25_search(query, index, k=k * 2)
    return fuse_results(
        vector_results,
        keyword_results,
        k=k,
        vector_weight=vector_weight,
        keyword_weight=keyword_weight,
    )
