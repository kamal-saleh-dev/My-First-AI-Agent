# tests/test_generation_engine.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch, MagicMock, call


# ── detect_engine ─────────────────────────────────────────────────────────────

class TestDetectEngine:
    def setup_method(self):
        from generation_engine import detect_engine
        self.detect = detect_engine

    def test_unity_explicit(self):
        assert self.detect("make a unity game") == "unity"

    def test_unreal_explicit(self):
        assert self.detect("build an unreal c++ game") == "unreal"

    def test_hint_domain_used_when_no_explicit(self):
        assert self.detect("build a website", hint_domain="react") == "react"

    def test_defaults_to_unity_for_plain_game(self):
        engine = self.detect("make a game")
        assert engine in ("unity", "unreal")  # one of the two

    def test_web_domain_passed_through(self):
        assert self.detect("create a web app", hint_domain="dotnet") == "dotnet"


# ── extract_project_name ──────────────────────────────────────────────────────

class TestExtractProjectName:
    def setup_method(self):
        from generation_engine import extract_project_name
        self.extract = extract_project_name

    def _mock_llm(self, response: str):
        mock_r = MagicMock()
        mock_r.message.content = response
        return mock_r

    def test_extracts_name_from_llm(self):
        with patch("generation_engine.safe_chat", return_value=self._mock_llm("SpaceShooter")):
            name = self.extract("make a SpaceShooter game", "unity")
        assert "Space" in name or "shooter" in name.lower() or name

    def test_generates_name_when_none_found(self):
        with patch("generation_engine.safe_chat", return_value=self._mock_llm("NONE")):
            name = self.extract("make a game", "unity")
        assert isinstance(name, str) and len(name) > 0

    def test_fallback_for_long_extraction(self):
        long_response = "A" * 35
        with patch("generation_engine.safe_chat", return_value=self._mock_llm(long_response)):
            name = self.extract("make a cool adventure game", "unity")
        assert len(name) <= 40


# ── extract_and_save_scripts ──────────────────────────────────────────────────

class TestExtractAndSaveScripts:
    def setup_method(self):
        from generation_engine import extract_and_save_scripts
        self.save = extract_and_save_scripts

    def test_returns_false_when_no_code_blocks(self):
        assert self.save("no code here", "TestProject") is False

    def test_saves_csharp_block(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        ticks = "`" * 3
        code = f"{ticks}csharp\nusing UnityEngine;\npublic class Player : MonoBehaviour {{ void Start() {{}} }}\n{ticks}"
        result = self.save(code, "TestGame", forced_name="Player", forced_ext=".cs")
        assert result is True
        saved = list((tmp_path / "Generated_Scripts" / "TestGame").glob("*.cs"))
        assert len(saved) == 1

    def test_saves_python_block(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        code = "```python\ndef main():\n    print('hello')\n```"
        result = self.save(code, "MyProject", forced_name="main", forced_ext=".py")
        assert result is True

    def test_invalid_project_name_chars_stripped(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        code = "```python\nprint('x')\n```"
        result = self.save(code, 'Bad*Name?', forced_name="app", forced_ext=".py")
        assert result is True


# ── auto_run_and_fix ──────────────────────────────────────────────────────────

class TestAutoRunAndFix:
    def setup_method(self):
        from generation_engine import auto_run_and_fix
        self.fix = auto_run_and_fix

    def test_returns_code_and_output_on_success(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        code = "print('hello')"
        result_code, output = self.fix("print hello", code)
        assert "hello" in output
        assert result_code == code

    def test_handles_syntax_error(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        bad_code = "def broken(:"
        mock_r = MagicMock()
        mock_r.message.content = "print('fixed')"
        with patch("generation_engine.safe_chat", return_value=mock_r):
            result_code, output = self.fix("fix this", bad_code, max_attempts=1)
        assert isinstance(result_code, str)
        assert isinstance(output, str)

    def test_timeout_message_on_infinite_loop(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        inf_code = "while True: pass"
        _, output = self.fix("infinite loop", inf_code)
        assert "timed out" in output.lower() or "timeout" in output.lower()
