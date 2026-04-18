# shutdown_manager.py — Graceful shutdown + background task executor
# Extracted from agent.py — handles signals, atexit, background threads

import signal
import atexit
import threading as _threading
from typing import Optional

from logger           import log
from process_registry import terminate_all as _terminate_all

# ── Background executor ───────────────────────────────────────────────────────

_current_task: Optional[_threading.Thread] = None
_task_lock     = _threading.Lock()
_shutdown_called = False                  # guard: prevents double-shutdown
stop_event     = _threading.Event()      # exported — generation loop polls this


def run_in_background(fn, *args, **kwargs):
    """Run fn(*args, **kwargs) in a daemon thread. Errors are logged, never swallowed."""
    global _current_task

    def _wrapper():
        try:
            fn(*args, **kwargs)
        except Exception as e:
            log.error(f"Background task error in {fn.__name__}: {e}")

    with _task_lock:
        stop_event.clear()   # reset for new task
        t = _threading.Thread(target=_wrapper, daemon=True, name=f"agent-{fn.__name__}")
        _current_task = t
        t.start()


def is_task_running() -> bool:
    return _current_task is not None and _current_task.is_alive()


# ── Graceful shutdown ─────────────────────────────────────────────────────────

def handle_shutdown(signum=None, frame=None):
    """Save state, flush logs, terminate child processes. Runs at most once."""
    global _shutdown_called
    if _shutdown_called:
        return          # ← prevents double-shutdown from atexit + SIGINT
    _shutdown_called = True

    try:
        log.info("Shutting down agent gracefully...")

        # ── Signal the generation loop to stop after current script ──────────
        stop_event.set()

        # ── Wait for background thread (max 5s) ──────────────────────────────
        with _task_lock:
            task = _current_task
        if task and task.is_alive():
            log.info("Waiting for background task to finish (max 5s)...")
            task.join(timeout=5.0)
            if task.is_alive():
                log.warn("Background task did not finish in time — checkpoint saved anyway.")

        # Save metrics
        try:
            from metrics import metrics
            metrics.save()
        except Exception:
            pass

        # Save session
        try:
            from session_manager import save_session
            save_session()
        except Exception:
            pass

        # Flush logger buffer to disk
        try:
            log.flush()
        except Exception:
            pass

        # Kill all child processes
        _terminate_all()
        log.info("Shutdown complete.")
    except Exception:
        pass


def register_shutdown_hooks():
    """Register SIGINT / SIGTERM / atexit handlers. Call once at startup."""
    signal.signal(signal.SIGINT,  handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)
    atexit.register(handle_shutdown)
    try:
        from metrics import metrics
        atexit.register(metrics.save)
    except Exception:
        pass
