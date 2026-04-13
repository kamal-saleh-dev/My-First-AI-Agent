# logger.py — Structured agent logger + thread-safe print
# Extracted from agent.py — single source of truth for all logging

import os
import time
import config as _cfg
import json as _json_mod
from datetime import datetime as _dt
from threading import Lock

# ── Shared print lock (imported by agent.py and any module that prints) ──
_print_lock = Lock()


class AgentLogger:
    LEVELS = {"DEBUG": 0, "INFO": 1, "SUCCESS": 1, "SAVE": 1, "RUN": 1, "WARN": 2, "ERROR": 3}
    ICONS  = {"DEBUG": "🔍", "INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌",
               "SUCCESS": "✅", "SAVE": "💾", "RUN": "🚀"}

    def __init__(self, min_level: str = _cfg.LOG_MIN_LEVEL,
                 log_file: str = _cfg.LOG_FILE):
        self.min_level = min_level
        self.log_file  = log_file
        self._buf: list = []
        self._lock = Lock()

    # ── Buffered file write — flush every FLUSH_EVERY entries ──────────────
    FLUSH_EVERY = _cfg.LOG_FLUSH_EVERY

    def _write(self, level: str, msg: str, **ctx):
        if self.LEVELS.get(level, 1) < self.LEVELS.get(self.min_level, 1):
            return

        icon  = self.ICONS.get(level, "•")
        ts    = _dt.now().strftime("%H:%M:%S")
        entry = {"ts": ts, "level": level, "msg": msg, **ctx}

        with self._lock:
            self._buf.append(entry)
            should_flush = len(self._buf) % self.FLUSH_EVERY == 0

        # Thread-safe console output (always immediate)
        try:
            with _print_lock:
                print(f"{icon} {msg}", flush=True)
        except Exception:
            pass

        # Buffered file write — only flush every FLUSH_EVERY entries
        if should_flush:
            self._flush_to_disk()

    def _flush_to_disk(self):
        """Write buffered entries to disk with rotation. Thread-safe."""
        with self._lock:
            entries_to_write = list(self._buf[-self.FLUSH_EVERY:])
        if not entries_to_write:
            return
        try:
            if os.path.exists(self.log_file) and os.path.getsize(self.log_file) > _cfg.LOG_MAX_FILE_MB * 1024 * 1024:
                rotated = self.log_file.replace(".jsonl", f"_{int(time.time())}.jsonl")
                os.replace(self.log_file, rotated)
                import glob as _glob
                old_logs = sorted(_glob.glob(self.log_file.replace(".jsonl", "_*.jsonl")))
                for old in old_logs[:-_cfg.LOG_KEEP_ROTATED]:
                    try:
                        os.remove(old)
                    except Exception:
                        pass
            with open(self.log_file, "a", encoding="utf-8") as f:
                for entry in entries_to_write:
                    f.write(_json_mod.dumps(entry, default=str, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def flush(self):
        """Force flush all buffered entries to disk (call on shutdown)."""
        with self._lock:
            entries = list(self._buf)
        if not entries:
            return
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                for entry in entries:
                    f.write(_json_mod.dumps(entry, default=str, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def debug(self, msg: str, **ctx):   self._write("DEBUG",   msg, **ctx)
    def info(self, msg: str, **ctx):    self._write("INFO",    msg, **ctx)
    def warn(self, msg: str, **ctx):    self._write("WARN",    msg, **ctx)
    def error(self, msg: str, **ctx):   self._write("ERROR",   msg, **ctx)
    def success(self, msg: str, **ctx): self._write("SUCCESS", msg, **ctx)
    def save(self, msg: str, **ctx):    self._write("SAVE",    msg, **ctx)
    def run(self, msg: str, **ctx):     self._write("RUN",     msg, **ctx)
    def last(self, n: int = 20) -> list:
        return self._buf[-n:]


# ── Global singleton ──────────────────────────────────────────────────────────
log = AgentLogger()

# Flush buffered logs on any exit
import atexit as _atexit
_atexit.register(log.flush)


def safe_print(*args, **kwargs):
    """Thread-safe print — flush=True by default, Unicode-safe, locked."""
    kwargs.setdefault("flush", True)
    try:
        with _print_lock:
            try:
                print(*args, **kwargs)
            except UnicodeEncodeError:
                text = " ".join(str(a) for a in args)
                cleaned = text.encode("utf-8", errors="replace").decode("utf-8")
                print(cleaned, **{k: v for k, v in kwargs.items() if k != "end"})
    except Exception:
        pass
