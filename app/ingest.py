from collections import defaultdict
from hashlib import sha256
from pathlib import Path
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.engine import get_vector_db

DATA_DIR = "./data"

def process_documents(data_dir=DATA_DIR, db=None):
    data_dir = Path(data_dir)
    if not data_dir.exists():
        data_dir.mkdir(parents=True)
        print(f"Created {data_dir} directory. Add your PDF files here.")

    all_docs = []
    print("Step 1: Loading documents...")
    for path in sorted(data_dir.iterdir()):
        if path.is_file() and path.suffix.lower() == ".pdf":
            filename = path.name
            loader = PyPDFLoader(str(path))
            docs = loader.load()
            
            for i, doc in enumerate(docs):
                doc.metadata["source"] = filename
                doc.metadata["page"] = i + 1
                doc.page_content = f"Source: {filename} | Page: {i + 1}\n{doc.page_content}"
            
            all_docs.extend(docs)
    
    if not all_docs:
        if db is None:
            db = get_vector_db()
        ids = db.get(include=[])["ids"]
        for start in range(0, len(ids), 100):
            db.delete(ids=ids[start : start + 100])
        print(f"No PDFs found in {data_dir}; cleared the stored corpus.")
        return

    print("Step 2: Chunking text...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=800,
        chunk_overlap=150,
        separators=["\n\n", "\n", ".", "!", "?", ",", " "]
    )
    
    chunks = text_splitter.split_documents(all_docs)
    print(f"Split {len(all_docs)} pages into {len(chunks)} contextualized chunks.")

    print("Step 3: Ingesting into Vector Store...")
    if db is None:
        db = get_vector_db()

    existing = db.get(include=["documents", "metadatas"])
    existing_by_id = {
        chunk_id: (content, metadata)
        for chunk_id, content, metadata in zip(
            existing["ids"], existing["documents"], existing["metadatas"]
        )
    }
    page_chunk_counts = defaultdict(int)
    desired_ids = []
    changed_chunks = []
    changed_ids = []
    for chunk in chunks:
        source = chunk.metadata["source"]
        page = chunk.metadata["page"]
        page_key = (source, page)
        ordinal = page_chunk_counts[page_key]
        page_chunk_counts[page_key] += 1
        chunk_id = sha256(f"{source}\0{page}\0{ordinal}".encode()).hexdigest()
        desired_ids.append(chunk_id)
        if existing_by_id.get(chunk_id) != (chunk.page_content, chunk.metadata):
            changed_chunks.append(chunk)
            changed_ids.append(chunk_id)

    for start in range(0, len(changed_chunks), 100):
        db.add_documents(
            changed_chunks[start : start + 100],
            ids=changed_ids[start : start + 100],
        )

    stale_ids = set(existing["ids"]) - set(desired_ids)
    stale_ids = sorted(stale_ids)
    for start in range(0, len(stale_ids), 100):
        db.delete(ids=stale_ids[start : start + 100])
    print(f"Success! Stored {len(desired_ids)} chunks from {len(all_docs)} pages.")

if __name__ == "__main__":
    process_documents()
