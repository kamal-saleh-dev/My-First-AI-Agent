"""Lifecycle, delegation, and orchestration for collaborative agents."""

from __future__ import annotations

import time
import uuid
from typing import Callable

from logger import log

from .base_agent import AgentResult, BaseAgent
from .message_bus import MessageBus
from .orchestration import ExecutionPlan, ExecutionStrategy, SequentialExecutionStrategy
from .shared_execution_context import SharedExecutionContext
from .specialized_agents import DEFAULT_AGENT_CLASSES


class AgentManager:
    """Register agents, delegate tasks, and supervise execution."""

    def __init__(
        self,
        *,
        shared_context: SharedExecutionContext | None = None,
        message_bus: MessageBus | None = None,
        register_defaults: bool = True,
    ):
        self.shared_context = shared_context or SharedExecutionContext()
        self.message_bus = message_bus or MessageBus()
        self.default_strategy: ExecutionStrategy = SequentialExecutionStrategy()
        self._agents: dict[str, BaseAgent] = {}
        self._lifecycle: dict[str, dict] = {}
        if register_defaults:
            self.register_default_agents()

    def register_default_agents(self) -> None:
        for agent_cls in DEFAULT_AGENT_CLASSES:
            self.register_agent(agent_cls(shared_context=self.shared_context, message_bus=self.message_bus))

    def register_agent(self, agent: BaseAgent) -> BaseAgent:
        if not isinstance(agent, BaseAgent):
            raise TypeError("register_agent expects a BaseAgent")
        agent.shared_context = self.shared_context
        agent.message_bus = self.message_bus
        self._agents[agent.name] = agent
        self._lifecycle[agent.name] = {
            "status": "ready",
            "registered_at": time.time(),
            "last_error": "",
        }
        log.info("Agent registered", agent=agent.name, role=agent.role)
        return agent

    def unregister_agent(self, agent_name: str) -> None:
        self._agents.pop(agent_name, None)
        self._lifecycle.pop(agent_name, None)
        log.info("Agent unregistered", agent=agent_name)

    def start_agent(self, agent_name: str) -> None:
        self._require_agent(agent_name)
        self._lifecycle[agent_name]["status"] = "ready"

    def stop_agent(self, agent_name: str) -> None:
        self._require_agent(agent_name)
        self._lifecycle[agent_name]["status"] = "stopped"

    def get_agent(self, agent_name: str) -> BaseAgent:
        return self._require_agent(agent_name)

    def list_agents(self) -> list[dict]:
        return [
            {
                "name": agent.name,
                "role": agent.role,
                "preferred_model": agent.preferred_model,
                "allowed_tools": list(agent.effective_allowed_tools),
                "policy": {
                    "max_steps": agent.policy.max_steps,
                    "max_retries": agent.policy.max_retries,
                    "tool_timeout": agent.policy.tool_timeout,
                    "repeat_limit": agent.policy.repeat_limit,
                },
                "lifecycle": dict(self._lifecycle.get(agent.name, {})),
            }
            for agent in self._agents.values()
        ]

    def agent_capabilities(self) -> dict[str, list[str]]:
        return {name: list(agent.effective_allowed_tools) for name, agent in self._agents.items()}

    def delegate_task(
        self,
        agent_name: str,
        task: str,
        *,
        context: dict | None = None,
        correlation_id: str = "",
        decision_fn: Callable[[list[dict]], str] | None = None,
    ) -> AgentResult:
        agent = self._require_agent(agent_name)
        lifecycle = self._lifecycle[agent_name]
        if lifecycle.get("status") == "stopped":
            return self._failed_result(agent_name, task, "agent_stopped")

        correlation_id = correlation_id or str(uuid.uuid4())
        context = dict(context or {})
        shared_task = self.shared_context.create_task(
            task,
            assigned_to=agent.name,
            correlation_id=correlation_id,
            metadata={"delegated_by": "AgentManager", "agent": agent.name, **context},
        )
        self.message_bus.send(
            "AgentManager",
            agent.name,
            task,
            context=context,
            correlation_id=correlation_id,
            metadata={"task_id": shared_task.task_id},
        )
        lifecycle["status"] = "running"

        try:
            result = agent.run(
                task,
                context=context,
                correlation_id=correlation_id,
                task_id=shared_task.task_id,
                decision_fn=decision_fn,
            )
            lifecycle["status"] = "ready"
            lifecycle["last_error"] = result.error
            return result
        except Exception as exc:
            error = str(exc)
            lifecycle["status"] = "failed"
            lifecycle["last_error"] = error
            self.shared_context.update_task(
                shared_task.task_id,
                "failed",
                {"agent_name": agent.name, "task": task, "status": "failed", "error": error},
            )
            log.error("Agent delegation failed", agent=agent.name, task=task, error=error)
            return self._failed_result(agent.name, task, error, task_id=shared_task.task_id)

    def orchestrate(
        self,
        task: str,
        *,
        workflow: list[str] | tuple[str, ...] | None = None,
        execution_plan: ExecutionPlan | None = None,
        strategy: ExecutionStrategy | None = None,
        context: dict | None = None,
        decision_fns: dict[str, Callable[[list[dict]], str]] | None = None,
        correlation_id: str = "",
    ) -> dict:
        workflow = list(workflow or ("PlannerAgent", "CodingAgent", "TestingAgent", "ReviewerAgent"))
        decision_fns = dict(decision_fns or {})
        plan = execution_plan or ExecutionPlan.from_workflow(
            task,
            workflow,
            context=context,
            correlation_id=correlation_id,
        )
        if execution_plan is not None and context:
            plan.context.update(dict(context))
        correlation_id = plan.correlation_id

        self.shared_context.add_goal(plan.task)
        self.shared_context.set_metadata("last_orchestration_id", correlation_id)
        self.shared_context.set_metadata("last_execution_strategy", (strategy or self.default_strategy).name)
        self.shared_context.global_state["status"] = "running"
        selected_strategy = strategy or self.default_strategy
        log.info(
            "Agent orchestration started",
            correlation_id=correlation_id,
            workflow=plan.workflow,
            strategy=selected_strategy.name,
        )

        strategy_result = selected_strategy.execute(self, plan, decision_fns=decision_fns)
        self.shared_context.global_state["status"] = strategy_result["status"]
        failed_step = strategy_result.get("failed_step")
        if failed_step:
            log.warn(
                "Agent orchestration stopped after failure",
                agent=failed_step.get("agent_name"),
                step_id=failed_step.get("step_id"),
            )

        return {
            "correlation_id": correlation_id,
            "task": plan.task,
            "workflow": plan.workflow,
            "strategy": selected_strategy.name,
            "execution_plan": plan.to_dict(),
            "status": self.shared_context.global_state.get("status"),
            "results": strategy_result["results"],
            "context": self.shared_context.snapshot(),
        }

    def lifecycle_snapshot(self) -> dict[str, dict]:
        return {name: dict(state) for name, state in self._lifecycle.items()}

    def _require_agent(self, agent_name: str) -> BaseAgent:
        try:
            return self._agents[agent_name]
        except KeyError as exc:
            raise KeyError(f"unknown agent: {agent_name}") from exc

    def _failed_result(
        self,
        agent_name: str,
        task: str,
        error: str,
        *,
        task_id: str = "",
    ) -> AgentResult:
        return AgentResult(
            agent_name=agent_name,
            task=task,
            status="failed",
            error=error,
            metadata={"task_id": task_id},
        )

    def delegated_task_for(self, agent_name: str, task: str, previous_results: list[dict]) -> str:
        if not previous_results:
            return task
        return f"{task}\n\nContinue from previous agent results."

    def _delegated_task_for(self, agent_name: str, task: str, previous_results: list[dict]) -> str:
        return self.delegated_task_for(agent_name, task, previous_results)
