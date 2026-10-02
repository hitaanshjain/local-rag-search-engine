# How it works

[Back to README](../README.md)

This project answers questions about PDFs using local Ollama models. FastAPI retrieves relevant chunks from Chroma, checks generated claims against their cited passages, compares competing rules, and sends the answer with file, PDF page, and passage excerpts to a React chat UI.

The [README](../README.md#how-it-works) has the pipeline diagram.

Ingestion reads the PDFs in `data/`, assigns `source` and one-based `page` metadata, labels chunks by their section heading (`6-15 TCMU…`, `Sec. 54-269.…`, or `APPENDIX C`), and extracts jurisdiction and document version from title material when available. The heading pattern requires an uppercase letter after a short section number. Two specific cases are then excluded: a candidate line containing the literal sequence `. .` (a spaced table-of-contents leader) and Charleston page footers such as `4-20.1 Supp. No. 6`. Dot leaders in other forms, such as `....` without spaces, are not rejected. A "Place, State" line counts as a jurisdiction only when the state is a US state. Re-running ingestion uses stable chunk IDs, updates changed chunks, and removes chunks absent from the current PDFs. After a successful corpus change, it atomically writes `chroma_db/index.version`, retrying transient Windows permission errors when replacing the marker. The API caches the BM25 index and rebuilds it only when that version changes. The generated `chroma_db/` directory is ignored by Git.

For a chat query, Chroma supplies vector candidates and `rank-bm25` scores the stored chunk corpus. Queries naming a section code use section headings and match codes such as `R-2` as whole terms; other queries retain the ordinary BM25 index. Retrieval combines normalized vector and BM25 scores at **0.25 vector / 0.75 BM25** by default, ranks **chunks**, and keeps keyword-only hits. `/chat` uses up to three retrieved chunks as context. When the top BM25 passage has a clear lead, or matches an explicitly named section, and is the top fused result, it sends that passage alone to reduce conflicting context for the small model. When two different source files match a broad question nearly equally, it asks which city or document the user means. Retrieval runs in a thread pool so its synchronous Chroma and BM25 work does not block the API event loop.

Extraction reads each PDF page with PyMuPDF and uses RapidOCR when its native text is weak. It keeps whichever result has more alphanumeric characters, writes each detected table row as column-labeled pairs (`Zone: P; Required yards Front: 10 ft. …; Required yards Side: none`) so a row stays readable in any chunk, keeps ruled tables however many cells are empty so a value stays in its column, and preserves recognized section headings as chunk boundaries. Pages without a detected table keep the PDF's drawing order, because sorting a borderless table's text by position scatters each row. Charleston page footers such as `4-20.1 Supp. No. 6` are not treated as headings. A page with no text, images, or drawings is recorded as intentionally blank and skips OCR. Ingestion writes `chroma_db/pages.json` with each PDF's page count, blank pages, and low-text pages after extraction and OCR; the ingestion log and `GET /documents` report low-text pages. Blank pages produce no chunks, while a low-text page can still produce a chunk if it contains some text. OCR and complex table layout are best effort; check the cited PDF for uncertain passages. Re-run ingestion to apply this extraction to existing PDFs.

The browser saves conversation turns and the selected PDF names locally when the browser allows it; blocked or full storage only loses that history. It sends recent turns with each follow-up. The API asks the model to rewrite the follow-up as a standalone search query and keeps the rewrite only if it retains every content word of the latest question and adds at most one word absent from the conversation; otherwise it searches a complete question as asked, or pairs a short one with the previous question. When a follow-up names a place its previous question did not, district codes and other places carried over from earlier turns are removed from the search query, since a code such as R-2 belongs to one jurisdiction: after a Union City R-2 guest-house question, "And in Charleston?" searches for Charleston guest-house rules. Place names come from the ingested jurisdictions. That search still abstains, because Charleston's ordinance calls these accessory dwelling units and retrieval does not map one term to the other. Answer claims remain tied to retrieved passages. Users can select one or more indexed PDFs; keyword search scores the whole corpus and then keeps only the selected PDFs, so scores and thresholds do not depend on the selection, and vector search and conflict comparison use the same selection. **New conversation** clears the turns and stops an in-progress response. The API itself is stateless, and query-only requests still search all indexed PDFs.

The API sends valid server-sent event frames over its POST response:

```text
event: status
data: {"stage":"searching","text":"Searching the selected documents…"}

event: status
data: {"stage":"drafting","text":"Drafting an answer…"}

event: status
data: {"stage":"checking","text":"Checking each claim against its cited passage…"}

event: status
data: {"stage":"comparing","text":"Comparing related rules…"}

event: sources
data: {"sources":[{"source":"zoning.pdf","page":4,"excerpt":"..."}]}

event: token
data: {"text":"Answer text [1]."}

event: timing
data: {"index_ms":<ms>,"rewrite_ms":<ms>,"retrieval_ms":<ms>,"vector_ms":<ms>,"keyword_ms":<ms>,"fusion_ms":<ms>,"ambiguity_ms":<ms>,"context_ms":<ms>,"draft_ms":<ms>,"check_ms":<ms>,"conflict_ms":<ms>,"answer_ms":<ms>,"drafts":<count>,"check_calls":<count>}

event: done
data: {}

```

`<ms>` and `<count>` stand for numbers; measured values are in [Measured response latency](LATENCY.md). `status` events mark each stage as it starts, and the UI shows the latest one until the answer arrives; `searching` is sent first, before any follow-up rewrite or retrieval, and a retry repeats `drafting` and `checking`. `timing` reports the stages for that request: the cached index check, follow-up rewrite, retrieval (with its vector, keyword, fusion, ambiguity, and context-selection parts), all drafts, claim checks and citation repair, conflict search and comparison, the total from drafting to the answer, the number of drafts, and the model calls made outside drafting. A clarification or an empty search sends `searching`, then `sources`, `token`, `timing`, and `done`.

An empty search sends an empty sources array and an abstention message. A search, generation, or checking failure sends a terminal `error` event; only an invalid document selection returns an HTTP error (422). The React client reads the response with `fetch`, `ReadableStream.getReader()`, and `TextDecoder`; it shows numbered sources, excerpts, and links to `/documents/{filename}#page=N`. The UI can stop a response with `AbortController`.

The API buffers the draft before sending any answer text. It checks each cited claim against its cited passage. A claim is confirmed without a model call when one sentence of the passage contains all of the claim's numbers, any district or section codes it names, and all of its content words, including at least one word naming what is measured; that sentence must also have the same negation words and contain any limit words the claim uses, such as "minimum", "maximum", or "exceed". Every other claim goes to the local model, which must return an evidence excerpt present in that passage. An unsupported citation may be reassigned only after the other passage is checked. If the first draft cannot be verified, a shorter extractive draft gets the same check; the API abstains if neither passes. It compares distinct retrieved pages in the same jurisdiction for differing rules, requires quoted evidence from both sides, and asks for clarification when the applicable jurisdiction, district, or version cannot be chosen. When the question names the other passage's section, jurisdiction, or version, the answer quotes that passage's rule instead of the draft. For differing numeric limits, it also compares rule sentences about the question's subject. The answer identifies jurisdiction, district, document version, and source using ingested metadata; missing fields say so explicitly. These checks reduce unsupported output but still depend partly on a small model and retrieved coverage; the model-based conflict check can also flag rules for different tiers of the same use (for example, developments with fewer than twenty units versus twenty or more) as conflicting. The `/chat` response also includes `X-LLM-Model` with the configured model name, which the answer evaluator records alongside its results.
