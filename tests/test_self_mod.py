# tests/test_self_mod.py — Comprehensive tests for self-modification system
import sys
import os
import json
import ast
import textwrap

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import MagicMock, patch, mock_open

import self_mod as sm


# ══════════════════════════════════════════════════════════════
# Test _detect_target_files
# ══════════════════════════════════════════════════════════════

class TestDetectTargetFiles:
    def setup_method(self):
        """Reset scan context so tests aren't affected by previous /scan calls."""
        sm._scan_context["scanned"] = False
        sm._scan_context["files"]   = []
        sm._scan_cache.clear()
    """
    _detect_target_files checks os.path.exists on candidates.
    We mock it to return True for all files so keyword routing is tested
    independently from the filesystem.
    """

    @pytest.fixture(autouse=True)
    def mock_file_exists(self):
        """Make every file appear to exist so path-filtering doesn't hide results."""
        with patch("self_mod.os.path.exists", return_value=True):
            # Also clear scan cache/context so they don't interfere
            original_cache   = sm._scan_cache.copy()
            original_scanned = sm._scan_context["scanned"]
            sm._scan_cache.clear()
            sm._scan_context["scanned"] = False
            yield
            sm._scan_cache.update(original_cache)
            sm._scan_context["scanned"] = original_scanned

    def test_keyword_mapping_model(self):
        result = sm._detect_target_files("improve escalation quality threshold")
        assert "model_advisor.py" in result

    def test_keyword_mapping_router(self):
        result = sm._detect_target_files("fix intent routing for vague requests")
        assert "model_router.py" in result

    def test_keyword_mapping_chat(self):
        result = sm._detect_target_files("improve streaming response handling")
        assert "chat_handler.py" in result

    def test_slash_command_adds_tool_registry_and_agent(self):
        result = sm._detect_target_files("add a /status command to show agent state")
        assert "tool_registry.py" in result
        assert "agent.py" in result

    def test_slash_command_with_explicit_slash(self):
        result = sm._detect_target_files("add /weather command")
        assert "tool_registry.py" in result
        assert "agent.py" in result

    def test_explicit_filename_in_task(self):
        result = sm._detect_target_files("fix the planner.py fallback logic")
        assert "planner.py" in result

    def test_vague_request_returns_modifiable_files(self):
        result = sm._detect_target_files("add voice output feature")
        assert len(result) > 0

    def test_no_protected_files_returned(self):
        result = sm._detect_target_files("modify self_mod.py to add new feature")
        assert "self_mod.py" not in result


# ══════════════════════════════════════════════════════════════
# Test _build_prompt
# ══════════════════════════════════════════════════════════════

class TestBuildPrompt:
    def test_includes_task(self):
        prompt = sm._build_prompt("add /status", ["tool_registry.py"], "")
        assert "add /status" in prompt

    def test_includes_file_content(self):
        prompt = sm._build_prompt("task", ["tool_registry.py"], "")
        assert "tool_registry.py" in prompt
        assert "```python" in prompt

    def test_includes_search_results(self):
        prompt = sm._build_prompt("task", ["tool_registry.py"], "search result here")
        assert "search result here" in prompt
        assert "WEB SEARCH RESULTS" in prompt

    def test_critical_symbols_preserved(self):
        prompt = sm._build_prompt("task", ["tool_registry.py"], "")
        assert "def get_tool" in prompt
        assert "BACKGROUND_TOOLS" in prompt
        assert "TOOL_REGISTRY" in prompt

    def test_agent_patched_flag(self):
        prompt = sm._build_prompt("task", ["tool_registry.py"], "", agent_patched=True)
        assert "agent.py is already patched surgically" in prompt


# ══════════════════════════════════════════════════════════════
# Test _parse_file_blocks
# ══════════════════════════════════════════════════════════════

