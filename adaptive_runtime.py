"""Phase 3 (redesigned): the opt-in Adaptive Autonomy runtime.

This is the integration surface for the audit's highest-ROI recommendations:

    * Reflection / replanning  (reflection_engine.ReflectionEngine)
    * Memory integration       (agent_memory.AgentMemoryBridge)
    * Adaptive model routing   (adaptive_router.AdaptiveModelRouter)

It reuses -- and does not rewrite -- the existing multi-agent building blocks
(AgentManager, the specialized agents, MessageBus, SharedExecutionContext) in
the exact same composition style as multi_agent_runtime.py.

Guarantees:
    * /auto  (autonomous_loop.AutonomousExecutor)    is untouched.
    * /multi (multi_agent_runtime.MultiAgentRuntime) is untouched.
    * It owns its own AgentManager instance, so per-step model escalation never
      leaks into other runtimes or global state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from logger import log, safe_print

from agents import AgentManager, MessageBus, SharedExecutionContext
from adaptive_router import AdaptiveModelRouter
from agent_memory import AgentMemoryBridge
from reflection_engine import (
    CONTINUE,
    DELEGATE_DEBUG,
    RETRY,
    STOP,
    SWITCH_MODEL,
    ReflectionEngine,
)

DEFAULT_ADAPTIVE_WORKFLOW: tuple[str, ...] = (
    "PlannerAgent",
    "CodingAgent",
    "ReviewerAgent",
    "TestingAgent",
)
DEBUGGER_AGENT = "DebuggerAgent"

_MAX_DETAIL_CHARS = 160

def _short(text: str, limit: int = _MAX_DETAIL_CHARS) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"

@dataclass
class AdaptiveStepResult:
    step: int
    agent: str
    status: str
    attempts: int
    final_decision: str
    model: str = ""
    detail: str = ""
    debugged: bool = False
    result: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "step": self.step,
            "agent": self.agent,
            "status": self.status,
            "attempts": self.attempts,
            "final_decision": self.final_decision,
            "model": self.model,
            "detail": self.detail,
            "debugged": self.debugged,
            "result": dict(self.result),
        }

@dataclass
class AdaptiveRunResult:
    status: str
    task: str
    workflow: list = field(default_factory=list)
    steps: list = field(default_factory=list)
    reflections: list = field(default_factory=list)
    events: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)

    @property
    def completed(self) -> bool:
        return self.status == "completed"

    @property
    def recovered(self) -> bool:
        return any(step.get("debugged") for step in self.steps)

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "task": self.task,
            "workflow": list(self.workflow),
            "steps": list(self.steps),
            "reflections": list(self.reflections),
            "events": list(self.events),
            "summary": dict(self.summary),
        }

class AdaptiveRuntime:
    """Opt-in reflect -> decide -> adapt coordinator over the existing agents."""

    def __init__(
        self,
        *,
        manager: AgentManager | None = None,
        workflow=None,
        reflection: ReflectionEngine | None = None,
        router: AdaptiveModelRouter | None = None,
        memory: AgentMemoryBridge | None = None,
        emit: Optional[Callable[[str], None]] = None,
    ):
        if manager is not None:
            self.manager = manager
            self.shared_context = manager.shared_context
            self.message_bus = manager.message_bus
        else:
            self.shared_context = SharedExecutionContext()
            self.message_bus = MessageBus()
            self.manager = AgentManager(
                shared_context=self.shared_context,
                message_bus=self.message_bus,
            )
        self.workflow = tuple(workflow or DEFAULT_ADAPTIVE_WORKFLOW)
        self._reflection = reflection
        self.router = router or AdaptiveModelRouter()
        self.memory = memory or AgentMemoryBridge()
        self.emit = emit or safe_print
        self.events: list[dict] = []

    # -- Visibility -----------------------------------------------------------
    def _record(self, event: dict) -> None:
        self.events.append(event)

    def _on_bus_event(self, bus_event) -> None:
        message = (getattr(bus_event, "payload", None) or {}).get("message") or {}
        if message.get("from") != "AgentManager":
            return
        self._record({
            "type": "delegated",
            "agent": message.get("to", ""),
            "task": message.get("task", ""),
        })
        self.emit(f"   ▶ active agent: {message.get('to', '')}")

    # -- Helpers --------------------------------------------------------------
    def _has_debugger(self) -> bool:
        try:
            self.manager.get_agent(DEBUGGER_AGENT)
            return True
        except Exception:
            return False

    def _base_model(self, agent_name: str) -> str:
        try:
            return str(self.manager.get_agent(agent_name).preferred_model or "")
        except Exception:
            return ""

    def _set_model(self, agent_name: str, model: str) -> None:
        if not model:
            return
        try:
            self.manager.get_agent(agent_name).preferred_model = model
        except Exception:
            pass

    @staticmethod
    def _status_detail(result) -> tuple[str, str]:
        if result is None:
            return "failed", ""
        if hasattr(result, "status"):
            detail = getattr(result, "final_answer", "") or getattr(result, "error", "")
            return str(result.status or "failed"), str(detail or "")
        if isinstance(result, dict):
            return (
                str(result.get("status") or "failed"),
                str(result.get("final_answer") or result.get("error") or ""),
            )
        return "failed", ""

    # -- Entry point ----------------------------------------------------------
    def run(self, task: str, *, decision_fns=None) -> AdaptiveRunResult:
        task = (task or "").strip()
        if not task:
            raise ValueError("adaptive runtime requires a non-empty task")

        decision_fns = dict(decision_fns or {})
        self.events = []
        reflection = self._reflection or ReflectionEngine(
            total_steps=len(self.workflow),
            can_debug=self._has_debugger(),
        )

        self.emit("\n🧠 Adaptive autonomy runtime (opt-in) starting")
        self.emit(f"   task     : {_short(task)}")
        self.emit(f"   workflow : {' → '.join(self.workflow)}")

        subscription_id = self.message_bus.subscribe("message_published", self._on_bus_event)
        steps: list[dict] = []
        status = "completed"
        try:
            for index, agent_name in enumerate(self.workflow, start=1):
                step_result = self._run_step(index, agent_name, task, decision_fns, reflection)
                steps.append(step_result.to_dict())
                if step_result.status != "completed":
                    status = "failed"
                    self.emit(f"   ⛔ workflow stopped at step {index} [{agent_name}]")
                    break
        finally:
            self.message_bus.unsubscribe(subscription_id)

        summary = reflection.summary()
        reflections = [r.to_dict() for r in reflection.history]
        self._record({"type": "run_status", "status": status})
        self.emit(f"   🏁 adaptive run status: {status} (progress {summary.get('progress')})\n")
        log.info("Adaptive runtime finished", status=status, steps=len(steps), progress=summary.get("progress"))

        return AdaptiveRunResult(
            status=status,
            task=task,
            workflow=list(self.workflow),
            steps=steps,
            reflections=reflections,
            events=list(self.events),
            summary=summary,
        )

    # -- Per-step reflect -> decide -> adapt loop -----------------------------
    def _run_step(self, index, agent_name, task, decision_fns, reflection) -> AdaptiveStepResult:
        base_model = self._base_model(agent_name)
        escalation = 0
        debugged = False
        last_result = None
        attempts = 0
        decision = STOP

        while True:
            model = self.router.select(base_model, escalation=escalation, role=agent_name)
            self._set_model(agent_name, model)
            context = self.memory.recall_context(task)
            result = self.manager.delegate_task(
                agent_name,
                task,
                context=context,
                decision_fn=decision_fns.get(agent_name),
            )
            last_result = result
            self.memory.record(task, result)

            verdict = reflection.reflect(index, agent_name, result)
            decision = verdict.decision
            attempts = verdict.attempts
            self._record({
                "type": "reflection",
                "step": index,
                "agent": agent_name,
                "status": getattr(result, "status", "failed"),
                "decision": decision,
                "attempts": verdict.attempts,
                "model": model,
            })
            self.emit(
                f"   {'✅' if verdict.success else '❌'} step {index} [{agent_name}] "
                f"→ {getattr(result, 'status', 'failed')} ({decision})"
            )

            if decision == CONTINUE:
                break
            if decision == SWITCH_MODEL:
                escalation += 1
                continue
            if decision == RETRY:
                continue
            if decision == DELEGATE_DEBUG:
                debugged = True
                self._delegate_debug(index, agent_name, task, result, decision_fns)
                escalation += 1
                continue
            break  # STOP / unhandled

        self._set_model(agent_name, base_model)  # reset so escalation never leaks forward

        status, detail = self._status_detail(last_result)
        return AdaptiveStepResult(
            step=index,
            agent=agent_name,
            status=status,
            attempts=attempts,
            final_decision=decision,
            model=self._base_model(agent_name),
            detail=detail,
            debugged=debugged,
            result=last_result.to_dict() if hasattr(last_result, "to_dict") else dict(last_result or {}),
        )

    def _delegate_debug(self, index, agent_name, task, failed_result, decision_fns) -> None:
        _, detail = self._status_detail(failed_result)
        debug_task = f"Diagnose and repair the failure from {agent_name}: {_short(detail)}"
        self.emit(f"   🛠 delegating to {DEBUGGER_AGENT} after {agent_name} failure")
        self._record({"type": "debug_delegation", "step": index, "from": agent_name})
        try:
            debug_result = self.manager.delegate_task(
                DEBUGGER_AGENT,
                debug_task,
                context={"failed_agent": agent_name, "original_task": task},
                decision_fn=decision_fns.get(DEBUGGER_AGENT),
            )
            self.memory.record(debug_task, debug_result)
        except Exception as exc:
            log.warn("Debug delegation failed", error=str(exc))

def run_adaptive(task: str, *, workflow=None, emit=None, decision_fns=None) -> AdaptiveRunResult:
    """Convenience wrapper: build a runtime and run a single task."""
    return AdaptiveRuntime(workflow=workflow, emit=emit).run(task, decision_fns=decision_fns)
