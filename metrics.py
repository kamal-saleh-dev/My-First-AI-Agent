# metrics.py — Agent performance metrics + dashboard
# Tracks generation stats, latency, success rates

import time, json, os
from collections import defaultdict
from datetime import datetime

METRICS_FILE = "agent_metrics.json"

# ─── Metrics store ────────────────────────────────────────────
class AgentMetrics:
    def __init__(self):
        import threading
        self._lock = threading.Lock()  # thread-safe writes for background threads
        self._data = {
            "session_start":     datetime.now().isoformat(),
            "generations":       0,
            "generation_success":0,
            "generation_failed": 0,
            "compile_runs":      0,
            "compile_success":   0,
            "compile_failed":    0,
            "fix_retries_total": 0,
            "llm_calls":         0,
            "llm_errors":        0,
            "planning_cache_hits":0,
            "latency_planning":  [],   # seconds per planning call
            "latency_generation":[],   # seconds per generation
            "latency_llm":       [],   # seconds per LLM call
            "domains_used":      defaultdict(int),
            "intents_routed":    defaultdict(int),
        }
        self._load()

    # ── Persistence ──────────────────────────────────────────
    def _load(self):
        try:
            if os.path.exists(METRICS_FILE):
                with open(METRICS_FILE, encoding="utf-8") as f:
                    saved = json.load(f)
                # Merge lifetime stats
                for key in ("generations","generation_success","generation_failed",
                            "compile_runs","compile_success","compile_failed",
                            "fix_retries_total","llm_calls","llm_errors","planning_cache_hits"):
                    self._data[key] += saved.get(key, 0)
        except Exception:
            pass

    def save(self):
        try:
            with self._lock:
                snapshot = self.snapshot()
            # Ensure all values are JSON-serializable plain dicts
            snapshot["top_domains"]     = dict(snapshot.get("top_domains", {}))
            snapshot["intent_breakdown"]= dict(snapshot.get("intent_breakdown", {}))
            tmp = METRICS_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(snapshot, f, indent=2, ensure_ascii=False)
            os.replace(tmp, METRICS_FILE)
        except Exception:
            pass

    # ── Recording methods ─────────────────────────────────────
    def record_generation(self, success: bool, domain: str, elapsed: float):
        self._data["generations"]          += 1
        self._data["generation_success" if success else "generation_failed"] += 1
        self._data["latency_generation"].append(round(elapsed, 2))
        self._data["domains_used"][domain] += 1
        if len(self._data["latency_generation"]) > 100:
            self._data["latency_generation"] = self._data["latency_generation"][-100:]

    def record_compile(self, success: bool, fix_retries: int = 0):
        self._data["compile_runs"]    += 1
        self._data["compile_success" if success else "compile_failed"] += 1
        self._data["fix_retries_total"] += fix_retries

    def record_llm_call(self, elapsed: float, error: bool = False):
        self._data["llm_calls"]       += 1
        self._data["llm_errors" if error else "llm_calls"]
        self._data["latency_llm"].append(round(elapsed, 2))
        if len(self._data["latency_llm"]) > 200:
            self._data["latency_llm"] = self._data["latency_llm"][-200:]

    def record_planning(self, elapsed: float, cache_hit: bool = False):
        if cache_hit:
            self._data["planning_cache_hits"] += 1
        self._data["latency_planning"].append(round(elapsed, 2))
        if len(self._data["latency_planning"]) > 100:
            self._data["latency_planning"] = self._data["latency_planning"][-100:]

    def record_intent(self, intent: str):
        self._data["intents_routed"][intent] += 1

    # ── Context manager for timing ────────────────────────────
    class Timer:
        def __init__(self, callback):
            self._cb = callback
        def __enter__(self):
            self._start = time.time()
            return self
        def __exit__(self, *_):
            self._cb(round(time.time() - self._start, 3))

    def time_generation(self):
        return self.Timer(lambda e: self._data["latency_generation"].append(e))

    def time_planning(self):
        return self.Timer(lambda e: self._data["latency_planning"].append(e))

    def time_llm(self):
        return self.Timer(lambda e: self._data["latency_llm"].append(e))

    # ── Computed stats ────────────────────────────────────────
    def _avg(self, lst):
        return round(sum(lst) / len(lst), 2) if lst else 0.0

    def _rate(self, success, total):
        return f"{round(success/total*100)}%" if total else "N/A"

    def snapshot(self) -> dict:
        d = self._data
        return {
            "session_start":        d["session_start"],
            "generations":          d["generations"],
            "generation_success":   d["generation_success"],
            "generation_failed":    d["generation_failed"],
            "generation_success_rate": self._rate(d["generation_success"], d["generations"]),
            "compile_runs":         d["compile_runs"],
            "compile_success_rate": self._rate(d["compile_success"], d["compile_runs"]),
            "fix_retries_total":    d["fix_retries_total"],
            "avg_fix_retries":      round(d["fix_retries_total"] / max(d["compile_runs"],1), 2),
            "llm_calls":            d["llm_calls"],
            "llm_error_rate":       self._rate(d["llm_errors"], d["llm_calls"]),
            "planning_cache_hits":  d["planning_cache_hits"],
            "cache_hit_rate":       self._rate(d["planning_cache_hits"], d["generations"]),
            "avg_latency_planning": self._avg(d["latency_planning"]),
            "avg_latency_generation": self._avg(d["latency_generation"]),
            "avg_latency_llm":      self._avg(d["latency_llm"]),
            "p95_latency_llm":      self._p95(d["latency_llm"]),
            "top_domains":          dict(sorted(d["domains_used"].items(), key=lambda x:-x[1])[:5]),
            "intent_breakdown":     dict(d["intents_routed"]),
        }

    def _p95(self, lst):
        if not lst: return 0.0
        s = sorted(lst)
        idx = int(len(s) * 0.95)
        return s[min(idx, len(s)-1)]

    # ── Dashboard print ───────────────────────────────────────
    def print_dashboard(self):
        s = self.snapshot()
        W = 50
        print(f"\n{'═'*W}")
        print(f"  📊 AGENT METRICS DASHBOARD")
        print(f"  Session: {s['session_start'][:19]}")
        print(f"{'═'*W}")

        print(f"\n  {'GENERATION':}")
        print(f"    Total:        {s['generations']}")
        print(f"    Success rate: {s['generation_success_rate']}")
        print(f"    Avg latency:  {s['avg_latency_generation']}s")

        print(f"\n  COMPILE (Unity)")
        print(f"    Runs:         {s['compile_runs']}")
        print(f"    Success rate: {s['compile_success_rate']}")
        print(f"    Fix retries:  {s['fix_retries_total']} total / {s['avg_fix_retries']} avg")

        print(f"\n  LLM CALLS")
        print(f"    Total:        {s['llm_calls']}")
        print(f"    Error rate:   {s['llm_error_rate']}")
        print(f"    Avg latency:  {s['avg_latency_llm']}s")
        print(f"    P95 latency:  {s['p95_latency_llm']}s")

        print(f"\n  PLANNING")
        print(f"    Cache hits:   {s['planning_cache_hits']} ({s['cache_hit_rate']})")
        print(f"    Avg latency:  {s['avg_latency_planning']}s")

        if s['top_domains']:
            print(f"\n  TOP DOMAINS")
            for d, n in s['top_domains'].items():
                bar = '█' * min(n, 20)
                print(f"    {d:12} {bar} {n}")

        if s['intent_breakdown']:
            print(f"\n  INTENTS ROUTED")
            for intent, n in sorted(s['intent_breakdown'].items(), key=lambda x:-x[1]):
                print(f"    {intent:12} {n}")

        print(f"\n{'═'*W}\n")


# ── Global instance ───────────────────────────────────────────
metrics = AgentMetrics()

# ── Standalone dashboard ──────────────────────────────────────
if __name__ == "__main__":
    metrics.print_dashboard()
