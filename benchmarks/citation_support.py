"""Sentence-by-sentence citation support for benchmark answers.

A separate local judge checks each cited sentence against the full physical PDF
pages it cites. A "supported" verdict counts only when the judge's quote appears
on a cited page. This is a screening measurement, not proof of correctness.
"""

import argparse
import json
import os
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import pymupdf
import requests
from langchain_ollama import ChatOllama

from app.engine import OLLAMA_BASE_URL
from app.pdf_extraction import extract_text_layout, text_is_usable

ABSTAIN = "I don't know based on these documents."
LABELS = ("supported", "partial", "unsupported", "uncited", "unverified")
CITATION_GROUP = re.compile(r"\[((?:\d+\s*,\s*)*\d+)\]")
SENTENCE_BREAK = re.compile(r"(?<=[.!?\]])\s+(?=[\"“A-Z])")
FACTUAL = re.compile(
    r"\d|\b(?:shall|must|may|permitted|prohibited|required|minimum|maximum|exceed)\b"
    r"|\b[A-Za-z][A-Za-z0-9]*-\d+\b",
    re.I,
)
QUOTE_MARKS = str.maketrans({"“": '"', "”": '"', "‘": "'", "’": "'"})


def split_sentences(answer: str) -> list[str]:
    sentences = []
    for line in answer.splitlines():
        line = line.strip()
        if not line or line.startswith("Jurisdiction:") or line.casefold() == ABSTAIN.casefold():
            continue
        for part in SENTENCE_BREAK.split(line):
            part = part.strip()
            if part and not strip_citations(part).rstrip().endswith("?"):
                sentences.append(part)
    return sentences


def sentence_citations(sentence: str) -> list[int]:
    return [int(n) for group in CITATION_GROUP.findall(sentence) for n in re.findall(r"\d+", group)]


def strip_citations(sentence: str) -> str:
    text = CITATION_GROUP.sub("", sentence)
    return re.sub(r"\s+([.,;:!?])", r"\1", re.sub(r"\s+", " ", text)).strip()


def normalize(text: str) -> str:
    return " ".join(text.translate(QUOTE_MARKS).split()).casefold()


def quote_on_page(quote: str, page_texts: list[str]) -> bool:
    quote = quote.translate(QUOTE_MARKS).strip(" \"'…").rstrip(".").strip()
    if len(quote.split()) < 3 and not re.search(r"\d", quote):
        return False
    needle = normalize(quote)
    return bool(needle) and any(needle in normalize(text) for text in page_texts)


def judge_sentence(claim: str, cited: list[dict], page_text, judge) -> tuple[str, str, list]:
    """Judge one claim against its cited pages joined together; the quote must be on one of them."""
    keys = list(dict.fromkeys((source.get("source"), source.get("page")) for source in cited))
    texts = {key: page_text(*key) for key in keys}
    readable = {key: text for key, text in texts.items() if text}
    if not readable:
        return "unverified", "", keys
    joined = "\n\n".join(f"=== {source} page {page} ===\n{text}" for (source, page), text in readable.items())
    try:
        reply = judge(claim, joined)
        verdict, quote = reply["verdict"], str(reply.get("quote") or "")
    except Exception:
        return "unverified", "", keys
    if verdict == "supported":
        label = "supported" if quote_on_page(quote, list(readable.values())) else "unverified"
    elif verdict == "partial":
        label = "partial"
    elif verdict == "unsupported":
        # An unreadable cited page might have held the support.
        label = "unverified" if len(readable) < len(keys) else "unsupported"
    else:
        label = "unverified"
    return label, quote, keys


def score_support(answer: str, sources: list[dict], page_text: Callable, judge: Callable) -> dict:
    rows = []
    for sentence in split_sentences(answer):
        refs = sentence_citations(sentence)
        claim = strip_citations(sentence)
        if not refs:
            if FACTUAL.search(claim):
                rows.append({"sentence": sentence, "citations": [], "label": "uncited", "quote": "", "pages": []})
            continue
        if any(not 1 <= number <= len(sources) for number in refs):
            rows.append({"sentence": sentence, "citations": refs, "label": "unverified", "quote": "", "pages": []})
            continue
        label, quote, keys = judge_sentence(claim, [sources[n - 1] for n in refs], page_text, judge)
        rows.append({"sentence": sentence, "citations": refs, "label": label, "quote": quote,
                     "pages": [list(key) for key in keys]})
    counts = Counter(row["label"] for row in rows)
    return {"sentences": rows, "counts": dict(counts), "scored": len(rows), "supported": counts["supported"]}


def _bucket(results: list[dict]) -> dict:
    counts = Counter()
    for result in results:
        counts.update(result["counts"])
    scored = sum(result["scored"] for result in results)
    supported = sum(result["supported"] for result in results)
    return {"scored": scored, "supported": supported, "counts": dict(counts),
            "support_rate": supported / scored if scored else None}


