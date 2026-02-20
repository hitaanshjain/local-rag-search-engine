import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from app.engine import get_vector_db

TEST_QUERIES = [
    "zoning regulations",
    "commercial lease terms",
    "property maintenance responsibility",
    "late rent penalty",
    "sublease permission"
]

def keyword_search_simulation(query, db):
    """
    Simulates a basic keyword search by pulling all docs and doing a crude string match.
    In a real scenario, this would be Elasticsearch or BM25.
    """
    docs = db.get()['documents']
    query_words = set(query.lower().split())
    scored_docs = []
    
    for doc in docs:
        score = sum(1 for word in query_words if word in doc.lower())
        scored_docs.append(score)

    return max(scored_docs) if scored_docs else 0

def run_accuracy_benchmark():
    print("Initializing Database connection...")
    db = get_vector_db()

    if not db.get()['documents']:
        print("Database is empty. Run `uv run python -m app.ingest` first.")
        return

    print("\nRunning Relevance Benchmark: Keyword vs Vector Search...")
    
    vector_wins = 0
    total_queries = len(TEST_QUERIES)

    for query in TEST_QUERIES:
        print(f"\nEvaluating Query: '{query}'")
        
        kw_score = keyword_search_simulation(query, db)
        
        results = db.similarity_search_with_score(query, k=1)
        if results:
            distance = results[0][1]
            vector_score = max(0, 100 - (distance * 100)) 
        else:
            vector_score = 0
            
        print(f"  Keyword Match Score: {kw_score}")
        print(f"  Vector Similarity Score: {vector_score:.2f}")

        if vector_score > (kw_score * 10):
            vector_wins += 1

    improvement = (vector_wins / total_queries) * 100
    
    print("\n--- Accuracy Benchmark Results ---")
    print(f"Queries Tested: {total_queries}")
    print(f"Vector Search Outperformed Keyword Search: {vector_wins} times")
    print(f"Calculated Improvement Rate: {improvement:.1f}%")
    print("----------------------------------")

if __name__ == "__main__":
    run_accuracy_benchmark()