import json

import pytest

from agents import (
    AgentExecutionPolicy,
    AgentManager,
    CodingAgent,
    ContextAgent,
    MessageBus,
    PlannerAgent,
    ReviewerAgent,
    SharedExecutionContext,
)


def _finish(answer="done"):
    return lambda messages: json.dumps(
        {"thought": "task complete", "tool": "finish", "args": {"answer": answer}}
    )


def test_message_bus_passing_and_history():
    bus = MessageBus()
    message = bus.send(
        "PlannerAgent",
        "CodingAgent",
        "Implement inventory system",
        context={"files": ["inventory.py"]},
        correlation_id="task-123",
        metadata={"priority": "high"},
    )

    received = bus.receive("CodingAgent")
    assert received == [message]
    assert bus.receive("CodingAgent") == []

    history = bus.history(correlation_id="task-123")
    assert history[0]["from"] == "PlannerAgent"
    assert history[0]["to"] == "CodingAgent"
    assert history[0]["task"] == "Implement inventory system"
    assert history[0]["metadata"]["priority"] == "high"


def test_message_bus_accepts_structured_dict_messages():
    bus = MessageBus()
    bus.publish({
        "from": "ReviewerAgent",
        "to": "PlannerAgent",
        "task": "Review plan",
        "context": {"status": "ready"},
        "correlation_id": "review-1",
    })

    received = bus.receive("PlannerAgent")
    assert received[0].from_agent == "ReviewerAgent"
    assert received[0].context["status"] == "ready"


def test_shared_execution_context_coordination():
    context = SharedExecutionContext()
    context.add_goal("Ship Phase 2")
    task = context.create_task("Plan implementation", assigned_to="PlannerAgent", correlation_id="phase-2")
    context.update_task(task.task_id, "completed", {"summary": "planned"})
    context.share_memory({"source": "PlannerAgent", "summary": "Use modular agents"})

    snapshot = context.snapshot()
    assert snapshot["shared_goals"] == ["Ship Phase 2"]
    assert snapshot["active_tasks"][0]["status"] == "completed"
    assert snapshot["active_tasks"][0]["result"]["summary"] == "planned"
    assert snapshot["shared_memory"][0]["source"] == "PlannerAgent"
    assert snapshot["global_state"]["status"] == "idle"


def test_agent_state_and_memory_are_isolated():
    shared_context = SharedExecutionContext()
    bus = MessageBus()
    planner = PlannerAgent(shared_context=shared_context, message_bus=bus)
    coder = CodingAgent(shared_context=shared_context, message_bus=bus)

    planner.remember({"note": "planning only"})
    coder.remember({"note": "coding only"})
    planner.state.reasoning_context["private"] = "planner-context"

    assert planner.local_memory_snapshot()[0]["note"] == "planning only"
    assert coder.local_memory_snapshot()[0]["note"] == "coding only"
    assert planner.state.local_memory is not coder.state.local_memory
    assert "private" not in coder.state.reasoning_context


def test_default_agents_register_capability_boundaries():
    manager = AgentManager()
    capabilities = manager.agent_capabilities()

    assert set(capabilities) == {
        "PlannerAgent",
        "CodingAgent",
        "ReviewerAgent",
        "TestingAgent",
        "DebuggerAgent",
        "ContextAgent",
    }
    assert "write_file" not in capabilities["PlannerAgent"]
    assert "edit_file" not in capabilities["ReviewerAgent"]
    assert capabilities["CodingAgent"] == ["read_file", "write_file", "edit_file", "search_files"]
    assert "run_tests" in capabilities["TestingAgent"]
    assert "edit_file" in capabilities["DebuggerAgent"]
    assert "scan_project" in capabilities["ContextAgent"]

    agents = {item["name"]: item for item in manager.list_agents()}
    assert agents["PlannerAgent"]["lifecycle"]["status"] == "ready"
    assert agents["PlannerAgent"]["policy"]["max_steps"] > 0


def test_tool_permission_enforcement(tmp_path):
    planner = PlannerAgent()
    coder = CodingAgent()

    with pytest.raises(PermissionError):
        planner.execute_tool(
            "write_file",
            {"root": str(tmp_path), "path": "plan.txt", "content": "blocked"},
        )

    result = coder.execute_tool(
        "write_file",
        {"root": str(tmp_path), "path": "code.txt", "content": "allowed"},
    )
    assert result.success is True
    assert (tmp_path / "code.txt").read_text(encoding="utf-8") == "allowed"


def test_agent_delegation_updates_bus_and_shared_context():
    manager = AgentManager(register_defaults=False)
    manager.register_agent(ContextAgent(policy=AgentExecutionPolicy(max_steps=1, max_retries=0)))

    result = manager.delegate_task(
        "ContextAgent",
        "Summarize project",
        context={"scope": "tests"},
        correlation_id="ctx-1",
        decision_fn=_finish("summary ready"),
    )

    assert result.status == "completed"
    assert result.final_answer == "summary ready"
    assert manager.message_bus.history(correlation_id="ctx-1")[0]["to"] == "ContextAgent"
    tasks = manager.shared_context.list_tasks()
    assert tasks[0]["assigned_to"] == "ContextAgent"
    assert tasks[0]["status"] == "completed"


def test_manager_orchestration_runs_workflow():
    manager = AgentManager(register_defaults=False)
    manager.register_agent(PlannerAgent(policy=AgentExecutionPolicy(max_steps=1, max_retries=0)))
    manager.register_agent(ReviewerAgent(policy=AgentExecutionPolicy(max_steps=1, max_retries=0)))

    output = manager.orchestrate(
        "Add feature safely",
        workflow=["PlannerAgent", "ReviewerAgent"],
        decision_fns={
            "PlannerAgent": _finish("plan ready"),
            "ReviewerAgent": _finish("review ready"),
        },
        correlation_id="orch-1",
    )

    assert output["status"] == "completed"
    assert [r["agent_name"] for r in output["results"]] == ["PlannerAgent", "ReviewerAgent"]
    assert output["results"][0]["final_answer"] == "plan ready"
    assert output["context"]["shared_goals"] == ["Add feature safely"]


def test_autonomous_loop_enforces_agent_allowed_tools():
    planner = PlannerAgent(policy=AgentExecutionPolicy(max_steps=1, max_retries=0))

    result = planner.run(
        "Try to modify a file",
        decision_fn=lambda messages: json.dumps({
            "thought": "attempt write",
            "tool": "write_file",
            "args": {"path": "blocked.txt", "content": "no"},
        }),
    )

    assert result.status == "failed"
    assert "tool_not_allowed" in result.error
    assert planner.state.failures[0]["reason"].startswith("tool_not_allowed")
