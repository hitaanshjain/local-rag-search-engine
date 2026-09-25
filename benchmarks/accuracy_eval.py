"""Evaluate source and page retrieval against excerpt-verified PDF labels."""

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

from pypdf import PdfReader

from app.engine import (
    EMBEDDING_MODEL,
    LLM_MODEL,
    bm25_search,
    build_search_index,
    fuse_results,
    get_vector_db,
    hybrid_search,
)


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
METHODS = (
    "vector_only",
    "substring_keyword",
    "bm25_keyword",
    "hybrid_substring",
    "hybrid_bm25",
)
LEVELS = ("source", "page")
METRICS = ("hit@3", "hit@5", "mrr")


def keyword_search_substring(query, index, k=5):
    """The former production scorer, retained only as a benchmark baseline."""
    words = set(query.lower().split())
    ranked = [
        (doc, sum(1 for word in words if word in doc.page_content.lower()))
        for doc in index.documents
    ]
    ranked.sort(key=lambda item: item[1], reverse=True)
    return ranked[:k]


def score_ranking(documents, relevant):
    expected_sources = {item["source"] for item in relevant}
    expected_pages = {(item["source"], item["page"]) for item in relevant}
    first_source = next(
        (
            rank
            for rank, doc in enumerate(documents, start=1)
            if doc.metadata.get("source") in expected_sources
        ),
        None,
    )
    first_page = next(
        (
            rank
            for rank, doc in enumerate(documents, start=1)
            if (doc.metadata.get("source"), doc.metadata.get("page")) in expected_pages
        ),
        None,
    )
    return {
        level: {
            "hit@3": int(rank is not None and rank <= 3),
            "hit@5": int(rank is not None and rank <= 5),
            "mrr": 1 / rank if rank is not None else 0.0,
        }
        for level, rank in (("source", first_source), ("page", first_page))
    }


def load_and_validate_queries():
    queries = json.loads((BENCHMARK_DIR / "eval_queries.json").read_text(encoding="utf-8"))
    old_queries = json.loads((BENCHMARK_DIR / "previous_queries.json").read_text(encoding="utf-8"))
    pdf_paths = sorted(DATA_DIR.glob("*.pdf"))
    readers = {path.name: PdfReader(str(path)) for path in pdf_paths}
    page_counts = {source: len(reader.pages) for source, reader in readers.items()}
    seen_ids = set()
    for item in queries:
        if not item["query"].strip() or item["id"] in seen_ids:
            raise ValueError(f"Blank query or duplicate ID: {item['id']}")
        seen_ids.add(item["id"])
        if len(item["relevant"]) != 1:
            raise ValueError(f"Expected one excerpt-backed page for {item['id']}")
        label = item["relevant"][0]
        source, page = label["source"], label["page"]
        if source not in readers or not 1 <= page <= page_counts[source]:
            raise ValueError(f"Invalid source or page for {item['id']}: {label}")
        page_text = " ".join((readers[source].pages[page - 1].extract_text() or "").split())
        evidence = " ".join(item["evidence"].split())
        if evidence.casefold() not in page_text.casefold():
            raise ValueError(f"Evidence is absent from labeled page for {item['id']}")
    return queries, old_queries, page_counts


def check_index_corpus(index, page_counts):
    observed = {(doc.metadata.get("source"), doc.metadata.get("page")) for doc in index.documents}
    sources = {source for source, _ in observed}
    if sources != set(page_counts):
        raise ValueError(f"Chroma sources {sources} do not match data PDFs {set(page_counts)}")
    for source, page in observed:
        if not isinstance(page, int) or not 1 <= page <= page_counts[source]:
            raise ValueError(f"Invalid stored source/page: {source}, {page}")
    if len(observed) != sum(page_counts.values()):
        raise ValueError("Chroma does not contain chunks for every PDF page; re-run ingestion")


def evaluate_query(query, db, index):
    text = query["query"]
    vector_candidates = db.similarity_search_with_score(text, k=10)
    substring_candidates = keyword_search_substring(text, index, k=10)
    bm25_candidates = bm25_search(text, index, k=10)
    rankings = {
        "vector_only": [doc for doc, _ in vector_candidates[:5]],
        "substring_keyword": [doc for doc, _ in substring_candidates[:5]],
        "bm25_keyword": [doc for doc, _ in bm25_candidates[:5]],
        "hybrid_substring": fuse_results(vector_candidates, substring_candidates, k=5),
        "hybrid_bm25": hybrid_search(text, db, k=5, index=index),
    }
    return {
        method: {
            "metrics": score_ranking(documents, query["relevant"]),
            "top5": [
                {"source": doc.metadata.get("source"), "page": doc.metadata.get("page")}
                for doc in documents
            ],
        }
        for method, documents in rankings.items()
    }


