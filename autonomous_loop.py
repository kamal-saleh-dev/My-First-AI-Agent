"""Autonomous think/act/observe execution loop.

Single-executor loop: one executor, one tool registry. A separate Phase 2
multi-agent package exists under `agents/` but is not wired into this loop or
the runtime; see docs/multi_agent_architecture.md.

State is in-memory by default. Optional, opt-in persistence is provided via
autonomous_checkpoint.AutonomousCheckpointStore (enable_checkpoints=True). Resume
restores prior ExecutionState only and does not replan.
"""

from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout
from dataclasses import asdict, dataclass, field
from typing import Callable, Optional

import config as _cfg
from autonomous_prompts import ObservationSummarizer, build_system_prompt, build_user_prompt
from autonomous_repetition import RepetitionDetector
from logger import log
from tool_registry import Tool, ToolResult, get_tool, list_tools

STOP_TOOLS = {"finish", "final_answer", "done", "stop"}

@dataclass
class Observation:
    step: int
    thought: str
    tool: str
    args: dict
    result: ToolResult
    success: bool
    error: str = ""
    elapsed: float = 0.0
    summary: str = ""

@dataclass
class ExecutionState:
    task: str
    status: str = "running"
    step: int = 0
    observations: list[Observation] = field(default_factory=list)
    final_answer: str = ""
    failure_reason: str = ""
    consecutive_failures: int = 0
    last_action_key: str = ""
    repeated_action_count: int = 0
    started_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["elapsed"] = round(self.updated_at - self.started_at, 3)
        return data

