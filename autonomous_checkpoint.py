"""Opt-in persistence for autonomous ExecutionState.

This module is intentionally self-contained: it does not import or depend on
recovery.py. It serializes ExecutionState (including its Observations and the
nested ToolResult values) to JSON and restores it for resume.

Persistence is opt-in. AutonomousExecutor only calls into this module when
enable_checkpoints=True, so default loop behavior is unchanged. Restoring a
checkpoint reinstates prior state only; it does not replan.
"""

from __future__ import annotations

import json
import os
import time
from typing import Optional

from autonomous_loop import ExecutionState, Observation
from tool_registry import ToolResult

DEFAULT_CHECKPOINT_ROOT = os.path.join(".checkpoints", "autonomous")

_STATE_FIELDS = (
    "task",
    "status",
    "step",
    "final_answer",
    "failure_reason",
    "consecutive_failures",
    "last_action_key",
    "repeated_action_count",
    "started_at",
    "updated_at",
)

_OBSERVATION_FIELDS = (
    "step",
    "thought",
    "tool",
    "args",
    "success",
    "error",
    "elapsed",
    "summary",
)

def _safe_id(checkpoint_id: str) -> str:
    allowed = ("-", "_", ".")
    cleaned = "".join(
        ch if ch.isalnum() or ch in allowed else "_" for ch in str(checkpoint_id).strip()
    )
    return cleaned or "default"

def serialize_tool_result(result: ToolResult) -> dict:
    return {
        "success": bool(getattr(result, "success", False)),
        "data": getattr(result, "data", None),
        "error": getattr(result, "error", "") or "",
    }

def deserialize_tool_result(data: Optional[dict]) -> ToolResult:
    data = data or {}
    return ToolResult(
        success=bool(data.get("success", False)),
        data=data.get("data"),
        error=data.get("error", "") or "",
    )

def serialize_observation(obs: Observation) -> dict:
    return {
        "step": obs.step,
        "thought": obs.thought,
        "tool": obs.tool,
        "args": obs.args,
        "result": serialize_tool_result(obs.result),
        "success": obs.success,
        "error": obs.error,
        "elapsed": obs.elapsed,
        "summary": obs.summary,
    }

def deserialize_observation(data: dict) -> Observation:
    fields = {key: data[key] for key in _OBSERVATION_FIELDS if key in data}
    fields.setdefault("step", 0)
    fields.setdefault("thought", "")
    fields.setdefault("tool", "")
    fields.setdefault("args", {})
    fields.setdefault("success", False)
    fields.setdefault("error", "")
    fields.setdefault("elapsed", 0.0)
    fields.setdefault("summary", "")
    return Observation(result=deserialize_tool_result(data.get("result")), **fields)

def serialize_state(state: ExecutionState) -> dict:
    return {
        "task": state.task,
        "status": state.status,
        "step": state.step,
        "final_answer": state.final_answer,
        "failure_reason": state.failure_reason,
        "consecutive_failures": state.consecutive_failures,
        "last_action_key": state.last_action_key,
        "repeated_action_count": state.repeated_action_count,
        "started_at": state.started_at,
        "updated_at": state.updated_at,
        "observations": [serialize_observation(obs) for obs in state.observations],
        "saved_at": time.time(),
        "version": 1,
    }

def deserialize_state(data: dict) -> ExecutionState:
    fields = {key: data[key] for key in _STATE_FIELDS if key in data}
    state = ExecutionState(**fields)
    state.observations = [
        deserialize_observation(obs) for obs in data.get("observations", [])
    ]
    return state

class AutonomousCheckpointStore:
    """JSON-backed store for autonomous ExecutionState snapshots."""

    def __init__(self, root: str = DEFAULT_CHECKPOINT_ROOT):
        self.root = root

    def _ensure_root(self) -> None:
        os.makedirs(self.root, exist_ok=True)

    def path_for(self, checkpoint_id: str) -> str:
        return os.path.join(self.root, f"{_safe_id(checkpoint_id)}.json")

    def save(self, state: ExecutionState, checkpoint_id: str) -> str:
        self._ensure_root()
        path = self.path_for(checkpoint_id)
        payload = serialize_state(state)
        tmp_path = f"{path}.tmp"
        with open(tmp_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        os.replace(tmp_path, path)
        return path

    def load(self, checkpoint_id: str) -> Optional[ExecutionState]:
        path = self.path_for(checkpoint_id)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return deserialize_state(data)

    def exists(self, checkpoint_id: str) -> bool:
        return os.path.exists(self.path_for(checkpoint_id))

    def delete(self, checkpoint_id: str) -> bool:
        path = self.path_for(checkpoint_id)
        if os.path.exists(path):
            os.remove(path)
            return True
        return False

    def list_ids(self) -> list[str]:
        if not os.path.isdir(self.root):
            return []
        ids = []
        for name in sorted(os.listdir(self.root)):
            if name.endswith(".json"):
                ids.append(name[: -len(".json")])
        return ids
