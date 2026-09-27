export const MESSAGE_KEY = "rag.messages";
export const DOCUMENT_KEY = "rag.selectedDocuments";

// Browsers that block site data throw on the first localStorage access, not just on use.
export function browserStorage(getStorage = () => window.localStorage) {
  try {
    return getStorage();
  } catch {
    return null;
  }
}

export function readStoredJson(storage, key, fallback) {
  try {
    const value = storage.getItem(key);
    return value === null ? fallback : JSON.parse(value);
  } catch {
    return fallback;
  }
}

// Saving is a convenience: a blocked or full store loses history, never the app.
export function writeStoredJson(storage, key, value) {
  try {
    storage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
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