class AutonomousExecutor:
    """Run a task through repeated model-selected tool calls."""

    def __init__(
        self,
        model_name: Optional[str] = None,
        decision_fn: Optional[Callable[[list[dict]], str]] = None,
        max_steps: int | None = None,
        max_retries: int | None = None,
        tool_timeout: int | None = None,
        repeat_limit: int | None = None,
        allowed_tools: set[str] | list[str] | tuple[str, ...] | None = None,
        agent_name: str = "AutonomousExecutor",
        system_context: str = "",
        event_handler: Optional[Callable[[str, dict], None]] = None,
        enable_checkpoints: bool = False,
        checkpoint_store=None,
        checkpoint_id: str = "",
    ):
        self.model_name = model_name
        self.decision_fn = decision_fn
        self.max_steps = max_steps or _cfg.AUTONOMOUS_MAX_STEPS
        self.max_retries = max_retries if max_retries is not None else _cfg.AUTONOMOUS_MAX_RETRIES
        self.tool_timeout = tool_timeout or _cfg.AUTONOMOUS_TOOL_TIMEOUT
        self.repeat_limit = repeat_limit or _cfg.AUTONOMOUS_REPEAT_LIMIT
        self.allowed_tools = set(allowed_tools) if allowed_tools is not None else None
        self.agent_name = agent_name
        self.system_context = system_context or "Use the available tools to complete the task."
        self.event_handler = event_handler
        self.summarizer = ObservationSummarizer()
        # Opt-in persistence. Default OFF preserves the original in-memory behavior.
        self.enable_checkpoints = bool(enable_checkpoints)
        self._checkpoint_store = checkpoint_store
        self.checkpoint_id = checkpoint_id or agent_name
        if model_name:
            log.info("Autonomous executor model selected", model=model_name)

    def execute(self, task: str, resume_state: "ExecutionState | None" = None) -> ExecutionState:
        state = resume_state if resume_state is not None else ExecutionState(task=task)
        if resume_state is not None:
            # Restore-only: continue from the persisted state without replanning.
            state.status = "running"
            state.updated_at = time.time()
            log.info("Autonomous loop resuming", task=state.task, step=state.step)
        repetition_detector = RepetitionDetector(self.repeat_limit)
        log.info("Autonomous loop started", task=state.task, max_steps=self.max_steps)
        self._emit("loop_started", state=state, task=state.task, max_steps=self.max_steps)
        self._save_checkpoint(state)

        while state.step < self.max_steps and state.status == "running":
            state.step += 1
            raw = self._decide(state)
            self._emit("decision_received", state=state, raw=raw)
            action, parse_error = parse_action(raw)

            if parse_error:
                self._record_failure(
                    state, "", {}, raw, f"malformed_json: {parse_error}", thought="Recover from malformed action"
                )
                if self._should_stop_after_failure(state):
                    break
                continue

            thought = str(action.get("thought", ""))
            tool_name = str(action.get("tool", "")).strip()
            args = action.get("args") or {}

            if tool_name in STOP_TOOLS:
                state.status = "completed"
                state.final_answer = str(args.get("answer") or action.get("answer") or thought)
                state.updated_at = time.time()
                log.success("Autonomous loop completed", steps=state.step)
                self._emit("stop_condition", state=state, reason="finish", tool=tool_name, args=args)
                break

            if not isinstance(args, dict):
                self._record_failure(state, tool_name, {}, raw, "args must be an object", thought=thought)
                if self._should_stop_after_failure(state):
                    break
                continue

            repeated, fingerprint, repeated_count = repetition_detector.observe(tool_name, args)
            state.last_action_key = fingerprint.key
            state.repeated_action_count = repeated_count
            if repeated:
                state.status = "failed"
                state.failure_reason = f"repeated action detected: {tool_name}"
                state.updated_at = time.time()
                log.warn(
                    "Autonomous loop stopped for repetition",
                    tool=tool_name,
                    args=args,
                    fingerprint=fingerprint.key,
                )
                self._emit(
                    "stop_condition",
                    state=state,
                    reason="repetition",
                    tool=tool_name,
                    args=args,
                    fingerprint=fingerprint.key,
                )
                break

            if self.allowed_tools is not None and tool_name not in self.allowed_tools:
                self._record_failure(
                    state,
                    tool_name,
                    args,
                    "",
                    f"tool_not_allowed: {tool_name}",
                    thought=thought,
                )
                if self._should_stop_after_failure(state):
                    break
                continue

            tool = get_tool(tool_name, structured=True)
            log.info("Autonomous decision", step=state.step, thought=thought, tool=tool_name, args=args)
            if not isinstance(tool, Tool):
                self._record_failure(state, tool_name, args, "", f"invalid_tool: {tool_name}", thought=thought)
                if self._should_stop_after_failure(state):
                    break
                continue

            started = time.time()
            try:
                log.run("Tool call started", tool=tool_name, args=args)
                self._emit("before_tool", state=state, thought=thought, tool=tool_name, args=args)
                result = self._execute_tool(tool, args)
                elapsed = time.time() - started
                observation = self._record_observation(
                    state, thought, tool_name, args, result, result.success, elapsed=elapsed
                )
                self._emit(
                    "after_tool",
                    state=state,
                    thought=thought,
                    tool=tool_name,
                    args=args,
                    result=result,
                    observation=observation,
                    elapsed=round(elapsed, 3),
                )
                if result.success:
                    state.consecutive_failures = 0
                    log.info("Tool call completed", tool=tool_name, elapsed=round(elapsed, 3))
                else:
                    state.consecutive_failures += 1
                    self._emit(
                        "failure",
                        state=state,
                        tool=tool_name,
                        args=args,
                        error=result.error or "tool returned failure",
                        observation=observation,
                    )
                    log.warn("Tool returned failure", tool=tool_name, result=result.brief(500))
                    if self._should_stop_after_failure(state):
                        break
            except Exception as e:
                elapsed = time.time() - started
                observation = self._record_failure(
                    state, tool_name, args, "", str(e), thought=thought, elapsed=elapsed
                )
                self._emit(
                    "after_tool",
                    state=state,
                    thought=thought,
                    tool=tool_name,
                    args=args,
                    result=observation.result,
                    observation=observation,
                    elapsed=round(elapsed, 3),
                )
                if self._should_stop_after_failure(state):
                    break

            # Opt-in: persist after each completed step for crash recovery.
            self._save_checkpoint(state)

        if state.status == "running":
            state.status = "failed"
            state.failure_reason = "max_steps_reached"
            state.updated_at = time.time()
            log.warn("Autonomous loop reached max steps", steps=state.step)
            self._emit("stop_condition", state=state, reason="max_steps_reached")

        # Opt-in: persist the terminal state.
        self._save_checkpoint(state)
        return state

    def run(self, task: str) -> str:
        state = self.execute(task)
        if state.status == "completed":
            return state.final_answer
        return state.failure_reason or "autonomous loop failed"

    def _decide(self, state: ExecutionState) -> str:
        messages = self._build_messages(state)
        if self.decision_fn:
            return self.decision_fn(messages)

        import llm_client
        response = llm_client.safe_chat(model=self.model_name, messages=messages)
        return llm_client.get_response(response)

    def _build_messages(self, state: ExecutionState) -> list[dict]:
        tools = list_tools()
        if self.allowed_tools is not None:
            tools = [tool for tool in tools if tool["name"] in self.allowed_tools]
        system = build_system_prompt(
            tools,
            agent_name=self.agent_name,
            agent_context=self.system_context,
        )
        user = build_user_prompt(
            state.task,
            state.step,
            self.summarizer.summarize_many(state.observations),
        )
        return [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

    def _execute_tool(self, tool: Tool, args: dict) -> ToolResult:
        executor = ThreadPoolExecutor(max_workers=1)
        future = executor.submit(tool.execute_structured, args)
        try:
            return future.result(timeout=self.tool_timeout)
        except FutureTimeout:
            future.cancel()
            raise TimeoutError(f"tool '{tool.name}' timed out after {self.tool_timeout}s")
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

    def _emit(self, event_type: str, **payload) -> None:
        if not self.event_handler:
            return
        try:
            self.event_handler(event_type, payload)
        except Exception as exc:
            log.warn("Autonomous event handler failed", event=event_type, error=str(exc))

    def _get_checkpoint_store(self):
        if self._checkpoint_store is None:
            # Lazy import avoids a circular import with autonomous_checkpoint.
            from autonomous_checkpoint import AutonomousCheckpointStore
            self._checkpoint_store = AutonomousCheckpointStore()
        return self._checkpoint_store

    def _save_checkpoint(self, state: ExecutionState) -> None:
        if not self.enable_checkpoints:
            return
        try:
            self._get_checkpoint_store().save(state, self.checkpoint_id)
        except Exception as exc:
            log.warn("Autonomous checkpoint save failed", id=self.checkpoint_id, error=str(exc))

    def _record_observation(
        self,
        state: ExecutionState,
        thought: str,
        tool: str,
        args: dict,
        result: ToolResult,
        success: bool,
        error: str = "",
        elapsed: float = 0.0,
    ) -> Observation:
        preview = self.summarizer.summarize(
            Observation(
                step=state.step,
                thought=thought,
                tool=tool,
                args=args,
                result=result,
                success=success,
                error=error,
                elapsed=round(elapsed, 3),
            )
        )["summary"]
        observation = Observation(
            step=state.step,
            thought=thought,
            tool=tool,
            args=args,
            result=result,
            success=success,
            error=error,
            elapsed=round(elapsed, 3),
            summary=preview,
        )
        state.observations.append(observation)
        state.updated_at = time.time()
        self._emit("observation_recorded", state=state, observation=observation)
        return observation

    def _record_failure(
        self,
        state: ExecutionState,
        tool: str,
        args: dict,
        result: str | ToolResult,
        error: str,
        thought: str = "",
        elapsed: float = 0.0,
    ) -> Observation:
        state.consecutive_failures += 1
        result_obj = ToolResult.from_value(result)
        result_obj.success = False
        if error and not result_obj.error:
            result_obj.error = error
        observation = self._record_observation(
            state, thought, tool, args, result_obj, False, error=error, elapsed=elapsed
        )
        self._emit("failure", state=state, tool=tool, args=args, error=error, observation=observation)
        log.warn(
            "Autonomous step failed",
            step=state.step,
            tool=tool,
            error=error,
            consecutive_failures=state.consecutive_failures,
        )
        return observation

    def _should_stop_after_failure(self, state: ExecutionState) -> bool:
        if state.consecutive_failures <= self.max_retries:
            log.info(
                "Autonomous loop retrying",
                consecutive_failures=state.consecutive_failures,
                max_retries=self.max_retries,
            )
            self._emit("retry", state=state, consecutive_failures=state.consecutive_failures)
            return False
        state.status = "failed"
        state.failure_reason = state.observations[-1].error or "retry_limit_exceeded"
        state.updated_at = time.time()
        log.error("Autonomous retry limit exceeded", reason=state.failure_reason)
        self._emit("stop_condition", state=state, reason=state.failure_reason)
        return True

def parse_action(raw: str | dict) -> tuple[dict, str]:
    """Parse a model action, recovering fenced or surrounded JSON objects."""
    if isinstance(raw, dict):
        data = raw
    else:
        text = str(raw or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            if "\n" in text:
                text = text.split("\n", 1)[1]
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start >= 0 and end > start:
                try:
                    data = json.loads(text[start:end + 1])
                except json.JSONDecodeError as e:
                    return {}, str(e)
            else:
                return {}, "no JSON object found"
        except Exception as e:
            return {}, str(e)

    if not isinstance(data, dict):
        return {}, "action must be a JSON object"
    if "tool" not in data:
        answer = data.get("final") or data.get("answer")
        if answer:
            data = {"thought": str(answer), "tool": "finish", "args": {"answer": str(answer)}}
        else:
            return {}, "missing tool"
    if "args" not in data or data["args"] is None:
        data["args"] = {}
    return data, ""