class TestParseFileBlocks:
    def test_primary_format(self):
        response = """
===FILE: tool_registry.py===
```python
TOOL_REGISTRY = {"NEW": lambda x: x}
```
"""
        blocks = sm._parse_file_blocks(response, ["tool_registry.py"])
        assert "tool_registry.py" in blocks
        assert "NEW" in blocks["tool_registry.py"]

    def test_fallback_single_file(self):
        response = """
```python
x = 1
```
"""
        blocks = sm._parse_file_blocks(response, ["tool_registry.py"])
        assert "tool_registry.py" in blocks
        assert "x = 1" in blocks["tool_registry.py"]

    def test_skips_protected_files(self):
        response = """
===FILE: self_mod.py===
```python
x = 1
```
"""
        blocks = sm._parse_file_blocks(response, ["self_mod.py"])
        assert "self_mod.py" not in blocks

    def test_skips_unlisted_files(self):
        response = """
===FILE: unknown.py===
```python
x = 1
```
"""
        blocks = sm._parse_file_blocks(response, ["tool_registry.py"])
        assert "unknown.py" not in blocks

    def test_empty_response(self):
        blocks = sm._parse_file_blocks("", ["tool_registry.py"])
        assert blocks == {}


# ══════════════════════════════════════════════════════════════
# Test _safety_check
# ══════════════════════════════════════════════════════════════

class TestSafetyCheck:
    def test_safe_code_passes(self):
        code = (
            "def hello():\n"
            "    \"\"\"Return a greeting.\"\"\"\n"
            "    msg = 'hello'\n"
            "    return msg\n"
            "\n"
            "def world():\n"
            "    return 'world'\n"
        )
        ok, reason = sm._safety_check(code, "test.py")
        assert ok is True, f"Safe code was blocked: {reason}"

    def test_os_system_blocked(self):
        code = "import os\nos.system('rm -rf /')\n"
        ok, reason = sm._safety_check(code, "test.py")
        assert ok is False
        assert "Dangerous pattern" in reason

    def test_eval_blocked(self):
        code = "eval('1+1')\n"
        ok, reason = sm._safety_check(code, "test.py")
        assert ok is False

    def test_shutil_rmtree_blocked(self):
        code = "import shutil\nshutil.rmtree('/')\n"
        ok, reason = sm._safety_check(code, "test.py")
        assert ok is False

    def test_syntax_error_blocked(self):
        code = "def broken(:\n"
        ok, reason = sm._safety_check(code, "test.py")
        assert ok is False
        assert "SyntaxError" in reason

    def test_too_short_blocked(self):
        code = "x = 1\n"
        ok, reason = sm._safety_check(code, "test.py")
        assert ok is False
        assert "Too short" in reason


# ══════════════════════════════════════════════════════════════
# Test _review_patch (8-layer reviewer)
# ══════════════════════════════════════════════════════════════

class TestReviewPatch:
    def test_syntax_check(self):
        original = "def a():\n    pass\n"
        new_code = "def a(:\n"  # broken
        ok, reason = sm._review_patch("task", "test.py", original, new_code)
        assert ok is False
        assert "SyntaxError" in reason

    def test_size_check_max_30_percent_deletion(self):
        # Build valid Python original with 100 lines
        original_lines = ["def func_{}():\n    pass".format(i) for i in range(50)]
        original = "\n".join(original_lines)
        # New code keeps only 5 functions (90% deleted)
        new_lines = ["def func_{}():\n    pass".format(i) for i in range(5)]
        new_code = "\n".join(new_lines)
        ok, reason = sm._review_patch("task", "test.py", original, new_code)
        assert ok is False
        assert "deletes too much" in reason

    def test_critical_symbols_preserved(self):
        original = "def get_tool():\n    pass\n"
        new_code = "def other():\n    pass\n"  # removed get_tool
        ok, reason = sm._review_patch("task", "tool_registry.py", original, new_code)
        assert ok is False
        assert "get_tool" in reason

    def test_original_defs_survive(self):
        original = "def a():\n    pass\ndef b():\n    pass\n"
        new_code = "def a():\n    pass\n"  # removed b
        ok, reason = sm._review_patch("task", "test.py", original, new_code)
        assert ok is False
        assert "b" in reason

    def test_dangerous_patterns_blocked(self):
        original = "x = 1\n"
        new_code = "import sys\nsys.exit(0)\n"
        ok, reason = sm._review_patch("task", "test.py", original, new_code)
        assert ok is False
        assert "dangerous" in reason.lower()

    def test_identical_patch_blocked(self):
        original = "x = 1\n"
        ok, reason = sm._review_patch("task", "test.py", original, original)
        assert ok is False
        assert "identical" in reason

    def test_valid_patch_passes(self):
        original = "def a():\n    pass\n"
        new_code = "def a():\n    return 1\ndef b():\n    pass\n"
        ok, reason = sm._review_patch("task", "test.py", original, new_code)
        assert ok is True
        assert "all checks passed" in reason


