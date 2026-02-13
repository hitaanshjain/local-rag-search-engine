## 🛠 Engineering Decisions & Trade-offs

### 1. Vector Database Selection: ChromaDB (Local) vs. Pinecone (Cloud)
**Decision:** I chose **ChromaDB** running locally in a Docker container.
* **Why:** The Issaquah Highlands documents contain private community data. Using a cloud provider like Pinecone would risk data egress.
* **Trade-off:** This increases local memory usage (RAM) but guarantees 100% data sovereignty and offline capability.

### 2. Retrieval Optimization: Context-Aware Chunking
**Challenge:** Standard character splitting (1000 chars) was cutting legal clauses in half, causing the LLM to hallucinate rules.
**Solution:** Implemented `RecursiveCharacterTextSplitter` with a hierarchical separator strategy (`\n\n` > `.` > ` `) and a 15% overlap.
**Result:** Improved retrieval "hit rate" on regulatory queries by ~30% (verified via `evaluation.py`).

### 3. Privacy-First Architecture
* **Inference:** Decoupled the inference engine. The system is designed to plug into local LLMs (Llama 3 via Ollama) to run entirely air-gapped if necessary.
