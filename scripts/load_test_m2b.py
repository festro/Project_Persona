#!/usr/bin/env python3
"""M2b sustained-load test for the unified llama-server.

Drives concurrent /v1/chat/completions requests against the qwen-test deployment
(Qwen3-30B-A3B-Instruct-2507 Q5_K_M, 4 parallel slots, Vulkan/RADV on Strix Halo)
to verify M2b acceptance from KNOWLEDGE.md DECISION 2026-05-09:

  - No thermal throttling (detected as throughput degradation across per-minute buckets).
  - No driver hangs (per-request timeout + /health poll detection).
  - No KV cache corruption (request error rate, completion length sanity).
  - Sustained throughput stability over a 30+ minute run.

Run from the API venv so httpx is available:

  cd ~/Git/Project_Persona
  source services/api/.venv/bin/activate   # or whichever venv has httpx
  python3 scripts/load_test_m2b.py --duration 1800 --concurrency 4 --out logs/m2b_$(date +%F_%H%M).json

Recommended side-by-side monitoring (separate terminals):

  watch -n 5 sensors                       # CPU / iGPU temps (lm-sensors)
  watch -n 5 'cat /sys/class/drm/card*/device/hwmon/hwmon*/temp*_input 2>/dev/null'
  amdgpu_top                               # if installed
  tail -F logs/persona.log                 # llama-server runtime log
"""

import argparse
import asyncio
import json
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx


DEFAULT_ENDPOINT = "http://127.0.0.1:8080/v1/chat/completions"
DEFAULT_HEALTH = "http://127.0.0.1:8080/health"
DEFAULT_DURATION_S = 1800
DEFAULT_CONCURRENCY = 4
DEFAULT_MAX_TOKENS = 128
DEFAULT_TIMEOUT_S = 120.0
DEFAULT_HEALTH_INTERVAL_S = 30

PROMPTS = [
    "Briefly: what is photosynthesis?",
    "Explain the difference between TCP and UDP in three sentences.",
    "What's the capital of Japan?",
    "Summarize the second law of thermodynamics for a curious teenager.",
    "Write a four-line haiku about Vulkan API debugging.",
    "List five common signs of CPU thermal throttling.",
    "What does mTLS mean and when do you use it?",
    "Define quantization in the context of LLM inference.",
    "Name three reasons a Mixture-of-Experts model might be faster than a dense model of the same parameter count.",
    "Outline the steps to safely shut down a Linux server holding open database connections.",
]


@dataclass
class Sample:
    started_at: float
    finished_at: float
    ok: bool
    error: Optional[str] = None
    completion_tokens: int = 0
    prompt_tokens: int = 0

    @property
    def latency_s(self) -> float:
        return self.finished_at - self.started_at

    @property
    def gen_tps(self) -> float:
        if not self.ok or self.latency_s <= 0 or self.completion_tokens <= 0:
            return 0.0
        return self.completion_tokens / self.latency_s


@dataclass
class Bucket:
    label: str
    samples: list = field(default_factory=list)

    def summary(self) -> dict:
        ok = [s for s in self.samples if s.ok]
        if not ok:
            return {"label": self.label, "n": len(self.samples), "ok": 0}
        latencies = [s.latency_s for s in ok]
        tps = [s.gen_tps for s in ok if s.gen_tps > 0]
        out = {
            "label": self.label,
            "n": len(self.samples),
            "ok": len(ok),
            "errors": len(self.samples) - len(ok),
            "lat_p50_s": round(statistics.median(latencies), 3),
            "lat_max_s": round(max(latencies), 3),
        }
        if len(latencies) >= 20:
            out["lat_p95_s"] = round(statistics.quantiles(latencies, n=20)[-1], 3)
        if tps:
            out["gen_tps_mean"] = round(statistics.mean(tps), 2)
            out["gen_tps_min"] = round(min(tps), 2)
            out["gen_tps_max"] = round(max(tps), 2)
        return out


async def one_request(client: httpx.AsyncClient, endpoint: str, prompt: str, max_tokens: int, timeout_s: float) -> Sample:
    payload = {
        "model": "qwen3-unified",
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.7,
        "stream": False,
    }
    started = time.monotonic()
    try:
        r = await client.post(endpoint, json=payload, timeout=timeout_s)
        finished = time.monotonic()
        if r.status_code != 200:
            return Sample(started, finished, False, f"http_{r.status_code}")
        body = r.json()
        usage = body.get("usage") or {}
        ct = int(usage.get("completion_tokens", 0) or 0)
        pt = int(usage.get("prompt_tokens", 0) or 0)
        return Sample(started, finished, True, None, ct, pt)
    except (httpx.TimeoutException, asyncio.TimeoutError):
        return Sample(started, time.monotonic(), False, "timeout")
    except Exception as e:
        return Sample(started, time.monotonic(), False, f"exc:{type(e).__name__}:{e}")


async def worker(name: int, client: httpx.AsyncClient, endpoint: str, max_tokens: int, timeout_s: float, stop_at: float, sink: list):
    i = 0
    while time.monotonic() < stop_at:
        prompt = PROMPTS[(name + i) % len(PROMPTS)]
        s = await one_request(client, endpoint, prompt, max_tokens, timeout_s)
        sink.append(s)
        i += 1


