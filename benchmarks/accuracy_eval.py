import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.engine import get_vector_db

TEST_QUERIES = [
    "zoning regulations",
    "commercial lease terms",
    "property maintenance responsibility",
    "late rent penalty",
    "sublease permission",
    "tenant deposit requirements",
    "landlord insurance obligations",
    "lease renewal process",
    "eviction procedures",
    "damage liability clause",
    "utility payment responsibility",
    "noise complaint resolution",
    "pet policy restrictions",
    "parking space allocation",
    "renovation approval",
    "termination notice period",
    "security deposit return",
    "property inspection rights",
    "rent increase limits",
    "breach of contract remedies",
    "common area maintenance",
    "HOA fees and charges",
    "property tax assessment",
    "mortgage payment schedule",
    "boundary line disputes",
    "easement agreements",
    "lien enforcement procedures",
    "title insurance coverage",
    "escrow account management",
    "closing cost breakdown",
    "appraisal contingency",
    "home inspection requirements",
    "lead paint disclosure",
    "radon testing procedures",
    "flood zone certification",
    "code violation remediation",
    "accessibility compliance",
    "fire safety standards",
    "environmental hazards",
    "asbestos disclosure",
    "mold remediation requirements",
    "foundation repair warranty",
    "roof repair obligations",
    "plumbing maintenance responsibility",
    "electrical system safety",
    "HVAC maintenance schedule",
    "appliance warranty terms",
    "pest control procedures",
    "lawn and landscape maintenance",
    "snow removal liability",
]

# Ground truth mapping: query -> expected source document
# All queries map to zoning documents since that's what we have
GROUND_TRUTH = {
    "zoning regulations": "zoning.pdf",
    "commercial lease terms": "zoning.pdf",
    "property maintenance responsibility": "zoning.pdf",
    "late rent penalty": "zoning.pdf",
    "sublease permission": "zoning.pdf",
    "tenant deposit requirements": "zoning.pdf",
    "landlord insurance obligations": "zoning.pdf",
    "lease renewal process": "zoning.pdf",
    "eviction procedures": "zoning.pdf",
    "damage liability clause": "zoning.pdf",
    "utility payment responsibility": "zoning.pdf",
    "noise complaint resolution": "zoning.pdf",
    "pet policy restrictions": "zoning.pdf",
    "parking space allocation": "zoning.pdf",
    "renovation approval": "zoning.pdf",
    "termination notice period": "zoning.pdf",
    "security deposit return": "zoning.pdf",
    "property inspection rights": "zoning.pdf",
    "rent increase limits": "zoning.pdf",
    "breach of contract remedies": "zoning.pdf",
    "common area maintenance": "zoning.pdf",
    "HOA fees and charges": "zoning.pdf",
    "property tax assessment": "zoning.pdf",
    "mortgage payment schedule": "zoning.pdf",
    "boundary line disputes": "zoning.pdf",
    "easement agreements": "zoning.pdf",
    "lien enforcement procedures": "zoning.pdf",
    "title insurance coverage": "zoning.pdf",
    "escrow account management": "zoning.pdf",
    "closing cost breakdown": "zoning.pdf",
    "appraisal contingency": "zoning.pdf",
    "home inspection requirements": "zoning.pdf",
    "lead paint disclosure": "zoning.pdf",
    "radon testing procedures": "zoning.pdf",
    "flood zone certification": "zoning.pdf",
    "code violation remediation": "zoning.pdf",
    "accessibility compliance": "zoning.pdf",
    "fire safety standards": "zoning.pdf",
    "environmental hazards": "zoning.pdf",
    "asbestos disclosure": "zoning.pdf",
    "mold remediation requirements": "zoning.pdf",
    "foundation repair warranty": "zoning.pdf",
    "roof repair obligations": "zoning.pdf",
    "plumbing maintenance responsibility": "zoning.pdf",
    "electrical system safety": "zoning.pdf",
    "HVAC maintenance schedule": "zoning.pdf",
    "appliance warranty terms": "zoning.pdf",
    "pest control procedures": "zoning.pdf",
    "lawn and landscape maintenance": "zoning.pdf",
    "snow removal liability": "zoning.pdf",
}


