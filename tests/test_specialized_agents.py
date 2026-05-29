import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config as _cfg
from agents import (
    CodingAgent,
    ContextAgent,
    DebuggerAgent,
    PlannerAgent,
    ReviewerAgent,
    TestingAgent,
)

DEFAULT_AGENT_CLASSES = (
    PlannerAgent,
    CodingAgent,
    ReviewerAgent,
    TestingAgent,
    DebuggerAgent,
    ContextAgent,
)

def test_six_default_roles_have_unique_names():
    names = [cls.name for cls in DEFAULT_AGENT_CLASSES]
    assert len(names) == 6
    assert len(set(names)) == 6

def test_roles_declare_models_and_prompts():
    for cls in DEFAULT_AGENT_CLASSES:
        assert isinstance(cls.name, str) and cls.name
        assert isinstance(cls.role, str) and cls.role
        assert getattr(cls, "preferred_model", None)
        assert getattr(cls, "system_prompt", "")

def test_planner_prefers_reasoning_model():
    assert PlannerAgent.preferred_model == _cfg.MULTI_AGENT_MODEL_DEEPSEEK

def test_planner_and_reviewer_cannot_write():
    for cls in (PlannerAgent, ReviewerAgent):
        assert "write_file" not in set(cls.allowed_tools)
        assert "write_file" in set(cls.restricted_tools)

def test_coding_agent_can_write():
    assert "write_file" in set(CodingAgent.allowed_tools)
