"""self_mod_safety.py — transactional verify-and-rollback for self-modification.

Audit milestone: "Safe Self-Modification" (the next milestone recommended by the
architecture audit), scoped to verify-and-rollback only.

Why this exists
---------------
Self-modification is already user-reachable: model_router.detect_mode() returns
SELF_MOD for a broad keyword set, and self_mod.py may edit high-blast-radius
files (model_router.py, chat_handler.py, tool_registry.py, autonomous_loop.py).
self_mod.py already validates *syntax* (ast), reviews patches (_review_patch),
keeps .bak backups, and reverts the single surgical agent.py patch on failure.

The gap this closes: there is no transactional, *behavioral* gate across a
multi-file patch set. If file #3 breaks imports, files #1-2 stay applied. A
syntactically-valid-but-broken edit to a routing/registry file can brick the
running agent.

What it adds (and ONLY this)
----------------------------
A transactional guard: snapshot -> apply -> verify (import + optional pytest)
-> commit, or atomic rollback of every file on any failure. It is composition,
not mutation: it does NOT modify self_mod.py, /auto, /multi, or the adaptive
runtime. This is the same opt-in composition style adaptive_runtime uses over
AgentManager.

Explicitly out of scope (deferred per the audit): full sandbox infrastructure
(Phase 9), self-improvement loops (Phase 10), and stack reconciliation.
"""

from __future__ import annotations

import os
import sys
import time
import shutil
import subprocess
from dataclasses import dataclass, field
from typing import Callable, Optional

from logger import log

__all__ = [
    "PathSafetyError",
    "FileSnapshot",
    "VerificationIssue",
    "SafetyResult",
    "SafeModificationGuard",
    "safe_self_modify",
]


# -- Config (local + env-overridable; mirrors config.py's AGENT_ convention) --
# Kept local on purpose so this milestone modifies no existing file. These can
# later be promoted into config.py to honor the single-source-of-truth rule.
def _env_int(key: str, default: int) -> int:
    val = os.getenv(f"AGENT_{key.upper()}")
    try:
        return int(val) if val is not None else int(default)
    except (TypeError, ValueError):
        return int(default)


def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(f"AGENT_{key.upper()}")
    if val is None:
        return bool(default)
    return val.strip().lower() in ("1", "true", "yes", "on")


SELF_MOD_VERIFY_TIMEOUT = _env_int("SELF_MOD_VERIFY_TIMEOUT", 30)     # import check
SELF_MOD_TEST_TIMEOUT   = _env_int("SELF_MOD_TEST_TIMEOUT", 120)      # pytest run
SELF_MOD_RUN_TESTS      = _env_bool("SELF_MOD_RUN_TESTS", True)
SELF_MOD_BACKUP_SUFFIX  = os.getenv("AGENT_SELF_MOD_BACKUP_SUFFIX", ".safebak")

# Fallback protected set, mirroring self_mod._PROTECTED. The live set is imported
# at runtime when available so the two never drift.
_DEFAULT_PROTECTED = {
    "self_mod.py", "self_mod_safety.py", "config.py", "llm_client.py",
    "logger.py", "state_manager.py", "recovery.py", "errors.py",
    "shutdown_manager.py", "session_manager.py", "process_registry.py",
}


class PathSafetyError(Exception):
    """Raised when a target path resolves outside the project root."""


@dataclass
class FileSnapshot:
    path: str
    existed: bool
    original: Optional[str] = None
    backup_path: Optional[str] = None


@dataclass
class VerificationIssue:
    target: str
    stage: str   # "path" | "protected" | "syntax" | "import" | "tests" | "target"
    detail: str

    def to_dict(self) -> dict:
        return {"target": self.target, "stage": self.stage, "detail": self.detail}


@dataclass
class SafetyResult:
    ok: bool
    committed: bool = False
    rolled_back: bool = False
    applied: list = field(default_factory=list)
    issues: list = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return not self.ok

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "committed": self.committed,
            "rolled_back": self.rolled_back,
            "applied": list(self.applied),
            "issues": [i.to_dict() for i in self.issues],
        }


def _tail(text: str, limit: int = 800) -> str:
    text = str(text or "")
    return text if len(text) <= limit else "…" + text[-limit:]


def _default_runner(cmd, *, cwd, timeout):
    return subprocess.run(cmd, cwd=cwd, timeout=timeout, capture_output=True, text=True)


def _project_root() -> str:
    try:
        import self_mod
        return self_mod._get_project_root()
    except Exception:
        return os.getcwd()


