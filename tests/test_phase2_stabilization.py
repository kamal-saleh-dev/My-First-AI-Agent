import json

from agents import (
    AgentExecutionPolicy,
    AgentManager,
    CodingAgent,
    ContextAgent,
    ExecutionPlan,
    ExecutionStep,
    MessageBus,
    PlannerAgent,
    ReviewerAgent,
    SequentialExecutionStrategy,
)


def _decisions(items):
    seq = iter(items)
    return lambda messages: next(seq)


def _finish(answer="done"):
    return lambda messages: json.dumps(
        {"thought": "complete", "tool": "finish", "args": {"answer": answer}}
    )


class HookedCodingAgent(CodingAgent):
    name = "HookedCodingAgent"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.hook_events = []

    def before_task(self, task, context, metadata=None):
        self.hook_events.append(("before_task", task))

    def after_task(self, task, result, metadata=None):
        self.hook_events.append(("after_task", result.status))

    def before_tool(self, tool_name, args, metadata=None):
        self.hook_events.append(("before_tool", tool_name))

    def after_tool(self, tool_name, args, result, metadata=None):
        self.hook_events.append(("after_tool", tool_name, result.success))

    def on_failure(self, error, metadata=None):
        self.hook_events.append(("failure", error))

    def on_executor_event(self, event_type, payload):
        if event_type in {"retry", "observation_recorded", "stop_condition"}:
            self.hook_events.append(("event", event_type))

    def summarize_pruned_records(self, kind, records):
        return {"kind": kind, "count": len(records), "custom": True}

    def after_state_pruned(self, kind, summary):
        self.hook_events.append(("pruned", kind, summary["count"]))


def test_execution_plan_and_sequential_strategy_direct_execution():
    manager = AgentManager(register_defaults=False)
    manager.register_agent(PlannerAgent(policy=AgentExecutionPolicy(max_steps=1, max_retries=0)))
    manager.register_agent(ReviewerAgent(policy=AgentExecutionPolicy(max_steps=1, max_retries=0)))
    plan = ExecutionPlan(
        task="Stabilize Phase 2",
        steps=[
            ExecutionStep(agent_name="PlannerAgent", step_id="plan"),
            ExecutionStep(agent_name="ReviewerAgent", step_id="review"),
        ],
        correlation_id="strategy-1",
    )

    result = SequentialExecutionStrategy().execute(
        manager,
        plan,
        decision_fns={
            "PlannerAgent": _finish("planned"),
            "ReviewerAgent": _finish("reviewed"),
        },
    )

    assert result["status"] == "completed"
    assert plan.workflow == ["PlannerAgent", "ReviewerAgent"]
    assert [step.status for step in plan.steps] == ["completed", "completed"]
    assert "elapsed" in plan.steps[0].timing
    assert plan.steps[0].metadata["timing"]["elapsed"] == plan.steps[0].timing["elapsed"]
    assert [item["final_answer"] for item in result["results"]] == ["planned", "reviewed"]


def test_execution_step_extensibility_metadata():
    step = ExecutionStep(
        agent_name="CodingAgent",
        priority=7,
        retry_policy={"max_retries": 2},
        timing={"queued_at": 10.0},
        dependency_metadata={"depends_on_status": {"plan": "completed"}},
        scheduling={"queue": "fast"},
        failure_metadata={"last_error": ""},
        metadata={"owner": "AgentManager"},
    )

    data = step.to_dict()
    assert data["priority"] == 7
    assert data["retry_policy"]["max_retries"] == 2
    assert data["dependency_metadata"]["depends_on_status"]["plan"] == "completed"
    assert data["scheduling"]["queue"] == "fast"
    assert data["metadata"]["owner"] == "AgentManager"
    assert data["metadata"]["priority"] == 7
    assert data["metadata"]["retry_policy"]["max_retries"] == 2


def test_agent_manager_orchestration_uses_execution_strategy():
    manager = AgentManager(register_defaults=False)
    manager.register_agent(PlannerAgent(policy=AgentExecutionPolicy(max_steps=1, max_retries=0)))
    manager.register_agent(ReviewerAgent(policy=AgentExecutionPolicy(max_steps=1, max_retries=0)))
    plan = ExecutionPlan.from_workflow(
        "Refactor orchestration",
        ["PlannerAgent", "ReviewerAgent"],
        correlation_id="orch-strategy",
    )

    output = manager.orchestrate(
        "ignored when explicit plan is supplied",
        execution_plan=plan,
        strategy=SequentialExecutionStrategy(),
        decision_fns={
            "PlannerAgent": _finish("plan ok"),
            "ReviewerAgent": _finish("review ok"),
        },
    )

    assert output["strategy"] == "sequential"
    assert output["task"] == "Refactor orchestration"
    assert output["execution_plan"]["steps"][0]["agent_name"] == "PlannerAgent"
    assert output["status"] == "completed"


def test_lifecycle_hooks_order_and_executor_observation_events(tmp_path):
    (tmp_path / "sample.txt").write_text("hello", encoding="utf-8")
    agent = HookedCodingAgent(policy=AgentExecutionPolicy(max_steps=2, max_retries=0))
    result = agent.run(
        "Read a file then finish",
        decision_fn=_decisions([
            json.dumps({
                "thought": "read",
                "tool": "read_file",
                "args": {"root": str(tmp_path), "path": "sample.txt"},
            }),
            json.dumps({"thought": "done", "tool": "finish", "args": {"answer": "ok"}}),
        ]),
    )

    assert result.status == "completed"
    names = [event[0] if event[0] != "event" else event[1] for event in agent.hook_events]
    assert names.index("before_task") < names.index("before_tool")
    assert names.index("before_tool") < names.index("observation_recorded")
    assert names.index("observation_recorded") < names.index("after_tool")
    assert names.index("after_tool") < names.index("stop_condition")
    assert names.index("stop_condition") < names.index("after_task")


