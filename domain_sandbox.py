# domain_sandbox.py — Dependency isolation: each domain runs in its own error boundary
# If Unity templates crash → React still works. If Unreal import fails → Python still works.
# Wraps every domain operation in an isolated try/except with structured error reporting.

import sys
import traceback
import threading
from typing import Any, Callable, Optional
from errors import GenerationError, TemplateError


class DomainIsolationError(GenerationError):
    """Raised when a domain operation fails and isolation kicks in."""


class DomainSandbox:
    """
    Runs domain operations in isolation — exceptions are caught, logged,
    and optionally retried or fallen back to a safe default.

    Usage:
        sandbox = DomainSandbox("unity")
        result  = sandbox.run(get_template, script_name, role)
        # If get_template raises → result is None, error is recorded
    """

    def __init__(self, domain: str):
        self.domain   = domain
        self._lock    = threading.Lock()
        self._errors: list[dict] = []
        self._healthy = True

    # ── Core execution ────────────────────────────────────────────────────────

    def run(self, fn: Callable, *args,
            fallback=None, reraise: bool = False, **kwargs) -> Any:
        """
        Execute fn(*args, **kwargs) in isolation.
        On exception:
          - records the error
          - returns fallback (default: None)
          - if reraise=True, re-raises as DomainIsolationError
        """
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            self._record_error(fn, exc)
            if reraise:
                raise DomainIsolationError(
                    f"Domain '{self.domain}' failed in {fn.__name__}: {exc}",
                    domain=self.domain
                ) from exc
            return fallback

    def run_import(self, module_name: str) -> Optional[Any]:
        """
        Safely import a module. Returns module or None on failure.
        A failed import marks the domain as degraded but doesn't kill the agent.
        """
        try:
            import importlib
            return importlib.import_module(module_name)
        except ImportError as exc:
            self._record_error(None, exc, label=f"import:{module_name}")
            self._healthy = False
            return None

    # ── Health ────────────────────────────────────────────────────────────────

    @property
    def healthy(self) -> bool:
        return self._healthy

    def reset(self):
        """Clear error history and mark domain healthy again."""
        with self._lock:
            self._errors.clear()
            self._healthy = True

    # ── Error tracking ────────────────────────────────────────────────────────

    def _record_error(self, fn: Optional[Callable], exc: Exception,
                      label: str = ""):
        entry = {
            "domain":   self.domain,
            "fn":       label or (fn.__qualname__ if fn else "unknown"),
            "error":    type(exc).__name__,
            "message":  str(exc),
            "traceback": traceback.format_exc(limit=5),
        }
        with self._lock:
            self._errors.append(entry)
            # Mark unhealthy after repeated failures
            if len(self._errors) >= 3:
                self._healthy = False

        # Always log — never silently swallow
        from logger import log
        log.warn(
            f"Domain '{self.domain}' error in {entry['fn']}: {entry['error']}: {entry['message']}"
        )

    def last_error(self) -> Optional[dict]:
        with self._lock:
            return self._errors[-1] if self._errors else None

    def error_count(self) -> int:
        with self._lock:
            return len(self._errors)

    def print_health(self):
        status = "✅ healthy" if self._healthy else f"⚠️ degraded ({self.error_count()} errors)"
        print(f"  {self.domain:<12} {status}")
        if self._errors:
            last = self._errors[-1]
            print(f"             last: {last['fn']} → {last['error']}: {last['message'][:60]}")


# ── Global domain registry ────────────────────────────────────────────────────

_SANDBOXES: dict[str, DomainSandbox] = {}
_SB_LOCK = threading.Lock()


def get_sandbox(domain: str) -> DomainSandbox:
    """Return the sandbox for a domain, creating it if needed."""
    with _SB_LOCK:
        if domain not in _SANDBOXES:
            _SANDBOXES[domain] = DomainSandbox(domain)
        return _SANDBOXES[domain]


def system_health() -> dict[str, bool]:
    """Return {domain: is_healthy} for all active sandboxes."""
    with _SB_LOCK:
        return {d: sb.healthy for d, sb in _SANDBOXES.items()}


def print_health_report():
    print(f"\n{'─'*40}")
    print("  🏥 Domain Health Report")
    print(f"{'─'*40}")
    with _SB_LOCK:
        if not _SANDBOXES:
            print("  No domains active yet.")
        else:
            for sb in _SANDBOXES.values():
                sb.print_health()
    print(f"{'─'*40}\n")


# ── Convenience decorator ─────────────────────────────────────────────────────

def isolated(domain: str, fallback=None, reraise: bool = False):
    """
    Decorator: run function inside domain sandbox.
    @isolated("unity")
    def get_unity_template(name, role): ...
    """
    def decorator(fn: Callable):
        import functools
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            sb = get_sandbox(domain)
            return sb.run(fn, *args, fallback=fallback,
                          reraise=reraise, **kwargs)
        return wrapper
    return decorator
