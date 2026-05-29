"""Phase 2 Runtime Integration — opt-in multi-agent runtime entry point.

This module exposes the already-built multi-agent system through a single,
explicit, user-accessible entry point (the ``/multi`` command). It is *opt-in*:
nothing here runs unless the user explicitly asks for it, and it does not change
the existing ``/auto`` autonomous loop in any way.

It reuses — and does not rewrite — the existing building blocks:

    * AgentManager            (registration, delegation, orchestration)
    * BaseAgent + Planner/Coding/Reviewer/Testing agents (specialized agents)
    * MessageBus              (inter-agent messages + observer events)
    * SharedExecutionContext  (shared goals / tasks / memory)
    * ExecutionPlan           (built by AgentManager.orchestrate)
    * ExecutionStrategy       (SequentialExecutionStrategy, the default)

It deliberately does NOT implement reflection, replanning, vector memory,
semantic retrieval, DAG execution, or long-term memory (those are Phase 3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from logger import log, safe_print

from agents import (
    AgentManager,
    ExecutionStrategy,
    MessageBus,
    SharedExecutionContext,
)

# Reuse the existing specialized agents in their natural collaboration order.
DEFAULT_MULTI_AGENT_WORKFLOW: tuple[str, ...] = (
    "PlannerAgent",
    "CodingAgent",
    "ReviewerAgent",
    "TestingAgent",
)

_MAX_DETAIL_CHARS = 160

def _short(text: str, limit: int = _MAX_DETAIL_CHARS) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= limit else text[: limit - 1] + "…"

@dataclass
class MultiAgentRunResult:
    """Structured outcome of a single ``/multi`` orchestration run."""

    status: str
    task: str
    correlation_id: str = ""
    workflow: list = field(default_factory=list)
    results: list = field(default_factory=list)
    events: list = field(default_factory=list)
    outcome: dict = field(default_factory=dict)

    @property
    def completed(self) -> bool:
        return self.status == "completed"

    def to_dict(self) -> dict:
        return {
            "status": self.status,
            "task": self.task,
            "correlation_id": self.correlation_id,
            "workflow": list(self.workflow),
            "results": list(self.results),
            "events": list(self.events),
        }

class MultiAgentRuntime:
    """Opt-in runtime that orchestrates the existing multi-agent system.

    The runtime is a thin coordinator: it wires a SharedExecutionContext and a
    MessageBus into an AgentManager (reusing all existing agents), subscribes a
    visibility observer to the bus, and then defers all real work to the
    existing ``AgentManager.orchestrate`` + ``SequentialExecutionStrategy``.
    """

    def __init__(
        self,
        *,
        manager: AgentManager | None = None,
        workflow: list[str] | tuple[str, ...] | None = None,
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
        self.workflow = tuple(workflow or DEFAULT_MULTI_AGENT_WORKFLOW)
        self.emit = emit or safe_print
        self.events: list[dict] = []

    # ── Visibility ─────────────────────────────────────────────────────
    def _record(self, event: dict) -> None:
        self.events.append(event)

    def _on_bus_event(self, bus_event) -> None:
        """Observer for MessageBus 'message_published' events.

        Fires once per delegation (AgentManager -> agent), giving live
        visibility into the *active agent* and its *delegated task*.
        """
        message = (getattr(bus_event, "payload", None) or {}).get("message") or {}
        if message.get("from") != "AgentManager":
            return
        active_agent = message.get("to", "")
        delegated_task = message.get("task", "")
        self._record({
            "type": "delegated",
            "agent": active_agent,
            "task": delegated_task,
            "correlation_id": getattr(bus_event, "correlation_id", ""),
        })
        self.emit(f"   ▶ active agent: {active_agent}")
        self.emit(f"     delegated task: {_short(delegated_task)}")

    def _render_step_results(self, outcome: dict) -> None:
        for index, result in enumerate(outcome.get("results", []), start=1):
            agent = result.get("agent_name", "?")
            status = result.get("status", "?")
            detail = result.get("final_answer") or result.get("error") or ""
            icon = "✅" if status == "completed" else "❌"
            self._record({
                "type": "step_result",
                "step": index,
                "agent": agent,
                "status": status,
                "detail": detail,
            })
            self.emit(f"   {icon} step {index} [{agent}] → {status}: {_short(detail)}")

    # ── Entry point ──────────────────────────────────────────────────
    def run(
        self,
        task: str,
        *,
        decision_fns: dict[str, Callable[[list[dict]], str]] | None = None,
        strategy: ExecutionStrategy | None = None,
    ) -> MultiAgentRunResult:
        task = (task or "").strip()
        if not task:
            raise ValueError("multi-agent runtime requires a non-empty task")

        self.events = []
        self.emit("\n🤖 Multi-agent runtime (opt-in) starting")
        self.emit(f"   task     : {_short(task)}")
        self.emit(f"   workflow : {' → '.join(self.workflow)}")

        subscription_id = self.message_bus.subscribe("message_published", self._on_bus_event)
        try:
            outcome = self.manager.orchestrate(
                task,
                workflow=self.workflow,
                decision_fns=decision_fns,
                strategy=strategy,
            )
        finally:
            self.message_bus.unsubscribe(subscription_id)

        self._render_step_results(outcome)
        status = outcome.get("status", "unknown")
        self._record({"type": "orchestration_status", "status": status})
        self.emit(f"   🏁 orchestration status: {status}\n")
        log.info(
            "Multi-agent runtime finished",
            status=status,
            correlation_id=outcome.get("correlation_id", ""),
            steps=len(outcome.get("results", [])),
        )

        return MultiAgentRunResult(
            status=status,
            task=outcome.get("task", task),
            correlation_id=outcome.get("correlation_id", ""),
            workflow=list(outcome.get("workflow", self.workflow)),
            results=list(outcome.get("results", [])),
            events=list(self.events),
            outcome=outcome,
        )

def run_multi_agent(
    task: str,
    *,
    workflow: list[str] | tuple[str, ...] | None = None,
    emit: Optional[Callable[[str], None]] = None,
    decision_fns: dict[str, Callable[[list[dict]], str]] | None = None,
) -> MultiAgentRunResult:
    """Convenience wrapper: build a runtime and run a single task."""
    return MultiAgentRuntime(workflow=workflow, emit=emit).run(task, decision_fns=decision_fns)
