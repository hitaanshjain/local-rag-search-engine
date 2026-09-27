"""Check generated claims against cited passages and compare competing rules."""

import json
import logging
import re
from dataclasses import dataclass

from langchain_core.documents import Document

ABSTAIN = "I don't know based on these documents."
CITATION = re.compile(r"\[(?:\d+\s*,\s*)*\d+\](?:\s*(?:and|,)\s*\[(?:\d+\s*,\s*)*\d+\])*")
IDENTIFIER = re.compile(r"\b[A-Za-z][A-Za-z0-9]*-\d+\b")
RULE_LANGUAGE = re.compile(r"\d|\b(?:shall|must|may|permitted|prohibited|required|allowed|minimum|maximum|exceed|limited)\b", re.I)
NUMBER_UNIT = re.compile(r"\b(\d[\d,]*(?:\.\d+)?)\s*(square feet|feet|percent|%|acres?|visits?|units?)\b", re.I)
QUESTION_FILLER = {
    "a", "an", "and", "are", "be", "can", "city", "district", "do", "does", "for", "have",
    "how", "in", "is", "large", "limit", "many", "may", "of", "on", "per", "the", "to",
    "what", "which", "with", "would", "apply", "applies", "such", "allow", "allowed", "s",
}
logger = logging.getLogger(__name__)


@dataclass
class Conflict:
    other: Document
    primary_quote: str
    other_quote: str


def collect_conflict_candidates(
    primary: Document,
    retrieved: list[Document],
    keyword_hits: list[tuple[Document, float]],
    limit: int = 8,
) -> list[Document]:
    """Keep separate source pages in the same jurisdiction for rule comparison."""
    candidates = [primary]
    primary_jurisdiction = normalized(primary.metadata.get("jurisdiction", ""))

    def page_key(doc: Document):
        source = doc.metadata.get("source")
        page = doc.metadata.get("page")
        return (source, page) if source is not None and page is not None else ("id", doc.id)

    seen = {page_key(primary)}
    for doc in [*retrieved, *(doc for doc, _ in keyword_hits)]:
        jurisdiction = normalized(doc.metadata.get("jurisdiction", ""))
        if primary_jurisdiction and jurisdiction and jurisdiction != primary_jurisdiction:
            continue
        key = page_key(doc)
        if key in seen:
            continue
        candidates.append(doc)
        seen.add(key)
        if len(candidates) >= limit:
            break
    return candidates


def normalized(text: str) -> str:
    return " ".join(text.split()).casefold()


def quote_in_passage(quote: str, passage: Document) -> bool:
    compact_quote = re.sub(r"\W+", "", quote.casefold())
    compact_passage = re.sub(r"\W+", "", passage.page_content.casefold())
    return len(compact_quote) >= 12 and compact_quote in compact_passage


def numeric_rule_conflicts(query: str, answer: str, primary: Document, candidates: list[Document]) -> list[Conflict]:
    """Find differing numeric limits in sentences about the question's subject."""
    answer_values = {(number.replace(",", ""), unit.casefold()) for number, unit in NUMBER_UNIT.findall(answer)}
    if not answer_values:
        return []
    primary_sentences = re.split(r"(?<=[.!?;])\s+", primary.page_content)
    primary_rule = next(
        (sentence.strip() for sentence in primary_sentences
         if any((number.replace(",", ""), unit.casefold()) in answer_values for number, unit in NUMBER_UNIT.findall(sentence))),
        None,
    )
    if not primary_rule:
        return []
    jurisdiction_words = set(re.findall(r"[a-z]+", primary.metadata.get("jurisdiction", "").casefold()))
    topic_query = IDENTIFIER.sub(" ", query.casefold())
    topic_words = {
        word.removesuffix("s") if len(word) > 4 else word
        for word in re.findall(r"[a-z]+", topic_query)
        if word not in QUESTION_FILLER and word not in jurisdiction_words
    }
    if not topic_words:
        return []
    conflicts = []
    for doc in candidates[1:]:
        for sentence in re.split(r"(?<=[.!?;])\s+", doc.page_content):
            words = {
                word.removesuffix("s") if len(word) > 4 else word
                for word in re.findall(r"[a-z]+", sentence.casefold())
            }
            if not topic_words <= words:
                continue
            values = {(number.replace(",", ""), unit.casefold()) for number, unit in NUMBER_UNIT.findall(sentence)}
            if any(unit == other_unit and number != other_number
                   for number, unit in answer_values for other_number, other_unit in values):
                quote = " ".join(sentence.split())
                if quote_in_passage(quote, doc) and quote_in_passage(primary_rule, primary):
                    conflicts.append(Conflict(doc, " ".join(primary_rule.split()), quote))
                    break
    return conflicts