# ══════════════════════════════════════════════════════════════
# Test _patch_agent_py (surgical patching)
# ══════════════════════════════════════════════════════════════

class TestPatchAgentPy:
    def test_adds_handler_after_time(self, tmp_path):
        agent = tmp_path / "agent.py"
        # Use proper structure: while loop with indented handlers
        # dedent uses backslash to avoid leading newline
        agent.write_text(textwrap.dedent("""\
            while True:
                user = input().strip()
                if user.strip() == "/time":
                    print("time")
                if user.strip() == "exit":
                    break
        """))

        sm._get_project_root = lambda: str(tmp_path)
        result = sm._patch_agent_py("add /status", "status", "STATUS")
        assert result is True, "Expected True (patched successfully)"

        content = agent.read_text()
        assert '"/status"' in content, "Handler not found in patched file"

        content = agent.read_text()
        assert '/status"' in content
        assert "STATUS" in content

    def test_skips_if_already_exists(self, tmp_path):
        agent = tmp_path / "agent.py"
        agent.write_text(textwrap.dedent("""
            if user.strip() == "/status":
                pass
        """))

        sm._get_project_root = lambda: str(tmp_path)
        result = sm._patch_agent_py("add /status", "status", "STATUS")
        assert result is True  # returns True because already exists

    def test_returns_false_if_no_anchor(self, tmp_path):
        agent = tmp_path / "agent.py"
        agent.write_text("x = 1\n")

        sm._get_project_root = lambda: str(tmp_path)
        result = sm._patch_agent_py("add /status", "status", "STATUS")
        assert result is False


# ══════════════════════════════════════════════════════════════
# Test _auto_install_deps
# ══════════════════════════════════════════════════════════════

class TestAutoInstallDeps:
    def test_detects_missing_import(self):
        import importlib as _real_importlib
        patches = {"test.py": "import pyjokes\nprint(pyjokes.get_joke())\n"}
        def fake_import(name):
            if name == "pyjokes":
                raise ImportError("No module named 'pyjokes'")
            return _real_importlib.import_module(name)
        with patch("importlib.import_module", side_effect=fake_import):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = sm._auto_install_deps(patches)
                assert "pyjokes" in result
                mock_run.assert_called()

    def test_ignores_stdlib(self):
        patches = {"test.py": "import os\nimport sys\n"}
        with patch("subprocess.run") as mock_run:
            result = sm._auto_install_deps(patches)
            assert result == []
            mock_run.assert_not_called()

    def test_ignores_internal_modules(self):
        patches = {"test.py": "import logger\nimport config\n"}
        with patch("subprocess.run") as mock_run:
            result = sm._auto_install_deps(patches)
            assert result == []

    def test_maps_import_to_pip_name(self):
        import importlib as _real_importlib
        patches = {"test.py": "import cv2\n"}
        def fake_import(name):
            if name == "cv2":
                raise ImportError("No module named 'cv2'")
            return _real_importlib.import_module(name)
        with patch("importlib.import_module", side_effect=fake_import):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0)
                result = sm._auto_install_deps(patches)
                assert "opencv-python" in result


