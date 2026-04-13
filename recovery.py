# recovery.py — Generation recovery architecture
# If a model crashes mid-generation, the agent saves a checkpoint and resumes
# from the last successful script — no full restart needed.

import os
import json
import time
import threading
from typing import Optional
from logger import log, safe_print
import config as _cfg


# ── Checkpoint data structure ─────────────────────────────────────────────────

class GenerationCheckpoint:
    """
    Snapshot of generation progress — saved after each script completes.
    On crash: reload and continue from last completed script.
    """

    def __init__(self, task: str, engine: str, project_name: str,
                 script_pairs: list, model_name: str):
        self.task         = task
        self.engine       = engine
        self.project_name = project_name
        self.script_pairs = script_pairs    # [(name, role), ...]
        self.model_name   = model_name
        self.created_at   = time.time()

        # Mutable progress state
        self.completed:   list[str]  = []   # script names finished OK
        self.failed:      list[str]  = []   # script names that failed
        self.current:     str        = ""   # currently generating
        self.attempts:    int        = 0    # total LLM attempts used
        self.status:      str        = "in_progress"  # in_progress | done | abandoned

    # ── Serialisation ─────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "task":         self.task,
            "engine":       self.engine,
            "project_name": self.project_name,
            "script_pairs": self.script_pairs,
            "model_name":   self.model_name,
            "created_at":   self.created_at,
            "completed":    self.completed,
            "failed":       self.failed,
            "current":      self.current,
            "attempts":     self.attempts,
            "status":       self.status,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GenerationCheckpoint":
        cp = cls(
            task         = d["task"],
            engine       = d["engine"],
            project_name = d["project_name"],
            script_pairs = d["script_pairs"],
            model_name   = d["model_name"],
        )
        cp.created_at = d.get("created_at", 0)
        cp.completed  = d.get("completed", [])
        cp.failed     = d.get("failed", [])
        cp.current    = d.get("current", "")
        cp.attempts   = d.get("attempts", 0)
        cp.status     = d.get("status", "in_progress")
        return cp

    # ── Progress helpers ──────────────────────────────────────────────────────

    @property
    def remaining_pairs(self) -> list:
        """Scripts not yet completed — resume from here."""
        done = set(self.completed)
        return [(n, r) for n, r in self.script_pairs if n not in done]

    @property
    def is_resumable(self) -> bool:
        return self.status == "in_progress" and bool(self.remaining_pairs)

    def mark_started(self, script_name: str):
        self.current = script_name

    def mark_done(self, script_name: str):
        if script_name not in self.completed:
            self.completed.append(script_name)
        self.current = ""

    def mark_failed(self, script_name: str):
        if script_name not in self.failed:
            self.failed.append(script_name)
        self.current = ""

    def mark_complete(self):
        self.status  = "done"
        self.current = ""

    def mark_abandoned(self):
        self.status = "abandoned"


# ── Checkpoint manager ────────────────────────────────────────────────────────