def test_hooks_observe_retry_failure_and_stop_conditions():
    agent = HookedCodingAgent(policy=AgentExecutionPolicy(max_steps=2, max_retries=1))
    result = agent.run(
        "Recover from malformed output",
        decision_fn=_decisions([
            "not json",
            json.dumps({"thought": "done", "tool": "finish", "args": {"answer": "recovered"}}),
        ]),
    )

    assert result.status == "completed"
    event_names = [event[1] for event in agent.hook_events if event[0] == "event"]
    failures = [event for event in agent.hook_events if event[0] == "failure"]
    assert "retry" in event_names
    assert "stop_condition" in event_names
    assert any("malformed_json" in failure[1] for failure in failures)


def test_message_bus_event_extensibility_and_broadcasts():
    bus = MessageBus()
    seen = []
    subscription_id = bus.subscribe("*", seen.append)

    bus.send("PlannerAgent", "CodingAgent", "Implement task", correlation_id="evt-1")
    custom = bus.emit_event("telemetry", payload={"value": 3}, correlation_id="evt-1")
    bus.broadcast("PlannerAgent", "Broadcast update", recipients=["ReviewerAgent"], correlation_id="evt-1")
    bus.unsubscribe(subscription_id)
    bus.emit_event("telemetry", payload={"value": 4}, correlation_id="evt-1")

    assert [event.event_type for event in seen] == [
        "message_published",
        "telemetry",
        "message_published",
        "message_broadcast",
    ]
    assert custom.payload["value"] == 3
    assert bus.receive("ReviewerAgent")[0].metadata["broadcast"] is True
    assert len(bus.events(correlation_id="evt-1")) == 5


def test_message_bus_subscriber_failure_is_logged_and_recorded(monkeypatch):
    bus = MessageBus()
    delivered = []
    warnings = []

    def bad_subscriber(event):
        raise RuntimeError("subscriber exploded")

    def good_subscriber(event):
        delivered.append(event.event_type)

    def fake_warn(message, **ctx):
        warnings.append({"message": message, **ctx})

    monkeypatch.setattr("agents.message_bus.log.warn", fake_warn)
    bus.subscribe("telemetry", bad_subscriber)
    bus.subscribe("telemetry", good_subscriber)

    event = bus.emit_event("telemetry", payload={"value": 1}, correlation_id="sub-fail")

    assert delivered == ["telemetry"]
    assert len(bus.subscriber_failures()) == 1
    assert bus.subscriber_failures()[0]["error"] == "subscriber exploded"
    assert event.metadata["subscriber_failures"][0]["event_id"] == event.event_id
    assert warnings[0]["message"] == "MessageBus subscriber failed"
    assert warnings[0]["error"] == "subscriber exploded"


def test_bounded_agent_state_prunes_memory_history_and_observations(tmp_path):
    agent = HookedCodingAgent(
        policy=AgentExecutionPolicy(
            max_action_history=2,
            max_observations=2,
            max_local_memory=2,
        )
    )
    for i in range(4):
        agent.remember({"note": f"memory-{i}"})

    for i in range(3):
        agent.execute_tool(
            "write_file",
            {"root": str(tmp_path), "path": f"file_{i}.txt", "content": str(i)},
        )

    assert [item["note"] for item in agent.state.local_memory] == ["memory-2", "memory-3"]
    assert len(agent.state.action_history) == 2
    assert len(agent.state.observations) == 2
    assert all(summary["custom"] for summary in agent.state.compaction_summaries)
    assert ("pruned", "local_memory", 1) in agent.hook_events
    assert any(event[:2] == ("pruned", "action_history") for event in agent.hook_events)


def test_compaction_summaries_are_bounded():
    agent = HookedCodingAgent(
        policy=AgentExecutionPolicy(
            max_local_memory=1,
            max_compaction_summaries=2,
        )
    )

    for i in range(5):
        agent.remember({"note": f"memory-{i}"})

    assert [item["note"] for item in agent.state.local_memory] == ["memory-4"]
    assert len(agent.state.compaction_summaries) == 2
    assert all(summary["kind"] == "local_memory" for summary in agent.state.compaction_summaries)


def test_sequential_strategy_stops_on_failed_step():
    manager = AgentManager(register_defaults=False)
    manager.register_agent(ContextAgent(policy=AgentExecutionPolicy(max_steps=1, max_retries=0)))
    manager.register_agent(ReviewerAgent(policy=AgentExecutionPolicy(max_steps=1, max_retries=0)))
    plan = ExecutionPlan.from_workflow(
        "Stop after failure",
        ["ContextAgent", "ReviewerAgent"],
        correlation_id="failed-plan",
    )

    result = SequentialExecutionStrategy().execute(
        manager,
        plan,
        decision_fns={
            "ContextAgent": lambda messages: json.dumps({
                "thought": "bad",
                "tool": "missing_tool",
                "args": {},
            }),
            "ReviewerAgent": _finish("should not run"),
        },
    )

    assert result["status"] == "failed"
    assert plan.steps[0].status == "failed"
    assert plan.steps[1].status == "pending"
    assert len(result["results"]) == 1