# ══════════════════════════════════════════════════════════════
# Test _sync_commands_to_gui
# ══════════════════════════════════════════════════════════════

class TestSyncCommandsToGui:
    def test_adds_new_command(self, tmp_path):
        sm._get_project_root = lambda: str(tmp_path)
        manifest = tmp_path / "commands_manifest.json"
        manifest.write_text("[]")

        # Key "NEW_CMD" → cmd "/new_cmd" (lowercased key)
        patches = {"tool_registry.py": 'TOOL_REGISTRY = {\n    "NEW_CMD": _tool_new,\n}\n'}
        sm._sync_commands_to_gui(patches, "add /new_cmd command")

        data = json.loads(manifest.read_text())
        cmds = [d["cmd"] for d in data]
        assert "/new_cmd" in cmds

    def test_skips_existing_commands(self, tmp_path):
        sm._get_project_root = lambda: str(tmp_path)
        manifest = tmp_path / "commands_manifest.json"
        manifest.write_text(json.dumps([{"cmd": "/new", "desc": "x", "section": "AGENT COMMANDS"}]))

        patches = {"tool_registry.py": 'TOOL_REGISTRY = {\n    "NEW": _tool_new,\n}\n'}
        sm._sync_commands_to_gui(patches, "add /new command")

        data = json.loads(manifest.read_text())
        assert len(data) == 1

    def test_generates_description_from_task(self, tmp_path):
        sm._get_project_root = lambda: str(tmp_path)
        manifest = tmp_path / "commands_manifest.json"
        manifest.write_text("[]")

        patches = {"tool_registry.py": 'TOOL_REGISTRY = {\n    "CALC": _tool_calc,\n}\n'}
        sm._sync_commands_to_gui(patches, "add a /calc command that solves math")

        data = json.loads(manifest.read_text())
        assert "math" in data[0]["desc"].lower()


# ══════════════════════════════════════════════════════════════
# Test self_mod_tool end-to-end flow
# ══════════════════════════════════════════════════════════════

class TestSelfModTool:
    def test_rejects_vague_requests(self, capsys):
        with patch.object(sm, "safe_print"):
            sm.self_mod_tool("edit yourself")
            # Should return early without doing anything
            # (no crash = success for vague rejection)

    def test_rejects_modify_yourself(self):
        with patch.object(sm, "safe_print"):
            sm.self_mod_tool("modify yourself")
            # Early return

    def test_full_flow_with_mocked_llm(self, tmp_path, monkeypatch):
        """End-to-end: task → detect → generate → review → apply."""
        root = tmp_path / "agent_root"
        root.mkdir()
        (root / "agent.py").write_text("""while True:
    if user.strip() == "/time":
        pass
""")
        (root / "tool_registry.py").write_text("""TOOL_REGISTRY = {}
""")
        (root / "commands_manifest.json").write_text("[]")

        sm._get_project_root = lambda: str(root)

        # Mock web search
        with patch.object(sm, "_web_search", return_value="search results"):
            patches_dict = {"tool_registry.py": textwrap.dedent("""\
                TOOL_REGISTRY = {}

                def _tool_status(user):
                    print("status")

                TOOL_REGISTRY["STATUS"] = _tool_status
            """)}

            def fake_wait(timeout=None):
                sm._confirmation_answer["answer"] = "YES"
                return True

            with patch.object(sm, "_generate_patch", return_value=patches_dict):
                with patch.object(sm._pending_confirmation, "wait",
                                  side_effect=fake_wait):
                    with patch.object(sm, "safe_print"):
                        sm.self_mod_tool("add a /status command")

        # Verify file was updated — STATUS must be registered (impl detail may vary)
        content = (root / "tool_registry.py").read_text()
        assert "STATUS" in content, f"STATUS not found in: {content[:200]}"
        assert "_tool_status" in content
