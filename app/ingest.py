import os
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.engine import get_vector_db

DATA_DIR = "./data"

def process_documents():
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)
        print(f"Created {DATA_DIR} directory. Add your mock property PDFs here.")
        return

    all_docs = []
    print("Step 1: Loading documents...")
    for filename in os.listdir(DATA_DIR):
        if filename.endswith(".pdf"):
            path = os.path.join(DATA_DIR, filename)
            loader = PyPDFLoader(path)
            docs = loader.load()
            
            for i, doc in enumerate(docs):
                doc.metadata["source"] = filename
                doc.metadata["page"] = i + 1
                doc.page_content = f"Source: {filename} | Page: {i + 1}\n{doc.page_content}"
            
            all_docs.extend(docs)
    
    if not all_docs:
        print("Error: No PDFs found in the /data directory.")
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
    db = get_vector_db()
    
    db.add_documents(chunks)
    print("Success! Database populated.")

if __name__ == "__main__":
    process_documents()