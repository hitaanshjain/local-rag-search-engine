import assert from "node:assert/strict";
import test from "node:test";
import { historyForRequest, readStoredJson, selectedAvailableDocuments } from "./conversation.js";

test("completed turns become bounded follow-up history", () => {
  const messages = [{ role: "greeting", text: "Hello" }, { role: "user", text: "R-2 rules?" }, { role: "bot", text: "R-2 answer" }, { role: "bot", text: "" }];
  assert.deepEqual(historyForRequest(messages), [
    { role: "user", text: "R-2 rules?" },
    { role: "assistant", text: "R-2 answer" },
  ]);
  assert.deepEqual(historyForRequest([]), []);
});

test("saved document choices stay within the indexed catalog", () => {
  const available = [{ name: "a.pdf" }, { name: "b.pdf" }];
  assert.deepEqual(selectedAvailableDocuments(null, available), ["a.pdf", "b.pdf"]);
  assert.deepEqual(selectedAvailableDocuments(["b.pdf", "gone.pdf", "b.pdf"], available), ["b.pdf"]);
  assert.deepEqual(selectedAvailableDocuments([], available), []);
});

test("invalid stored conversation data falls back safely", () => {
  assert.deepEqual(readStoredJson({ getItem: () => "broken" }, "key", []), []);
});
