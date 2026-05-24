"""Base abstractions for isolated autonomous agents."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterable, Optional

import config as _cfg
from autonomous_loop import AutonomousExecutor, ExecutionState
from logger import log
from tool_registry import Tool, ToolResult, get_tool

from .message_bus import AgentMessage, MessageBus
from .shared_execution_context import SharedExecutionContext


@dataclass
class AgentExecutionPolicy:
    max_steps: int = _cfg.AUTONOMOUS_MAX_STEPS
    max_retries: int = _cfg.AUTONOMOUS_MAX_RETRIES
    tool_timeout: int = _cfg.AUTONOMOUS_TOOL_TIMEOUT
    repeat_limit: int = _cfg.AUTONOMOUS_REPEAT_LIMIT
    max_action_history: int = 200
    max_observations: int = 200
    max_local_memory: int = 200
    max_compaction_summaries: int = 50


@dataclass
class AgentState:
    status: str = "idle"
    current_task_id: str = ""
    action_history: list[dict] = field(default_factory=list)
    local_memory: list[dict] = field(default_factory=list)
    retry_counters: dict[str, int] = field(default_factory=dict)
    observations: list[dict] = field(default_factory=list)
    reasoning_context: dict = field(default_factory=dict)
    failures: list[dict] = field(default_factory=list)
    compaction_summaries: list[dict] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class AgentResult:
    agent_name: str
    task: str
    status: str
    final_answer: str = ""
    error: str = ""
    observations: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class BaseAgent:
    """Autonomous agent with isolated state and explicit tool capability limits."""

    name = "BaseAgent"
    role = "base"
    system_prompt = "Use your allowed tools to complete the assigned engineering task."
    preferred_model = "local"
    allowed_tools: tuple[str, ...] = ()
    restricted_tools: tuple[str, ...] = ()

    def __init__(
        self,
        *,
        shared_context: SharedExecutionContext | None = None,
        message_bus: MessageBus | None = None,
        policy: AgentExecutionPolicy | None = None,
        preferred_model: str | None = None,
    ):
        self.shared_context = shared_context or SharedExecutionContext()
        self.message_bus = message_bus or MessageBus()
        self.policy = policy or AgentExecutionPolicy()
        self.preferred_model = preferred_model or self.preferred_model
        self.state = AgentState(reasoning_context={"role": self.role})

    @property
    def effective_allowed_tools(self) -> tuple[str, ...]:
        restricted = set(self.restricted_tools)
        return tuple(tool for tool in self.allowed_tools if tool not in restricted)

    def can_use_tool(self, tool_name: str) -> bool:
        return tool_name in self.effective_allowed_tools

    def assert_tool_allowed(self, tool_name: str) -> None:
        if not self.can_use_tool(tool_name):
            raise PermissionError(f"{self.name} is not allowed to use tool '{tool_name}'")

    def execute_tool(self, tool_name: str, args: dict | None = None) -> ToolResult:
        args = dict(args or {})
        try:
            self.assert_tool_allowed(tool_name)
        except Exception as exc:
            self.on_failure(str(exc), {"phase": "permission", "tool": tool_name, "args": args})
            raise
        tool = get_tool(tool_name, structured=True)
        if not isinstance(tool, Tool):
            error = f"unknown tool: {tool_name}"
            self.on_failure(error, {"phase": "tool_lookup", "tool": tool_name, "args": args})
            raise ValueError(error)

        started = time.time()
        log.run("Agent tool call started", agent=self.name, tool=tool_name, args=args)
        self.before_tool(tool_name, args, {"source": "direct"})
        try:
            result = tool.execute_structured(args)
        except Exception as exc:
            result = ToolResult.fail(str(exc))
        elapsed = round(time.time() - started, 3)
        self._record_tool_result(tool_name, args, result, elapsed)
        self.after_tool(tool_name, args, result, {"source": "direct", "elapsed": elapsed})
        if not result.success:
            self.on_failure(result.error or "tool returned failure", {"phase": "tool", "tool": tool_name})
        return result

    def run(
        self,
        task: str,
        *,
        context: dict | None = None,
        correlation_id: str = "",
        task_id: str = "",
        decision_fn: Optional[Callable[[list[dict]], str]] = None,
    ) -> AgentResult:
        context = dict(context or {})
        correlation_id = correlation_id or str(uuid.uuid4())
        shared_task = self.shared_context.get_task(task_id) if task_id else None
        if shared_task is None:
            shared_task = self.shared_context.create_task(
                task,
                assigned_to=self.name,
                correlation_id=correlation_id,
                metadata={"agent": self.name, "role": self.role, **context},
            )

        self.state.status = "running"
        self.state.current_task_id = shared_task.task_id
        self.state.reasoning_context = {
            **self.state.reasoning_context,
            "task": task,
            "context": context,
            "correlation_id": shared_task.correlation_id,
        }
        self.state.updated_at = time.time()
        self.shared_context.update_task(shared_task.task_id, "running")
        log.info(
            "Agent task started",
            agent=self.name,
            role=self.role,
            task_id=shared_task.task_id,
            correlation_id=shared_task.correlation_id,
        )

        self.before_task(task, context, shared_task.to_dict())
        try:
            executor = self._build_executor(decision_fn=decision_fn)
            execution_state = executor.execute(self._compose_task(task, context))
            result = self._result_from_execution(task, execution_state, shared_task.task_id)
        except Exception as exc:
            result = AgentResult(
                agent_name=self.name,
                task=task,
                status="failed",
                error=str(exc),
                metadata={"task_id": shared_task.task_id, "preferred_model": self.preferred_model},
            )
            self.state.status = "failed"
            self.state.failures.append(
                {"task": task, "reason": str(exc), "task_id": shared_task.task_id, "ts": time.time()}
            )
            self.on_failure(str(exc), {"phase": "task", "task_id": shared_task.task_id})

        shared_status = "completed" if result.status == "completed" else "failed"
        self.shared_context.update_task(shared_task.task_id, shared_status, result.to_dict())
        self.remember(
            {
                "type": "task_result",
                "task": task,
                "status": result.status,
                "correlation_id": shared_task.correlation_id,
            }
        )
        if result.status != "completed":
            self.on_failure(result.error or "task failed", {"phase": "task_result", "task_id": shared_task.task_id})
        self.after_task(task, result, shared_task.to_dict())
        log.info("Agent task finished", agent=self.name, status=result.status, error=result.error)
        return result

    def send_message(
        self,
        to_agent: str,
        task: str,
        *,
        context: dict | None = None,
        correlation_id: str = "",
        metadata: dict | None = None,
    ) -> AgentMessage:
        return self.message_bus.send(
            self.name,
            to_agent,
            task,
            context=context,
            correlation_id=correlation_id,
            metadata=metadata,
        )

    def receive_messages(self, limit: int | None = None) -> list[AgentMessage]:
        return self.message_bus.receive(self.name, limit=limit)

    def remember(self, entry: dict) -> None:
        self._append_bounded("local_memory", {"ts": time.time(), **dict(entry)})
        self.state.updated_at = time.time()

    def local_memory_snapshot(self) -> list[dict]:
        return list(self.state.local_memory)

    def reset_state(self) -> None:
        self.state = AgentState(reasoning_context={"role": self.role})

    def before_task(self, task: str, context: dict, metadata: dict | None = None) -> None:
        """Hook called immediately before the autonomous loop starts a task."""

    def after_task(self, task: str, result: AgentResult, metadata: dict | None = None) -> None:
        """Hook called after task completion or failure handling."""

    def before_tool(self, tool_name: str, args: dict, metadata: dict | None = None) -> None:
        """Hook called before an allowed tool executes."""

    def after_tool(
        self,
        tool_name: str,
        args: dict,
        result: ToolResult,
        metadata: dict | None = None,
    ) -> None:
        """Hook called after a tool returns or fails."""

    def on_failure(self, error: str, metadata: dict | None = None) -> None:
        """Hook called for tool, retry, stop, and task failures."""

    def on_executor_event(self, event_type: str, payload: dict) -> None:
        """Generic hook for future telemetry, retry, observation, and stop events."""

    def summarize_pruned_records(self, kind: str, records: list[dict]) -> dict:
        """Summarization hook for bounded state compaction."""
        return {
            "kind": kind,
            "count": len(records),
            "ts": time.time(),
            "first": records[0] if records else {},
            "last": records[-1] if records else {},
        }

    def after_state_pruned(self, kind: str, summary: dict) -> None:
        """Hook called after local state is compacted."""

    def _build_executor(self, decision_fn: Optional[Callable[[list[dict]], str]]) -> AutonomousExecutor:
        return AutonomousExecutor(
            model_name=self.preferred_model,
            decision_fn=decision_fn,
            max_steps=self.policy.max_steps,
            max_retries=self.policy.max_retries,
            tool_timeout=self.policy.tool_timeout,
            repeat_limit=self.policy.repeat_limit,
            allowed_tools=set(self.effective_allowed_tools),
            agent_name=self.name,
            system_context=self._system_context(),
            event_handler=self._handle_executor_event,
        )

    def _handle_executor_event(self, event_type: str, payload: dict) -> None:
        self.on_executor_event(event_type, payload)
        tool_name = str(payload.get("tool") or "")
        args = dict(payload.get("args") or {})
        metadata = {"source": "autonomous_executor", "event": event_type}
        if "state" in payload:
            metadata["step"] = getattr(payload["state"], "step", None)

        if event_type == "before_tool" and tool_name:
            self.before_tool(tool_name, args, metadata)
        elif event_type == "after_tool" and tool_name:
            result = ToolResult.from_value(payload.get("result"))
            self.after_tool(tool_name, args, result, metadata)
        elif event_type == "failure":
            self.on_failure(str(payload.get("error") or "failure"), {**metadata, "tool": tool_name})

    def _compose_task(self, task: str, context: dict) -> str:
        if not context:
            return task
        return f"{task}\n\nShared context:\n{context}"

    def _system_context(self) -> str:
        tools = ", ".join(self.effective_allowed_tools) or "none"
        return (
            f"{self.system_prompt}\n"
            f"Role: {self.role}.\n"
            f"Allowed tools: {tools}.\n"
            "Keep local reasoning and observations isolated unless explicitly shared."
        )

    def _result_from_execution(
        self,
        task: str,
        execution_state: ExecutionState,
        task_id: str,
    ) -> AgentResult:
        observations = [self._serialize_observation(obs) for obs in execution_state.observations]
        self._extend_bounded("observations", observations)
        self._extend_bounded(
            "action_history",
            [{
                "step": obs["step"],
                "tool": obs["tool"],
                "args": obs["args"],
                "success": obs["success"],
            }
            for obs in observations],
        )
        if execution_state.status != "completed":
            self.state.failures.append(
                {
                    "task": task,
                    "reason": execution_state.failure_reason,
                    "task_id": task_id,
                    "ts": time.time(),
                }
            )
        self.state.status = execution_state.status
        self.state.updated_at = time.time()
        return AgentResult(
            agent_name=self.name,
            task=task,
            status=execution_state.status,
            final_answer=execution_state.final_answer,
            error=execution_state.failure_reason,
            observations=observations,
            metadata={
                "task_id": task_id,
                "steps": execution_state.step,
                "preferred_model": self.preferred_model,
                "allowed_tools": list(self.effective_allowed_tools),
            },
        )

    def _record_tool_result(self, tool_name: str, args: dict, result: ToolResult, elapsed: float) -> None:
        record = {
            "step": len(self.state.action_history) + 1,
            "tool": tool_name,
            "args": dict(args),
            "success": result.success,
            "error": result.error,
            "elapsed": elapsed,
            "result": result.to_dict(),
        }
        self._append_bounded("action_history", record)
        self._append_bounded("observations", record)
        if not result.success:
            self.state.failures.append(record)
            self.state.retry_counters[tool_name] = self.state.retry_counters.get(tool_name, 0) + 1
        self.state.updated_at = time.time()

    def _append_bounded(self, kind: str, entry: dict) -> None:
        records = getattr(self.state, kind)
        records.append(dict(entry))
        self._prune_records(kind)

    def _extend_bounded(self, kind: str, entries: list[dict]) -> None:
        records = getattr(self.state, kind)
        records.extend(dict(entry) for entry in entries)
        self._prune_records(kind)

    def _prune_records(self, kind: str) -> None:
        records = getattr(self.state, kind)
        limits = {
            "action_history": self.policy.max_action_history,
            "observations": self.policy.max_observations,
            "local_memory": self.policy.max_local_memory,
        }
        limit = limits.get(kind)
        if limit is None or limit < 0 or len(records) <= limit:
            return
        overflow = len(records) - limit
        pruned = records[:overflow]
        del records[:overflow]
        summary = self.summarize_pruned_records(kind, pruned)
        self._append_compaction_summary(summary)
        self.after_state_pruned(kind, summary)

    def _append_compaction_summary(self, summary: dict) -> None:
        self.state.compaction_summaries.append(dict(summary))
        limit = self.policy.max_compaction_summaries
        if limit is None or limit < 0:
            return
        if limit == 0:
            self.state.compaction_summaries.clear()
            return
        overflow = len(self.state.compaction_summaries) - limit
        if overflow > 0:
            del self.state.compaction_summaries[:overflow]

    def _serialize_observation(self, observation) -> dict:
        return {
            "step": observation.step,
            "thought": observation.thought,
            "tool": observation.tool,
            "args": dict(observation.args),
            "success": observation.success,
            "error": observation.error,
            "elapsed": observation.elapsed,
            "summary": observation.summary,
            "result": observation.result.to_dict(),
        }


def tools(*names: str) -> tuple[str, ...]:
    return tuple(names)


def merge_tools(base: Iterable[str], restricted: Iterable[str]) -> tuple[str, ...]:
    blocked = set(restricted)
    return tuple(name for name in base if name not in blocked)
