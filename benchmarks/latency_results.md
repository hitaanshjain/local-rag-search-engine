# Streaming chat latency benchmark

Run at: 2026-10-02T22:36:11.093470+00:00
Git HEAD at run: `0d832d14e4f3a7efc34268f358003d15ebd3d8d1` (clean worktree).
Models: `llama3.2:3b` LLM and `nomic-embed-text` embeddings.
Hardware: GPU for the loaded LLM (Ollama reports 2554708622 bytes in VRAM); host GPU NVIDIA GeForce RTX 4060 Laptop GPU, 8188 MiB, CPU Intel(R) Core(TM) i9-14900HX, Windows-11-10.0.26300-SP0.
Corpus: 1070 PDF pages, 4854 indexed chunks, 5 files.
Queries: 5 fixed queries, 2 measured requests each, plus one warmup request.

## Results

| Metric | Median | P90 |
|---|---:|---:|
| retrieval_ms | 181.2 ms | 201.8 ms |
| index_ms | 4.3 ms | 5.3 ms |
| vector_ms | 129.4 ms | 151.0 ms |
| keyword_ms | 14.8 ms | 19.5 ms |
| fusion_ms | 0.1 ms | 0.1 ms |
| first_status_ms | 23.4 ms | 27.5 ms |
| ttft_ms | 1499.0 ms | 2589.4 ms |
| full_response_ms | 1499.0 ms | 2589.4 ms |
| draft_ms | 738.8 ms | 904.5 ms |
| check_ms | 0.3 ms | 1468.7 ms |
| conflict_ms | 0.0 ms | 351.0 ms |
| answer_ms | 1354.6 ms | 2384.0 ms |
| drafts | 2.0 | 2.0 |
| check_calls | 1.0 | 4.0 |

Client times start before the POST. First status stops at the first SSE `status` event, TTFT at the first nonempty `token` event (the checked answer), and full response at `done`. The final SSE `timing` event reports retrieval (`retrieval_ms`, including its index check, vector, keyword, and fusion stages plus thread scheduling) and answer stages: `draft_ms` (all drafts), `check_ms` (claim checks and citation repair), `conflict_ms` (conflict search and comparison), `answer_ms` (drafting through the answer), `drafts`, and `check_calls` (model calls outside drafting). P90 uses the nearest-rank method. The warmup request is excluded from all statistics.

## Measured requests

| Query ID | Run | Retrieval | First status | TTFT | Full response | Draft | Check | Conflict | Drafts | Check calls |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| iss_03 | 1 | 110.7 ms | 5.2 ms | 1455.5 ms | 1455.6 ms | 1044.9 ms | 0.3 ms | 296.6 ms | 2 | 1 |
| iss_03 | 2 | 171.4 ms | 7.9 ms | 1542.4 ms | 1542.5 ms | 904.5 ms | 0.3 ms | 462.0 ms | 2 | 1 |
| sum_04 | 1 | 226.0 ms | 23.9 ms | 2095.2 ms | 2095.2 ms | 904.3 ms | 945.9 ms | 0.0 ms | 2 | 4 |
| sum_04 | 2 | 179.3 ms | 8.0 ms | 1811.6 ms | 1811.6 ms | 705.0 ms | 923.1 ms | 0.0 ms | 2 | 4 |
| urb_03 | 1 | 185.2 ms | 27.5 ms | 1013.4 ms | 1013.5 ms | 804.3 ms | 0.0 ms | 0.0 ms | 2 | 0 |
| urb_03 | 2 | 201.8 ms | 30.5 ms | 858.0 ms | 858.0 ms | 631.0 ms | 0.0 ms | 0.0 ms | 2 | 0 |
| uni_02 | 1 | 177.8 ms | 23.0 ms | 969.0 ms | 969.0 ms | 772.7 ms | 0.0 ms | 0.0 ms | 2 | 0 |
| uni_02 | 2 | 172.1 ms | 18.9 ms | 748.0 ms | 748.0 ms | 561.1 ms | 0.0 ms | 0.0 ms | 2 | 0 |
| cha_02 | 1 | 187.7 ms | 24.5 ms | 2589.4 ms | 2589.4 ms | 564.1 ms | 1468.7 ms | 351.0 ms | 1 | 4 |
| cha_02 | 2 | 183.2 ms | 25.5 ms | 2756.1 ms | 2756.2 ms | 655.2 ms | 1595.2 ms | 301.4 ms | 1 | 4 |
