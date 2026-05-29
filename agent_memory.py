"""Integrate the existing RAG memory store into the agent workflow.

The architecture audit's key Phase 4 finding was that memory_store.py was fully
implemented but had no callers -- the agents never read from or wrote to it.
This bridge is that missing wiring: AdaptiveRuntime recalls relevant past
experience before delegating a step (injected via the delegated context, which
BaseAgent already folds into the prompt) and records the outcome afterwards.

memory_store.py itself is intentionally left unchanged; this is pure integration.
"""

from __future__ import annotations

import config as _cfg
from logger import log

def _default_store():
    from memory_store import memory
    return memory

def _status_answer(result) -> tuple[str, str]:
    if result is None:
        return "failed", ""
    if isinstance(result, dict):
        return (
            str(result.get("status") or "failed"),
            str(result.get("final_answer") or result.get("error") or ""),
        )
    return (
        str(getattr(result, "status", "failed") or "failed"),
        str(getattr(result, "final_answer", "") or getattr(result, "error", "") or ""),
    )

class AgentMemoryBridge:
    """Recall/record helper around the singleton (or an injected) MemoryStore."""

    CONTEXT_KEY = "past_experience"

    def __init__(
        self,
        store=None,
        *,
        enabled: bool | None = None,
        top_k: int | None = None,
        only_successful: bool | None = None,
    ):
        self._store = store
        self.enabled = _cfg.ADAPTIVE_MEMORY_ENABLED if enabled is None else bool(enabled)
        self.top_k = int(top_k if top_k is not None else _cfg.ADAPTIVE_MEMORY_TOP_K)
        self.only_successful = (
            _cfg.ADAPTIVE_MEMORY_ONLY_SUCCESS if only_successful is None else bool(only_successful)
        )

    @property
    def store(self):
        if self._store is None:
            self._store = _default_store()
        return self._store

    def recall_text(self, task: str) -> str:
        if not self.enabled or not str(task or "").strip():
            return ""
        try:
            if self.only_successful:
                hits = self.store.search(task, top_k=self.top_k, only_successful=True)
                return self._format_hits(hits)
            return self.store.format_context(task, top_k=self.top_k) or ""
        except Exception as exc:
            log.warn("Memory recall failed", error=str(exc))
            return ""

    def recall_context(self, task: str) -> dict:
        """Return a context dict for AgentManager.delegate_task(context=...)."""
        text = self.recall_text(task)
        return {self.CONTEXT_KEY: text} if text else {}

    def record(self, task: str, result, *, files=None, feedback: str = "") -> None:
        if not self.enabled or not str(task or "").strip():
            return
        status, answer = _status_answer(result)
        try:
            self.store.add(
                task=task,
                success=(status == "completed"),
                solution=answer,
                feedback=feedback,
                files=files or [],
            )
        except Exception as exc:
            log.warn("Memory record failed", error=str(exc))

    @staticmethod
    def _format_hits(hits) -> str:
        if not hits:
            return ""
        lines = ["RELEVANT PAST EXPERIENCE (reuse these patterns):"]
        for hit in hits:
            ok = "success" if hit.get("s", 1) else "failed"
            lines.append(f"- [{ok}] task: {hit.get('q', '')}")
            solution = hit.get("r") or ""
            if solution:
                lines.append(f"  pattern: {solution}")
        return "\n".join(lines)