class SafeModificationGuard:
    """Snapshot -> apply -> verify -> (commit | rollback) for a set of file patches.

    Verification stages, in order:
      pre-apply : path-safety, protected/allowlist, Python syntax (in-process).
                  On any failure here, the disk is never touched.
      post-apply: subprocess import of each modified .py module, then an
                  optional pytest run. Any failure rolls back EVERY file as a
                  unit (and removes newly created files).

    A custom ``runner`` can be injected for tests so no real subprocess/pytest
    is spawned.
    """

    def __init__(
        self,
        root: Optional[str] = None,
        *,
        run_tests: Optional[bool] = None,
        verify_timeout: Optional[int] = None,
        test_timeout: Optional[int] = None,
        test_target: Optional[str] = None,
        protected=None,
        modifiable=None,
        backup_suffix: Optional[str] = None,
        runner: Optional[Callable] = None,
    ):
        self._root = os.path.abspath(root or _project_root())
        self.run_tests = SELF_MOD_RUN_TESTS if run_tests is None else bool(run_tests)
        self.verify_timeout = int(verify_timeout if verify_timeout is not None else SELF_MOD_VERIFY_TIMEOUT)
        self.test_timeout = int(test_timeout if test_timeout is not None else SELF_MOD_TEST_TIMEOUT)
        self.test_target = test_target
        self.backup_suffix = backup_suffix or SELF_MOD_BACKUP_SUFFIX
        self.runner = runner or _default_runner
        self._protected = set(protected) if protected is not None else None
        self.modifiable = set(modifiable) if modifiable is not None else None

    # -- public API -----------------------------------------------------------
    def run(self, patches: dict, *, run_tests: Optional[bool] = None) -> SafetyResult:
        run_tests = self.run_tests if run_tests is None else bool(run_tests)
        if not patches:
            return SafetyResult(ok=False, issues=[VerificationIssue("<none>", "target", "no patches provided")])

        valid: dict = {}
        issues: list = []
        for fname, code in patches.items():
            try:
                abspath = self._resolve(fname)
            except PathSafetyError as exc:
                issues.append(VerificationIssue(fname, "path", str(exc)))
                continue
            if self._is_protected(fname):
                issues.append(VerificationIssue(fname, "protected", "protected file — refused"))
                continue
            if self.modifiable is not None and os.path.basename(fname) not in self.modifiable:
                issues.append(VerificationIssue(fname, "protected", "not in modifiable allowlist"))
                continue
            if fname.endswith(".py"):
                try:
                    compile(code, abspath, "exec")
                except SyntaxError as exc:
                    issues.append(VerificationIssue(fname, "syntax", str(exc)))
                    continue
            valid[fname] = (abspath, code)

        # Pre-apply gate: if anything is wrong, never touch disk.
        if issues:
            log.warn("Safe self-mod refused before applying", count=len(issues))
            return SafetyResult(ok=False, issues=issues)

        snapshots = self._snapshot(valid)
        self._apply(valid)
        applied = list(valid.keys())

        runtime_issues = self._verify_runtime(valid, run_tests=run_tests)
        if runtime_issues:
            self._rollback(snapshots)
            log.warn("Safe self-mod rolled back after verification failure", count=len(runtime_issues))
            return SafetyResult(ok=False, rolled_back=True, applied=applied, issues=runtime_issues)

        self._commit(snapshots)
        log.info("Safe self-mod committed", files=len(applied))
        return SafetyResult(ok=True, committed=True, applied=applied)

    # -- internals ------------------------------------------------------------
    def _resolve(self, path: str) -> str:
        candidate = path if os.path.isabs(path) else os.path.join(self._root, path)
        candidate = os.path.abspath(candidate)
        try:
            common = os.path.commonpath([self._root, candidate])
        except ValueError:
            raise PathSafetyError(f"path escapes project root: {path}")
        if common != self._root:
            raise PathSafetyError(f"path escapes project root: {path}")
        return candidate

    def _protected_set(self) -> set:
        if self._protected is not None:
            return self._protected
        try:
            from self_mod import _PROTECTED as live
            return set(live) | {"self_mod_safety.py"}
        except Exception:
            return set(_DEFAULT_PROTECTED)

    def _is_protected(self, fname: str) -> bool:
        return os.path.basename(fname) in self._protected_set()

    def _module_name(self, abspath: str) -> str:
        rel = os.path.relpath(abspath, self._root)
        if rel.endswith(".py"):
            rel = rel[:-3]
        return rel.replace(os.sep, ".").replace("/", ".")

    def _snapshot(self, valid: dict) -> list:
        snaps: list = []
        for _fname, (abspath, _code) in valid.items():
            if os.path.exists(abspath):
                backup = f"{abspath}.{int(time.time())}{self.backup_suffix}"
                try:
                    shutil.copy2(abspath, backup)
                except Exception:
                    backup = None
                with open(abspath, encoding="utf-8", errors="ignore") as fh:
                    original = fh.read()
                snaps.append(FileSnapshot(abspath, True, original, backup))
            else:
                snaps.append(FileSnapshot(abspath, False, None, None))
        return snaps

    def _apply(self, valid: dict) -> None:
        for _fname, (abspath, code) in valid.items():
            parent = os.path.dirname(abspath)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent, exist_ok=True)
            with open(abspath, "w", encoding="utf-8") as fh:
                fh.write(code)

    def _verify_runtime(self, valid: dict, *, run_tests: bool) -> list:
        issues: list = []
        for fname, (abspath, _code) in valid.items():
            if not fname.endswith(".py"):
                continue
            module = self._module_name(abspath)
            cmd = [sys.executable, "-c", f"import importlib; importlib.import_module({module!r})"]
            try:
                proc = self.runner(cmd, cwd=self._root, timeout=self.verify_timeout)
            except Exception as exc:
                issues.append(VerificationIssue(fname, "import", f"verification error: {exc}"))
                continue
            if getattr(proc, "returncode", 1) != 0:
                issues.append(VerificationIssue(fname, "import", _tail(getattr(proc, "stderr", ""))))
        if issues:
            return issues  # broken imports -> no point running the suite

        if run_tests:
            target = self.test_target or "."
            cmd = [sys.executable, "-m", "pytest", target, "-q"]
            try:
                proc = self.runner(cmd, cwd=self._root, timeout=self.test_timeout)
            except Exception as exc:
                return [VerificationIssue("<suite>", "tests", f"test run error: {exc}")]
            if getattr(proc, "returncode", 1) != 0:
                detail = _tail((getattr(proc, "stdout", "") or "") + (getattr(proc, "stderr", "") or ""))
                issues.append(VerificationIssue("<suite>", "tests", detail))
        return issues

    def _rollback(self, snapshots: list) -> None:
        for snap in snapshots:
            try:
                if snap.existed:
                    with open(snap.path, "w", encoding="utf-8") as fh:
                        fh.write(snap.original or "")
                elif os.path.exists(snap.path):
                    os.remove(snap.path)
            except Exception as exc:
                log.warn("Rollback failed for file", path=snap.path, error=str(exc))

    def _commit(self, snapshots: list) -> None:
        # Backups are intentionally kept so self_mod's /diff keeps working.
        return None


