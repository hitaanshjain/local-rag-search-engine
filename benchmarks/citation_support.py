"""Sentence-by-sentence citation support for benchmark answers.

A separate local judge checks each cited sentence against the full physical PDF
pages it cites. A "supported" verdict counts only when the judge's quote appears
on a cited page. This is a screening measurement, not proof of correctness.
"""

import re
from collections import Counter
from typing import Callable

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
