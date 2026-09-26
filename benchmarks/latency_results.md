# Streaming chat latency benchmark

Run at: 2026-09-25T05:09:05.362898+00:00
Git HEAD at run: `0eed7423ebf992265f2b0d1d70451fae7e1fd92e` (worktree changes may have been present).
Models: `llama3.2:3b` LLM and `nomic-embed-text` embeddings.
Hardware: GPU for the loaded LLM (Ollama reports 2554708622 bytes in VRAM).
Corpus: 1070 checked-in PDF pages.
Queries: 5 fixed queries, 2 measured requests each, plus one warmup request.

## Results

| Metric | Median | P90 |
|---|---:|---:|
| retrieval_ms | 174.4 ms | 186.2 ms |
| index_ms | 0.9 ms | 0.9 ms |
| vector_ms | 127.4 ms | 145.5 ms |
| keyword_ms | 14.4 ms | 20.7 ms |
| fusion_ms | 0.0 ms | 0.0 ms |
| ttft_ms | 313.4 ms | 537.5 ms |
| full_response_ms | 775.0 ms | 950.3 ms |

Time to first token (TTFT) starts before the POST and stops at the first nonempty SSE `token` event. Full response time stops at the SSE `done` event. The API reports retrieval and its index, vector, keyword, and fusion stages in `Server-Timing`; total retrieval also includes thread scheduling and other overhead. P90 uses the nearest-rank method. The warmup request is excluded from all statistics.

## Measured requests

| Query ID | Run | Retrieval | Index | Vector | Keyword | Fusion | TTFT | Full response |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| iss_03 | 1 | 173.0 ms | 0.9 ms | 111.4 ms | 22.3 ms | 0.0 ms | 294.6 ms | 757.0 ms |
| iss_03 | 2 | 186.2 ms | 0.8 ms | 127.7 ms | 20.7 ms | 0.0 ms | 303.5 ms | 646.5 ms |
| sum_04 | 1 | 186.2 ms | 0.9 ms | 141.6 ms | 16.4 ms | 0.0 ms | 502.1 ms | 846.3 ms |
| sum_04 | 2 | 168.5 ms | 1.0 ms | 127.1 ms | 14.4 ms | 0.0 ms | 321.2 ms | 666.9 ms |
| urb_03 | 1 | 167.6 ms | 0.9 ms | 126.1 ms | 14.2 ms | 0.0 ms | 428.1 ms | 950.3 ms |
| urb_03 | 2 | 166.7 ms | 0.7 ms | 123.6 ms | 13.8 ms | 0.0 ms | 276.6 ms | 793.1 ms |
| uni_02 | 1 | 185.1 ms | 0.7 ms | 145.5 ms | 14.5 ms | 0.1 ms | 537.5 ms | 664.1 ms |
| uni_02 | 2 | 175.8 ms | 0.8 ms | 132.4 ms | 15.6 ms | 0.0 ms | 305.6 ms | 420.1 ms |
| cha_02 | 1 | 224.5 ms | 0.9 ms | 187.9 ms | 12.4 ms | 0.0 ms | 705.1 ms | 1247.4 ms |
| cha_02 | 2 | 146.6 ms | 0.7 ms | 112.6 ms | 11.8 ms | 0.0 ms | 265.6 ms | 796.3 ms |