def summarize(per_query):
    count = len(per_query)
    return {
        method: {
            level: {
                metric: sum(row["results"][method]["metrics"][level][metric] for row in per_query) / count
                for metric in METRICS
            }
            for level in LEVELS
        }
        for method in METHODS
    }


def results_table(summary):
    lines = [
        "| Method | Source hit@3 | Source hit@5 | Source MRR | Page hit@3 | Page hit@5 | Page MRR |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for method in METHODS:
        source, page = summary[method]["source"], summary[method]["page"]
        lines.append(
            f"| {method} | {source['hit@3']:.1%} | {source['hit@5']:.1%} | {source['mrr']:.3f} | "
            f"{page['hit@3']:.1%} | {page['hit@5']:.1%} | {page['mrr']:.3f} |"
        )
    return "\n".join(lines)


def write_results(result, old_queries):
    json_path = BENCHMARK_DIR / "results.json"
    markdown_path = BENCHMARK_DIR / "results.md"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Retrieval accuracy benchmark",
        "",
        f"Run at: {result['run_at_utc']}",
        f"Git HEAD at run: `{result['git_head_at_run']}` (task 4 worktree changes were uncommitted during the run).",
        f"Models: `{result['models']['embedding']}` embeddings; `{result['models']['llm']}` configured for answers (not used in retrieval scoring).",
        f"Corpus: {result['corpus']['pages']} PDF pages, {result['corpus']['chunks']} indexed chunks, {len(result['corpus']['files'])} files.",
        f"Queries: {result['query_count']} excerpt-verified questions.",
        "",
        "## Results",
        "",
        results_table(result["summary"]),
        "",
        "Hit@k and reciprocal rank inspect the top k *chunks*. Source metrics match their file name; page metrics match file name and physical PDF page. MRR is the mean reciprocal rank of the first match. Each method returns at most five chunks. Hybrid candidate pools contain ten vector and ten keyword chunks with 0.5/0.5 weights.",
        "",
        "## Query changes",
        "",
        "All 50 old queries were removed because their labels all pointed to `zoning.pdf` regardless of answer location. The 20 new questions below were written from the cited PDF passages. None of the old labels was carried forward.",
        "",
        "### Removed queries",
        "",
        "| Old # | Removed query |",
        "|---:|---|",
    ]
    lines.extend(f"| {i} | {query} |" for i, query in enumerate(old_queries, start=1))
    lines.extend([
        "",
        "### Added queries and label evidence",
        "",
        "Each label was set by reading the specified physical PDF page; the benchmark checks that its evidence excerpt occurs on that page before scoring.",
        "",
        "| ID | Query | Source | PDF page | Evidence excerpt |",
        "|---|---|---|---:|---|",
    ])
    for item in result["queries"]:
        label = item["relevant"][0]
        lines.append(
            f"| {item['id']} | {item['query']} | {label['source']} | {label['page']} | {item['evidence']} |"
        )
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_accuracy_benchmark():
    queries, old_queries, page_counts = load_and_validate_queries()
    db = get_vector_db()
    index = build_search_index(db)
    check_index_corpus(index, page_counts)
    per_query = [
        {**query, "results": evaluate_query(query, db, index)}
        for query in queries
    ]
    git_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    result = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head_at_run": git_head,
        "models": {"embedding": EMBEDDING_MODEL, "llm": LLM_MODEL},
        "corpus": {
            "files": page_counts,
            "pages": sum(page_counts.values()),
            "chunks": len(index.documents),
        },
        "query_count": len(queries),
        "summary": summarize(per_query),
        "queries": per_query,
    }
    write_results(result, old_queries)
    print(results_table(result["summary"]))
    print(f"Wrote {BENCHMARK_DIR / 'results.md'} and {BENCHMARK_DIR / 'results.json'}")
    return result


if __name__ == "__main__":
    run_accuracy_benchmark()