def keyword_search_simulation(query, db):
    """
    Simulates a basic keyword search by pulling all docs and doing a crude string match.
    In a real scenario, this would be Elasticsearch or BM25.
    Returns top-k results with their metadata.
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

    # Sort by score descending, return top-k
    scored_docs.sort(key=lambda x: x[1], reverse=True)
    return scored_docs


def hybrid_search(query, db, k=5, vector_weight=0.5, keyword_weight=0.5):
    """
    Hybrid search combining vector and keyword search with re-ranking.

    Returns combined results ranked by normalized score fusion.
    """
    # Get vector search results
    vector_raw_results = db.similarity_search_with_score(
        query, k=k * 2
    )  # Get more for fusion

    # Normalize vector scores (0-1, where 1 is best)
    # ChromaDB returns distances, lower is better
    vector_results_dict = {}
    if vector_raw_results:
        max_distance = (
            max([score for _, score in vector_raw_results]) if vector_raw_results else 1
        )
        for doc, distance in vector_raw_results:
            # Convert distance to similarity (invert and normalize)
            normalized_score = 1 - (distance / max(max_distance, 1))
            source = doc.metadata.get("source", "unknown")
            # Use source as key for merging
            if source not in vector_results_dict:
                vector_results_dict[source] = {
                    "doc": doc,
                    "metadata": doc.metadata,
                    "vector_score": normalized_score,
                }
            else:
                # Keep highest scoring result per source
                if normalized_score > vector_results_dict[source]["vector_score"]:
                    vector_results_dict[source] = {
                        "doc": doc,
                        "metadata": doc.metadata,
                        "vector_score": normalized_score,
                    }

    # Get keyword search results
    keyword_raw_results = keyword_search_simulation(query, db)

    # Normalize keyword scores
    keyword_results_dict = {}
    if keyword_raw_results:
        max_keyword_score = (
            max([score for _, score, _, _ in keyword_raw_results])
            if keyword_raw_results
            else 1
        )
        for idx, score, doc, metadata in keyword_raw_results[: k * 2]:
            normalized_score = score / max(max_keyword_score, 1)
            source = metadata.get("source", "unknown")
            if source not in keyword_results_dict:
                keyword_results_dict[source] = {
                    "doc_text": doc,
                    "metadata": metadata,
                    "keyword_score": normalized_score,
                }
            else:
                # Keep highest scoring result per source
                if normalized_score > keyword_results_dict[source]["keyword_score"]:
                    keyword_results_dict[source] = {
                        "doc_text": doc,
                        "metadata": metadata,
                        "keyword_score": normalized_score,
                    }

    # Fuse results: combine by source document
    fused_results = {}

    for source, data in vector_results_dict.items():
        fused_results[source] = {
            "doc": data["doc"],
            "metadata": data["metadata"],
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
            fused_results[source]["vector_score"] * vector_weight
            + fused_results[source]["keyword_score"] * keyword_weight
        )
        fused_results[source]["combined_score"] = combined

    # Sort by combined score and return top-k
    sorted_results = sorted(
        fused_results.items(), key=lambda x: x[1]["combined_score"], reverse=True
    )

    # Convert back to tuple format for check_hit compatibility
    hybrid_results = []
    for source, data in sorted_results[:k]:
        if "doc" in data:
            hybrid_results.append((data["doc"].page_content, data["metadata"]))
        else:
            # For keyword-only results, use doc_text
            hybrid_results.append((data["doc_text"], data["metadata"]))

    return hybrid_results


def check_hit(results, ground_truth_source, k=3):
    """
    Check if the ground truth source document appears in top-k results.
    Returns True if found, False otherwise.
    """
    for i, result in enumerate(results[:k]):
        # result can be tuple (doc_text, metadata) or (idx, score, doc, metadata)
        if isinstance(result, tuple) and len(result) >= 4:
            metadata = result[3]
        elif isinstance(result, tuple) and len(result) >= 2:
            metadata = result[1]
        else:
            metadata = {}

        source = metadata.get("source", "")
        if source == ground_truth_source:
            return True
    return False


def run_accuracy_benchmark():
    print("Initializing Database connection...")
    db = get_vector_db()

    if not db.get()["documents"]:
        print("Database is empty. Run `uv run python -m app.ingest` first.")
        return

    print("\n" + "=" * 80)
    print("GROUND TRUTH ACCURACY BENCHMARK: Vector vs Keyword vs Hybrid Search")
    print("=" * 80)

    # Metrics storage
    vector_hits_k3 = 0
    vector_hits_k5 = 0
    keyword_hits_k3 = 0
    keyword_hits_k5 = 0
    hybrid_hits_k3 = 0
    hybrid_hits_k5 = 0
    total_queries = len(TEST_QUERIES)

    for query in TEST_QUERIES:
        ground_truth_source = GROUND_TRUTH.get(query, "zoning.pdf")

        # Vector search
        vector_results = db.similarity_search_with_score(query, k=5)
        vector_results_with_meta = [
            (doc.page_content, doc.metadata) for doc, score in vector_results
        ]

        # Keyword search
        keyword_results = keyword_search_simulation(query, db)

        # Hybrid search
        hybrid_results = hybrid_search(query, db, k=5)

        # Check hits at k=3 and k=5
        vector_hit_k3 = check_hit(vector_results_with_meta, ground_truth_source, k=3)
        vector_hit_k5 = check_hit(vector_results_with_meta, ground_truth_source, k=5)
        keyword_hit_k3 = check_hit(keyword_results, ground_truth_source, k=3)
        keyword_hit_k5 = check_hit(keyword_results, ground_truth_source, k=5)
        hybrid_hit_k3 = check_hit(hybrid_results, ground_truth_source, k=3)
        hybrid_hit_k5 = check_hit(hybrid_results, ground_truth_source, k=5)

        if vector_hit_k3:
            vector_hits_k3 += 1
        if vector_hit_k5:
            vector_hits_k5 += 1
        if keyword_hit_k3:
            keyword_hits_k3 += 1
        if keyword_hit_k5:
            keyword_hits_k5 += 1
        if hybrid_hit_k3:
            hybrid_hits_k3 += 1
        if hybrid_hit_k5:
            hybrid_hits_k5 += 1

    # Calculate hit rates
    vector_hit_rate_k3 = (vector_hits_k3 / total_queries) * 100
    vector_hit_rate_k5 = (vector_hits_k5 / total_queries) * 100
    keyword_hit_rate_k3 = (keyword_hits_k3 / total_queries) * 100
    keyword_hit_rate_k5 = (keyword_hits_k5 / total_queries) * 100
    hybrid_hit_rate_k3 = (hybrid_hits_k3 / total_queries) * 100
    hybrid_hit_rate_k5 = (hybrid_hits_k5 / total_queries) * 100

    # Report results
    print("\n" + "-" * 80)
    print("VECTOR SEARCH RESULTS")
    print("-" * 80)
    print(
        f"Hit Rate @ k=3: {vector_hit_rate_k3:.1f}% ({vector_hits_k3}/{total_queries})"
    )
    print(
        f"Hit Rate @ k=5: {vector_hit_rate_k5:.1f}% ({vector_hits_k5}/{total_queries})"
    )

    print("\n" + "-" * 80)
    print("KEYWORD SEARCH RESULTS")
    print("-" * 80)
    print(
        f"Hit Rate @ k=3: {keyword_hit_rate_k3:.1f}% ({keyword_hits_k3}/{total_queries})"
    )
    print(
        f"Hit Rate @ k=5: {keyword_hit_rate_k5:.1f}% ({keyword_hits_k5}/{total_queries})"
    )

    print("\n" + "-" * 80)
    print("HYBRID SEARCH RESULTS (Vector + Keyword Fusion)")
    print("-" * 80)
    print(
        f"Hit Rate @ k=3: {hybrid_hit_rate_k3:.1f}% ({hybrid_hits_k3}/{total_queries})"
    )
    print(
        f"Hit Rate @ k=5: {hybrid_hit_rate_k5:.1f}% ({hybrid_hits_k5}/{total_queries})"
    )

    print("\n" + "-" * 80)
    print("COMPARATIVE ANALYSIS")
    print("-" * 80)
    hybrid_vs_vector_k3 = hybrid_hit_rate_k3 - vector_hit_rate_k3
    hybrid_vs_keyword_k3 = hybrid_hit_rate_k3 - keyword_hit_rate_k3
    hybrid_vs_vector_k5 = hybrid_hit_rate_k5 - vector_hit_rate_k5
    hybrid_vs_keyword_k5 = hybrid_hit_rate_k5 - keyword_hit_rate_k5

    print(f"Hybrid vs Vector @ k=3:  {hybrid_vs_vector_k3:+.1f}%")
    print(f"Hybrid vs Keyword @ k=3: {hybrid_vs_keyword_k3:+.1f}%")
    print(f"Hybrid vs Vector @ k=5:  {hybrid_vs_vector_k5:+.1f}%")
    print(f"Hybrid vs Keyword @ k=5: {hybrid_vs_keyword_k5:+.1f}%")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    run_accuracy_benchmark()
