# Streaming chat latency benchmark

Run at: 2026-09-27T00:25:21.729805+00:00
Git HEAD at run: `b2eb89484e12925d5b0bbe08e6ef64ff7284b51b` (worktree changes may have been present).
Models: `llama3.2:3b` LLM and `nomic-embed-text` embeddings.
Hardware: GPU for the loaded LLM (Ollama reports 2554708622 bytes in VRAM).
Corpus: 1070 checked-in PDF pages.
Queries: 5 fixed queries, 2 measured requests each, plus one warmup request.

## Results

| Metric | Median | P90 |
|---|---:|---:|
| retrieval_ms | 215.6 ms | 227.8 ms |
| index_ms | 6.7 ms | 7.7 ms |
| vector_ms | 165.9 ms | 181.0 ms |
| keyword_ms | 16.6 ms | 19.4 ms |
| fusion_ms | 0.1 ms | 0.1 ms |
| ttft_ms | 1884.8 ms | 3587.2 ms |
| full_response_ms | 1884.8 ms | 3587.2 ms |

Time to first token (TTFT) starts before the POST and stops at the first nonempty SSE `token` event. Full response time stops at the SSE `done` event. The API reports retrieval and its index, vector, keyword, and fusion stages in `Server-Timing`; total retrieval also includes thread scheduling and other overhead. P90 uses the nearest-rank method. The warmup request is excluded from all statistics.

## Measured requests

| Query ID | Run | Retrieval | Index | Vector | Keyword | Fusion | TTFT | Full response |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| iss_03 | 1 | 207.0 ms | 3.0 ms | 150.3 ms | 20.3 ms | 0.1 ms | 2077.0 ms | 2077.0 ms |
| iss_03 | 2 | 218.2 ms | 7.2 ms | 154.5 ms | 19.4 ms | 0.1 ms | 1825.7 ms | 1825.7 ms |
| sum_04 | 1 | 213.0 ms | 6.7 ms | 163.2 ms | 16.6 ms | 0.1 ms | 1944.0 ms | 1944.0 ms |
| sum_04 | 2 | 177.0 ms | 6.0 ms | 119.0 ms | 19.4 ms | 0.1 ms | 1454.6 ms | 1454.6 ms |
| urb_03 | 1 | 221.0 ms | 7.8 ms | 173.4 ms | 15.1 ms | 0.1 ms | 2053.3 ms | 2053.3 ms |
| urb_03 | 2 | 183.4 ms | 6.4 ms | 131.6 ms | 15.2 ms | 0.1 ms | 1821.1 ms | 1821.1 ms |
| uni_02 | 1 | 230.9 ms | 6.8 ms | 181.0 ms | 16.5 ms | 0.1 ms | 1141.4 ms | 1141.4 ms |
| uni_02 | 2 | 220.4 ms | 5.8 ms | 170.6 ms | 16.9 ms | 0.1 ms | 963.6 ms | 963.6 ms |
| cha_02 | 1 | 227.8 ms | 7.7 ms | 184.9 ms | 13.7 ms | 0.1 ms | 4127.5 ms | 4127.6 ms |
| cha_02 | 2 | 211.0 ms | 7.2 ms | 168.6 ms | 12.6 ms | 0.1 ms | 3587.2 ms | 3587.2 ms |
