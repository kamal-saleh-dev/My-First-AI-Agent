import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import AgentResult
from agents.orchestration import (
    ExecutionPlan,
    ExecutionStep,
    SequentialExecutionStrategy,
)

class FakeManager:
    """Minimal stand-in matching the manager surface the strategy calls."""

    def __init__(self, failing=None):
        self.failing = set(failing or ())
        self.calls = []

    def delegated_task_for(self, agent_name, task, previous_results):
        return task

    def delegate_task(self, agent_name, task, *, context=None, correlation_id="", decision_fn=None):
        self.calls.append(agent_name)
        status = "failed" if agent_name in self.failing else "completed"
        return AgentResult(
            agent_name=agent_name,
            task=task,
            status=status,
            final_answer="" if status == "failed" else "ok",
            error="boom" if status == "failed" else "",
        )

def _plan(workflow):
    return ExecutionPlan.from_workflow(
        "ship it",
        workflow,
        context={},
        correlation_id="orchestration-test",
        metadata={},
    )

def test_plan_from_workflow_shape():
    workflow = ("PlannerAgent", "CodingAgent", "TestingAgent")
    plan = _plan(workflow)
    assert plan.workflow == list(workflow)
    assert len(plan.steps) == 3
    assert isinstance(plan.to_dict(), dict)

def test_execution_step_serializes():
    step = ExecutionStep(agent_name="PlannerAgent", task="plan")
    data = step.to_dict()
    assert data["agent_name"] == "PlannerAgent"
    assert isinstance(data["depends_on"], list)

def test_sequential_strategy_runs_all_steps():
    workflow = ("PlannerAgent", "CodingAgent")
    plan = _plan(workflow)
    manager = FakeManager()
    outcome = SequentialExecutionStrategy().execute(manager, plan, decision_fns={})
    assert outcome["status"] == "completed"
    assert outcome["failed_step"] is None
    assert manager.calls == list(workflow)

def test_sequential_strategy_halts_on_failure():
    workflow = ("PlannerAgent", "CodingAgent", "TestingAgent")
    plan = _plan(workflow)
    manager = FakeManager(failing={"CodingAgent"})
    outcome = SequentialExecutionStrategy().execute(manager, plan, decision_fns={})
    assert outcome["status"] == "failed"
    assert outcome["failed_step"] is not None
    assert outcome["failed_step"]["agent_name"] == "CodingAgent"
    assert "TestingAgent" not in manager.calls

def test_strategy_name_is_sequential():
    assert SequentialExecutionStrategy().name == "sequential"
