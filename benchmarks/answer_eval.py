"""Run answer and citation checks against the live chat API.

Phrase matching is a screening metric, not a semantic correctness judgment.
Inspect the recorded answers and passages before making quality claims.
"""

import argparse
import codecs
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path

import pymupdf
import requests
from pypdf import PdfReader

from app.engine import EMBEDDING_MODEL
from app.pdf_extraction import extract_text_layout
from benchmarks.citation_support import LABELS, OllamaJudge, PageTexts, score_support, summarize_support
from benchmarks.run_info import corpus_size, describe_git, git_state


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
API_URL = os.getenv("RAG_API_URL", "http://127.0.0.1:8000/chat")
ABSTAIN = "I don't know based on these documents."
EVALUATION_SETS = {
    "heldout_queries.json": "Final holdout",
    "regression_queries.json": "Regression (former holdout)",
    "coverage_development_queries.json": "Coverage development",
}
HOLDOUT = "heldout_queries.json"
CATEGORIES = {"conflict", "table", "exception", "outdated"}


def load_queries(dataset_filename="heldout_queries.json"):
    rows = json.loads((HERE / dataset_filename).read_text(encoding="utf-8"))
    if len({row["id"] for row in rows}) != len(rows):
        raise ValueError("Duplicate held-out query ID")
    readers = {}
    for row in rows:
        if row["kind"] not in {"answerable", "unanswerable", "ambiguous"}:
            raise ValueError(f"Unknown query kind: {row['kind']}")
        if "category" in row and row["category"] not in CATEGORIES:
            raise ValueError(f"Unknown category for {row['id']}: {row['category']}")
        if row["kind"] != "answerable":
            continue
        reader = readers.setdefault(row["source"], PdfReader(ROOT / "data" / row["source"]))
        for page in [row["page"], *row.get("additional_relevant_pages", [])]:
            if not 1 <= page <= len(reader.pages):
                raise ValueError(f"Invalid PDF page for {row['id']}")
            if row.get("evidence_extractor") == "layout":
                # Table cells that pypdf flattens out of order are checked against the app's extractor.
                with pymupdf.open(ROOT / "data" / row["source"]) as pdf:
                    raw = extract_text_layout(pdf[page - 1])
            else:
                raw = reader.pages[page - 1].extract_text() or ""
            actual = " ".join(raw.split()).casefold()
            expected = " ".join(row["evidence"].split()).casefold()
            if expected not in actual:
                raise ValueError(f"Evidence missing from PDF page for {row['id']}")
    return rows


def score_answer(row, answer, sources):
    citations = [
        int(number)
        for group in re.findall(r"\[((?:\d+\s*,\s*)*\d+)\]", answer)
        for number in re.findall(r"\d+", group)
    ]
    valid = all(1 <= number <= len(sources) for number in citations)
    if row["kind"] == "answerable":
        fact_match = any(phrase.casefold() in answer.casefold() for phrase in row["accepted_answers"])
        fact_match = fact_match and not any(
            re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", answer, re.I)
            for phrase in row.get("forbidden_answers", [])
        )
        citation_match = any(
            1 <= number <= len(sources)
            and sources[number - 1].get("source") == row["source"]
            and sources[number - 1].get("page") in [row["page"], *row.get("additional_relevant_pages", [])]
            for number in citations
        )
        passed = fact_match and citation_match and valid
    elif row["kind"] == "unanswerable":
        fact_match = answer.strip().casefold() == ABSTAIN.casefold()
        citation_match = not citations
        passed = fact_match and citation_match
    else:
        fact_match = bool(re.search(r"\b(which|specify|clarify)\b", answer, re.I) and "?" in answer)
        citation_match = not citations
        passed = fact_match and citation_match
    return {
        "fact_match": fact_match,
        "citation_match": citation_match,
        "citation_refs_valid": valid,
        "pass": passed,
    }


