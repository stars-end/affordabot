#!/usr/bin/env python3
"""Quick POC: two-node (two VPS) search scheduling against throttle-aware mock engine.

This script does NOT hit real DDG/Bing endpoints. It runs a local mock server that applies
per-IP/per-engine soft throttling rules and then drives synthetic traffic with jitter,
round-robin routing, and bounded concurrency.
"""

from __future__ import annotations

import argparse
import json
import os
import random
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


@dataclass
class Scenario:
    name: str
    total_rpm: float
    duration_sim_minutes: int
    jitter_min_sim_s: float
    jitter_max_sim_s: float
    max_concurrency_per_node: int


class ThrottleState:
    def __init__(self, window_sim_s: float, limit_by_engine: dict[str, int]):
        self.window_sim_s = window_sim_s
        self.limit_by_engine = limit_by_engine
        self.events: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        self.lock = threading.Lock()

    def evaluate(self, node_id: str, engine: str, now_sim_s: float) -> tuple[int, str]:
        key = (node_id, engine)
        with self.lock:
            dq = self.events[key]
            while dq and now_sim_s - dq[0] > self.window_sim_s:
                dq.popleft()
            limit = self.limit_by_engine[engine]
            if len(dq) >= limit:
                return 429, "soft_throttle"
            dq.append(now_sim_s)
            return 200, "ok"


class SearchMockHandler(BaseHTTPRequestHandler):
    state: ThrottleState
    t0_real: float
    sim_seconds_per_real_second: float

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        if parsed.path != "/search":
            self.send_response(404)
            self.end_headers()
            return

        qs = urllib.parse.parse_qs(parsed.query)
        node_id = qs.get("node", ["node-a"])[0]
        engine = qs.get("engine", ["ddg"])[0]
        if engine not in self.state.limit_by_engine:
            engine = "ddg"

        now_sim_s = (time.time() - self.t0_real) * self.sim_seconds_per_real_second
        status, reason = self.state.evaluate(node_id=node_id, engine=engine, now_sim_s=now_sim_s)

        body = {
            "status": status,
            "reason": reason,
            "node": node_id,
            "engine": engine,
            "sim_time_s": round(now_sim_s, 3),
        }
        payload = json.dumps(body).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args) -> None:  # noqa: A003
        return


@dataclass
class ScenarioResult:
    name: str
    total_requests: int
    ok: int
    throttled: int
    by_node: dict[str, dict[str, int]]


def _request(base_url: str, node: str, engine: str) -> int:
    url = f"{base_url}/search?" + urllib.parse.urlencode({"node": node, "engine": engine, "q": "housing policy"})
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def run_scenario(base_url: str, sim_scale: float, scenario: Scenario) -> ScenarioResult:
    interval_sim_s = 60.0 / scenario.total_rpm
    interval_real_s = interval_sim_s / sim_scale

    t_end = time.time() + (scenario.duration_sim_minutes * 60.0) / sim_scale
    next_ts = time.time()
    node_cycle = ["node-a", "node-b"]
    node_idx = 0

    in_flight = {"node-a": 0, "node-b": 0}
    results_by_node: dict[str, dict[str, int]] = {
        "node-a": {"ok": 0, "throttled": 0},
        "node-b": {"ok": 0, "throttled": 0},
    }

    ok = 0
    throttled = 0
    total = 0

    lock = threading.Lock()

    def worker(node: str, engine: str) -> None:
        nonlocal ok, throttled, total
        status = _request(base_url=base_url, node=node, engine=engine)
        with lock:
            total += 1
            if status == 200:
                ok += 1
                results_by_node[node]["ok"] += 1
            else:
                throttled += 1
                results_by_node[node]["throttled"] += 1
            in_flight[node] -= 1

    threads: list[threading.Thread] = []
    while time.time() < t_end:
        now = time.time()
        if now < next_ts:
            time.sleep(min(0.005, next_ts - now))
            continue

        node = node_cycle[node_idx % len(node_cycle)]
        node_idx += 1

        if in_flight[node] < scenario.max_concurrency_per_node:
            in_flight[node] += 1
            engine = "ddg" if random.random() < 0.75 else "bing"
            th = threading.Thread(target=worker, args=(node, engine), daemon=True)
            threads.append(th)
            th.start()

        jitter_sim_s = random.uniform(scenario.jitter_min_sim_s, scenario.jitter_max_sim_s)
        jitter_real_s = jitter_sim_s / sim_scale
        next_ts = now + interval_real_s + jitter_real_s

    for th in threads:
        th.join()

    return ScenarioResult(
        name=scenario.name,
        total_requests=total,
        ok=ok,
        throttled=throttled,
        by_node=results_by_node,
    )


