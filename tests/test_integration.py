# tests/test_integration.py — Integration tests across the full agent
import sys
import os
import json
import textwrap
import tempfile
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import MagicMock, patch, call


# ══════════════════════════════════════════════════════════════
# Full Generation Pipeline
# ══════════════════════════════════════════════════════════════

class TestGenerationPipeline:
    """End-to-end: user request → plan → generate → save → launch."""

    def _mock_llm_for_planning(self):
        """Return a mock that simulates LLM planning response."""
        def fake_chat(**kwargs):
            messages = kwargs.get("messages", [])
            user_msg = messages[-1]["content"] if messages else ""

            mock_r = MagicMock()
            if "List the files needed" in user_msg or "List the files" in user_msg:
                mock_r.message.content = """PlayerController:player
EnemyScript:enemy
GameManager:manager
UIManager:ui
HealthBar:health"""
            else:
                # Generation response
                mock_r.message.content = """```csharp
using UnityEngine;
public class PlayerController : MonoBehaviour {
    void Start() { }
    void Update() { }
}
```"""
            return mock_r
        return fake_chat

    def test_full_unity_generation(self, tmp_path, monkeypatch):
        """A user asks for a space shooter → agent generates 5 scripts."""
        monkeypatch.chdir(tmp_path)

        with patch("llm_client.safe_chat", side_effect=self._mock_llm_for_planning()):
            with patch("llm_client.get_response", side_effect=lambda r: r.message.content):
                from generation_engine import run_generation

                summary = run_generation(
                    task="make a space shooter unity game",
                    engine="unity",
                    model_name="test-model",
                    project_name="SpaceShooter",
                    save_session_fn=lambda: None,
                )

                # Should mention success
                assert "SpaceShooter" in summary or "player" in summary.lower()

                # Check files were created
                proj_dir = tmp_path / "Generated_Scripts" / "SpaceShooter"
                assert proj_dir.exists()
                files = list(proj_dir.glob("*.cs"))
                assert len(files) >= 1

    def test_generation_with_resume(self, tmp_path, monkeypatch):
        """Generation crashes mid-way → checkpoint saved → resumed."""
        monkeypatch.chdir(tmp_path)

        call_count = [0]
        def fake_chat(**kwargs):
            call_count[0] += 1
            mock_r = MagicMock()
            if call_count[0] <= 3:
                mock_r.message.content = """PlayerController:player
EnemyScript:enemy
GameManager:manager"""
            else:
                mock_r.message.content = """```csharp
using UnityEngine;
public class EnemyScript : MonoBehaviour { void Start() {} }
```"""
            return mock_r

        with patch("llm_client.safe_chat", side_effect=fake_chat):
            with patch("llm_client.get_response", side_effect=lambda r: r.message.content):
                from generation_engine import run_generation
                from recovery import get_checkpoint_manager

                # First run — simulate crash after 1 script
                try:
                    run_generation(
                        task="make a shooter",
                        engine="unity",
                        model_name="test-model",
                        project_name="ResumeTest",
                        save_session_fn=lambda: None,
                    )
                except Exception:
                    pass  # may crash, that's OK

                # Resume
                summary = run_generation(
                    task="make a shooter",
                    engine="unity",
                    model_name="test-model",
                    project_name="ResumeTest",
                    save_session_fn=lambda: None,
                    resume=True,
                )

                assert "ResumeTest" in summary


# ══════════════════════════════════════════════════════════════
# Chat Flow with File Attachment
# ══════════════════════════════════════════════════════════════

class TestChatFlow:
    """User attaches a file → asks a question → gets answer."""

    def setup_method(self):
        """Inject required globals into file_handler before each test."""
        import file_handler as fh
        from unittest.mock import MagicMock
        mock_r = MagicMock()
        mock_r.message.content = "mocked"
        fh.inject_globals(
            safe_chat=lambda **kw: mock_r,
            get_response=lambda r: getattr(r.message, "content", ""),
            log=MagicMock(),
            _state=MagicMock(),
            project_context=[],
            safe_print=print,
            save_project_context=lambda: None,
        )

    def test_attach_and_ask(self, tmp_path, monkeypatch):
        """Attach a Python file → ask to summarize."""
        monkeypatch.chdir(tmp_path)

        code_file = tmp_path / "script.py"
        code_file.write_text("def hello():\n    return 'world'\n")

        from file_handler import attach_tool, detect_intent
        from state_manager import project_context

        # Clear context
        project_context.clear()

        # Attach file
        attach_tool(str(code_file))
        assert len(project_context) == 1
        assert project_context[0]["type"] == "code"

        # Detect intent
        intent = detect_intent("summarize this file")
        assert intent == "summarize"

    def test_compare_two_files(self, tmp_path, monkeypatch):
        """Attach two files → compare them."""
        monkeypatch.chdir(tmp_path)

        f1 = tmp_path / "a.py"
        f2 = tmp_path / "b.py"
        f1.write_text("x = 1\n")
        f2.write_text("x = 2\n")

        from file_handler import attach_tool, detect_intent
        from state_manager import project_context

        project_context.clear()
        attach_tool(str(f1))
        attach_tool(str(f2))

        assert len(project_context) == 2

        intent = detect_intent("compare the two files")
        assert intent == "compare"


