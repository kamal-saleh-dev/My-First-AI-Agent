# tests/test_project_tools.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch, MagicMock


# ── save_last_project / load_last_project ─────────────────────────────────────

class TestProjectMemory:
    def test_round_trip(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AGENT_BASE_DIR", str(tmp_path))
        import importlib, config, project_tools
        importlib.reload(config)

        from project_tools import save_last_project, load_last_project, MEMORY_FILE
        mem = tmp_path / "agent_memory.txt"
        monkeypatch.setattr("project_tools.MEMORY_FILE", str(mem))

        save_last_project("/some/path/main.py")
        assert load_last_project() == "/some/path/main.py"

    def test_load_returns_none_if_missing(self, tmp_path, monkeypatch):
        monkeypatch.setattr("project_tools.MEMORY_FILE",
                            str(tmp_path / "nonexistent.txt"))
        from project_tools import load_last_project
        assert load_last_project() is None


# ── delete_tool ───────────────────────────────────────────────────────────────

class TestDeleteTool:
    def test_deletes_existing_folder(self, tmp_path, monkeypatch, capsys):
        target = tmp_path / "MyGame"
        target.mkdir()
        (target / "file.txt").write_text("x")

        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("project_tools.MEMORY_FILE",
                            str(tmp_path / "mem.txt"))

        from project_tools import delete_tool
        delete_tool(f"delete {target}")
        assert not target.exists()

    def test_missing_folder_prints_error(self, tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        from project_tools import delete_tool
        delete_tool("delete __nonexistent_folder__")
        assert "not found" in capsys.readouterr().out.lower()


# ── run_python ────────────────────────────────────────────────────────────────

class TestRunPython:
    def test_runs_valid_script(self, tmp_path, capsys):
        script = tmp_path / "hello.py"
        script.write_text("print('hello world')")

        from project_tools import run_python
        run_python(str(script))
        # No crash = success (output goes to subprocess, not capsys)

    def test_timeout_handled_gracefully(self, tmp_path, capsys):
        script = tmp_path / "loop.py"
        script.write_text("while True: pass")

        from project_tools import run_python
        run_python(str(script))   # should not raise
        out = capsys.readouterr().out
        assert "timed out" in out.lower() or "timeout" in out.lower()


# ── job_tool ──────────────────────────────────────────────────────────────────

class TestJobTool:
    def test_opens_browser_for_upwork(self):
        mock_r = MagicMock()
        mock_r.message.content = "Game Developer | Upwork | Remote"

        with patch("project_tools.safe_chat", return_value=mock_r), \
             patch("project_tools.webbrowser.open") as mock_open:
            from project_tools import job_tool
            job_tool("find me a game developer job on upwork")

        mock_open.assert_called_once()
        url = mock_open.call_args[0][0]
        assert "upwork.com" in url

    def test_opens_linkedin_for_non_upwork(self):
        mock_r = MagicMock()
        mock_r.message.content = "Python Developer | LinkedIn | Egypt"

        with patch("project_tools.safe_chat", return_value=mock_r), \
             patch("project_tools.webbrowser.open") as mock_open:
            from project_tools import job_tool
            job_tool("find python jobs on linkedin")

        url = mock_open.call_args[0][0]
        assert "linkedin.com" in url
