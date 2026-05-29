"""Tests for the memory bridge that wires memory_store into the agent loop."""

import os

from agent_memory import AgentMemoryBridge
from memory_store import MemoryStore

def _bridge(tmp_path, **kwargs):
    store = MemoryStore(path=os.path.join(str(tmp_path), "mem.json"))
    return AgentMemoryBridge(store=store, **kwargs)

def test_record_then_recall(tmp_path):
    bridge = _bridge(tmp_path, enabled=True, top_k=3)
    bridge.record("add /weather command", {"status": "completed", "final_answer": "added _tool_weather"})
    text = bridge.recall_text("add /weather command")
    assert "weather" in text.lower()

def test_recall_context_shape(tmp_path):
    bridge = _bridge(tmp_path, enabled=True)
    bridge.record("build login api", {"status": "completed", "final_answer": "done"})
    context = bridge.recall_context("build login api")
    assert context.get(AgentMemoryBridge.CONTEXT_KEY)

def test_disabled_is_noop(tmp_path):
    bridge = _bridge(tmp_path, enabled=False)
    bridge.record("some task", {"status": "completed"})
    assert bridge.recall_text("some task") == ""
    assert bridge.recall_context("some task") == {}
    assert len(bridge.store) == 0

def test_recall_empty_when_no_match(tmp_path):
    bridge = _bridge(tmp_path, enabled=True)
    assert bridge.recall_text("a completely unrelated nonexistent query") == ""

def test_only_successful_filters_failures(tmp_path):
    bridge = _bridge(tmp_path, enabled=True, only_successful=True)
    bridge.record("flaky task alpha", {"status": "failed", "error": "nope"})
    assert bridge.recall_text("flaky task alpha") == ""

def test_record_accepts_agentresult_like(tmp_path):
    bridge = _bridge(tmp_path, enabled=True)

    class R:
        status = "completed"
        final_answer = "did the thing"
        error = ""

    bridge.record("do the thing", R())
    assert len(bridge.store) == 1
