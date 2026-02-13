import chromadb
from sentence_transformers import SentenceTransformer
import numpy as np


print("Loading model...")
model = SentenceTransformer('all-MiniLM-L6-v2') 
client = chromadb.PersistentClient(path="./db") # Point to your existing DB
collection = client.get_collection("iss_highlands_docs")

test_cases = [
    {
        "query": "What are the fence height regulations?",
        "expected_keywords": ["6 feet", "height limit", "fence"]
    },
    {
        "query": "Can I paint my house blue?",
        "expected_keywords": ["architectural committee", "approved colors", "exterior"]
    },
    {
        "query": "noise complaint rules",
        "expected_keywords": ["quiet hours", "10pm", "nuisance"]
    }
]

def evaluate_retrieval(k=3):
    print(f"Running evaluation on {len(test_cases)} test cases...")
    score = 0
    
    for case in test_cases:
        query_vector = model.encode(case["query"]).tolist()
        
        # Query the DB
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=k
        )
        
        retrieved_texts = results['documents'][0]


        hit = False
        for text in retrieved_texts:
            if any(kw in text.lower() for kw in case["expected_keywords"]):
                hit = True
                break
        
        if hit:
            score += 1
            print(f"[PASS] {case['query']}")
        else:
            print(f"[FAIL] {case['query']}")
            print(f"   Retrieved: {[t[:50]... for t in retrieved_texts]}")

    print(f"\nFinal Retrieval Accuracy: {score}/{len(test_cases)} ({score/len(test_cases)*100:.1f}%)")

if __name__ == "__main__":
    evaluate_retrieval()
