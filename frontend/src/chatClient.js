import { createSSEParser } from "./sse.js";

export async function streamChat(query, onEvent, { fetchImpl = fetch, signal, apiBase = "/api", history = [], documents = null } = {}) {
  const response = await fetchImpl(`${apiBase}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, history, documents }),
    signal,
  });
  if (!response.ok || !response.body) throw new Error("Chat request failed.");

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let completed = false;
  const parser = createSSEParser((event, data) => {
    if (event === "error") throw new Error(data.message || "Answer generation failed.");
    if (event === "done") completed = true;
    onEvent(event, data);
  });
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
    }
    parser.push(decoder.decode());
    if (!completed) throw new Error("Response stream ended unexpectedly.");
  } finally {
    reader.releaseLock();
  }
}

export function citationParts(text, sourceCount) {
  const parts = [];
  const pattern = /\[((?:\d+\s*,\s*)*\d+)\]/g;
  let last = 0;
  for (const match of text.matchAll(pattern)) {
    const numbers = match[1].match(/\d+/g).map(Number);
    if (!numbers.some((number) => number >= 1 && number <= sourceCount)) continue;
    if (match.index > last) parts.push({ text: text.slice(last, match.index) });
    numbers.forEach((number, i) => {
      if (i) parts.push({ text: ", " });
      if (number >= 1 && number <= sourceCount) parts.push({ number });
      else parts.push({ text: `[${number}]` });
    });
    last = match.index + match[0].length;
  }
  if (last < text.length) parts.push({ text: text.slice(last) });
  return parts;
}

export function documentUrl(apiBase, source) {
  return `${apiBase}/documents/${encodeURIComponent(source.source)}#page=${encodeURIComponent(source.page)}`;
}
