"""Tests for self_mod_runtime_guard — the live SELF_MOD verify-and-rollback wiring.

These tests use a fake self_mod module (with the same _get_project_root /
_project_path / _apply_patches surface the wrapper relies on) and an injected
fake runner, so nothing here spawns a real subprocess, runs real pytest, or
imports agent.py. The real test suite is therefore unaffected.
"""

import os
import types
from collections import namedtuple

import pytest

import self_mod_runtime_guard as guard_mod
from self_mod_safety import SafeModificationGuard

_CP = namedtuple("_CP", ["returncode", "stdout", "stderr"])


class FakeRunner:
    """Stand-in for subprocess.run used by SafeModificationGuard verification."""

    def __init__(self, *, import_rc=0, test_rc=0, fail_modules=()):
        self.calls = []
        self.import_rc = import_rc
        self.test_rc = test_rc
        self.fail_modules = set(fail_modules)

    def __call__(self, cmd, *, cwd=None, timeout=None):
        self.calls.append(list(cmd))
        joined = " ".join(cmd)
        if "pytest" in joined:
            return _CP(self.test_rc, "1 passed", "")
        rc = self.import_rc
        for mod in self.fail_modules:
            if f"'{mod}'" in joined:
                rc = 1
        return _CP(rc, "", "ImportError" if rc else "")

    @property
    def ran_pytest(self):
        return any("pytest" in " ".join(c) for c in self.calls)

    def imported(self, module):
        return any(f"'{module}'" in " ".join(c) for c in self.calls)


def _make_fake_self_mod(root):
    """Minimal fake exposing the surface guarded_apply_patches depends on."""
    mod = types.ModuleType("fake_self_mod")

    def _get_project_root():
        return str(root)

    def _project_path(path):
        return path if os.path.isabs(path) else os.path.join(str(root), path)

    def _apply_patches(patches):
        updated = []
        for fname, code in patches.items():
            p = _project_path(fname)
            parent = os.path.dirname(p)
            if parent:
                os.makedirs(parent, exist_ok=True)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(code)
            updated.append(fname)
        return updated

    mod._get_project_root = _get_project_root
    mod._project_path = _project_path
    mod._apply_patches = _apply_patches
    return mod


def _guard(root, runner, *, run_tests=False):
    return SafeModificationGuard(root=str(root), runner=runner, run_tests=run_tests)


