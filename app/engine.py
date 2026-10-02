import os
import re
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any

from chromadb.config import Settings
from langchain_chroma import Chroma
from langchain_ollama import OllamaEmbeddings, ChatOllama
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.documents import Document
from rank_bm25 import BM25Okapi

OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
DB_PATH = "./chroma_db"
INDEX_VERSION_PATH = Path(DB_PATH) / "index.version"
PAGE_REPORT_PATH = Path(DB_PATH) / "pages.json"
EMBEDDING_MODEL = "nomic-embed-text"
LLM_MODEL = os.getenv("LLM_MODEL", "llama3.2:3b")


def get_vector_db() -> Chroma:
    """Initializes and returns the Chroma vector database connection."""
    print("Initializing Vector DB...")
    embedding_function = OllamaEmbeddings(
        model=EMBEDDING_MODEL, base_url=OLLAMA_BASE_URL
    )
    return Chroma(
        persist_directory=DB_PATH,
        embedding_function=embedding_function,
        client_settings=Settings(anonymized_telemetry=False),
    )


def get_llm() -> ChatOllama:
    """Initializes and returns the local LLM connection."""
    print("Initializing LLM...")
    return ChatOllama(model=LLM_MODEL, base_url=OLLAMA_BASE_URL, temperature=0)


def get_rag_prompt() -> ChatPromptTemplate:
    """Returns the standardized prompt template for RAG queries."""
    return ChatPromptTemplate.from_template("""
    You are a helpful AI assistant. You are given a context that may contain information from multiple different documents.
    Your goal is to answer the user's question accurately.

    Instructions:
    1. Look for the specific answer in the context below.
    2. If the context contains information about different topics (e.g., different games or subjects), ONLY use the part that is relevant to the user's question.
    3. {citation_instruction}
    4. If the passages do not answer the question, reply exactly: I don't know based on these documents.
    5. If the question does not specify a jurisdiction or district and the passages have different answers, ask which jurisdiction or district the user means.
    6. Do not mention "the provided context" or "documents" otherwise. Answer directly.

    Context:
    {context}

    Earlier conversation (for understanding the question; verify every answer against the context above):
    {history}

    Question: {question}
    """)


def tokenize(text: str) -> list[str]:
    return re.findall(r"\b\w+\b", text.lower())


def tokenize_with_identifiers(text: str) -> list[str]:
    return re.findall(r"\b\w+(?:-\w+)*\b", text.lower())


@dataclass
class SearchIndex:
    documents: list[Document]
    bm25: Any | None
    section_bm25: Any | None = None


class SearchIndexCache:
    """Keep the keyword index until ingestion publishes a new corpus version."""

    def __init__(self, db: Chroma, marker_path: Path = INDEX_VERSION_PATH):
        self.db = db
        self.marker_path = Path(marker_path)
        self._lock = Lock()
        self._version: str | None = None
        self._index: SearchIndex | None = None

    def get(self) -> SearchIndex:
        with self._lock:
            version = self.marker_path.read_text(encoding="utf-8") if self.marker_path.exists() else None
            if self._index is None or version != self._version:
                self._index = build_search_index(self.db)
                self._version = version
            return self._index


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
    section_bm25 = BM25Okapi([
        tokenize_with_identifiers(f"{doc.metadata.get('section', '')} {doc.page_content}")
        for doc in documents
    ]) if documents else None
    return SearchIndex(documents=documents, bm25=bm25, section_bm25=section_bm25)


def bm25_search(
    query: str, index: SearchIndex, k: int = 5, sources: set[str] | None = None
) -> list[tuple[Document, float]]:
    """Score against the whole corpus, then keep only the selected documents' chunks.

    Scoring before filtering keeps scores on one scale whatever the selection, so the
    thresholds in select_context and needs_clarification mean the same thing.
    """
    section_query = bool(re.search(r"\b[A-Za-z][A-Za-z0-9]*-\d+\b", query)) and index.section_bm25 is not None
    scorer = index.section_bm25 if section_query else index.bm25
    words = tokenize_with_identifiers(query) if section_query else tokenize(query)
    if scorer is None or not words:
        return []
    scores = scorer.get_scores(words)
    ranked = sorted(enumerate(scores), key=lambda item: item[1], reverse=True)
    hits = (
        (index.documents[i], float(score)) for i, score in ranked
        if score > 0 and (sources is None or index.documents[i].metadata.get("source") in sources)
    )
    return [hit for _, hit in zip(range(k), hits)]