def parse_sse(chunks, meta=None):
    sources = []
    tokens = []
    buffer = ""
    decoder = codecs.getincrementaldecoder("utf-8")()
    for chunk in chunks:
        buffer = (buffer + decoder.decode(chunk)).replace("\r\n", "\n")
        while "\n\n" in buffer:
            frame, buffer = buffer.split("\n\n", 1)
            fields = dict(
                line.split(": ", 1) for line in frame.splitlines()
                if line.startswith(("event: ", "data: "))
            )
            if "data" not in fields:
                continue
            name = fields.get("event")
            data = json.loads(fields["data"])
            if name == "sources":
                sources = data["sources"]
            elif name == "token":
                tokens.append(data["text"])
            elif name == "error":
                raise RuntimeError(data.get("message", "Chat stream failed"))
            elif name == "timing" and meta is not None:
                meta["timing"] = data
            elif name == "done":
                return "".join(tokens), sources
    raise ValueError("Chat stream ended without a done event")


def read_chat(query, session=requests, url=API_URL, meta=None):
    with session.post(url, json={"query": query}, stream=True, timeout=(10, 300)) as response:
        response.raise_for_status()
        if meta is not None:
            meta["llm"] = response.headers.get("X-LLM-Model")
        return parse_sse(response.iter_content(chunk_size=None), meta)


