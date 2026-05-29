import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import AgentResult
from agents.agent_manager import AgentManager
from agents.message_bus import MessageBus
from agents.shared_execution_context import SharedExecutionContext

def _finish(messages):
    return json.dumps({"thought": "done", "tool": "finish", "args": {"answer": "done"}})

def test_default_registration():
    manager = AgentManager()
    assert len(manager.list_agents()) == 6

def test_accepts_shared_collaborators_as_keywords():
    ctx = SharedExecutionContext()
    bus = MessageBus()
    manager = AgentManager(shared_context=ctx, message_bus=bus)
    assert manager.shared_context is ctx
    assert manager.message_bus is bus

def test_delegate_runs_agent():
    manager = AgentManager()
    result = manager.delegate_task("PlannerAgent", "plan the work", decision_fn=_finish)
    assert isinstance(result, AgentResult)
    assert result.status == "completed"
    assert result.final_answer == "done"

def test_unregister_removes_agent():
    manager = AgentManager()
    manager.unregister_agent("ContextAgent")
    with pytest.raises(KeyError):
        manager.get_agent("ContextAgent")

def test_stopped_agent_rejects_delegation():
    manager = AgentManager()
    manager.stop_agent("PlannerAgent")
    result = manager.delegate_task("PlannerAgent", "plan", decision_fn=_finish)
    assert result.status == "failed"
    assert result.error == "agent_stopped"

def test_orchestrate_sequential_workflow():
    manager = AgentManager()
    workflow = ("PlannerAgent", "CodingAgent")
    decision_fns = {name: _finish for name in workflow}
    outcome = manager.orchestrate("build feature", workflow=workflow, decision_fns=decision_fns)
    assert outcome["status"] == "completed"
    assert [r["status"] for r in outcome["results"]] == ["completed", "completed"]
