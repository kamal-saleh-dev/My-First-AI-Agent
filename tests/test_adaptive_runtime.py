"""Integration tests for the opt-in AdaptiveRuntime (deterministic, no network)."""

import os

import pytest

from adaptive_runtime import AdaptiveRuntime, run_adaptive
from agent_memory import AgentMemoryBridge
from memory_store import MemoryStore
from reflection_engine import ReflectionEngine

def _finish(_messages):
    return '{"thought": "done", "tool": "finish", "args": {"answer": "ok"}}'

def _fail(_messages):
    return "this is deliberately not valid json"

def _memory(tmp_path):
    store = MemoryStore(path=os.path.join(str(tmp_path), "mem.json"))
    return AgentMemoryBridge(store=store, enabled=True)

def _quiet(*_args, **_kwargs):
    return None

def test_all_steps_succeed(tmp_path):
    runtime = AdaptiveRuntime(
        workflow=("PlannerAgent", "CodingAgent"),
        memory=_memory(tmp_path),
        emit=_quiet,
    )
    result = runtime.run(
        "build a small feature",
        decision_fns={"PlannerAgent": _finish, "CodingAgent": _finish},
    )
    assert result.completed is True
    assert len(result.steps) == 2
    assert all(step["status"] == "completed" for step in result.steps)

def test_empty_task_raises(tmp_path):
    runtime = AdaptiveRuntime(memory=_memory(tmp_path), emit=_quiet)
    with pytest.raises(ValueError):
        runtime.run("   ")

def test_failure_stops_workflow(tmp_path):
    runtime = AdaptiveRuntime(
        workflow=("PlannerAgent", "CodingAgent"),
        reflection=ReflectionEngine(total_steps=2, can_debug=False),
        memory=_memory(tmp_path),
        emit=_quiet,
    )
    result = runtime.run(
        "do something",
        decision_fns={"PlannerAgent": _fail, "CodingAgent": _finish},
    )
    assert result.status == "failed"
    assert len(result.steps) == 1
    assert result.steps[0]["agent"] == "PlannerAgent"

def test_model_escalation_recorded(tmp_path):
    runtime = AdaptiveRuntime(
        workflow=("CodingAgent",),
        reflection=ReflectionEngine(total_steps=1, can_debug=False),
        memory=_memory(tmp_path),
        emit=_quiet,
    )
    result = runtime.run("implement", decision_fns={"CodingAgent": _fail})
    decisions = [e.get("decision") for e in result.events if e.get("type") == "reflection"]
    assert "switch_model" in decisions

def test_failure_triggers_debug_delegation(tmp_path):
    runtime = AdaptiveRuntime(
        workflow=("TestingAgent",),
        memory=_memory(tmp_path),
        emit=_quiet,
    )
    result = runtime.run(
        "run the tests",
        decision_fns={"TestingAgent": _fail, "DebuggerAgent": _fail},
    )
    assert result.status == "failed"
    assert result.recovered is True
    assert any(e.get("type") == "debug_delegation" for e in result.events)

def test_run_adaptive_helper(monkeypatch):
    import config as cfg
    monkeypatch.setattr(cfg, "ADAPTIVE_MEMORY_ENABLED", False)
    result = run_adaptive(
        "quick task",
        workflow=("PlannerAgent",),
        emit=_quiet,
        decision_fns={"PlannerAgent": _finish},
    )
    assert result.completed is True
