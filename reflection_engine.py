"""Lightweight reflection and replanning for adaptive autonomy.

Phase 3 (redesigned). The architecture audit concluded that the original
three-module design (reflection_engine + progress_tracker + failure_analyzer)
was over-engineered for this project, and that the highest-ROI gap was simply a
thin control layer that, after each agent step, decides whether to continue,
retry, switch model, hand off to the debugger, or stop.

This module is that layer: one small, rules-based, dependency-free evaluator
(no extra LLM calls). It is consumed only by adaptive_runtime.py and never
touches the /auto or /multi code paths.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field

import config as _cfg
from logger import log

# -- Control decisions ---------------------------------------------------------
CONTINUE = "continue"              # step succeeded -- move on
RETRY = "retry"                    # retry the step with the same model
SWITCH_MODEL = "switch_model"      # retry the step with an escalated model
DELEGATE_DEBUG = "delegate_debug"  # hand the failure to the DebuggerAgent, then retry
STOP = "stop"                      # give up on this step / workflow

VALID_DECISIONS = (CONTINUE, RETRY, SWITCH_MODEL, DELEGATE_DEBUG, STOP)

def _status_error(result) -> tuple[str, str]:
    """Accept an AgentResult-like object or a plain dict."""
    if result is None:
        return "failed", ""
    if isinstance(result, dict):
        return str(result.get("status") or "failed"), str(result.get("error") or "")
    return (
        str(getattr(result, "status", "failed") or "failed"),
        str(getattr(result, "error", "") or ""),
    )

def _normalize_error(error: str) -> str:
    return " ".join(str(error or "").split()).lower()[:120]

def _coerce_int(value, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)

@dataclass
class Reflection:
    """The verdict for a single observed agent step."""

    step: int
    agent: str
    status: str
    success: bool
    decision: str
    reason: str = ""
    progress: float = 0.0
    stuck: bool = False
    attempts: int = 0
    repeated_failures: int = 0
    escalation: int = 0
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)

class ReflectionEngine:
    """Stateful, bounded evaluator that turns step outcomes into control decisions.

    Termination is guaranteed: every failure increments per-agent attempt and
    failure-signature counters, and each decision branch is bounded by a
    configured limit, so repeated failures always converge to DELEGATE_DEBUG (at
    most ``max_debug_delegations`` times) and then STOP.
    """

    def __init__(
        self,
        *,
        total_steps: int = 0,
        max_retries: int | None = None,
        max_escalations: int | None = None,
        max_debug_delegations: int | None = None,
        stuck_threshold: int | None = None,
        can_debug: bool = True,
    ):
        self.total_steps = max(_coerce_int(total_steps, 0), 0)
        self.max_retries = _coerce_int(max_retries, _cfg.ADAPTIVE_MAX_STEP_RETRIES)
        self.max_escalations = _coerce_int(max_escalations, _cfg.ADAPTIVE_MAX_ESCALATIONS)
        self.max_debug_delegations = _coerce_int(
            max_debug_delegations, _cfg.ADAPTIVE_MAX_DEBUG_DELEGATIONS
        )
        self.stuck_threshold = max(_coerce_int(stuck_threshold, _cfg.ADAPTIVE_STUCK_THRESHOLD), 1)
        self.can_debug = bool(can_debug)

        self._completed = 0
        self._attempts: dict[str, int] = {}
        self._escalations: dict[str, int] = {}
        self._failure_sigs: dict[str, int] = {}
        self._debug_delegations = 0
        self.history: list[Reflection] = []

    def reflect(self, step: int, agent: str, result) -> Reflection:
        status, error = _status_error(result)
        success = status == "completed"

        if success:
            self._completed += 1
            return self._record(
                Reflection(
                    step=step,
                    agent=agent,
                    status=status,
                    success=True,
                    decision=CONTINUE,
                    reason="step completed",
                    progress=self._progress(step),
                    attempts=self._attempts.get(agent, 0),
                    escalation=self._escalations.get(agent, 0),
                )
            )

        attempts = self._attempts.get(agent, 0) + 1
        self._attempts[agent] = attempts

        signature = f"{agent}::{_normalize_error(error)}"
        repeated = self._failure_sigs.get(signature, 0) + 1
        self._failure_sigs[signature] = repeated
        stuck = repeated >= self.stuck_threshold

        decision, reason = self._decide_on_failure(agent, attempts, stuck)
        reflection = Reflection(
            step=step,
            agent=agent,
            status=status,
            success=False,
            decision=decision,
            reason=reason,
            progress=self._progress(step),
            stuck=stuck,
            attempts=attempts,
            repeated_failures=repeated,
            escalation=self._escalations.get(agent, 0),
        )
        log.info(
            "Reflection decision",
            agent=agent,
            step=step,
            decision=decision,
            attempts=attempts,
            repeated=repeated,
            stuck=stuck,
        )
        return self._record(reflection)

    def progress_score(self) -> float:
        denom = self.total_steps or max(len(self.history), 1)
        return round(min(self._completed / denom, 1.0), 3)

    def summary(self) -> dict:
        return {
            "completed": self._completed,
            "total_steps": self.total_steps,
            "progress": self.progress_score(),
            "debug_delegations": self._debug_delegations,
            "attempts": dict(self._attempts),
            "escalations": dict(self._escalations),
            "decisions": [r.decision for r in self.history],
        }

    def _decide_on_failure(self, agent: str, attempts: int, stuck: bool) -> tuple[str, str]:
        if stuck:
            return STOP, "stuck: repeated identical failure"

        if attempts <= self.max_retries:
            if self._escalations.get(agent, 0) < self.max_escalations:
                self._escalations[agent] = self._escalations.get(agent, 0) + 1
                return SWITCH_MODEL, f"escalate model (attempt {attempts})"
            return RETRY, f"retry with current model (attempt {attempts})"

        if (
            self.can_debug
            and agent != "DebuggerAgent"
            and self._debug_delegations < self.max_debug_delegations
        ):
            self._debug_delegations += 1
            return DELEGATE_DEBUG, "retry limit reached; delegating to DebuggerAgent"

        return STOP, "retry and debug budget exhausted"

    def _progress(self, step: int) -> float:
        denom = self.total_steps or max(step, 1)
        return round(min(self._completed / denom, 1.0), 3)

    def _record(self, reflection: Reflection) -> Reflection:
        self.history.append(reflection)
        return reflection