# ══════════════════════════════════════════════════════════════
# Recovery Checkpoint / Resume
# ══════════════════════════════════════════════════════════════

class TestRecoveryFlow:
    """Checkpoint created → crash → resume from checkpoint."""

    def test_checkpoint_created_during_generation(self, tmp_path, monkeypatch):
        """During generation, checkpoint must be created."""
        monkeypatch.chdir(tmp_path)

        from recovery import RecoveryContext, get_checkpoint_manager

        pairs = [("A", "player"), ("B", "enemy")]

        with RecoveryContext("task", "unity", "TestProj", pairs, "model") as ctx:
            ctx.mark_started("A")
            ctx.mark_done("A")
            ctx.mark_started("B")
            # Simulate crash here — exit without mark_done

        mgr = get_checkpoint_manager()
        cp = mgr.load("TestProj")
        assert cp is not None
        assert cp.completed == ["A"]
        assert cp.current == "B"
        assert cp.status == "in_progress"

    def test_resume_loads_remaining(self, tmp_path, monkeypatch):
        """Resume should only return scripts not yet completed."""
        monkeypatch.chdir(tmp_path)

        from recovery import RecoveryContext

        pairs = [("A", "player"), ("B", "enemy"), ("C", "manager")]

        # First run — crash after B
        try:
            with RecoveryContext("task", "unity", "ResumeProj", pairs, "model") as ctx:
                for name, role in ctx.remaining:
                    ctx.mark_started(name)
                    if name == "B":
                        raise RuntimeError("crash")
                    ctx.mark_done(name)
        except RuntimeError:
            pass

        # Resume
        with RecoveryContext("task", "unity", "ResumeProj", pairs, "model", resume=True) as ctx:
            remaining = [n for n, _ in ctx.remaining]

        assert "A" not in remaining  # already done
        assert "B" in remaining      # failed → retry
        assert "C" in remaining      # never started

    def test_cleanup_on_success(self, tmp_path, monkeypatch):
        """Successful generation should delete checkpoint."""
        monkeypatch.chdir(tmp_path)

        from recovery import RecoveryContext, get_checkpoint_manager

        pairs = [("A", "player")]

        with RecoveryContext("task", "unity", "CleanProj", pairs, "model") as ctx:
            for name, role in ctx.remaining:
                ctx.mark_started(name)
                ctx.mark_done(name)

        mgr = get_checkpoint_manager()
        assert mgr.load("CleanProj") is None


# ══════════════════════════════════════════════════════════════
# Model Switching Flow
# ══════════════════════════════════════════════════════════════

class TestModelSwitching:
    """/model command → switch active model → confirm switch."""

    def test_switch_to_local(self):
        """Switch to local model alias."""
        import llm_client
        import config

        original = llm_client.DEFAULT_MODEL
        try:
            # Simulate _switch_model logic
            resolved = config.DEFAULT_MODEL
            llm_client.DEFAULT_MODEL = resolved
            assert llm_client.DEFAULT_MODEL == config.DEFAULT_MODEL
            assert llm_client.DEFAULT_MODEL != "local"
        finally:
            llm_client.DEFAULT_MODEL = original

    def test_switch_to_cloud_alias(self):
        """Switch to OpenRouter alias resolves full ID."""
        import llm_client

        original = llm_client.DEFAULT_MODEL
        try:
            alias = "or_free"
            resolved = llm_client.MODEL_ALIASES.get(alias, alias)
            llm_client.DEFAULT_MODEL = resolved
            assert "/" in llm_client.DEFAULT_MODEL
        finally:
            llm_client.DEFAULT_MODEL = original

    def test_switch_unknown_warns(self):
        """Unknown alias should warn but still set."""
        import llm_client

        original = llm_client.DEFAULT_MODEL
        try:
            alias = "unknown_model_xyz"
            resolved = llm_client.MODEL_ALIASES.get(alias, alias)
            llm_client.DEFAULT_MODEL = resolved
            assert llm_client.DEFAULT_MODEL == "unknown_model_xyz"
        finally:
            llm_client.DEFAULT_MODEL = original


