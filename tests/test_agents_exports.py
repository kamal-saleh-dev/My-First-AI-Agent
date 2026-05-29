import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import agents

def test_all_is_defined_and_unique():
    assert hasattr(agents, "__all__")
    assert len(agents.__all__) == len(set(agents.__all__))

def test_all_exports_are_importable():
    for name in agents.__all__:
        assert hasattr(agents, name), f"missing export: {name}"

def test_key_symbols_present():
    expected = {
        "AgentManager",
        "BaseAgent",
        "AgentResult",
        "AgentState",
        "MessageBus",
        "AgentMessage",
        "BusEvent",
        "SharedExecutionContext",
        "SharedTask",
        "ExecutionPlan",
        "ExecutionStep",
        "ExecutionStrategy",
        "SequentialExecutionStrategy",
        "PlannerAgent",
        "CodingAgent",
        "ReviewerAgent",
        "TestingAgent",
        "DebuggerAgent",
        "ContextAgent",
    }
    assert expected.issubset(set(agents.__all__))