def safe_self_modify(
    task: str,
    *,
    run_tests: Optional[bool] = None,
    guard: Optional[SafeModificationGuard] = None,
    web_search: bool = False,
) -> SafetyResult:
    """Opt-in safe entry point for self-modification.

    Reuses self_mod's existing detect -> generate -> review building blocks to
    produce patches, then routes the apply step through SafeModificationGuard so
    a bad patch set is verified and rolled back as a unit. Composition only — it
    does not modify self_mod.py or the existing SELF_MOD dispatch path, so all
    current behavior is preserved.
    """
    task = (task or "").strip()
    if not task:
        return SafetyResult(ok=False, issues=[VerificationIssue("<task>", "target", "empty task")])

    import self_mod

    targets = self_mod._detect_target_files(task)
    if not targets:
        return SafetyResult(ok=False, issues=[VerificationIssue("<targets>", "target", "no target files detected")])

    search = ""
    if web_search:
        try:
            search = self_mod._web_search(task)
        except Exception:
            search = ""

    patches = self_mod._generate_patch(task, targets, search)
    if not patches:
        return SafetyResult(ok=False, issues=[VerificationIssue("<patches>", "target", "no patches generated")])

    g = guard or SafeModificationGuard()
    root = g._root

    reviewed: dict = {}
    for fname, code in patches.items():
        abspath = os.path.join(root, fname)
        original = ""
        if os.path.exists(abspath):
            with open(abspath, encoding="utf-8", errors="ignore") as fh:
                original = fh.read()
        try:
            ok, reason = self_mod._review_patch(task, fname, original, code, skip_llm=True)
        except Exception as exc:
            ok, reason = False, f"review error: {exc}"
        if ok:
            reviewed[fname] = code
        else:
            log.warn("Patch rejected by review", file=fname, reason=str(reason))

    if not reviewed:
        return SafetyResult(ok=False, issues=[VerificationIssue("<review>", "target", "all patches rejected by review")])

    return g.run(reviewed, run_tests=run_tests)