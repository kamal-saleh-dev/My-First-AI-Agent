import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autonomous_checkpoint import (
    AutonomousCheckpointStore,
    deserialize_state,
    serialize_state,
)
from autonomous_loop import AutonomousExecutor, ExecutionState, Observation
from tool_registry import ToolResult

def _finish(messages):
    return json.dumps({"thought": "finish", "tool": "finish", "args": {"answer": "ok"}})

def _sample_state():
    state = ExecutionState(task="demo task")
    state.step = 2
    state.status = "completed"
    state.final_answer = "done"
    result = ToolResult(success=True, data={"path": "a.py"}, error="")
    state.observations.append(
        Observation(
            step=1,
            thought="read it",
            tool="read_file",
            args={"path": "a.py"},
            result=result,
            success=True,
            summary="read a.py",
        )
    )
    return state

def test_state_round_trip():
    state = _sample_state()
    restored = deserialize_state(serialize_state(state))
    assert restored.task == state.task
    assert restored.status == "completed"
    assert restored.step == 2
    assert len(restored.observations) == 1
    obs = restored.observations[0]
    assert obs.tool == "read_file"
    assert isinstance(obs.result, ToolResult)
    assert obs.result.success is True
    assert obs.result.data == {"path": "a.py"}

def test_store_save_load_delete(tmp_path):
    store = AutonomousCheckpointStore(root=str(tmp_path / "cp"))
    assert store.load("missing") is None
    store.save(_sample_state(), "run-1")
    assert store.exists("run-1") is True
    assert "run-1" in store.list_ids()
    loaded = store.load("run-1")
    assert loaded is not None
    assert loaded.task == "demo task"
    assert store.delete("run-1") is True
    assert store.exists("run-1") is False

def test_executor_opt_in_checkpointing(tmp_path):
    store = AutonomousCheckpointStore(root=str(tmp_path / "cp"))
    executor = AutonomousExecutor(
        decision_fn=_finish,
        enable_checkpoints=True,
        checkpoint_store=store,
        checkpoint_id="exec-1",
    )
    state = executor.execute("do something")
    assert state.status == "completed"
    persisted = store.load("exec-1")
    assert persisted is not None
    assert persisted.status == "completed"

def test_checkpoints_disabled_by_default(tmp_path):
    store = AutonomousCheckpointStore(root=str(tmp_path / "cp"))
    executor = AutonomousExecutor(
        decision_fn=_finish,
        checkpoint_store=store,
        checkpoint_id="exec-2",
    )
    executor.execute("task")
    assert store.load("exec-2") is None

def test_resume_state_restores(tmp_path):
    prior = _sample_state()
    prior.status = "running"
    prior.step = 3
    executor = AutonomousExecutor(decision_fn=_finish)
    final = executor.execute("demo task", resume_state=prior)
    assert final.status == "completed"
    assert final.step >= 3
