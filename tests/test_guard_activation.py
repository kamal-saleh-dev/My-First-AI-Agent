"""Guard activation regression tests (v1.0 must-do).

Proves the self-modification guard in the CURRENT repository state actually
fires. `self_mod._safety_check(code, filename) -> (is_safe, reason)` is the
runtime gate every candidate patch must pass before it can be written.

These tests call the real guard; they do not mock or reimplement it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import self_mod


# A clean, non-trivial patch for a modifiable file (>= 5 real lines, no
# dangerous tokens) so it passes every layer of the guard.
_BENIGN_PATCH = (
    "def add(a, b):\n"
    "    total = a + b\n"
    "    checked = total\n"
    "    final = checked\n"
    "    return final\n"
)


def test_dangerous_os_system_blocked():
    ok, reason = self_mod._safety_check(
        "import os\nos.system('rm -rf /')\n", "agent.py"
    )
    assert ok is False
    assert "Dangerous" in reason


def test_dangerous_eval_and_exec_blocked():
    ok_eval, _ = self_mod._safety_check("x = eval('1 + 1')\n", "agent.py")
    ok_exec, _ = self_mod._safety_check("exec('x = 1')\n", "agent.py")
    assert ok_eval is False
    assert ok_exec is False


def test_dangerous_subprocess_blocked():
    ok, reason = self_mod._safety_check(
        "import subprocess\nsubprocess.call(['ls'])\n", "agent.py"
    )
    assert ok is False
    assert "Dangerous" in reason


def test_syntax_error_blocked():
    ok, reason = self_mod._safety_check("def broken(:\n    return 1\n", "agent.py")
    assert ok is False
    assert "SyntaxError" in reason


def test_too_short_patch_blocked():
    ok, reason = self_mod._safety_check("x = 1\n", "agent.py")
    assert ok is False
    assert "short" in reason.lower()


def test_benign_modifiable_patch_passes():
    ok, reason = self_mod._safety_check(_BENIGN_PATCH, "agent.py")
    assert ok is True
    assert reason == "ok"


def test_protected_files_never_targetable():
    # Disjoint sets guarantee a protected core file can never be chosen as a
    # modification target (targets are only ever drawn from _MODIFIABLE).
    assert self_mod._PROTECTED, "protected set must be non-empty"
    assert self_mod._MODIFIABLE, "modifiable set must be non-empty"
    assert self_mod._PROTECTED.isdisjoint(self_mod._MODIFIABLE)
    for core in (
        "self_mod.py",
        "config.py",
        "logger.py",
        "llm_client.py",
        "session_manager.py",
    ):
        assert core in self_mod._PROTECTED
        assert core not in self_mod._MODIFIABLE
