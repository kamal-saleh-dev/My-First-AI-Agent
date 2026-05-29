import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agents.message_bus import AgentMessage, BusEvent, MessageBus

def _bus():
    return MessageBus()

def test_send_and_receive_returns_list():
    bus = _bus()
    bus.send("PlannerAgent", "CodingAgent", "implement feature")
    received = bus.receive("CodingAgent")
    assert isinstance(received, list)
    assert len(received) == 1
    msg = received[0]
    assert isinstance(msg, AgentMessage)
    assert msg.from_agent == "PlannerAgent"
    assert msg.to_agent == "CodingAgent"
    assert msg.task == "implement feature"
    assert not hasattr(msg, "content")
    # receive consumes the inbox
    assert bus.receive("CodingAgent") == []

def test_peek_does_not_consume():
    bus = _bus()
    bus.send("A", "B", "t1")
    assert len(bus.peek("B")) == 1
    assert len(bus.peek("B")) == 1
    assert len(bus.receive("B")) == 1

def test_publish_requires_sender_and_recipient():
    bus = _bus()
    with pytest.raises(ValueError):
        bus.publish({"from": "", "to": "B", "task": "t"})

def test_message_dict_round_trip():
    msg = AgentMessage.from_dict({"from": "A", "to": "B", "task": "t"})
    data = msg.to_dict()
    assert data["from"] == "A"
    assert data["to"] == "B"
    assert data["task"] == "t"
    restored = AgentMessage.from_dict(data)
    assert restored.from_agent == "A"
    assert restored.to_agent == "B"
    assert restored.task == "t"

def test_history_records_messages():
    bus = _bus()
    bus.send("A", "B", "t1")
    bus.send("B", "A", "t2")
    history = bus.history()
    assert isinstance(history, list)
    assert len(history) == 2
    assert history[0]["task"] == "t1"

def test_emit_event_isolates_subscriber_failures():
    bus = _bus()
    seen = []

    def good(event):
        seen.append(event.event_type)

    def bad(event):
        raise RuntimeError("boom")

    bus.subscribe("task_done", good)
    bus.subscribe("task_done", bad)
    event = bus.emit_event("task_done", payload={"k": "v"})
    assert isinstance(event, BusEvent)
    assert seen == ["task_done"]
    assert len(bus.subscriber_failures()) == 1

def test_clear_resets_state():
    bus = _bus()
    bus.send("A", "B", "t1")
    bus.clear()
    assert bus.receive("B") == []
    assert bus.history() == []