def known_places(index: SearchIndex) -> set[str]:
    """Place names from ingested jurisdictions: "Charleston, South Carolina" -> "Charleston"."""
    return {
        jurisdiction.split(",")[0].strip()
        for jurisdiction in {doc.metadata.get("jurisdiction") for doc in index.documents}
        if jurisdiction
    }


def needs_clarification(query: str, index: SearchIndex, sources: set[str] | None = None) -> bool:
    """Ask for a jurisdiction when two sources score nearly alike on the query.

    A query naming exactly one indexed place is compared only across that place's PDFs,
    since file names need not mention it.
    """
    named = [
        place for place in known_places(index)
        if re.search(rf"\b{re.escape(place.lower())}\b", query.lower())
    ]
    if len(named) == 1:
        place_sources = {
            doc.metadata.get("source") for doc in index.documents
            if (doc.metadata.get("jurisdiction") or "").split(",")[0].strip() == named[0]
        }
        sources = place_sources if sources is None else sources & place_sources
    stopwords = {
        "a", "an", "are", "at", "do", "does", "for", "how", "in", "is",
        "many", "of", "the", "to", "what", "which", "who",
    }
    words = [word for word in tokenize(query) if word not in stopwords]
    if not words:
        return False
    hits = bm25_search(query, index, k=30, sources=sources)
    if not hits:
        return False
    top_document, _ = hits[0]
    document_words = set(tokenize(top_document.page_content))
    coverage = sum(word in document_words for word in words) / len(words)
    if coverage < 0.6:
        return False
    best_by_source: dict[str, tuple[float, float]] = {}
    for document, score in hits:
        source = document.metadata.get("source")
        if source is not None and score > best_by_source.get(source, (0, 0))[0]:
            terms = set(tokenize(document.page_content))
            match_coverage = sum(word in terms for word in words) / len(words)
            best_by_source[source] = (score, match_coverage)
    best = sorted(best_by_source.values(), reverse=True)
    return len(best) > 1 and best[1][0] >= best[0][0] * 0.9 and best[1][1] >= best[0][1]


def select_context(
    results: list[Document], keyword_results: list[tuple[Document, float]], query: str = ""
) -> list[Document]:
    """Keep a clear keyword leader or one from the explicitly named section."""
    if not results or len(keyword_results) < 2:
        return results
    first, runner_up = keyword_results[:2]
    if (
        first[0].id is not None
        and first[0].id == results[0].id
        and (first[1] >= runner_up[1] * 1.4 or section_matches_query(query, first[0]))
    ):
        return results[:1]
    return results


def section_matches_query(query: str, doc: Document) -> bool:
    identifiers = set(re.findall(r"\b[A-Za-z][A-Za-z0-9]*-\d+\b", query.casefold()))
    section_identifiers = set(re.findall(
        r"\b[A-Za-z][A-Za-z0-9]*-\d+\b", doc.metadata.get("section", "").casefold()
    ))
    return bool(identifiers & section_identifiers)


def prioritize_section_matches(query: str, results: list[Document]) -> list[Document]:
    """Keep passages for an explicitly named section ahead of broader matches."""
    return sorted(results, key=lambda doc: not section_matches_query(query, doc))


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
    vector_weight: float = 0.25,
    keyword_weight: float = 0.75,
    index: SearchIndex | None = None,
    timings: dict[str, float] | None = None,
    sources: set[str] | None = None,
) -> list[Document]:
    index = index if index is not None else build_search_index(db)
    started = perf_counter()
    search_filter = None
    if sources:
        search_filter = {"source": next(iter(sources))} if len(sources) == 1 else {"source": {"$in": sorted(sources)}}
    vector_results = db.similarity_search_with_score(query, k=k * 2, filter=search_filter) if search_filter else db.similarity_search_with_score(query, k=k * 2)
    vector_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    keyword_results = bm25_search(query, index, k=k * 2, sources=sources)
    keyword_ms = (perf_counter() - started) * 1000
    started = perf_counter()
    results = prioritize_section_matches(query, fuse_results(
        vector_results,
        keyword_results,
        k=k,
        vector_weight=vector_weight,
        keyword_weight=keyword_weight,
    ))
    if timings is not None:
        timings.update(vector=vector_ms, keyword=keyword_ms, fusion=(perf_counter() - started) * 1000)
    return results