async def health_poller(client: httpx.AsyncClient, health_url: str, interval_s: int, stop_at: float, sink: list):
    while time.monotonic() < stop_at:
        t0 = time.monotonic()
        try:
            r = await client.get(health_url, timeout=10.0)
            sink.append((t0, r.status_code == 200, r.text[:120] if r.status_code != 200 else "ok"))
        except Exception as e:
            sink.append((t0, False, f"exc:{type(e).__name__}:{e}"))
        await asyncio.sleep(interval_s)


def bucketize_by_minute(samples: list) -> list:
    if not samples:
        return []
    t0 = samples[0].started_at
    buckets: dict = {}
    for s in samples:
        minute = int((s.started_at - t0) // 60)
        b = buckets.setdefault(minute, Bucket(f"min{minute:02d}"))
        b.samples.append(s)
    return [buckets[k] for k in sorted(buckets)]


def progress_line(elapsed: float, total: float, samples: list) -> str:
    ok = sum(1 for s in samples if s.ok)
    errs = len(samples) - ok
    rate = len(samples) / elapsed if elapsed > 0 else 0
    return f"[{int(elapsed)}/{int(total)}s] req={len(samples)} ok={ok} err={errs} req/s={rate:.2f}"


async def progress_reporter(start: float, stop_at: float, samples: list, interval_s: int = 30):
    total = stop_at - start
    while time.monotonic() < stop_at:
        await asyncio.sleep(interval_s)
        elapsed = time.monotonic() - start
        print(progress_line(elapsed, total, samples), flush=True)


async def main():
    parser = argparse.ArgumentParser(
        description="M2b sustained-load test for the unified llama-server.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--endpoint", default=DEFAULT_ENDPOINT)
    parser.add_argument("--health", default=DEFAULT_HEALTH)
    parser.add_argument("--duration", type=int, default=DEFAULT_DURATION_S,
                        help=f"Test duration in seconds (default {DEFAULT_DURATION_S} = 30 min)")
    parser.add_argument("--concurrency", type=int, default=DEFAULT_CONCURRENCY,
                        help=f"Concurrent workers (default {DEFAULT_CONCURRENCY}, match parallel slots)")
    parser.add_argument("--max-tokens", type=int, default=DEFAULT_MAX_TOKENS)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_S)
    parser.add_argument("--out", default=None, help="Optional JSON report output path")
    parser.add_argument("--no-health", action="store_true", help="Skip /health polling")
    parser.add_argument("--progress-interval", type=int, default=30,
                        help="Progress line interval in seconds (default 30)")
    args = parser.parse_args()

    start = time.monotonic()
    stop_at = start + args.duration
    samples: list = []
    health: list = []

    print(f"M2b load test")
    print(f"  endpoint    {args.endpoint}")
    print(f"  duration    {args.duration}s")
    print(f"  concurrency {args.concurrency}")
    print(f"  max_tokens  {args.max_tokens}")
    print(f"  timeout     {args.timeout}s")
    print(f"  start       {time.strftime('%Y-%m-%dT%H:%M:%S')}")
    print(f"  out         {args.out or '<stdout only>'}")
    print("", flush=True)

    limits = httpx.Limits(
        max_connections=args.concurrency + 4,
        max_keepalive_connections=args.concurrency + 4,
    )
    async with httpx.AsyncClient(limits=limits) as client:
        tasks = [
            asyncio.create_task(
                worker(i, client, args.endpoint, args.max_tokens, args.timeout, stop_at, samples)
            )
            for i in range(args.concurrency)
        ]
        if not args.no_health:
            tasks.append(asyncio.create_task(
                health_poller(client, args.health, DEFAULT_HEALTH_INTERVAL_S, stop_at, health)
            ))
        tasks.append(asyncio.create_task(
            progress_reporter(start, stop_at, samples, args.progress_interval)
        ))
        await asyncio.gather(*tasks, return_exceptions=True)

    total = len(samples)
    ok = sum(1 for s in samples if s.ok)
    err_counts: dict = {}
    for s in samples:
        if not s.ok:
            key = s.error or "?"
            err_counts[key] = err_counts.get(key, 0) + 1

    overall = Bucket("overall")
    overall.samples = samples
    per_minute = bucketize_by_minute(samples)
    health_ok = sum(1 for _, b, _ in health if b)
    health_fail = len(health) - health_ok

    report = {
        "endpoint": args.endpoint,
        "duration_s": args.duration,
        "concurrency": args.concurrency,
        "max_tokens": args.max_tokens,
        "total_requests": total,
        "ok_requests": ok,
        "error_requests": total - ok,
        "errors": err_counts,
        "overall": overall.summary(),
        "per_minute": [b.summary() for b in per_minute],
        "health_polls": len(health),
        "health_ok": health_ok,
        "health_fail": health_fail,
        "wall_start": time.strftime("%Y-%m-%dT%H:%M:%S"),
    }

    print("")
    print("=== M2b report ===")
    print(json.dumps(report, indent=2))

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(report, indent=2))
        print(f"\nReport written to {out_path}")

    bad = (total - ok) > 0 or health_fail > 0
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    asyncio.run(main())
