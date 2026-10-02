# Measured response latency

[Back to README](../README.md)

Measured at commit `0d832d1` (clean worktree) on October 2, 2026, against the API built from that commit and the same 1,070-page, 4,854-chunk index. Hardware: NVIDIA GeForce RTX 4060 Laptop GPU (8 GB), Intel Core i9-14900HX, Windows 11. Ollama reported `llama3.2:3b` fully loaded on the **GPU** (all 2,554,708,622 bytes in VRAM), with `nomic-embed-text` embeddings.

The [latency results](../benchmarks/latency_results.md) and [raw samples](../benchmarks/latency_results.json) record five fixed questions with two measured requests each (10 requests), after one excluded warmup request. Client times are measured from the HTTP client; retrieval and answer stages are measured inside the API for the same request. P90 uses the nearest-rank method, so with 10 samples it is the ninth-slowest request.

| Metric | Median | P90 |
|---|---:|---:|
| Retrieval (server) | 181.2 ms | 201.8 ms |
| Cached index check | 4.3 ms | 5.3 ms |
| Vector query | 129.4 ms | 151.0 ms |
| BM25 query | 14.8 ms | 19.5 ms |
| First status event (`searching`) | 23.4 ms | 27.5 ms |
| First answer token | 1,499.0 ms | 2,589.4 ms |
| Full response | 1,499.0 ms | 2,589.4 ms |
| Drafting (server) | 738.8 ms | 904.5 ms |
| Claim checks and repair (server) | 0.3 ms | 1,468.7 ms |
| Conflict comparison (server) | 0.0 ms | 351.0 ms |

The first status event arrives before retrieval, because `searching` is sent before any follow-up rewrite or search. The answer is sent as one checked token after drafting, claim checks, and conflict comparison, so the first answer token nearly equals the full response time. Four of the five questions (`iss_03`, `sum_04`, `urb_03`, `uni_02`) needed a second, extractive draft on both runs, so the median request made two drafts. The P90 reflects `cha_02`, which needed four model calls for claim checks and citation repair. Conflict comparison ran on only two of the five questions, so its median is 0.0 ms. `uni_02` ("What maximum front-yard wall or fence height applies in Union City?") is no longer answered with a clarification question; neither of its drafts passes the claim check, so it returns the abstention in 748–969 ms. Its labeled page states both a four-foot and a six-foot front-yard limit. Across the eight requests that produced an answer, the median first answer token is 1,677.0 ms, the median full response is 1,677.1 ms, and their P90s are 2,756.1 ms and 2,756.2 ms. The previous committed run, at `69a339c`, measured a 1,827.5 ms median full response (2,370.1 ms across its eight answered requests) and a 3,748.7 ms P90; there, `uni_02` was wrongly answered with "Which city or document do you mean?" in 212–417 ms. The run before that, at `3f2fd87`, measured a 1,398.5 ms median full response and a 227.9 ms median first status; that API sent its first status after retrieval. These are small local GPU samples; other desktop load during the run was not recorded.

Claim checks and conflict comparison currently run in sequence. Conflict comparison uses the finished draft, and no concurrent-check configuration has been benchmarked.
