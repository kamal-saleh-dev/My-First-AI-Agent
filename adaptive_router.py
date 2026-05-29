"""Failure-driven adaptive model routing for the adaptive runtime.

The audit recommended adaptive routing *where justified* and noted the pieces
already existed (model aliases + an escalation ladder). This is the thin policy
that connects them to the reflection engine: when a step keeps failing, escalate
the model along a configured ladder of llm_client aliases.

It does NOT replace model_router.py (intent/domain routing) and does NOT affect
/auto or /multi. Raw provider model strings are never hardcoded here -- only
aliases resolved through llm_client.MODEL_ALIASES.
"""

from __future__ import annotations

import config as _cfg
from logger import log

def _known_aliases() -> dict:
    try:
        import llm_client
        return dict(getattr(llm_client, "MODEL_ALIASES", {}) or {})
    except Exception:
        return {}

class AdaptiveModelRouter:
    """Pick the model for an agent's next attempt based on escalation level."""

    def __init__(self, ladder=None):
        raw = tuple(ladder if ladder is not None else _cfg.ADAPTIVE_ESCALATION_LADDER)
        self.ladder = tuple(str(model) for model in raw if str(model).strip())
        aliases = _known_aliases()
        if aliases:
            for model in self.ladder:
                if model not in aliases:
                    log.warn("Adaptive router: model not in MODEL_ALIASES", model=model)

    def select(self, base_model: str, *, escalation: int = 0, role: str = "") -> str:
        """Return the model to use for the next attempt.

        ``escalation == 0`` keeps the agent's own preferred model. Higher levels
        walk up the ladder, clamped to its last entry. Falls back to
        ``base_model`` when the ladder is empty.
        """
        base_model = str(base_model or "")
        if escalation <= 0 or not self.ladder:
            return base_model or (self.ladder[0] if self.ladder else "")
        index = min(int(escalation), len(self.ladder)) - 1
        index = max(index, 0)
        chosen = self.ladder[index] or base_model
        log.info(
            "Adaptive router escalation",
            role=role,
            escalation=escalation,
            base=base_model,
            chosen=chosen,
        )
        return chosen

    def fallback_chain(self, base_model: str) -> list:
        chain: list = []
        for model in (base_model, *self.ladder):
            model = str(model or "")
            if model and model not in chain:
                chain.append(model)
        return chain

    def describe(self) -> dict:
        return {"ladder": list(self.ladder)}
