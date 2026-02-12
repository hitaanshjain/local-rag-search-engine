# Local RAG: Private Document Search Engine

A high-performance, local **Retrieval Augmented Generation (RAG)** system that allows users to query information from their PDF documents.

Built with **Python**, **LangChain**, **Ollama (Llama 3)**, and **FastAPI**, this project implements a full data ingestion pipeline and a semantic search API.

## Architecture

The system follows a standard RAG architecture:
1.  **Ingestion:** PDFs are loaded, split into chunks, and embedded into vectors.
2.  **Storage:** Vectors are stored locally in **ChromaDB**.
3.  **Retrieval:** User queries are converted to vectors to find the most relevant context.
4.  **Generation:** **Llama 3** synthesizes an answer based strictly on the retrieved context.

```mermaid
graph LR
    PDF[PDF Document] -->|Ingest Script| Splitter[Text Splitter]
    Splitter -->|Chunks| Embed[Nomic Embeddings]
    Embed -->|Vectors| DB[(ChromaDB)]
    
    User -->|Query| API[FastAPI Server]
    API -->|Search| DB
    DB -->|Context| API
    API -->|Context + Query| LLM[Llama 3]
    LLM -->|Answer| API
    API -->|JSON| User
