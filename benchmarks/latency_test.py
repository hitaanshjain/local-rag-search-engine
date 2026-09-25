"""Measure streaming chat latency and server-reported retrieval time."""

import json
import math
import os
import re
import statistics
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from pypdf import PdfReader

from app.engine import EMBEDDING_MODEL, LLM_MODEL, OLLAMA_BASE_URL


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_DIR = Path(__file__).resolve().parent
API_URL = os.getenv("RAG_API_URL", "http://127.0.0.1:8000/chat")
QUERY_IDS = ("iss_03", "sum_04", "urb_03", "uni_02", "cha_02")
METRICS = ("retrieval_ms", "ttft_ms", "full_response_ms")


def measure_stream(query, session=requests, url=API_URL, clock=time.perf_counter):
    started = clock()
    first_token_ms = None
    full_response_ms = None
    buffer = ""
    with session.post(url, json={"query": query}, stream=True, timeout=(10, 300)) as response:
        response.raise_for_status()
        timing = response.headers.get("Server-Timing", "")
        match = re.search(r"(?:^|,)\s*retrieval;dur=([0-9.]+)", timing)
        if not match:
            raise ValueError("Chat response did not report retrieval time")
        retrieval_ms = float(match.group(1))
        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            buffer = (buffer + chunk).replace("\r\n", "\n")
            boundary = buffer.find("\n\n")
            while boundary != -1:
                frame = buffer[:boundary]
                buffer = buffer[boundary + 2 :]
                fields = dict(
                    line.split(": ", 1)
                    for line in frame.splitlines()
                    if line.startswith(("event: ", "data: "))
                )
                event = fields.get("event")
                if event == "token" and first_token_ms is None:
                    if json.loads(fields["data"]).get("text"):
                        first_token_ms = (clock() - started) * 1000
                if event == "done":
                    full_response_ms = (clock() - started) * 1000
                    break
                boundary = buffer.find("\n\n")
            if full_response_ms is not None:
                break

    if first_token_ms is None or full_response_ms is None:
        raise ValueError("Chat stream ended without a token and done event")
    return {
        "retrieval_ms": retrieval_ms,
        "ttft_ms": first_token_ms,
        "full_response_ms": full_response_ms,
    }


def ollama_hardware(session=requests):
    response = session.get(f"{OLLAMA_BASE_URL}/api/ps", timeout=10)
    response.raise_for_status()
    models = response.json().get("models", [])
    llm = next((model for model in models if model.get("name") == LLM_MODEL), None)
    if llm is None:
        raise ValueError(f"Ollama did not report loaded model {LLM_MODEL}")
    vram = llm.get("size_vram", 0)
    return {
        "mode": "GPU" if vram > 0 else "CPU",
        "llm_size_vram_bytes": vram,
        "llm_name": llm["name"],
    }


def summary_table(summary):
    lines = ["| Metric | Median | P90 |", "|---|---:|---:|"]
    for metric in METRICS:
        lines.append(
            f"| {metric} | {summary[metric]['median']:.1f} ms | {summary[metric]['p90']:.1f} ms |"
        )
    return "\n".join(lines)


def summarize(samples):
    summary = {}
    for metric in METRICS:
        values = sorted(sample[metric] for sample in samples)
        summary[metric] = {
            "median": statistics.median(values),
            "p90": values[math.ceil(0.9 * len(values)) - 1],
        }
    return summary


def write_results(result):
    (BENCHMARK_DIR / "latency_results.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "# Streaming chat latency benchmark",
        "",
        f"Run at: {result['run_at_utc']}",
        f"Git HEAD at run: `{result['git_head_at_run']}` (task 5 worktree changes were uncommitted during the run).",
        f"Models: `{result['models']['llm']}` LLM and `{result['models']['embedding']}` embeddings.",
        f"Hardware: {result['hardware']['mode']} for the loaded LLM (Ollama reports {result['hardware']['llm_size_vram_bytes']} bytes in VRAM).",
        f"Corpus: {result['corpus_pages']} checked-in PDF pages.",
        f"Queries: {result['query_count']} fixed queries, {result['iterations']} measured requests each, plus one warmup request.",
        "",
        "## Results",
        "",
        summary_table(result["summary"]),
        "",
        "Time to first token (TTFT) starts before the POST and stops at the first nonempty SSE `token` event. Full response time stops at the SSE `done` event. Retrieval time is measured by the server around its production hybrid search for the *same request* and returned in the `Server-Timing` header. P90 uses the nearest-rank method. The warmup request is excluded from all statistics.",
        "",
        "## Measured requests",
        "",
        "| Query ID | Run | Retrieval | TTFT | Full response |",
        "|---|---:|---:|---:|---:|",
    ]
    for sample in result["samples"]:
        lines.append(
            f"| {sample['query_id']} | {sample['iteration']} | {sample['retrieval_ms']:.1f} ms | "
            f"{sample['ttft_ms']:.1f} ms | {sample['full_response_ms']:.1f} ms |"
        )
    (BENCHMARK_DIR / "latency_results.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )


def run_latency_benchmark(iterations=2):
    if iterations < 1:
        raise ValueError("iterations must be positive")
    all_queries = json.loads((BENCHMARK_DIR / "eval_queries.json").read_text(encoding="utf-8"))
    by_id = {item["id"]: item["query"] for item in all_queries}
    queries = [(query_id, by_id[query_id]) for query_id in QUERY_IDS]
    corpus_pages = sum(len(PdfReader(str(path)).pages) for path in (ROOT / "data").glob("*.pdf"))

    samples = []
    with requests.Session() as session:
        measure_stream(queries[0][1], session=session)
        hardware = ollama_hardware(session=session)
        for query_id, query in queries:
            for iteration in range(1, iterations + 1):
                measurement = measure_stream(query, session=session)
                samples.append({"query_id": query_id, "iteration": iteration, **measurement})
                print(f"{query_id} run {iteration}: {measurement}", flush=True)

    git_head = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    result = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head_at_run": git_head,
        "models": {"embedding": EMBEDDING_MODEL, "llm": LLM_MODEL},
        "hardware": hardware,
        "corpus_pages": corpus_pages,
        "query_count": len(queries),
        "query_ids": list(QUERY_IDS),
        "iterations": iterations,
        "warmup_requests": 1,
        "samples": samples,
        "summary": summarize(samples),
    }
    write_results(result)
    print(summary_table(result["summary"]))
    return result


if __name__ == "__main__":
    run_latency_benchmark()
