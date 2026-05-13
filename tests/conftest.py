# tests/conftest.py — shared pytest fixtures and path setup
import sys
import os
import json
import tempfile
import shutil

# Make sure project root is on the path for all test files
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import MagicMock, patch


# ══════════════════════════════════════════════════════════════
# Mock LLM Fixture
# ══════════════════════════════════════════════════════════════

@pytest.fixture
def mock_llm():
    """
    Returns a callable that patches `llm_client.safe_chat`.

    Usage:
        def test_something(mock_llm):
            mock_llm("some response text")
            # ... code that calls safe_chat ...
    """
    patches = []

    def _inject(response_text: str, model: str = None):
        mock_r = MagicMock()
        mock_r.message.content = response_text

        def fake_chat(**kwargs):
            if model and kwargs.get("model") != model:
                pass
            return mock_r

        p = patch("llm_client.safe_chat", side_effect=fake_chat)
        p.start()
        patches.append(p)
        return fake_chat

    yield _inject

    for p in patches:
        p.stop()


@pytest.fixture
def mock_llm_response():
    """Return a pre-built mock response object."""
    def _make(text: str):
        r = MagicMock()
        r.message.content = text
        return r
    return _make


# ══════════════════════════════════════════════════════════════
# Temporary Project Fixture
# ══════════════════════════════════════════════════════════════

@pytest.fixture
def temp_project(tmp_path):
    """
    Create a temporary project directory structure.
    Returns the base path.
    """
    base = tmp_path / "agent_project"
    base.mkdir()

    (base / "agent.py").write_text("""
while True:
    user = input()
    if user.strip() == "/time":
        print("time")
    if user.strip() == "/help":
        print("help")
    if user.strip() == "exit":
        break
""")

    (base / "tool_registry.py").write_text("""
TOOL_REGISTRY = {
    "GAME": lambda x: x,
    "STATUS": lambda x: x,
}
def get_tool(mode):
    return TOOL_REGISTRY.get(mode)
""")

    (base / "chat_handler.py").write_text("""
def chat_tool(task):
    pass
""")

    (base / "commands_manifest.json").write_text("[]")

    (base / "Generated_Scripts").mkdir()

    return base


@pytest.fixture
def temp_agent_root(tmp_path, monkeypatch):
    """
    Set up a temporary directory as the agent root (for self_mod file ops).
    """
    root = tmp_path / "agent_root"
    root.mkdir()

    (root / "agent.py").write_text("""while True:
    pass
""")
    (root / "tool_registry.py").write_text("""TOOL_REGISTRY = {}
""")
    (root / "commands_manifest.json").write_text("[]")
    (root / "self_mod.py").write_text("# self\n")

    import self_mod as sm
    original = sm._get_project_root
    sm._get_project_root = lambda: str(root)

    yield root

    sm._get_project_root = original


# ══════════════════════════════════════════════════════════════
# Mock File System & State
# ══════════════════════════════════════════════════════════════

@pytest.fixture
def clean_state():
    """Reset shared mutable state before/after tests."""
    import state_manager
    state_manager.chat_history.clear()
    state_manager.project_context.clear()
    state_manager._state.current_project_name = ""
    state_manager._state.awaiting_project_name = False
    yield
    state_manager.chat_history.clear()
    state_manager.project_context.clear()


@pytest.fixture
def mock_safe_chat():
    """Patch safe_chat globally for a test."""
    with patch("llm_client.safe_chat") as m:
        mock_r = MagicMock()
        mock_r.message.content = "mocked response"
        m.return_value = mock_r
        yield m


@pytest.fixture
def mock_get_response():
    """Patch get_response globally for a test."""
    with patch("llm_client.get_response") as m:
        m.side_effect = lambda r: getattr(r.message, "content", str(r))
        yield m
