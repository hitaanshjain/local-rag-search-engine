# Streaming chat latency benchmark

Run at: 2026-09-27T01:42:13.240794+00:00
Git HEAD at run: `3f2fd87b8c608c3a90bcec28a7a4b045685b1e90` (worktree changes may have been present).
Models: `llama3.2:3b` LLM and `nomic-embed-text` embeddings.
Hardware: GPU for the loaded LLM (Ollama reports 2554708622 bytes in VRAM).
Corpus: 1070 checked-in PDF pages.
Queries: 5 fixed queries, 2 measured requests each, plus one warmup request.

## Results

| Metric | Median | P90 |
|---|---:|---:|
| retrieval_ms | 209.2 ms | 229.5 ms |
| index_ms | 5.6 ms | 6.9 ms |
| vector_ms | 147.7 ms | 183.4 ms |
| keyword_ms | 15.2 ms | 22.6 ms |
| fusion_ms | 0.1 ms | 0.1 ms |
| first_status_ms | 227.9 ms | 256.1 ms |
| ttft_ms | 1398.4 ms | 3948.9 ms |
| full_response_ms | 1398.5 ms | 3948.9 ms |
| draft_ms | 787.2 ms | 1011.1 ms |
| check_ms | 0.3 ms | 2374.8 ms |
| conflict_ms | 353.5 ms | 433.9 ms |
| answer_ms | 1168.7 ms | 3763.6 ms |
| drafts | 1.0 | 2.0 |
| check_calls | 1.0 | 5.0 |

Client times start before the POST. First status stops at the first SSE `status` event, TTFT at the first nonempty `token` event (the checked answer), and full response at `done`. The API reports retrieval and its index, vector, keyword, and fusion stages in `Server-Timing`; total retrieval also includes thread scheduling and other overhead. The final SSE `timing` event reports answer stages: `draft_ms` (all drafts), `check_ms` (claim checks and citation repair), `conflict_ms` (conflict search and comparison), `answer_ms` (drafting through the answer), `drafts`, and `check_calls` (model calls outside drafting). P90 uses the nearest-rank method. The warmup request is excluded from all statistics.

## Measured requests

| Query ID | Run | Retrieval | First status | TTFT | Full response | Draft | Check | Conflict | Drafts | Check calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| iss_03 | 1 | 229.5 ms | 236.8 ms | 1393.8 ms | 1393.9 ms | 739.4 ms | 0.3 ms | 417.7 ms | 1 | 1 |
| iss_03 | 2 | 198.2 ms | 220.2 ms | 1163.6 ms | 1163.6 ms | 605.8 ms | 0.3 ms | 341.7 ms | 1 | 1 |
| sum_04 | 1 | 219.1 ms | 240.1 ms | 2186.3 ms | 2186.4 ms | 833.0 ms | 680.1 ms | 433.9 ms | 1 | 2 |
| sum_04 | 2 | 226.1 ms | 231.5 ms | 1744.7 ms | 1744.7 ms | 586.1 ms | 608.7 ms | 318.4 ms | 1 | 2 |
| urb_03 | 1 | 199.2 ms | 224.2 ms | 1403.0 ms | 1403.1 ms | 813.9 ms | 0.3 ms | 365.3 ms | 1 | 1 |
| urb_03 | 2 | 194.4 ms | 224.2 ms | 1242.0 ms | 1242.0 ms | 727.8 ms | 0.2 ms | 290.4 ms | 1 | 1 |
| uni_02 | 1 | 226.7 ms | 256.1 ms | 1370.3 ms | 1370.4 ms | 1114.5 ms | 0.0 ms | 0.0 ms | 2 | 0 |
| uni_02 | 2 | 168.0 ms | 190.9 ms | 950.9 ms | 951.0 ms | 760.6 ms | 0.0 ms | 0.0 ms | 2 | 0 |
| cha_02 | 1 | 241.2 ms | 268.1 ms | 4525.1 ms | 4525.1 ms | 901.0 ms | 2785.2 ms | 571.7 ms | 1 | 5 |
| cha_02 | 2 | 181.1 ms | 186.7 ms | 3948.9 ms | 3948.9 ms | 1011.1 ms | 2374.8 ms | 377.4 ms | 1 | 5 |