def render_markdown(results: list[ScenarioResult], out_path: str, sim_scale: float) -> None:
    lines = []
    lines.append("# Two-VPS Search Rate POC Results")
    lines.append("")
    lines.append(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())}")
    lines.append(f"Simulation speed: 1 real second = {sim_scale:.1f} simulated seconds")
    lines.append("")
    lines.append("## Scope")
    lines.append("- Local mock test only (no external DDG/Bing traffic).")
    lines.append("- Mock server enforces per-node, per-engine sliding-window throttles.")
    lines.append("- Useful for controller behavior; not a guarantee for real-world anti-bot systems.")
    lines.append("")
    lines.append("## Results")
    lines.append("")
    lines.append("| Scenario | Requests | 200 OK | 429 Throttled | Throttle % |")
    lines.append("|---|---:|---:|---:|---:|")
    for r in results:
        pct = (100.0 * r.throttled / r.total_requests) if r.total_requests else 0.0
        lines.append(f"| {r.name} | {r.total_requests} | {r.ok} | {r.throttled} | {pct:.1f}% |")

    lines.append("")
    lines.append("## Node-level breakdown")
    lines.append("")
    for r in results:
        lines.append(f"### {r.name}")
        lines.append("| Node | 200 OK | 429 |")
        lines.append("|---|---:|---:|")
        for node, stats in r.by_node.items():
            lines.append(f"| {node} | {stats['ok']} | {stats['throttled']} |")
        lines.append("")

    lines.append("## Takeaway")
    lines.append("- Low steady rates with jitter should remain stable under per-IP soft limits.")
    lines.append("- Higher sustained rates can trigger throttling even with two nodes.")
    lines.append("- In production, use adaptive backoff and per-engine health scoring.")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--sim-scale", type=float, default=30.0)
    parser.add_argument(
        "--out",
        default="backend/artifacts/poc_two_vps_search_rate_report.md",
    )
    args = parser.parse_args()

    state = ThrottleState(
        window_sim_s=60.0,
        limit_by_engine={
            "ddg": 12,
            "bing": 15,
        },
    )

    SearchMockHandler.state = state
    SearchMockHandler.t0_real = time.time()
    SearchMockHandler.sim_seconds_per_real_second = args.sim_scale

    server = ThreadingHTTPServer((args.host, args.port), SearchMockHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    base_url = f"http://{args.host}:{args.port}"

    scenarios = [
        Scenario(
            name="workload_200_per_hour_total",
            total_rpm=3.33,
            duration_sim_minutes=25,
            jitter_min_sim_s=0.0,
            jitter_max_sim_s=8.0,
            max_concurrency_per_node=1,
        ),
        Scenario(
            name="conservative_ceiling_24_per_min_total",
            total_rpm=24.0,
            duration_sim_minutes=15,
            jitter_min_sim_s=0.0,
            jitter_max_sim_s=3.0,
            max_concurrency_per_node=2,
        ),
        Scenario(
            name="stress_40_per_min_total",
            total_rpm=40.0,
            duration_sim_minutes=10,
            jitter_min_sim_s=0.0,
            jitter_max_sim_s=1.5,
            max_concurrency_per_node=2,
        ),
    ]

    results: list[ScenarioResult] = []
    try:
        for scenario in scenarios:
            results.append(run_scenario(base_url=base_url, sim_scale=args.sim_scale, scenario=scenario))
    finally:
        server.shutdown()
        server.server_close()

    render_markdown(results=results, out_path=args.out, sim_scale=args.sim_scale)

    print(json.dumps([r.__dict__ for r in results], indent=2))
    print(f"Report written: {args.out}")


if __name__ == "__main__":
    main()
