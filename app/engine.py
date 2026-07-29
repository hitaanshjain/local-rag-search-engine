import os
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate

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


def keyword_search(query: str, db: Chroma, k: int = 5):
    """
    Keyword search using simple string matching.
    Returns top-k results with metadata.
    """
    docs = db.get()["documents"]
    metadatas = db.get()["metadatas"]

    query_words = set(query.lower().split())
    scored_docs = []

    for idx, doc in enumerate(docs):
        score = sum(1 for word in query_words if word in doc.lower())
        scored_docs.append(
            (idx, score, doc, metadatas[idx] if idx < len(metadatas) else {})
        )

    scored_docs.sort(key=lambda x: x[1], reverse=True)
    return scored_docs[:k]


def hybrid_search(
    query: str,
    db: Chroma,
    k: int = 5,
    vector_weight: float = 0.5,
    keyword_weight: float = 0.5,
):
    """
    Hybrid search combining vector and keyword search with score fusion and re-ranking.

    Args:
        query: Search query string
        db: ChromaDB instance
        k: Number of results to return
        vector_weight: Weight for vector search scores (0-1)
        keyword_weight: Weight for keyword search scores (0-1)

    Returns:
        List of Document objects, ordered by combined score
    """
    # Get vector search results
    vector_raw_results = db.similarity_search_with_score(query, k=k * 2)

    # Normalize and index vector results by source
    vector_results_dict = {}
    if vector_raw_results:
        max_distance = (
            max([score for _, score in vector_raw_results]) if vector_raw_results else 1
        )
        for doc, distance in vector_raw_results:
            normalized_score = 1 - (distance / max(max_distance, 1))
            source = doc.metadata.get("source", "unknown")
            if source not in vector_results_dict:
                vector_results_dict[source] = {
                    "doc": doc,
                    "vector_score": normalized_score,
                }
            elif normalized_score > vector_results_dict[source]["vector_score"]:
                vector_results_dict[source]["doc"] = doc
                vector_results_dict[source]["vector_score"] = normalized_score

    # Get keyword search results
    keyword_raw_results = keyword_search(query, db, k=k * 2)

    # Normalize and index keyword results by source
    keyword_results_dict = {}
    if keyword_raw_results:
        max_keyword_score = (
            max([score for _, score, _, _ in keyword_raw_results])
            if keyword_raw_results
            else 1
        )
        for idx, score, doc_text, metadata in keyword_raw_results:
            normalized_score = score / max(max_keyword_score, 1)
            source = metadata.get("source", "unknown")
            if source not in keyword_results_dict:
                keyword_results_dict[source] = {
                    "doc_text": doc_text,
                    "metadata": metadata,
                    "keyword_score": normalized_score,
                }
            elif normalized_score > keyword_results_dict[source]["keyword_score"]:
                keyword_results_dict[source]["doc_text"] = doc_text
                keyword_results_dict[source]["metadata"] = metadata
                keyword_results_dict[source]["keyword_score"] = normalized_score

    # Fuse results by source document
    fused_results = {}

    for source, data in vector_results_dict.items():
        fused_results[source] = {
            "doc": data["doc"],
            "vector_score": data.get("vector_score", 0),
            "keyword_score": keyword_results_dict.get(source, {}).get(
                "keyword_score", 0
            ),
        }

    for source, data in keyword_results_dict.items():
        if source not in fused_results:
            fused_results[source] = {
                "doc_text": data["doc_text"],
                "metadata": data["metadata"],
                "vector_score": 0,
                "keyword_score": data.get("keyword_score", 0),
            }

    # Re-rank by combined score
    for source in fused_results:
        combined = (
            fused_results[source].get("vector_score", 0) * vector_weight
            + fused_results[source].get("keyword_score", 0) * keyword_weight
        )
        fused_results[source]["combined_score"] = combined

    # Sort by combined score
    sorted_results = sorted(
        fused_results.items(), key=lambda x: x[1]["combined_score"], reverse=True
    )

    # Convert to Document objects for compatibility
    result_docs = []
    for source, data in sorted_results[:k]:
        if "doc" in data:
            result_docs.append(data["doc"])

    return result_docs
