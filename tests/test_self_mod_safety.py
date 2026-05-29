"""Tests for self_mod_safety — deterministic, no network, no real pytest spawn.

A FakeRunner is injected into every guard so the import/pytest verification
stages never spawn a real subprocess (which would otherwise recurse into pytest).
The pre-apply syntax check runs in-process and is exercised for real.
"""

import os
from collections import namedtuple

import self_mod_safety as sms
from self_mod_safety import SafeModificationGuard

_CP = namedtuple("_CP", ["returncode", "stdout", "stderr"])


class FakeRunner:
    """Records commands and fakes import + pytest outcomes without spawning."""

    def __init__(self, *, import_rc=0, test_rc=0, fail_modules=()):
        self.calls = []
        self.import_rc = import_rc
        self.test_rc = test_rc
        self.fail_modules = set(fail_modules)

    def __call__(self, cmd, *, cwd, timeout):
        self.calls.append(list(cmd))
        if "pytest" in cmd:
            return _CP(self.test_rc, "pytest summary", "")
        joined = " ".join(cmd)
        rc = self.import_rc
        for mod in self.fail_modules:
            if f"'{mod}'" in joined:
                rc = 1
        return _CP(rc, "", "ImportError" if rc else "")

    @property
    def ran_pytest(self):
        return any("pytest" in c for c in self.calls)


def _write(root, name, text):
    path = os.path.join(str(root), name)
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _read(root, name):
    with open(os.path.join(str(root), name), encoding="utf-8") as fh:
        return fh.read()


def _guard(root, runner, **kw):
    kw.setdefault("run_tests", False)
    return SafeModificationGuard(root=str(root), runner=runner, **kw)


def test_apply_and_commit_success(tmp_path):
    _write(tmp_path, "alpha.py", "VALUE = 1\n")
    runner = FakeRunner()
    res = _guard(tmp_path, runner).run({"alpha.py": "VALUE = 2\n"})
    assert res.ok and res.committed and not res.rolled_back
    assert res.applied == ["alpha.py"]
    assert "VALUE = 2" in _read(tmp_path, "alpha.py")


def test_syntax_error_rejected_before_apply(tmp_path):
    _write(tmp_path, "alpha.py", "VALUE = 1\n")
    runner = FakeRunner()
    res = _guard(tmp_path, runner).run({"alpha.py": "def broken(:\n"})
    assert not res.ok and not res.rolled_back and res.applied == []
    assert any(i.stage == "syntax" for i in res.issues)
    assert _read(tmp_path, "alpha.py") == "VALUE = 1\n"   # untouched
    assert runner.calls == []                            # never verified


def test_import_failure_triggers_rollback(tmp_path):
    _write(tmp_path, "alpha.py", "ORIGINAL = True\n")
    runner = FakeRunner(fail_modules={"alpha"})
    res = _guard(tmp_path, runner).run({"alpha.py": "ORIGINAL = False\n"})
    assert not res.ok and res.rolled_back
    assert any(i.stage == "import" for i in res.issues)
    assert _read(tmp_path, "alpha.py") == "ORIGINAL = True\n"


def test_test_failure_triggers_rollback(tmp_path):
    _write(tmp_path, "alpha.py", "ORIGINAL = True\n")
    runner = FakeRunner(test_rc=1)
    res = _guard(tmp_path, runner, run_tests=True).run({"alpha.py": "ORIGINAL = False\n"})
    assert not res.ok and res.rolled_back
    assert any(i.stage == "tests" for i in res.issues)
    assert runner.ran_pytest
    assert _read(tmp_path, "alpha.py") == "ORIGINAL = True\n"


def test_multifile_atomic_rollback(tmp_path):
    _write(tmp_path, "alpha.py", "A = 1\n")
    _write(tmp_path, "beta.py", "B = 1\n")
    runner = FakeRunner(fail_modules={"beta"})
    res = _guard(tmp_path, runner).run({"alpha.py": "A = 2\n", "beta.py": "B = 2\n"})
    assert not res.ok and res.rolled_back
    assert _read(tmp_path, "alpha.py") == "A = 1\n"   # rolled back despite importing fine
    assert _read(tmp_path, "beta.py") == "B = 1\n"


def test_created_file_removed_on_rollback(tmp_path):
    runner = FakeRunner(fail_modules={"gamma"})
    res = _guard(tmp_path, runner).run({"gamma.py": "G = 1\n"})
    assert not res.ok and res.rolled_back
    assert not os.path.exists(os.path.join(str(tmp_path), "gamma.py"))


def test_path_traversal_blocked(tmp_path):
    runner = FakeRunner()
    res = _guard(tmp_path, runner).run({"../evil.py": "X = 1\n"})
    assert not res.ok and res.applied == []
    assert any(i.stage == "path" for i in res.issues)
    assert not os.path.exists(os.path.join(os.path.dirname(str(tmp_path)), "evil.py"))
    assert runner.calls == []


def test_protected_file_blocked(tmp_path):
    _write(tmp_path, "config.py", "DEFAULT_MODEL = 'x'\n")
    runner = FakeRunner()
    res = _guard(tmp_path, runner).run({"config.py": "DEFAULT_MODEL = 'y'\n"})
    assert not res.ok and res.applied == []
    assert any(i.stage == "protected" for i in res.issues)
    assert "'x'" in _read(tmp_path, "config.py")


def test_modifiable_allowlist_enforced(tmp_path):
    _write(tmp_path, "model_router.py", "M = 1\n")
    runner = FakeRunner()
    guard = _guard(tmp_path, runner, modifiable={"agent.py"})
    res = guard.run({"model_router.py": "M = 2\n"})
    assert not res.ok and res.applied == []
    assert any(i.stage == "protected" for i in res.issues)
    assert _read(tmp_path, "model_router.py") == "M = 1\n"


def test_run_tests_skipped_when_disabled(tmp_path):
    _write(tmp_path, "alpha.py", "A = 1\n")
    runner = FakeRunner()
    res = _guard(tmp_path, runner, run_tests=False).run({"alpha.py": "A = 2\n"})
    assert res.ok
    assert not runner.ran_pytest
    assert all("pytest" not in c for c in runner.calls)


def test_safe_self_modify_composes_self_mod(tmp_path, monkeypatch):
    import self_mod
    _write(tmp_path, "model_router.py", "M = 1\n")
    monkeypatch.setattr(self_mod, "_detect_target_files", lambda task: ["model_router.py"])
    monkeypatch.setattr(self_mod, "_generate_patch", lambda task, targets, search: {"model_router.py": "M = 2\n"})
    monkeypatch.setattr(self_mod, "_review_patch", lambda *a, **k: (True, "ok"))
    guard = _guard(tmp_path, FakeRunner())
    res = sms.safe_self_modify("add a thing", guard=guard)
    assert res.ok and res.applied == ["model_router.py"]
    assert "M = 2" in _read(tmp_path, "model_router.py")


def test_safe_self_modify_rejects_when_review_fails(tmp_path, monkeypatch):
    import self_mod
    _write(tmp_path, "model_router.py", "M = 1\n")
    monkeypatch.setattr(self_mod, "_detect_target_files", lambda task: ["model_router.py"])
    monkeypatch.setattr(self_mod, "_generate_patch", lambda task, targets, search: {"model_router.py": "M = 2\n"})
    monkeypatch.setattr(self_mod, "_review_patch", lambda *a, **k: (False, "removes symbol"))
    guard = _guard(tmp_path, FakeRunner())
    res = sms.safe_self_modify("add a thing", guard=guard)
    assert not res.ok
    assert _read(tmp_path, "model_router.py") == "M = 1\n"   # nothing applied