class CheckpointManager:
    """
    Persists checkpoints to disk. Thread-safe.
    One checkpoint file per project (named by project_name).
    """

    CHECKPOINT_DIR = os.path.join(_cfg.BASE_DIR, ".checkpoints")

    def __init__(self):
        os.makedirs(self.CHECKPOINT_DIR, exist_ok=True)
        self._lock = threading.Lock()

    def _path(self, project_name: str) -> str:
        safe = project_name.replace(" ", "_").replace("/", "_")
        return os.path.join(self.CHECKPOINT_DIR, f"{safe}.json")

    def save(self, cp: GenerationCheckpoint):
        """Atomically write checkpoint to disk."""
        path = self._path(cp.project_name)
        tmp  = path + ".tmp"
        try:
            with self._lock:
                with open(tmp, "w", encoding="utf-8") as f:
                    json.dump(cp.to_dict(), f, ensure_ascii=False, indent=2)
                os.replace(tmp, path)
        except Exception as e:
            log.warn(f"Checkpoint save failed for {cp.project_name}: {e}")

    def load(self, project_name: str) -> Optional[GenerationCheckpoint]:
        """Load checkpoint if it exists and is resumable."""
        path = self._path(project_name)
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            cp = GenerationCheckpoint.from_dict(data)
            if not cp.is_resumable:
                return None
            return cp
        except Exception as e:
            log.warn(f"Checkpoint load failed for {project_name}: {e}")
            return None

    def delete(self, project_name: str):
        path = self._path(project_name)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    def list_resumable(self) -> list[dict]:
        """Return all in-progress checkpoints (for /resume command)."""
        results = []
        try:
            for fname in os.listdir(self.CHECKPOINT_DIR):
                if not fname.endswith(".json"):
                    continue
                fpath = os.path.join(self.CHECKPOINT_DIR, fname)
                try:
                    with open(fpath) as f:
                        d = json.load(f)
                    if d.get("status") == "in_progress":
                        remaining = len(d.get("script_pairs", [])) - len(d.get("completed", []))
                        results.append({
                            "project":   d["project_name"],
                            "engine":    d["engine"],
                            "completed": len(d.get("completed", [])),
                            "remaining": remaining,
                            "created":   time.strftime(
                                "%Y-%m-%d %H:%M", time.localtime(d.get("created_at", 0))
                            ),
                        })
                except Exception:
                    continue
        except Exception:
            pass
        return results

    def print_resumable(self):
        items = self.list_resumable()
        if not items:
            safe_print("📋 No resumable generations found.")
            return
        safe_print(f"\n📋 Resumable generations ({len(items)}):")
        for item in items:
            safe_print(f"   • {item['project']} [{item['engine']}] "
                       f"{item['completed']} done, {item['remaining']} remaining "
                       f"(started {item['created']})")
        safe_print("  Use: /resume <project_name>\n")


# ── Recovery context manager ─────────────────────────────────────────────────

class RecoveryContext:
    """
    Wraps a generation run with checkpoint save/load logic.
    Usage:
        with RecoveryContext(task, engine, project_name, script_pairs, model) as ctx:
            for script_name, script_role in ctx.remaining:
                ctx.mark_started(script_name)
                code = generate(...)
                ctx.mark_done(script_name)
        # On exception: checkpoint is saved, user can /resume later
    """

    def __init__(self, task: str, engine: str, project_name: str,
                 script_pairs: list, model_name: str,
                 resume: bool = False):
        self._manager = _checkpoint_manager
        self._cp: Optional[GenerationCheckpoint] = None
        self._task         = task
        self._engine       = engine
        self._project_name = project_name
        self._script_pairs = script_pairs
        self._model_name   = model_name
        self._resume       = resume

    def __enter__(self) -> "RecoveryContext":
        if self._resume:
            existing = self._manager.load(self._project_name)
            if existing and existing.is_resumable:
                self._cp = existing
                safe_print(f"♻️  Resuming '{self._project_name}': "
                           f"{len(self._cp.completed)}/{len(self._cp.script_pairs)} done, "
                           f"{len(self._cp.remaining_pairs)} remaining.")
                return self

        # Fresh checkpoint
        self._cp = GenerationCheckpoint(
            self._task, self._engine, self._project_name,
            self._script_pairs, self._model_name
        )
        self._manager.save(self._cp)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if exc_type is None:
            self._cp.mark_complete()
            self._manager.save(self._cp)
            self._manager.delete(self._project_name)   # clean up on success
        else:
            # Save progress so user can resume
            self._manager.save(self._cp)
            safe_print(
                f"\n⚠️  Generation interrupted for '{self._project_name}'.\n"
                f"   {len(self._cp.completed)} scripts saved. "
                f"Run '/resume {self._project_name}' to continue.\n"
            )
        return False  # don't suppress the exception

    # ── Forwarded checkpoint API ──────────────────────────────────────────────

    @property
    def remaining(self) -> list:
        return self._cp.remaining_pairs if self._cp else self._script_pairs

    @property
    def completed(self) -> list:
        return self._cp.completed if self._cp else []

    def mark_started(self, name: str):
        if self._cp:
            self._cp.mark_started(name)
            self._manager.save(self._cp)

    def mark_done(self, name: str):
        if self._cp:
            self._cp.mark_done(name)
            self._manager.save(self._cp)

    def mark_failed(self, name: str):
        if self._cp:
            self._cp.mark_failed(name)
            self._manager.save(self._cp)


# ── Global singleton ──────────────────────────────────────────────────────────
_checkpoint_manager = CheckpointManager()


def get_checkpoint_manager() -> CheckpointManager:
    return _checkpoint_manager
