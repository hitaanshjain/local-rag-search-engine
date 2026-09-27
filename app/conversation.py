"""Use bounded conversation context to retrieve evidence for follow-ups."""


def format_history(history: list[dict[str, str]]) -> str:
    return "\n".join(
        f"{'User' if turn['role'] == 'user' else 'Assistant'}: {turn['text']}"
        for turn in history[-6:]
    )


async def contextualize_query(query: str, history: list[dict[str, str]], llm) -> str:
    if not history:
        return query
    prompt = (
        "Rewrite the latest question as one standalone search query using the conversation only to resolve "
        "references such as 'it', 'there', or 'that district'. Keep the current question's intent. "
        "Do not answer it or add facts. Return only the search query.\n"
        f"Conversation:\n{format_history(history)}\nLatest question: {query}"
    )
    response = await llm.ainvoke(prompt)
    rewritten = str(response.content).strip().strip('"')
    return rewritten[:500] or query
