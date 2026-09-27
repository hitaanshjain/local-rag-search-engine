export const MESSAGE_KEY = "rag.messages";
export const DOCUMENT_KEY = "rag.selectedDocuments";

export function readStoredJson(storage, key, fallback) {
  try {
    const value = storage.getItem(key);
    return value === null ? fallback : JSON.parse(value);
  } catch {
    return fallback;
  }
}

export function historyForRequest(messages) {
  return messages
    .filter((message) => (message.role === "user" || message.role === "bot") && message.text?.trim())
    .map((message) => ({ role: message.role === "bot" ? "assistant" : "user", text: message.text.slice(0, 4000) }))
    .slice(-12);
}

export function selectedAvailableDocuments(saved, available) {
  if (saved === null) return available.map((doc) => doc.name);
  if (!Array.isArray(saved)) return available.map((doc) => doc.name);
  const names = new Set(available.map((doc) => doc.name));
  return [...new Set(saved)].filter((name) => names.has(name));
}
