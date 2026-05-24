"""Execution plan and strategy abstractions for agent orchestration."""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass, field
from typing import Callable


@dataclass
class ExecutionStep:
    """One schedulable unit in an execution plan."""

    agent_name: str
    task: str = ""
    step_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    context: dict = field(default_factory=dict)
    depends_on: tuple[str, ...] = ()
    metadata: dict = field(default_factory=dict)
    retry_policy: dict = field(default_factory=dict)
    timing: dict = field(default_factory=dict)
    dependency_metadata: dict = field(default_factory=dict)
    scheduling: dict = field(default_factory=dict)
    failure_metadata: dict = field(default_factory=dict)
    priority: int = 0
    status: str = "pending"
    result: dict = field(default_factory=dict)

    def __post_init__(self):
        metadata = dict(self.metadata)
        metadata.setdefault("retry_policy", dict(self.retry_policy))
        metadata.setdefault("timing", dict(self.timing))
        metadata.setdefault("dependency_metadata", dict(self.dependency_metadata))
        metadata.setdefault("scheduling", dict(self.scheduling))
        metadata.setdefault("failure_metadata", dict(self.failure_metadata))
        metadata.setdefault("priority", self.priority)
        self.metadata = metadata

    def sync_metadata(self) -> None:
        self.metadata["retry_policy"] = dict(self.retry_policy)
        self.metadata["timing"] = dict(self.timing)
        self.metadata["dependency_metadata"] = dict(self.dependency_metadata)
        self.metadata["scheduling"] = dict(self.scheduling)
        self.metadata["failure_metadata"] = dict(self.failure_metadata)
        self.metadata["priority"] = self.priority

    def to_dict(self) -> dict:
        self.sync_metadata()
        data = asdict(self)
        data["depends_on"] = list(self.depends_on)
        return data


@dataclass
class ExecutionPlan:
    """A task-level plan composed of execution steps."""

    task: str
    steps: list[ExecutionStep]
    context: dict = field(default_factory=dict)
    correlation_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    @classmethod
    def from_workflow(
        cls,
        task: str,
        workflow: list[str] | tuple[str, ...],
        *,
        context: dict | None = None,
        correlation_id: str = "",
        metadata: dict | None = None,
    ) -> "ExecutionPlan":
        return cls(
            task=task,
            steps=[ExecutionStep(agent_name=agent_name) for agent_name in workflow],
            context=dict(context or {}),
            correlation_id=correlation_id or str(uuid.uuid4()),
            metadata=dict(metadata or {}),
        )

    @property
    def workflow(self) -> list[str]:
        return [step.agent_name for step in self.steps]

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "steps": [step.to_dict() for step in self.steps],
            "context": dict(self.context),
            "correlation_id": self.correlation_id,
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


class ExecutionStrategy(ABC):
    """Strategy interface for executing an ExecutionPlan."""

    name = "base"

    @abstractmethod
    def execute(
        self,
        manager,
        plan: ExecutionPlan,
        *,
        decision_fns: dict[str, Callable[[list[dict]], str]] | None = None,
    ) -> dict:
        raise NotImplementedError


class SequentialExecutionStrategy(ExecutionStrategy):
    """Current behavior: run plan steps one after another."""

    name = "sequential"

    def execute(
        self,
        manager,
        plan: ExecutionPlan,
        *,
        decision_fns: dict[str, Callable[[list[dict]], str]] | None = None,
    ) -> dict:
        decision_fns = dict(decision_fns or {})
        results: list[dict] = []
        shared_context = {"original_task": plan.task, **dict(plan.context)}

        for step in plan.steps:
            step.status = "running"
            started_at = time.time()
            step.timing["started_at"] = started_at
            step.sync_metadata()
            agent_task = step.task or manager.delegated_task_for(step.agent_name, plan.task, results)
            step_context = {**shared_context, **dict(step.context)}
            result = manager.delegate_task(
                step.agent_name,
                agent_task,
                context=step_context,
                correlation_id=plan.correlation_id,
                decision_fn=decision_fns.get(step.agent_name) or decision_fns.get(step.step_id),
            )
            result_dict = result.to_dict()
            step.result = result_dict
            step.status = "completed" if result.status == "completed" else "failed"
            completed_at = time.time()
            step.timing.update({
                "completed_at": completed_at,
                "elapsed": round(completed_at - started_at, 3),
            })
            if result.status != "completed":
                step.failure_metadata.update({"error": result.error, "agent_name": step.agent_name})
            step.sync_metadata()
            results.append(result_dict)
            shared_context["previous_results"] = list(results)
            if result.status != "completed":
                return {
                    "status": "failed",
                    "results": results,
                    "failed_step": step.to_dict(),
                    "shared_context": shared_context,
                }

        return {
            "status": "completed",
            "results": results,
            "failed_step": None,
            "shared_context": shared_context,
        }
