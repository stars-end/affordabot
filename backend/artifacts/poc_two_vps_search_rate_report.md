# Two-VPS Search Rate POC Results

Generated: 2026-04-10 20:31:11 UTC
Simulation speed: 1 real second = 30.0 simulated seconds

## Scope
- Local mock test only (no external DDG/Bing traffic).
- Mock server enforces per-node, per-engine sliding-window throttles.
- Useful for controller behavior; not a guarantee for real-world anti-bot systems.

## Results

| Scenario | Requests | 200 OK | 429 Throttled | Throttle % |
|---|---:|---:|---:|---:|
| workload_200_per_hour_total | 69 | 69 | 0 | 0.0% |
| conservative_ceiling_24_per_min_total | 229 | 229 | 0 | 0.0% |
| stress_40_per_min_total | 261 | 258 | 3 | 1.1% |

## Node-level breakdown

### workload_200_per_hour_total
| Node | 200 OK | 429 |
|---|---:|---:|
| node-a | 35 | 0 |
| node-b | 34 | 0 |

### conservative_ceiling_24_per_min_total
| Node | 200 OK | 429 |
|---|---:|---:|
| node-a | 115 | 0 |
| node-b | 114 | 0 |

### stress_40_per_min_total
| Node | 200 OK | 429 |
|---|---:|---:|
| node-a | 130 | 1 |
| node-b | 128 | 2 |

## Takeaway
- Low steady rates with jitter should remain stable under per-IP soft limits.
- Higher sustained rates can trigger throttling even with two nodes.
- In production, use adaptive backoff and per-engine health scoring.
