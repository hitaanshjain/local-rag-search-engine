"""Use bounded conversation context to retrieve evidence for follow-ups."""

import logging
import re

logger = logging.getLogger(__name__)


def format_history(history: list[dict[str, str]]) -> str:
    return "\n".join(
        f"{'User' if turn['role'] == 'user' else 'Assistant'}: {turn['text']}"
        for turn in history[-6:]
    )


FILLER = {
    "a", "about", "an", "and", "any", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from",
    "has", "have", "how", "in", "is", "it", "its", "may", "much", "of", "on", "or", "same", "that", "the",
    "there", "this", "to", "what", "when", "where", "which", "who", "with", "would",
    "their", "they", "them", "these", "those", "i", "me", "my", "we", "our", "you", "your",
}


def content_words(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.casefold())
    return {
        word[:-1] if len(word) > 3 and word.endswith("s") and not word.endswith("ss") else word
        for word in words if word not in FILLER
    }


def fallback_query(query: str, history: list[dict[str, str]]) -> str:
    """Search a complete question as asked; pair a short one with the previous question."""
    if len(content_words(query)) >= 4:
        return query
    previous = next((turn["text"] for turn in reversed(history) if turn["role"] == "user"), "")
    return f"{previous} {query}".strip()


def acceptable_rewrite(rewritten: str, query: str, history: list[dict[str, str]]) -> bool:
    """Keep the latest question's words and add at most one word absent from the conversation.

    One new word allows a natural "maximum" or "size"; a rewrite that invents a new subject
    ("parking spaces for a restaurant") adds several and is rejected.
    """
    words = content_words(rewritten)
    known = content_words(query) | content_words(" ".join(turn["text"] for turn in history))
    return bool(words) and content_words(query) <= words and len(words - known) <= 1


async def contextualize_query(query: str, history: list[dict[str, str]], llm) -> str:
    """Rewrite a follow-up as a standalone search query, rejecting rewrites that drift."""
    if not history:
        return query
    prompt = (
        "Rewrite the latest question as one standalone search query. Use the conversation only to fill in "
        "what the latest question leaves out: the subject being asked about, and the place, district, or "
        "document it refers to ('it', 'there', 'that district'). If the latest question only names a new "
        "place, district, or document, keep the earlier question's subject and apply it to the new one. "
        "If the latest question is already complete, return it unchanged. "
        "Do not answer it or add facts. Return only the search query.\n"
        f"Conversation:\n{format_history(history)}\nLatest question: {query}"
    )
    try:
        response = await llm.ainvoke(prompt)
    except Exception:
        logger.warning("Follow-up rewrite failed; searching without it", exc_info=True)
        return fallback_query(query, history)
    rewritten = str(response.content).strip().strip('"')[:500]
    if acceptable_rewrite(rewritten, query, history):
        return rewritten
    logger.info("Rejected follow-up rewrite %r for %r", rewritten, query)
    return fallback_query(query, history)
