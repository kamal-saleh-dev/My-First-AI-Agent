import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.shared_execution_context import SharedExecutionContext, SharedTask

def test_metadata_and_goals():
    ctx = SharedExecutionContext()
    ctx.add_goal("ship stabilization")
    ctx.set_metadata("phase", "stabilization")
    assert ctx.get_metadata("phase") == "stabilization"
    assert ctx.get_metadata("missing", "fallback") == "fallback"
    assert "ship stabilization" in ctx.shared_goals

def test_task_lifecycle_sets_idle_when_done():
    ctx = SharedExecutionContext()
    task = ctx.create_task("analyze repo", assigned_to="PlannerAgent")
    assert isinstance(task, SharedTask)
    assert ctx.global_state["status"] == "running"
    assert ctx.get_task(task.task_id) is task
    ctx.update_task(task.task_id, "completed", {"ok": True})
    assert ctx.get_task(task.task_id).status == "completed"
    assert ctx.get_task(task.task_id).result == {"ok": True}
    assert ctx.global_state["status"] == "idle"

def test_list_tasks_and_serialization():
    ctx = SharedExecutionContext()
    task = ctx.create_task("review changes")
    listed = ctx.list_tasks()
    assert any(item["task_id"] == task.task_id for item in listed)
    data = task.to_dict()
    for key in ("task_id", "description", "assigned_to", "status", "result"):
        assert key in data

def test_get_task_missing_returns_none():
    ctx = SharedExecutionContext()
    assert ctx.get_task("does-not-exist") is None

def test_share_memory_and_snapshot():
    ctx = SharedExecutionContext()
    ctx.add_goal("goal-1")
    ctx.share_memory({"note": "remember this"})
    snap = ctx.snapshot()
    assert snap["shared_goals"] == ["goal-1"]
    assert snap["shared_memory"][0]["note"] == "remember this"
    assert "ts" in snap["shared_memory"][0]
    assert set(snap) >= {
        "shared_goals",
        "execution_metadata",
        "active_tasks",
        "global_state",
        "shared_memory",
    }
