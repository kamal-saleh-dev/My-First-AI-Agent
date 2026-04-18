# tests/test_checkpoint.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import json
import pytest
from recovery import RecoveryContext, get_checkpoint_manager

TASK         = "__test_space_shooter__"
ENGINE       = "unity"
PROJECT_NAME = "TestCheckpointProject"
PAIRS        = [
    ("Script1", "player"),
    ("Script2", "enemy"),
    ("Script3", "spawner"),
    ("Script4", "ui"),
    ("Script5", "manager"),
]


@pytest.fixture(autouse=True)
def cleanup_checkpoint():
    """Remove checkpoint file before and after every test."""
    mgr  = get_checkpoint_manager()
    path = mgr._path(PROJECT_NAME)
    if os.path.exists(path):
        os.remove(path)
    yield
    if os.path.exists(path):
        os.remove(path)


class TestCheckpointSave:
    def test_file_created_on_crash(self):
        """Checkpoint file must exist after a mid-generation crash."""
        mgr = get_checkpoint_manager()
        try:
            with RecoveryContext(TASK, ENGINE, PROJECT_NAME, PAIRS, "test-model") as ctx:
                for name, role in ctx.remaining:
                    ctx.mark_started(name)
                    if name == "Script3":
                        raise RuntimeError("simulated crash")
                    ctx.mark_done(name)
        except RuntimeError:
            pass

        assert os.path.exists(mgr._path(PROJECT_NAME)), \
            "Checkpoint file was not created after crash"

    def test_completed_scripts_recorded(self):
        """Scripts finished before crash must appear in completed list."""
        mgr = get_checkpoint_manager()
        try:
            with RecoveryContext(TASK, ENGINE, PROJECT_NAME, PAIRS, "test-model") as ctx:
                for name, role in ctx.remaining:
                    ctx.mark_started(name)
                    if name == "Script3":
                        raise RuntimeError("simulated crash")
                    ctx.mark_done(name)
        except RuntimeError:
            pass

        with open(mgr._path(PROJECT_NAME)) as f:
            data = json.load(f)

        assert data["completed"] == ["Script1", "Script2"]

    def test_failed_script_recorded(self):
        """The script that crashed must appear in failed list."""
        mgr = get_checkpoint_manager()
        try:
            with RecoveryContext(TASK, ENGINE, PROJECT_NAME, PAIRS, "test-model") as ctx:
                for name, role in ctx.remaining:
                    ctx.mark_started(name)
                    if name == "Script3":
                        ctx.mark_failed(name)
                        raise RuntimeError("simulated crash")
                    ctx.mark_done(name)
        except RuntimeError:
            pass

        with open(mgr._path(PROJECT_NAME)) as f:
            data = json.load(f)

        assert "Script3" in data["failed"]

    def test_status_is_in_progress(self):
        """Status must be 'in_progress' after a crash, not 'done'."""
        mgr = get_checkpoint_manager()
        try:
            with RecoveryContext(TASK, ENGINE, PROJECT_NAME, PAIRS, "test-model") as ctx:
                for name, role in ctx.remaining:
                    ctx.mark_started(name)
                    if name == "Script2":
                        raise RuntimeError("simulated crash")
                    ctx.mark_done(name)
        except RuntimeError:
            pass

        with open(mgr._path(PROJECT_NAME)) as f:
            data = json.load(f)

        assert data["status"] == "in_progress"


class TestCheckpointResume:
    def _crash_after(self, crash_on: str):
        """Helper: run generation, crash at crash_on script."""
        try:
            with RecoveryContext(TASK, ENGINE, PROJECT_NAME, PAIRS, "test-model") as ctx:
                for name, role in ctx.remaining:
                    ctx.mark_started(name)
                    if name == crash_on:
                        raise RuntimeError("simulated crash")
                    ctx.mark_done(name)
        except RuntimeError:
            pass

    def test_completed_scripts_skipped_on_resume(self):
        """Scripts already done must not appear in remaining after resume."""
        self._crash_after("Script3")
        with RecoveryContext(TASK, ENGINE, PROJECT_NAME, PAIRS, "test-model", resume=True) as ctx:
            remaining = [n for n, _ in ctx.remaining]
        assert "Script1" not in remaining
        assert "Script2" not in remaining

    def test_failed_script_retried_on_resume(self):
        """The script that crashed must be retried (appear in remaining)."""
        self._crash_after("Script3")
        with RecoveryContext(TASK, ENGINE, PROJECT_NAME, PAIRS, "test-model", resume=True) as ctx:
            remaining = [n for n, _ in ctx.remaining]
        assert "Script3" in remaining

    def test_pending_scripts_included_on_resume(self):
        """Scripts not yet started must be included in remaining."""
        self._crash_after("Script3")
        with RecoveryContext(TASK, ENGINE, PROJECT_NAME, PAIRS, "test-model", resume=True) as ctx:
            remaining = [n for n, _ in ctx.remaining]
        assert "Script4" in remaining
        assert "Script5" in remaining


class TestCheckpointCleanup:
    def test_file_deleted_after_success(self):
        """Checkpoint file must be deleted when generation completes fully."""
        mgr = get_checkpoint_manager()
        with RecoveryContext(TASK, ENGINE, PROJECT_NAME, PAIRS, "test-model") as ctx:
            for name, role in ctx.remaining:
                ctx.mark_started(name)
                ctx.mark_done(name)

        assert not os.path.exists(mgr._path(PROJECT_NAME))

    def test_fresh_run_ignores_old_checkpoint(self):
        """resume=False must start all scripts from scratch."""
        try:
            with RecoveryContext(TASK, ENGINE, PROJECT_NAME, PAIRS, "test-model") as ctx:
                for name, role in ctx.remaining:
                    ctx.mark_started(name)
                    ctx.mark_done(name)
                    raise RuntimeError("crash immediately after first")
        except RuntimeError:
            pass

        with RecoveryContext(TASK, ENGINE, PROJECT_NAME, PAIRS, "test-model", resume=False) as ctx:
            remaining = [n for n, _ in ctx.remaining]

        assert remaining == [n for n, _ in PAIRS], \
            f"Fresh run should include all scripts, got: {remaining}"
