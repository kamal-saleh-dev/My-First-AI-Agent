# profiler.py — Performance profiling for generation, planning, and file parsing
# Usage:
#   from profiler import profiler
#   with profiler.track("generation", engine="unity"):
#       ...code...
#   profiler.report()

import time
import functools
import threading
from collections import defaultdict
from typing import Callable


class AgentProfiler:
    """
    Lightweight profiler — zero overhead when disabled.
    Thread-safe. Tracks min/max/avg/count per operation label.
    """

    def __init__(self, enabled: bool = True):
        self.enabled = enabled
        self._lock   = threading.Lock()
        self._data: dict[str, list[float]] = defaultdict(list)

    # ── Context manager ───────────────────────────────────────────────────────

    class _Track:
        def __init__(self, profiler, label: str):
            self._p     = profiler
            self._label = label
            self._start = 0.0

        def __enter__(self):
            if self._p.enabled:
                self._start = time.perf_counter()
            return self

        def __exit__(self, *_):
            if self._p.enabled and self._start:
                elapsed = time.perf_counter() - self._start
                with self._p._lock:
                    self._p._data[self._label].append(round(elapsed, 4))

    def track(self, label: str, **tags) -> "_Track":
        """
        Context manager to time a block.
        tags are appended to the label: track("generation", engine="unity")
        → label = "generation[engine=unity]"
        """
        if tags:
            tag_str = ",".join(f"{k}={v}" for k, v in tags.items())
            label = f"{label}[{tag_str}]"
        return self._Track(self, label)

    # ── Decorator ─────────────────────────────────────────────────────────────

    def measure(self, label: str = ""):
        """Decorator: @profiler.measure('my_function')"""
        def decorator(fn: Callable):
            lbl = label or fn.__qualname__
            @functools.wraps(fn)
            def wrapper(*args, **kwargs):
                with self.track(lbl):
                    return fn(*args, **kwargs)
            return wrapper
        return decorator

    # ── Manual record ─────────────────────────────────────────────────────────

    def record(self, label: str, elapsed: float):
        if self.enabled:
            with self._lock:
                self._data[label].append(round(elapsed, 4))

    # ── Stats ─────────────────────────────────────────────────────────────────

    def stats(self, label: str) -> dict:
        samples = self._data.get(label, [])
        if not samples:
            return {}
        s = sorted(samples)
        n = len(s)
        return {
            "count": n,
            "total": round(sum(s), 3),
            "avg":   round(sum(s) / n, 3),
            "min":   round(s[0], 3),
            "max":   round(s[-1], 3),
            "p50":   round(s[n // 2], 3),
            "p95":   round(s[min(int(n * 0.95), n - 1)], 3),
        }

    def all_stats(self) -> dict[str, dict]:
        with self._lock:
            labels = list(self._data.keys())
        return {lbl: self.stats(lbl) for lbl in labels}

    def slowest(self, n: int = 5) -> list[tuple[str, float]]:
        """Return top N slowest labels by average latency."""
        avgs = [(lbl, self.stats(lbl).get("avg", 0)) for lbl in self._data]
        return sorted(avgs, key=lambda x: -x[1])[:n]

    def reset(self):
        with self._lock:
            self._data.clear()

    # ── Console report ────────────────────────────────────────────────────────

    def report(self, top_n: int = 20):
        all_s = self.all_stats()
        if not all_s:
            print("📊 Profiler: no data recorded.")
            return

        print(f"\n{'═'*60}")
        print("  📊 PERFORMANCE PROFILER REPORT")
        print(f"{'═'*60}")
        print(f"  {'Label':<35} {'cnt':>4} {'avg':>7} {'p95':>7} {'max':>7}")
        print(f"  {'-'*35} {'-'*4} {'-'*7} {'-'*7} {'-'*7}")

        sorted_labels = sorted(all_s.items(), key=lambda x: -x[1].get("avg", 0))
        for label, s in sorted_labels[:top_n]:
            short = label[:34]
            print(f"  {short:<35} {s['count']:>4} "
                  f"{s['avg']:>6.2f}s {s['p95']:>6.2f}s {s['max']:>6.2f}s")

        print(f"{'═'*60}\n")

        slow = self.slowest(3)
        if slow:
            print("  🐢 Slowest operations:")
            for lbl, avg in slow:
                print(f"     {lbl}: avg {avg:.2f}s")
            print()


# ── Global singleton ──────────────────────────────────────────────────────────
profiler = AgentProfiler(enabled=True)
