import time
import requests
import statistics

API_URL = "http://localhost:8000/chat"
TEST_QUERIES = [
    "What are the zoning regulations?",
    "Explain the commercial lease terms.",
    "Who is responsible for property maintenance?",
    "What is the penalty for late rent?",
    "Can the property be subleased?"
]

def run_latency_test(iterations=10):
    print(f"Running Latency Benchmark: {iterations} iterations per query...")
    latencies = []
    
    for query in TEST_QUERIES:
        for _ in range(iterations):
            start_time = time.time()
            try:
                response = requests.post(API_URL, json={"query": query})
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f"Request failed: {e}")
                continue
            
            end_time = time.time()
            latency_ms = (end_time - start_time) * 1000
            latencies.append(latency_ms)
            
    if not latencies:
        print("Test failed. No successful requests.")
        return

    p50 = statistics.median(latencies)
    p90 = statistics.quantiles(latencies, n=10)[8]
    p99 = statistics.quantiles(latencies, n=100)[98]
    mean_latency = statistics.mean(latencies)

    print("\n--- Benchmark Results ---")
    print(f"Total Requests: {len(latencies)}")
    print(f"Mean Latency:   {mean_latency:.2f} ms")
    print(f"P50 (Median):   {p50:.2f} ms")
    print(f"P90 Latency:    {p90:.2f} ms")
    print(f"P99 Latency:    {p99:.2f} ms")
    print("-------------------------")

if __name__ == "__main__":
    run_latency_test()