import assert from "node:assert/strict";
import test from "node:test";

import { citationParts, documentUrl, streamChat } from "./chatClient.js";

test("streamChat reports source and token events and rejects server errors", async () => {
  const events = [];
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('event: sources\ndata: {"sources":[]}\n\n'));
      controller.enqueue(new TextEncoder().encode('event: token\ndata: {"text":"Hello"}\n\n'));
      controller.enqueue(new TextEncoder().encode('event: error\ndata: {"message":"Answer generation failed."}\n\n'));
      controller.close();
    },
  });
  const fetchImpl = async () => ({ ok: true, body });

  await assert.rejects(
    streamChat("question", (name, data) => events.push([name, data]), { fetchImpl }),
    /Answer generation failed/,
  );
  assert.deepEqual(events.map(([name]) => name), ["sources", "token"]);
});

test("streamChat passes the abort signal to fetch", async () => {
  const controller = new AbortController();
  const fetchImpl = async (_url, options) => {
    assert.equal(options.signal, controller.signal);
    throw new DOMException("cancelled", "AbortError");
  };
  await assert.rejects(streamChat("question", () => {}, { fetchImpl, signal: controller.signal }), {
    name: "AbortError",
  });
});

test("streamChat sends selected documents and prior turns", async () => {
  const fetchImpl = async (_url, options) => {
    assert.deepEqual(JSON.parse(options.body), {
      query: "How large?",
      history: [{ role: "user", text: "R-2 guest house?" }],
      documents: ["rules.pdf"],
    });
    return { ok: true, body: new ReadableStream({ start(controller) {
      controller.enqueue(new TextEncoder().encode('event: done\\ndata: {}\\n\\n'.replaceAll('\\n', '\n')));
      controller.close();
    } }) };
  };
  await streamChat("How large?", () => {}, { fetchImpl, history: [{ role: "user", text: "R-2 guest house?" }], documents: ["rules.pdf"] });
});

test("streamChat rejects a connection that closes before done", async () => {
  const body = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode('event: token\ndata: {"text":"Partial"}\n\n'));
      controller.close();
    },
  });
  await assert.rejects(
    streamChat("question", () => {}, { fetchImpl: async () => ({ ok: true, body }) }),
    /ended unexpectedly/,
  );
});

test("citation links use only numbered retrieved sources", () => {
  assert.deepEqual(citationParts("A limit [1]. Unknown [9].", 2), [
    { text: "A limit " }, { number: 1 }, { text: ". Unknown [9]." },
  ]);
  assert.equal(
    documentUrl("http://localhost:8000", { source: "A rules.pdf", page: 7 }),
    "http://localhost:8000/documents/A%20rules.pdf#page=7",
  );
  assert.deepEqual(citationParts("A [1, 2].", 2), [
    { text: "A " }, { number: 1 }, { text: ", " }, { number: 2 }, { text: "." },
  ]);
});
