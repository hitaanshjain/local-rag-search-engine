import assert from "node:assert/strict";
import test from "node:test";

import { createSSEParser } from "./sse.js";

test("parses sources, split token frames, and done", () => {
  const events = [];
  const parser = createSSEParser((event, data) => events.push([event, data]));

  parser.push('event: sources\ndata: {"sources":[{"source":"zoning.pdf","page":2}]}\n\n');
  parser.push('event: token\ndata: {"text":"hé');
  parser.push('llo\\nworld"}\n\nevent: done\ndata: {}\n\n');

  assert.deepEqual(events, [
    ["sources", { sources: [{ source: "zoning.pdf", page: 2 }] }],
    ["token", { text: "héllo\nworld" }],
    ["done", {}],
  ]);
});