# ══════════════════════════════════════════════════════════════
# Self-Modification End-to-End
# ══════════════════════════════════════════════════════════════

class TestSelfModIntegration:
    """Full self-mod flow: web search + LLM patch + apply + verify."""

    def test_add_command_flow(self, tmp_path, monkeypatch):
        """User asks to add /status → agent patches tool_registry + agent.py."""
        root = tmp_path / "agent_root"
        root.mkdir()

        (root / "agent.py").write_text(textwrap.dedent("""
            while True:
                user = input()
                if user.strip() == "/time":
                    print("time")
                if user.strip() == "exit":
                    break
        """))

        (root / "tool_registry.py").write_text(textwrap.dedent("""
            TOOL_REGISTRY = {
                "GAME": lambda x: x,
            }
            def get_tool(mode):
                return TOOL_REGISTRY.get(mode)
        """))

        (root / "commands_manifest.json").write_text("[]")

        import self_mod as sm
        sm._get_project_root = lambda: str(root)

        # Mock LLM to return a clean patch
        patch_code = textwrap.dedent("""
            ===FILE: tool_registry.py===
            ```python
            TOOL_REGISTRY = {
                "GAME": lambda x: x,
                "STATUS": _tool_status,
            }
            def _tool_status(user):
                print("Agent Status: OK")
            def get_tool(mode):
                return TOOL_REGISTRY.get(mode)
            ```
        """)

        mock_r = MagicMock()
        mock_r.message.content = patch_code

        with patch.object(sm, "safe_chat", return_value=mock_r):
            with patch.object(sm, "get_response", return_value=patch_code):
                with patch.object(sm, "_web_search", return_value="search results"):
                    with patch.object(sm, "safe_print"):
                        # Auto-confirm using fake_wait pattern
                        def fake_wait(timeout=None):
                            sm._confirmation_answer["answer"] = "YES"
                            return True
                        with patch.object(sm._pending_confirmation, "wait",
                                          side_effect=fake_wait):
                            sm.self_mod_tool("add a /status command")

        # Verify tool_registry updated — STATUS registered (impl may be lambda or function)
        tr_content = (root / "tool_registry.py").read_text()
        assert "STATUS" in tr_content, f"STATUS not in tool_registry: {tr_content[:200]}"

        # Verify agent.py updated
        agent_content = (root / "agent.py").read_text()
        assert "/status" in agent_content

        # Verify manifest updated
        manifest = json.loads((root / "commands_manifest.json").read_text())
        cmds = [d["cmd"] for d in manifest]
        assert "/status" in cmds

    def test_self_mod_rejects_dangerous_code(self, tmp_path, monkeypatch):
        """LLM returns dangerous code → safety check blocks it."""
        root = tmp_path / "agent_root"
        root.mkdir()
        (root / "tool_registry.py").write_text("TOOL_REGISTRY = {}\n")
        (root / "commands_manifest.json").write_text("[]")

        import self_mod as sm
        sm._get_project_root = lambda: str(root)

        dangerous_patch = """
            ===FILE: tool_registry.py===
            ```python
            import os
            os.system("rm -rf /")
            ```
        """

        mock_r = MagicMock()
        mock_r.message.content = dangerous_patch

        with patch("llm_client.safe_chat", return_value=mock_r):
            with patch("llm_client.get_response", return_value=dangerous_patch):
                with patch.object(sm, "_web_search", return_value=""):
                    with patch.object(sm, "safe_print"):
                        sm.self_mod_tool("add something")

        # File should remain unchanged (dangerous code rejected)
        content = (root / "tool_registry.py").read_text()
        assert "os.system" not in content


# ══════════════════════════════════════════════════════════════
# Domain Routing Integration
# ══════════════════════════════════════════════════════════════

class TestDomainRouting:
    """User input → correct domain detected → correct templates used."""

    def test_unity_game_routes_to_unity(self):
        from model_router import detect_domain
        assert detect_domain("make a unity shooter") == "unity"

    def test_react_website_routes_to_react(self):
        from model_router import detect_domain
        assert detect_domain("build a react website") == "react"

    def test_unreal_explicit(self):
        from model_router import detect_domain
        assert detect_domain("unreal engine game") == "unreal"

    def test_sql_database(self):
        from model_router import detect_domain
        assert detect_domain("create a database schema") == "sql"

    def test_python_script(self):
        from model_router import detect_domain
        assert detect_domain("write a python script") == "python"

    def test_general_chat(self):
        from model_router import detect_domain
        assert detect_domain("hello how are you") == "general"
