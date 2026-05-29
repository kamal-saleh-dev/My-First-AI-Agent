import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from multi_agent_runtime import (
    DEFAULT_MULTI_AGENT_WORKFLOW,
    MultiAgentRuntime,
    run_multi_agent,
)

def _finish(messages):
    return json.dumps({"thought": "done", "tool": "finish", "args": {"answer": "done"}})

def _decision_fns(workflow):
    return {name: _finish for name in workflow}

def _silent(_message):
    pass

def test_runtime_reuses_existing_agents_and_completes():
    runtime = MultiAgentRuntime(emit=_silent)
    assert runtime.workflow == DEFAULT_MULTI_AGENT_WORKFLOW
    result = runtime.run("demo runtime task", decision_fns=_decision_fns(runtime.workflow))
    assert result.status == "completed"
    assert result.completed is True
    assert [r["status"] for r in result.results] == ["completed"] * len(runtime.workflow)
    assert [r["agent_name"] for r in result.results] == list(runtime.workflow)

def test_runtime_emits_visibility_events():
    captured = []
    runtime = MultiAgentRuntime(emit=captured.append)
    result = runtime.run("visible task", decision_fns=_decision_fns(runtime.workflow))

    delegated = [e for e in result.events if e["type"] == "delegated"]
    step_results = [e for e in result.events if e["type"] == "step_result"]
    statuses = [e for e in result.events if e["type"] == "orchestration_status"]

    # active agent + delegated task visibility, one per workflow step
    assert [e["agent"] for e in delegated] == list(runtime.workflow)
    assert all(e["task"] for e in delegated)
    # step result visibility, one per workflow step
    assert [e["agent"] for e in step_results] == list(runtime.workflow)
    assert all(e["status"] == "completed" for e in step_results)
    # orchestration status visibility
    assert len(statuses) == 1
    assert statuses[0]["status"] == "completed"
    # something was actually printed to the emit sink
    assert any("orchestration status" in line for line in captured)

def test_runtime_shares_one_bus_and_context_with_manager():
    runtime = MultiAgentRuntime(emit=_silent)
    assert runtime.manager.message_bus is runtime.message_bus
    assert runtime.manager.shared_context is runtime.shared_context

def test_runtime_unsubscribes_observer_after_run():
    runtime = MultiAgentRuntime(emit=_silent)
    before = len(runtime.message_bus.events())
    runtime.run("cleanup task", decision_fns=_decision_fns(runtime.workflow))
    snapshot = len(runtime.events)
    # the observer must not linger after the run completes
    runtime.message_bus.send("PlannerAgent", "CodingAgent", "late message")
    assert len(runtime.events) == snapshot
    assert len(runtime.message_bus.events()) > before

def test_run_multi_agent_helper_runs_workflow():
    result = run_multi_agent(
        "helper task",
        emit=_silent,
        decision_fns=_decision_fns(DEFAULT_MULTI_AGENT_WORKFLOW),
    )
    assert result.status == "completed"
    assert result.task == "helper task"

def test_empty_task_is_rejected():
    runtime = MultiAgentRuntime(emit=_silent)
    try:
        runtime.run("   ")
    except ValueError as exc:
        assert "non-empty" in str(exc)
    else:  # pragma: no cover - explicit failure if no error raised
        raise AssertionError("expected ValueError for empty task")

def test_auto_command_routing_is_unchanged():
    import tool_registry

    assert tool_registry.TOOL_REGISTRY["AUTO"] is tool_registry._tool_auto
    assert "AUTO" in tool_registry.BACKGROUND_TOOLS
    # new opt-in entry point is registered alongside, without touching /auto
    assert tool_registry.TOOL_REGISTRY["MULTI"] is tool_registry._tool_multi
    assert "MULTI" in tool_registry.BACKGROUND_TOOLS
    assert tool_registry.get_tool("MULTI") is tool_registry._tool_multi

def test_multi_and_auto_modes_are_distinct():
    from model_router import detect_mode

    assert detect_mode("/auto build a parser")[0] == "AUTO"
    assert detect_mode("/multi build a parser")[0] == "MULTI"
    assert detect_mode("/multiagent build a parser")[0] == "MULTI"