def write_results(result, output_prefix="answer_results"):
    (HERE / f"{output_prefix}.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    count_text = ", ".join(f"{count} {kind}" for kind, count in result["counts"].items())
    lines = [
        f"# {result['evaluation_set']} answer evaluation", "",
        f"Run at: {result['run_at_utc']}",
        describe_git(result),
        f"Dataset: `{result['dataset_file']}`.",
        f"Models: `{result['models']['llm']}` and `{result['models']['embedding']}`.",
        *([f"Corpus: {result['corpus']['pages']} PDF pages, {result['corpus']['chunks']} indexed chunks, {len(result['corpus']['files'])} files."] if "corpus" in result else []),
        f"Queries: {len(result['queries'])} ({count_text}).", "",
        f"Automated checks passed: {result['passed']}/{len(result['queries'])}.", "",
        "Answerable items pass when the answer contains an accepted phrase and cites the labeled physical PDF page. Unanswerable items require the exact abstention. The ambiguous item requires a clarification question. These are screening checks, not proof that every sentence is factually supported. The no-answer and ambiguity labels are task expectations, not exhaustive corpus proofs.",
        "", "## Per-query results", "",
        "| ID | Kind | Fact/behavior | Labeled page citation | Valid refs | Pass |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in result["queries"]:
        score = row["score"]
        lines.append(f"| {row['id']} | {row['kind']} | {score['fact_match']} | {score['citation_match']} | {score['citation_refs_valid']} | {score['pass']} |")
    if len(result.get("category_pass", {})) > 1:
        lines += ["", "## By category", "", "| Category | Passed |", "|---|---:|"]
        lines += [f"| {name} | {value['passed']}/{value['total']} |" for name, value in result["category_pass"].items()]
    support = result.get("citation_support")
    if support:
        def rate(bucket):
            return "n/a" if bucket["support_rate"] is None else f"{bucket['support_rate']:.0%}"
        lines += [
            "", "## Citation support", "",
            f"Judge: `{support['judge_model']}`. Each answer sentence is judged against the full physical PDF pages it cites; "
            "a supported verdict counts only when the judge's quote appears on a cited page. Page-level judging is more "
            "lenient than chunk-level judging. Reported separately from pass/fail.", "",
            f"Supported sentences: {support['overall']['supported']}/{support['overall']['scored']} ({rate(support['overall'])}).", "",
            "| Category | Scored | " + " | ".join(LABELS) + " | Support rate |",
            "|---|---:|" + "---:|" * len(LABELS) + "---:|",
        ]
        for name, bucket in support["by_category"].items():
            lines.append(f"| {name} | {bucket['scored']} | " + " | ".join(str(bucket["counts"].get(label, 0)) for label in LABELS) + f" | {rate(bucket)} |")
        flagged = [(row["id"], item) for row in result["queries"] for item in row.get("citation_support", {}).get("sentences", []) if item["label"] != "supported"]
        if flagged:
            lines += ["", "### Sentences not supported", "", "| ID | Label | Sentence | Judge quote |", "|---|---|---|---|"]
            lines += [f"| {row_id} | {item['label']} | {item['sentence'].replace('|', '/')} | {item['quote'].replace('|', '/')} |" for row_id, item in flagged]
    lines += ["", "## Answers for review", ""]
    for row in result["queries"]:
        lines += [f"### {row['id']}", "", f"Question: {row['query']}", "", f"Answer: {row['answer']}", "", f"Sources: {json.dumps(row['sources'], ensure_ascii=False)}", ""]
    (HERE / f"{output_prefix}.md").write_text("\n".join(lines), encoding="utf-8")


def run_answer_benchmark(dataset_filename="development_queries.json", output_prefix="answer_results",
                         support=True, judge=None, page_text=None, final_holdout=False):
    if dataset_filename == HOLDOUT and not final_holdout:
        raise ValueError("The final holdout runs once; pass --final-holdout to run it.")
    queries = load_queries(dataset_filename)
    if support and judge is None:
        judge = OllamaJudge()
        judge.check_available()
    page_text = page_text or PageTexts()
    results = []
    served_models = set()
    with requests.Session() as session:
        for row in queries:
            meta = {}
            answer, sources = read_chat(row["query"], session=session, meta=meta)
            served_models.add(meta["llm"])
            result = {**row, "answer": answer, "sources": sources, "score": score_answer(row, answer, sources),
                      "timing": meta.get("timing")}
            if support and row["kind"] == "answerable" and answer.strip().casefold() != ABSTAIN.casefold():
                result["citation_support"] = score_support(answer, sources, page_text, judge)
            results.append(result)
            print(f"{row['id']}: {'pass' if result['score']['pass'] else 'FAIL'}", flush=True)
    if len(served_models) != 1 or None in served_models:
        raise RuntimeError(f"API did not report one LLM model: {sorted(map(str, served_models))}")
    served_llm = served_models.pop()
    counts = {kind: sum(row["kind"] == kind for row in queries) for kind in ("answerable", "unanswerable", "ambiguous")}
    category_pass = {}
    for row in results:
        bucket = category_pass.setdefault(row.get("category", "general"), {"passed": 0, "total": 0})
        bucket["total"] += 1
        bucket["passed"] += row["score"]["pass"]
    result = {
        "run_at_utc": datetime.now(timezone.utc).isoformat(),
        **git_state(),
        "models": {"embedding": EMBEDDING_MODEL, "llm": served_llm},
        "corpus": corpus_size(),
        "dataset_file": dataset_filename,
        "evaluation_set": EVALUATION_SETS.get(dataset_filename, "Development"),
        "counts": counts,
        "passed": sum(row["score"]["pass"] for row in results),
        "category_pass": category_pass,
        "queries": results,
    }
    if support:
        result["citation_support"] = {
            "judge_model": getattr(judge, "model", None),
            **summarize_support([(row.get("category", "general"), row["citation_support"])
                                 for row in results if "citation_support" in row]),
        }
    write_results(result, output_prefix)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="development_queries.json")
    parser.add_argument("--output-prefix", default="answer_results")
    parser.add_argument("--no-support", action="store_true", help="skip sentence-level citation support")
    parser.add_argument("--final-holdout", action="store_true", help="required to run heldout_queries.json (run it once)")
    options = parser.parse_args()
    run_answer_benchmark(options.dataset, options.output_prefix, support=not options.no_support,
                         final_holdout=options.final_holdout)
