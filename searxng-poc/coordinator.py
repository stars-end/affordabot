import asyncio
import aiohttp
import random
import time
import json
from collections import defaultdict

NODES = [
    "http://localhost:8081/search",
    "http://localhost:8082/search"
]

# Provide a set of diverse, non-repeating queries
QUERIES = [
    "what is the capital of france",
    "latest machine learning news",
    "how to bake a sourdough bread",
    "best open source llm 2024",
    "python asyncio tutorial",
    "docker compose vs docker swarm",
    "how to use git rebase",
    "top 10 science fiction movies",
    "climate change mitigation strategies",
    "history of the roman empire",
    "what is quantum computing",
    "benefits of drinking green tea",
    "how to start a vegetable garden",
    "differences between fast and slow twitch muscle fibers",
    "understanding the theory of relativity",
    "how does a combustion engine work",
    "best hiking trails in the pacific northwest",
    "renewable energy trends 2024",
    "how to learn rust programming language",
    "what is a vector database"
] * 10 # Repeat to get 200 queries

async def fetch_search(session, node_url, query):
    """Attempt a search on a specific node."""
    params = {
        "q": query,
        "format": "json"
    }
    start_time = time.time()
    try:
        async with session.get(node_url, params=params, timeout=10) as response:
            latency = time.time() - start_time
            if response.status == 200:
                data = await response.json()
                results = data.get("results", [])
                if not results:
                    return {"success": False, "error": "Empty results", "latency": latency, "node": node_url}
                return {"success": True, "latency": latency, "node": node_url, "num_results": len(results)}
            elif response.status == 429:
                return {"success": False, "error": "Rate limited (429)", "latency": latency, "node": node_url}
            else:
                return {"success": False, "error": f"HTTP {response.status}", "latency": latency, "node": node_url}
    except Exception as e:
        latency = time.time() - start_time
        return {"success": False, "error": str(e), "latency": latency, "node": node_url}

async def execute_query(session, query, query_id):
    """Execute a query with retry logic across nodes and jitter."""
    # Add random jitter between 1 and 3 seconds before starting
    await asyncio.sleep(random.uniform(1, 3))

    # Randomly select initial node
    nodes = NODES.copy()
    random.shuffle(nodes)

    first_node = nodes[0]
    second_node = nodes[1]

    # Try first node
    result = await fetch_search(session, first_node, query)

    if result["success"]:
        print(f"Query {query_id} succeeded on {first_node}. Latency: {result['latency']:.2f}s")
        return result

    print(f"Query {query_id} failed on {first_node} ({result['error']}). Retrying on {second_node}...")

    # Try second node on failure
    retry_result = await fetch_search(session, second_node, query)
    if retry_result["success"]:
         print(f"Query {query_id} succeeded on retry ({second_node}). Latency: {retry_result['latency']:.2f}s")
    else:
         print(f"Query {query_id} completely failed. Node 1: {result['error']}, Node 2: {retry_result['error']}")

    # We return the outcome. Note that if retry succeeded, we consider it a success overall but log the retry.
    return {
        "success": retry_result["success"],
        "node": second_node if retry_result["success"] else None,
        "latency": result["latency"] + retry_result["latency"], # Total time spent
        "error": f"Node 1: {result['error']}, Node 2: {retry_result.get('error', 'N/A')}",
        "first_node_failed": True
    }


async def main():
    print(f"Starting POC Benchmark with {len(QUERIES)} queries...")

    # We want ~200 searches per hour. That's about 1 query every 18 seconds.
    # To run this benchmark in a reasonable time, we'll condense it a bit,
    # but still keep concurrency low to avoid bursting.
    # Let's process them in small batches (e.g. 2-3 at a time)

    stats = {
        "total": len(QUERIES),
        "success": 0,
        "failed": 0,
        "retried_and_succeeded": 0,
        "latencies": [],
        "errors": defaultdict(int),
        "node_success": defaultdict(int)
    }

    start_time = time.time()

    async with aiohttp.ClientSession() as session:
        # We process queries iteratively or in very small chunks to keep concurrency low
        concurrency_limit = 2

        for i in range(0, len(QUERIES), concurrency_limit):
            chunk = QUERIES[i:i+concurrency_limit]
            tasks = [execute_query(session, q, i+j) for j, q in enumerate(chunk)]

            results = await asyncio.gather(*tasks)

            for res in results:
                if res["success"]:
                    stats["success"] += 1
                    stats["latencies"].append(res["latency"])
                    stats["node_success"][res["node"]] += 1
                    if res.get("first_node_failed"):
                        stats["retried_and_succeeded"] += 1
                else:
                    stats["failed"] += 1
                    stats["errors"][res["error"]] += 1

            # Add a slight delay between chunks to further spread load
            await asyncio.sleep(random.uniform(0.5, 1.5))

    end_time = time.time()

    print("\n--- Benchmark Results ---")
    print(f"Total Queries: {stats['total']}")
    print(f"Total Time: {end_time - start_time:.2f} seconds")
    print(f"Success Rate: {(stats['success'] / stats['total']) * 100:.2f}%")
    print(f"Total Failed: {stats['failed']}")
    print(f"Retried & Succeeded: {stats['retried_and_succeeded']}")

    if stats["latencies"]:
        latencies = sorted(stats["latencies"])
        median = latencies[len(latencies)//2]
        p95 = latencies[int(len(latencies)*0.95)]
        print(f"Median Latency: {median:.2f}s")
        print(f"P95 Latency: {p95:.2f}s")

    print("\nNode Success Distribution:")
    for node, count in stats["node_success"].items():
        print(f"  {node}: {count}")

    if stats["errors"]:
        print("\nErrors Encountered:")
        for err, count in stats["errors"].items():
            print(f"  {err}: {count}")

    # Write summary to file
    with open("summary.json", "w") as f:
        json.dump(stats, f, indent=2)

if __name__ == "__main__":
    asyncio.run(main())