def cited_claims(answer: str, passage_count: int, allow_invalid: bool = False) -> list[tuple[str, list[int]]] | None:
    if answer.strip() == ABSTAIN:
        return []
    claims = []
    previous = 0
    for match in CITATION.finditer(answer):
        claim = answer[previous:match.start()].strip(" \n\t.;")
        citations = [int(value) for value in re.findall(r"\d+", match.group(0))]
        if (not claim or re.search(r"[.!?]\s+[A-Z]", claim)
                or (not allow_invalid and any(number < 1 or number > passage_count for number in citations))):
            return None
        claims.append((claim, citations))
        previous = match.end()
    if not claims or answer[previous:].strip(" \n\t.;"):
        return None
    return claims


def json_content(response) -> dict:
    text = response.content if hasattr(response, "content") else str(response)
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I)
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try:
            value, _ = decoder.raw_decode(text[match.start():])
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            return value
    raise ValueError("Expected a JSON object")


async def verify_answer(answer: str, passages: list[Document], llm) -> bool:
    """Fail closed unless every claim has valid citations and an exact evidence quote."""
    claims = cited_claims(answer, len(passages))
    if claims is None:
        return False
    for claim, citations in claims:
        for number in citations:
            if not await claim_supported(claim, passages[number - 1], llm):
                return False
    return True


async def claim_supported(claim: str, passage: Document, llm) -> bool:
    prompt = (
        "Determine whether this cited passage supports every factual assertion in the claim. "
        "Ignore source-attribution phrases; use the passage section and jurisdiction to identify scope. "
        "Ordinary paraphrases count as support. A different quantity, opposite permission, or different "
        "subject is not support. Return only JSON with supported (boolean) and quote (an exact copied "
        "excerpt showing the answer fact). No other text.\n"
        f"Claim: {claim}\n"
        f"Cited section: {passage.metadata.get('section', 'unknown')}\n"
        f"Cited jurisdiction: {passage.metadata.get('jurisdiction', 'unknown')}\n"
        f"Passage: {passage.page_content}"
    )
    try:
        result = json_content(await llm.ainvoke(prompt))
    except (ValueError, TypeError, json.JSONDecodeError):
        return False
    quote = result.get("quote")
    if not isinstance(quote, str) or not quote_in_passage(quote, passage):
        return False
    if result.get("supported") is True:
        return True
    retry = (
        "Decide whether this exact excerpt supports every factual assertion, allowing ordinary paraphrase and "
        "using the section heading for scope. A different number or opposite rule is unsupported. "
        "Return only JSON with supported (boolean) and quote (copy the same excerpt).\n"
        f"Claim: {claim}\nSection: {passage.metadata.get('section', 'unknown')}\nExcerpt: {quote}"
    )
    try:
        second = json_content(await llm.ainvoke(retry))
    except (ValueError, TypeError, json.JSONDecodeError):
        return False
    return second.get("supported") is True and isinstance(second.get("quote"), str) and quote_in_passage(second["quote"], passage)


async def repair_answer(answer: str, passages: list[Document], llm) -> str | None:
    """Reassign citations only to passages that independently support each claim."""
    leading = re.fullmatch(r"\s*\[(\d+)\]\s+(.+?)\s*", answer, flags=re.S)
    if leading and not CITATION.search(leading.group(2)):
        answer = f"{leading.group(2).rstrip('.')} [{leading.group(1)}]."
    claims = cited_claims(answer, len(passages), allow_invalid=True)
    if claims is None:
        return None
    repaired = []
    for claim, original_citations in claims:
        supporting = [
            number
            for number, passage in enumerate(passages, start=1)
            if await claim_supported(claim, passage, llm)
        ]
        if not supporting:
            return None
        chosen = next((number for number in original_citations if number in supporting), supporting[0])
        repaired.append(f"{claim} [{chosen}].")
    return " ".join(repaired)