def _write(root, name, text):
    path = os.path.join(str(root), name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(text)
    return path


def _read(root, name):
    with open(os.path.join(str(root), name), encoding="utf-8") as fh:
        return fh.read()


@pytest.fixture(autouse=True)
def _reset_global_state():
    # Ensure each test starts and ends with no active install.
    guard_mod._ORIGINAL_APPLY = None
    guard_mod._GUARD = None
    yield
    guard_mod._ORIGINAL_APPLY = None
    guard_mod._GUARD = None


def test_install_is_idempotent_and_uninstall_restores(tmp_path):
    fake = _make_fake_self_mod(tmp_path)
    original = fake._apply_patches
    runner = FakeRunner()

    assert guard_mod.install(fake, guard=_guard(tmp_path, runner)) is True
    assert guard_mod.is_installed() is True
    assert getattr(fake._apply_patches, "_runtime_guard", False) is True

    # Second install is a no-op (no double-wrap).
    assert guard_mod.install(fake, guard=_guard(tmp_path, runner)) is False

    assert guard_mod.uninstall(fake) is True
    assert fake._apply_patches is original
    assert guard_mod.is_installed() is False


def test_success_commit_returns_updated(tmp_path):
    _write(tmp_path, "alpha.py", "VALUE = 1\n")
    fake = _make_fake_self_mod(tmp_path)
    runner = FakeRunner()
    guard_mod.install(fake, guard=_guard(tmp_path, runner))

    updated = fake._apply_patches({"alpha.py": "VALUE = 2\n"})

    assert updated == ["alpha.py"]
    assert _read(tmp_path, "alpha.py") == "VALUE = 2\n"


def test_success_runs_pytest_when_enabled(tmp_path):
    _write(tmp_path, "alpha.py", "VALUE = 1\n")
    fake = _make_fake_self_mod(tmp_path)
    runner = FakeRunner()
    guard_mod.install(fake, guard=_guard(tmp_path, runner, run_tests=True))

    updated = fake._apply_patches({"alpha.py": "VALUE = 2\n"})

    assert updated == ["alpha.py"]
    assert runner.imported("alpha")
    assert runner.ran_pytest is True


def test_import_failure_rolls_back_and_returns_empty(tmp_path):
    _write(tmp_path, "alpha.py", "VALUE = 1\n")
    fake = _make_fake_self_mod(tmp_path)
    runner = FakeRunner(fail_modules={"alpha"})
    guard_mod.install(fake, guard=_guard(tmp_path, runner))

    updated = fake._apply_patches({"alpha.py": "VALUE = 2\n"})

    assert updated == []
    assert _read(tmp_path, "alpha.py") == "VALUE = 1\n"  # rolled back


def test_test_failure_rolls_back_and_returns_empty(tmp_path):
    _write(tmp_path, "alpha.py", "VALUE = 1\n")
    fake = _make_fake_self_mod(tmp_path)
    runner = FakeRunner(test_rc=1)
    guard_mod.install(fake, guard=_guard(tmp_path, runner, run_tests=True))

    updated = fake._apply_patches({"alpha.py": "VALUE = 2\n"})

    assert updated == []
    assert _read(tmp_path, "alpha.py") == "VALUE = 1\n"


def test_multifile_atomic_rollback(tmp_path):
    _write(tmp_path, "alpha.py", "A = 1\n")
    _write(tmp_path, "beta.py", "B = 1\n")
    fake = _make_fake_self_mod(tmp_path)
    runner = FakeRunner(fail_modules={"beta"})
    guard_mod.install(fake, guard=_guard(tmp_path, runner))

    updated = fake._apply_patches({"alpha.py": "A = 2\n", "beta.py": "B = 2\n"})

    assert updated == []
    # Both files restored even though only beta failed to import.
    assert _read(tmp_path, "alpha.py") == "A = 1\n"
    assert _read(tmp_path, "beta.py") == "B = 1\n"


def test_created_file_removed_on_rollback(tmp_path):
    fake = _make_fake_self_mod(tmp_path)
    runner = FakeRunner(fail_modules={"gamma"})
    guard_mod.install(fake, guard=_guard(tmp_path, runner))

    updated = fake._apply_patches({"gamma.py": "G = 1\n"})

    assert updated == []
    assert not os.path.exists(os.path.join(str(tmp_path), "gamma.py"))


def test_empty_updated_passes_through_without_verification(tmp_path):
    fake = _make_fake_self_mod(tmp_path)

    # Simulate the existing path rejecting everything (safety/review).
    def _apply_nothing(patches):
        return []

    fake._apply_patches = _apply_nothing
    runner = FakeRunner()
    guard_mod.install(fake, guard=_guard(tmp_path, runner))

    updated = fake._apply_patches({"alpha.py": "VALUE = 2\n"})

    assert updated == []
    assert runner.calls == []  # verification never ran


def test_run_tests_skipped_when_disabled(tmp_path):
    _write(tmp_path, "alpha.py", "VALUE = 1\n")
    fake = _make_fake_self_mod(tmp_path)
    runner = FakeRunner()
    guard_mod.install(fake, guard=_guard(tmp_path, runner, run_tests=False))

    fake._apply_patches({"alpha.py": "VALUE = 2\n"})

    assert runner.imported("alpha")
    assert runner.ran_pytest is False


def test_entry_point_module_skips_import_probe_but_runs_tests(tmp_path):
    _write(tmp_path, "agent.py", "X = 1\n")
    fake = _make_fake_self_mod(tmp_path)
    runner = FakeRunner()
    guard_mod.install(fake, guard=_guard(tmp_path, runner, run_tests=True))

    updated = fake._apply_patches({"agent.py": "X = 2\n"})

    assert updated == ["agent.py"]
    assert runner.imported("agent") is False  # never import-probed
    assert runner.ran_pytest is True          # still gated by the suite


def test_run_tests_override_takes_precedence(tmp_path):
    _write(tmp_path, "alpha.py", "VALUE = 1\n")
    fake = _make_fake_self_mod(tmp_path)
    runner = FakeRunner()
    # Guard default says run tests, but the install-time override disables it.
    guard_mod.install(
        fake, guard=_guard(tmp_path, runner, run_tests=True), run_tests=False
    )

    fake._apply_patches({"alpha.py": "VALUE = 2\n"})

    assert runner.ran_pytest is False