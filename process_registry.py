# process_registry.py — Shared subprocess registry
# Import from here instead of agent.py to avoid circular imports

import atexit as _atexit
from threading import Lock as _Lock
import config as _cfg

_registry_lock = _Lock()
child_processes: list = []

def register(proc):
    """Add a subprocess to the registry."""
    with _registry_lock:
        # Clean up dead processes first
        child_processes[:] = [p for p in child_processes if p.poll() is None]
        child_processes.append(proc)
    return proc

def terminate_all(timeout: float = None):
    if timeout is None: timeout = _cfg.PROC_TERMINATE_TIMEOUT
    """Terminate all registered child processes gracefully."""
    import time
    with _registry_lock:
        procs = list(child_processes)

    for p in procs:
        try:
            if p.poll() is None:
                p.terminate()
        except Exception:
            pass

    # Give them time to exit
    deadline = time.time() + timeout
    for p in procs:
        try:
            remaining = max(0, deadline - time.time())
            p.wait(timeout=remaining)
        except Exception:
            pass

    # Force kill any that survived
    for p in procs:
        try:
            if p.poll() is None:
                p.kill()
        except Exception:
            pass

    with _registry_lock:
        child_processes.clear()


# ── Auto-cleanup on any exit (crash, sys.exit, normal) ───────────────────────
# Registered here so it fires even if agent.py's shutdown handler is skipped.
_atexit.register(terminate_all)
