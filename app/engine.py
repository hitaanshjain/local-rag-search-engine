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
        model=EMBEDDING_MODEL, 
        base_url=OLLAMA_BASE_URL
    )
    return Chroma(persist_directory=DB_PATH, embedding_function=embedding_function)

def get_llm() -> ChatOllama:
    """Initializes and returns the local LLM connection."""
    print("Initializing LLM...")
    return ChatOllama(
        model=LLM_MODEL, 
        base_url=OLLAMA_BASE_URL 
    )

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