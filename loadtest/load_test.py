"""HTTP load test for POST /recommend.

Replays the 88 labelled evaluation queries against a running server at several
concurrency levels and reports throughput, latency percentiles and error rate.

    gunicorn --bind=127.0.0.1:5000 --workers=1 --threads=4 app.app:app   # same settings as the Docker image
    python loadtest/load_test.py --url http://127.0.0.1:5000 --seconds 20

Results are written to loadtest/results.json.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import itertools
import json
from pathlib import Path
import threading
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]


def load_queries() -> list[str]:
    items = []
    for name in ("queries.json", "heldout.json"):
        items += json.loads((ROOT / "evaluation" / name).read_text())
    return [item["q"] for item in items]


def post(url: str, query: str) -> tuple[float, bool]:
    body = json.dumps({"query": query}).encode()
    request = urllib.request.Request(f"{url}/recommend", data=body, headers={"Content-Type": "application/json"})
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            ok = response.status == 200 and "recommendations" in json.loads(response.read())
    except Exception:
        ok = False
    return time.perf_counter() - start, ok


def pct(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1)))]


def run_level(url: str, queries: list[str], concurrency: int, seconds: float) -> dict:
    latencies, errors, lock = [], 0, threading.Lock()
    cycle, cycle_lock = itertools.cycle(queries), threading.Lock()
    deadline = time.perf_counter() + seconds

    def worker() -> None:
        nonlocal errors
        while time.perf_counter() < deadline:
            with cycle_lock:
                query = next(cycle)
            elapsed, ok = post(url, query)
            with lock:
                latencies.append(elapsed)
                errors += not ok

    start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=concurrency) as pool:
        for _ in range(concurrency):
            pool.submit(worker)
    duration = time.perf_counter() - start
    throughput = len(latencies) / duration
    return {
        "concurrency": concurrency,
        "requests": len(latencies),
        "errors": errors,
        "error_rate": round(errors / len(latencies), 4) if latencies else 1.0,
        "throughput_rps": round(throughput, 1),
        "requests_per_day_at_this_rate": int(throughput * 86400),
        "p50_ms": round(pct(latencies, 50) * 1000, 1),
        "p95_ms": round(pct(latencies, 95) * 1000, 1),
        "p99_ms": round(pct(latencies, 99) * 1000, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", default="http://127.0.0.1:5000")
    parser.add_argument("--seconds", type=float, default=20)
    parser.add_argument("--levels", default="1,4,8,16")
    args = parser.parse_args()

    queries = load_queries()
    for query in queries[:5]:  # warm the model and caches
        post(args.url, query)
    results = []
    for level in (int(x) for x in args.levels.split(",")):
        result = run_level(args.url, queries, level, args.seconds)
        results.append(result)
        print(json.dumps(result))
    out = Path(__file__).resolve().parent / "results.json"
    out.write_text(json.dumps({"url": args.url, "seconds_per_level": args.seconds, "levels": results}, indent=2))
    print(f"Saved {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
