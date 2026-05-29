import json
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents import AgentResult
from agents.agent_manager import AgentManager

def _finish(messages):
    return json.dumps({"thought": "done", "tool": "finish", "args": {"answer": "done"}})

def _manager():
    return AgentManager()

def test_agent_run_returns_result():
    agent = _manager().get_agent("PlannerAgent")
    result = agent.run("draft a plan", decision_fn=_finish)
    assert isinstance(result, AgentResult)
    assert result.status == "completed"
    assert result.agent_name == "PlannerAgent"
    assert result.final_answer == "done"

def test_restricted_tool_is_denied():
    reviewer = _manager().get_agent("ReviewerAgent")
    assert reviewer.can_use_tool("read_file") is True
    assert reviewer.can_use_tool("write_file") is False
    with pytest.raises(PermissionError):
        reviewer.execute_tool("write_file", {"path": "x.py", "content": "y"})

def test_effective_allowed_tools_excludes_restricted():
    planner = _manager().get_agent("PlannerAgent")
    assert "write_file" not in planner.effective_allowed_tools
    assert "edit_file" not in planner.effective_allowed_tools
    assert "search_files" in planner.effective_allowed_tools

def test_agents_have_isolated_state():
    manager = _manager()
    planner = manager.get_agent("PlannerAgent")
    coder = manager.get_agent("CodingAgent")
    assert planner.state is not coder.state
    assert planner.name != coder.name

def test_result_is_serializable():
    agent = _manager().get_agent("TestingAgent")
    result = agent.run("run the suite", decision_fn=_finish)
    data = result.to_dict()
    assert data["agent_name"] == "TestingAgent"
    assert data["status"] == "completed"