async def detect_conflicts(query: str, primary: Document, candidates: list[Document], llm, answer: str = "") -> list[Conflict]:
    """Ask for contradictory rules, then require exact excerpts from both passages."""
    if len(candidates) < 2:
        return []
    passages = "\n\n".join(
        f"[{number}] Source: {doc.metadata.get('source')}; section: {doc.metadata.get('section', 'unknown')}; "
        f"version: {doc.metadata.get('version', 'unknown')}\n{doc.page_content}"
        for number, doc in enumerate(candidates, start=1)
    )
    prompt = (
        "Compare passage [1] with the other passages for rules about the SAME subject in the question. "
        "Report differing limits or permissions for the same regulated use and topic, including a general "
        "section versus a district section or two document versions. A qualified measurement such as heated "
        "floor area can differ from an unqualified size limit and should be reported for explanation. "
        "Both quotes must state the actual operative rules; a heading or a rule for a different use is not a conflict. "
        "Return only JSON: {\"conflicts\": [{\"candidate\": 2, \"primary_quote\": "
        "\"exact excerpt from [1]\", \"other_quote\": \"exact excerpt from the candidate\"}]}. "
        "Return an empty array if no rules conflict. Do not treat different subjects as conflicts.\n"
        f"Question: {query}\nPassages:\n{passages}"
    )
    response = await llm.ainvoke(prompt)
    try:
        result = json_content(response)
    except ValueError:
        prose = normalized(response.content)
        if "empty array" in prose and re.search(r"\bno (?:conflicts?|conflicting rules|rules about the same subject)\b", prose):
            return numeric_rule_conflicts(query, answer, primary, candidates)
        formatting_prompt = (
            "Convert this conflict-check result to one JSON object with a conflicts array. "
            "Preserve the decision and exact quoted text. If it says there are no conflicts, return "
            "only {\"conflicts\": []}. Do not invent a conflict.\n"
            f"Result: {response.content}"
        )
        try:
            result = json_content(await llm.ainvoke(formatting_prompt))
        except ValueError:
            logger.warning("Conflict check returned unparseable output")
            return numeric_rule_conflicts(query, answer, primary, candidates)
    entries = result.get("conflicts")
    if not isinstance(entries, list):
        logger.warning("Conflict check omitted its conflicts list")
        return numeric_rule_conflicts(query, answer, primary, candidates)
    conflicts = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        number = entry.get("candidate")
        primary_quote = entry.get("primary_quote")
        other_quote = entry.get("other_quote")
        if not isinstance(number, int) or not 2 <= number <= len(candidates):
            continue
        other = candidates[number - 1]
        if not isinstance(primary_quote, str) or not isinstance(other_quote, str):
            continue
        if not quote_in_passage(primary_quote, primary) or not quote_in_passage(other_quote, other):
            continue
        if not RULE_LANGUAGE.search(primary_quote) or not RULE_LANGUAGE.search(other_quote):
            continue
        if normalized(primary_quote) in normalized(other_quote) or normalized(other_quote) in normalized(primary_quote):
            continue
        conflicts.append(Conflict(other=other, primary_quote=primary_quote, other_quote=other_quote))
    for conflict in numeric_rule_conflicts(query, answer, primary, candidates):
        if conflict.other not in [item.other for item in conflicts]:
            conflicts.append(conflict)
    return conflicts


def resolve_conflict(query: str, primary: Document, other: Document) -> str | None:
    """Choose only when the question explicitly matches one passage's scope."""
    query_codes = set(IDENTIFIER.findall(query.casefold()))
    primary_codes = set(IDENTIFIER.findall(primary.metadata.get("section", "").casefold()))
    other_codes = set(IDENTIFIER.findall(other.metadata.get("section", "").casefold()))
    if query_codes & primary_codes and not query_codes & other_codes:
        return "primary"
    if query_codes & other_codes and not query_codes & primary_codes:
        return "other"
    primary_jurisdiction = primary.metadata.get("jurisdiction", "")
    other_jurisdiction = other.metadata.get("jurisdiction", "")
    if primary_jurisdiction and other_jurisdiction and primary_jurisdiction != other_jurisdiction:
        primary_named = normalized(primary_jurisdiction) in normalized(query)
        other_named = normalized(other_jurisdiction) in normalized(query)
        if primary_named != other_named:
            return "primary" if primary_named else "other"
    primary_version = primary.metadata.get("version", "")
    other_version = other.metadata.get("version", "")
    if primary_version and other_version and primary_version != other_version:
        primary_named = normalized(primary_version) in normalized(query)
        other_named = normalized(other_version) in normalized(query)
        if primary_named != other_named:
            return "primary" if primary_named else "other"
    return None


def format_scope(doc: Document, query: str) -> str:
    section = doc.metadata.get("section", "")
    district_heading = re.match(r"^\d+-\d+\s+([A-Z][A-Z0-9-]{0,5})\s+[A-Z]", section)
    section_codes = IDENTIFIER.findall(section)
    query_codes = set(IDENTIFIER.findall(query.casefold()))
    district = next((code for code in section_codes if code.casefold() in query_codes), None)
    district = district or (district_heading.group(1) if district_heading else None)
    district = district or (section_codes[0] if section_codes else "not specified")
    return (
        f"Jurisdiction: {doc.metadata.get('jurisdiction') or 'not identified'} | "
        f"District: {district} | "
        f"Document version: {doc.metadata.get('version') or 'not identified'} | "
        f"Source: {doc.metadata.get('source') or 'unknown'}"
    )