def summarize_support(items: list[tuple[str, dict]]) -> dict:
    by_category = {}
    for category, result in items:
        by_category.setdefault(category, []).append(result)
    return {
        "overall": _bucket([result for _, result in items]),
        "by_category": {category: _bucket(results) for category, results in sorted(by_category.items())},
    }


ROOT = Path(__file__).resolve().parents[1]
HERE = Path(__file__).resolve().parent
DEFAULT_PAGE_ROOTS = [ROOT / "data", HERE / "fixtures" / "pdfs"]
DEFAULT_JUDGE_MODEL = "qwen2.5:7b"
JUDGE_PROMPT = """You check whether PDF page text supports one sentence.

Page text:
<<<
{page}
>>>

Sentence: {sentence}

Decide whether the page text states everything the sentence claims. Numbers, units, district or
section codes, negation ("not", "no"), and exceptions ("except", "unless") all matter. If the
sentence claims anything the page does not state, it is not fully supported.

Reply with JSON only, in this shape:
{{"verdict": "supported", "quote": "exact text copied from the page"}}
The verdict must be one of "supported", "partial", or "unsupported". The quote must be the
shortest passage from the page text that supports the sentence, copied character for character,
or an empty string when nothing supports it."""


class PageTexts:
    """Full physical page text from the app's layout extractor, cached per page."""

    def __init__(self, roots=None):
        self.roots = [Path(root) for root in (roots or DEFAULT_PAGE_ROOTS)]
        self._cache = {}

    def __call__(self, source, page):
        key = (source, page)
        if key not in self._cache:
            self._cache[key] = self._load(source, page)
        return self._cache[key]

    def _load(self, source, page):
        if not isinstance(source, str) or not isinstance(page, int):
            return None
        path = next((root / source for root in self.roots if (root / source).is_file()), None)
        if path is None:
            return None
        with pymupdf.open(path) as pdf:
            if not 1 <= page <= len(pdf):
                return None
            text = extract_text_layout(pdf[page - 1])
        return text if text_is_usable(text) else None


class OllamaJudge:
    def __init__(self, model=None, llm=None):
        self.model = model or os.getenv("BENCH_JUDGE_MODEL", DEFAULT_JUDGE_MODEL)
        self.llm = llm or ChatOllama(
            model=self.model, base_url=OLLAMA_BASE_URL, temperature=0, format="json", num_ctx=8192,
        )

    def __call__(self, sentence, page):
        reply = self.llm.invoke(JUDGE_PROMPT.format(page=page[:16000], sentence=sentence)).content
        data = json.loads(reply)
        if data.get("verdict") not in {"supported", "partial", "unsupported"}:
            raise ValueError(f"Judge returned an unknown verdict: {data.get('verdict')!r}")
        return {"verdict": data["verdict"], "quote": str(data.get("quote") or "")}

    def check_available(self):
        response = requests.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=10)
        response.raise_for_status()
        names = {model["name"] for model in response.json().get("models", [])}
        if self.model not in names:
            raise RuntimeError(
                f"Judge model {self.model} is not available. Run: docker compose exec ollama ollama pull {self.model}"
            )


def calibrate(rows, judge, page_text):
    results = []
    for row in rows:
        label, quote, _ = judge_sentence(row["sentence"], [{"source": row["source"], "page": row["page"]}], page_text, judge)
        results.append({**row, "label": label, "quote": quote, "agree": label == row["expected"]})
    by_expected = {}
    for row in results:
        by_expected.setdefault(row["expected"], []).append(row["agree"])
    return {
        "judge_model": getattr(judge, "model", None),
        "rows": results,
        "agreement": {
            "overall": sum(row["agree"] for row in results) / len(results),
            "by_expected": {label: sum(values) / len(values) for label, values in sorted(by_expected.items())},
        },
    }


def write_calibration(result):
    result = {"run_at_utc": datetime.now(timezone.utc).isoformat(), **result}
    (HERE / "judge_calibration_results.json").write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    lines = [
        "# Citation-support judge calibration", "",
        f"Run at: {result['run_at_utc']}", f"Judge: `{result['judge_model']}`.", "",
        f"Agreement with hand labels: {result['agreement']['overall']:.0%} ({len(result['rows'])} pairs).", "",
        "| Expected | Agreement |", "|---|---:|",
        *[f"| {label} | {value:.0%} |" for label, value in result["agreement"]["by_expected"].items()],
        "", "| ID | Expected | Judge label | Sentence |", "|---|---|---|---|",
        *[f"| {row['id']} | {row['expected']} | {row['label']} | {row['sentence']} |" for row in result["rows"]],
        "",
    ]
    (HERE / "judge_calibration_results.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--calibrate", action="store_true", required=True)
    parser.parse_args()
    judge = OllamaJudge()
    judge.check_available()
    rows = json.loads((HERE / "judge_calibration.json").read_text(encoding="utf-8"))
    write_calibration(calibrate(rows, judge, PageTexts()))
