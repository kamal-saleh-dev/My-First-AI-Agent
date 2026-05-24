"""Shared coordination state for collaborative agents."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from threading import RLock


@dataclass
class SharedTask:
    task_id: str
    description: str
    assigned_to: str = ""
    status: str = "pending"
    correlation_id: str = ""
    metadata: dict = field(default_factory=dict)
    result: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "task_id": self.task_id,
            "description": self.description,
            "assigned_to": self.assigned_to,
            "status": self.status,
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata),
            "result": dict(self.result),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }


class SharedExecutionContext:
    """Thread-safe global coordination state.

    Agent-local memory stays inside each agent. Only explicit shared goals,
    tasks, metadata, state, and shared memory entries live here.
    """

    def __init__(self):
        self._lock = RLock()
        self.shared_goals: list[str] = []
        self.execution_metadata: dict = {}
        self.active_tasks: dict[str, SharedTask] = {}
        self.global_state: dict = {"status": "idle"}
        self.shared_memory: list[dict] = []

    def add_goal(self, goal: str) -> None:
        with self._lock:
            self.shared_goals.append(goal)

    def set_metadata(self, key: str, value) -> None:
        with self._lock:
            self.execution_metadata[key] = value

    def get_metadata(self, key: str, default=None):
        with self._lock:
            return self.execution_metadata.get(key, default)

    def create_task(
        self,
        description: str,
        assigned_to: str = "",
        correlation_id: str = "",
        metadata: dict | None = None,
    ) -> SharedTask:
        with self._lock:
            task = SharedTask(
                task_id=str(uuid.uuid4()),
                description=description,
                assigned_to=assigned_to,
                correlation_id=correlation_id or str(uuid.uuid4()),
                metadata=dict(metadata or {}),
            )
            self.active_tasks[task.task_id] = task
            self.global_state["status"] = "running"
            return task

    def update_task(self, task_id: str, status: str, result: dict | None = None) -> None:
        with self._lock:
            task = self.active_tasks[task_id]
            task.status = status
            if result is not None:
                task.result = dict(result)
            task.updated_at = time.time()
            if all(t.status in ("completed", "failed", "cancelled") for t in self.active_tasks.values()):
                self.global_state["status"] = "idle"

    def get_task(self, task_id: str) -> SharedTask | None:
        with self._lock:
            return self.active_tasks.get(task_id)

    def list_tasks(self) -> list[dict]:
        with self._lock:
            return [task.to_dict() for task in self.active_tasks.values()]

    def share_memory(self, entry: dict) -> None:
        with self._lock:
            self.shared_memory.append({"ts": time.time(), **dict(entry)})

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "shared_goals": list(self.shared_goals),
                "execution_metadata": dict(self.execution_metadata),
                "active_tasks": [task.to_dict() for task in self.active_tasks.values()],
                "global_state": dict(self.global_state),
                "shared_memory": list(self.shared_memory),
            }
