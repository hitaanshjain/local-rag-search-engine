# Streaming chat latency benchmark

Run at: 2026-09-28T20:51:27.706752+00:00
Git HEAD at run: `69a339c7e5d8f191bf038bc9803dd8ac8346ea13` (clean worktree).
Models: `llama3.2:3b` LLM and `nomic-embed-text` embeddings.
Hardware: GPU for the loaded LLM (Ollama reports 2554708622 bytes in VRAM); host GPU NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB, CPU Intel(R) Core(TM) i9-14900HX, Windows-11-10.0.26200-SP0.
Corpus: 1070 PDF pages, 4854 indexed chunks, 5 files.
Queries: 5 fixed queries, 2 measured requests each, plus one warmup request.

## Results

| Metric | Median | P90 |
|---|---:|---:|
| retrieval_ms | 273.0 ms | 331.7 ms |
| index_ms | 6.2 ms | 7.9 ms |
| vector_ms | 209.3 ms | 265.9 ms |
| keyword_ms | 17.9 ms | 22.3 ms |
| fusion_ms | 0.1 ms | 0.1 ms |
| first_status_ms | 15.7 ms | 24.5 ms |
| ttft_ms | 1827.4 ms | 3748.7 ms |
| full_response_ms | 1827.5 ms | 3748.7 ms |
| draft_ms | 821.4 ms | 998.4 ms |
| check_ms | 0.3 ms | 2352.7 ms |
| conflict_ms | 0.0 ms | 357.2 ms |
| answer_ms | 1517.0 ms | 3551.0 ms |
| drafts | 2.0 | 2.0 |
| check_calls | 1.0 | 5.0 |

Client times start before the POST. First status stops at the first SSE `status` event, TTFT at the first nonempty `token` event (the checked answer), and full response at `done`. The final SSE `timing` event reports retrieval (`retrieval_ms`, including its index check, vector, keyword, and fusion stages plus thread scheduling) and answer stages: `draft_ms` (all drafts), `check_ms` (claim checks and citation repair), `conflict_ms` (conflict search and comparison), `answer_ms` (drafting through the answer), `drafts`, and `check_calls` (model calls outside drafting). P90 uses the nearest-rank method. The warmup request is excluded from all statistics.

## Measured requests

| Query ID | Run | Retrieval | First status | TTFT | Full response | Draft | Check | Conflict | Drafts | Check calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| iss_03 | 1 | 331.7 ms | 23.1 ms | 2047.2 ms | 2047.2 ms | 1341.0 ms | 0.3 ms | 357.2 ms | 2 | 1 |
| iss_03 | 2 | 258.3 ms | 19.5 ms | 1607.7 ms | 1607.7 ms | 984.9 ms | 0.4 ms | 349.6 ms | 2 | 1 |
| sum_04 | 1 | 294.1 ms | 24.5 ms | 2942.2 ms | 2942.3 ms | 998.4 ms | 1631.2 ms | 0.0 ms | 2 | 4 |
| sum_04 | 2 | 331.1 ms | 11.8 ms | 2693.0 ms | 2693.0 ms | 826.5 ms | 1531.3 ms | 0.0 ms | 2 | 4 |
| urb_03 | 1 | 253.2 ms | 10.1 ms | 1151.3 ms | 1151.4 ms | 893.9 ms | 0.0 ms | 0.0 ms | 2 | 0 |
| urb_03 | 2 | 256.8 ms | 21.2 ms | 1029.0 ms | 1029.1 ms | 756.2 ms | 0.0 ms | 0.0 ms | 2 | 0 |
| uni_02 | 1 | 394.8 ms | 30.4 ms | 417.5 ms | 417.5 ms | 0.0 ms | 0.0 ms | 0.0 ms | 0 | 0 |
| uni_02 | 2 | 206.8 ms | 11.3 ms | 211.9 ms | 211.9 ms | 0.0 ms | 0.0 ms | 0.0 ms | 0 | 0 |
| cha_02 | 1 | 287.7 ms | 10.2 ms | 4044.3 ms | 4044.3 ms | 816.4 ms | 2352.7 ms | 583.7 ms | 1 | 5 |
| cha_02 | 2 | 193.5 ms | 8.1 ms | 3748.7 ms | 3748.7 ms | 745.9 ms | 2466.2 ms | 338.6 ms | 1 | 5 |
