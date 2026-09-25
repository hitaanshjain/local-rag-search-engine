# Streaming chat latency benchmark

Run at: 2026-09-25T01:41:41.996448+00:00
Git HEAD at run: `6e7b760268da3573a1c3a2f1722fc59a6c05a7bc` (task 5 worktree changes were uncommitted during the run).
Models: `llama3.2:1b` LLM and `nomic-embed-text` embeddings.
Hardware: GPU for the loaded LLM (Ollama reports 1514584145 bytes in VRAM).
Corpus: 1070 checked-in PDF pages.
Queries: 5 fixed queries, 2 measured requests each, plus one warmup request.

## Results

| Metric | Median | P90 |
|---|---:|---:|
| retrieval_ms | 1327.3 ms | 1739.6 ms |
| ttft_ms | 1638.7 ms | 2098.5 ms |
| full_response_ms | 1878.2 ms | 2414.5 ms |

Time to first token (TTFT) starts before the POST and stops at the first nonempty SSE `token` event. Full response time stops at the SSE `done` event. Retrieval time is measured by the server around its production hybrid search for the *same request* and returned in the `Server-Timing` header. P90 uses the nearest-rank method. The warmup request is excluded from all statistics.

## Measured requests

| Query ID | Run | Retrieval | TTFT | Full response |
|---|---:|---:|---:|---:|
| iss_03 | 1 | 1217.5 ms | 1349.3 ms | 1750.5 ms |
| iss_03 | 2 | 994.2 ms | 1130.8 ms | 1335.1 ms |
| sum_04 | 1 | 1739.6 ms | 2009.5 ms | 2242.9 ms |
| sum_04 | 2 | 1296.7 ms | 1429.4 ms | 1669.7 ms |
| urb_03 | 1 | 888.3 ms | 6499.7 ms | 6792.8 ms |
| urb_03 | 2 | 1582.1 ms | 1715.2 ms | 1990.3 ms |
| uni_02 | 1 | 1357.8 ms | 1562.1 ms | 1807.3 ms |
| uni_02 | 2 | 953.7 ms | 1074.7 ms | 1271.3 ms |
| cha_02 | 1 | 1602.3 ms | 1807.8 ms | 1949.1 ms |
| cha_02 | 2 | 1953.6 ms | 2098.5 ms | 2414.5 ms |
