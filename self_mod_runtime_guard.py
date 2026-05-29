"""self_mod_runtime_guard.py — route the live SELF_MOD apply path through safety.

Completes the Safe Self-Modification milestone (Phase C integration step).

The safety *mechanism* (SafeModificationGuard), its tests, and its docs already
exist in self_mod_safety.py. What was missing was the wiring: the real
self_mod._apply_patches() write path was never verified or rolled back. This
module supplies the smallest possible integration:

    install() monkeypatches self_mod._apply_patches with a thin wrapper that
      1. snapshots every target file in the patch set (recording which are new),
      2. calls the ORIGINAL _apply_patches unchanged — its _safety_check,
         LLM review loop, .bak backups and per-file compile-revert all still run,
      3. verifies the result transactionally by subprocess-importing each
         updated module and (optionally) running pytest, and
      4. on ANY verification failure, rolls the whole set back atomically
         (restores originals, deletes newly created files) and returns [] so the
         existing handler reports "no files updated" exactly as before.

Design constraints honored:
  * self_mod.py is NOT modified, redesigned, or rewritten.
  * The detect / generate / review / preview / confirmation flow is untouched
    (everything upstream of _apply_patches runs exactly as before).
  * There is a SINGLE guard implementation (SafeModificationGuard is reused for
    verification), so there is no parallel SELF_MOD path.
  * /auto, /multi and Adaptive Autonomy are unaffected — they never touch
    _apply_patches.

Activation happens once, from the production entry point (agent.py), so unit
tests that import self_mod directly never see the wrapper unless they install it
explicitly. This keeps the existing test suite byte-for-byte unaffected.
"""

from __future__ import annotations

import os
from typing import Callable, List, Optional, Sequence, Tuple

from logger import log
from self_mod_safety import SafeModificationGuard

__all__ = [
    "install",
    "uninstall",
    "is_installed",
    "guarded_apply_patches",
]

# Modules that are unsafe to import in a probe subprocess because importing them
# has side effects or starts a blocking loop (entry points / GUI). For these we
# skip the import probe and rely on the existing post-write compile check plus
# the pytest gate. They are still snapshotted and rolled back like any other file.
_IMPORT_UNSAFE = {"agent.py", "agent_gui.py"}

# Module-level state for an idempotent, reversible install.
_ORIGINAL_APPLY: Optional[Callable] = None
_GUARD: Optional[SafeModificationGuard] = None

# A file snapshot: (absolute_path, existed_before, original_text_or_None)
_Snapshot = Tuple[str, bool, Optional[str]]


def is_installed() -> bool:
    """True if the runtime guard is currently wrapping _apply_patches."""
    return _ORIGINAL_APPLY is not None


def _snapshot(self_mod_module, names: Sequence[str]) -> List[_Snapshot]:
    """Capture current on-disk state for every candidate target, in memory."""
    snaps: List[_Snapshot] = []
    for fname in names:
        abspath = self_mod_module._project_path(fname)
        if os.path.exists(abspath):
            try:
                with open(abspath, encoding="utf-8", errors="ignore") as fh:
                    snaps.append((abspath, True, fh.read()))
            except Exception as exc:  # unreadable — treat as untouched
                log.warn(f"Self-mod guard: snapshot read failed for {abspath}: {exc}")
                snaps.append((abspath, True, None))
        else:
            snaps.append((abspath, False, None))
    return snaps


def _rollback(snaps: Sequence[_Snapshot]) -> None:
    """Restore every snapshot: rewrite originals, delete files that were new."""
    for abspath, existed, original in snaps:
        try:
            if existed:
                if original is not None:
                    with open(abspath, "w", encoding="utf-8") as fh:
                        fh.write(original)
            elif os.path.exists(abspath):
                os.remove(abspath)
        except Exception as exc:
            log.warn(f"Self-mod guard: rollback failed for {abspath}: {exc}")


def _verify_targets(self_mod_module, updated: Sequence[str]):
    """Build the {fname: (abspath, code)} map verified via import probe.

    Entry-point modules are excluded from the import probe (see _IMPORT_UNSAFE);
    they are still covered by the pytest gate.
    """
    valid = {}
    for fname in updated:
        if os.path.basename(fname) in _IMPORT_UNSAFE:
            continue
        abspath = self_mod_module._project_path(fname)
        code = ""
        if os.path.exists(abspath):
            try:
                with open(abspath, encoding="utf-8", errors="ignore") as fh:
                    code = fh.read()
            except Exception:
                code = ""
        valid[fname] = (abspath, code)
    return valid


def guarded_apply_patches(
    self_mod_module,
    original_apply: Callable,
    guard: SafeModificationGuard,
    patches: dict,
    *,
    run_tests: Optional[bool] = None,
) -> List[str]:
    """Snapshot -> original apply -> verify -> commit or atomic rollback.

    Returns the same shape the original _apply_patches returns (a list of
    updated filenames). On verification failure it returns [] after rolling
    back, which the existing handler already treats as "nothing applied".
    """
    if not patches:
        return original_apply(patches)

    # Snapshot the full candidate set up-front so multi-file edits are one unit.
    snaps = _snapshot(self_mod_module, list(patches.keys()))

    # Run the existing apply path untouched.
    updated = original_apply(patches)

    # Nothing written (rejected by safety/review) -> preserve existing behavior.
    if not updated:
        return updated

    effective_run_tests = guard.run_tests if run_tests is None else run_tests
    verify_valid = _verify_targets(self_mod_module, updated)
    issues = guard._verify_runtime(verify_valid, run_tests=effective_run_tests)

    if issues:
        _rollback(snaps)
        for issue in issues:
            log.warn(
                "Self-mod verification failed — changes rolled back "
                f"[{issue.stage}] {issue.target}: {issue.detail}"
            )
        return []

    log.info(f"Self-mod verified and committed ({len(updated)} file(s))")
    return updated


def install(
    self_mod_module=None,
    *,
    guard: Optional[SafeModificationGuard] = None,
    runner: Optional[Callable] = None,
    run_tests: Optional[bool] = None,
) -> bool:
    """Wrap self_mod._apply_patches with verify-and-rollback. Idempotent.

    Returns True if newly installed, False if it was already installed.
    """
    global _ORIGINAL_APPLY, _GUARD

    if self_mod_module is None:
        import self_mod as self_mod_module

    # Idempotent: never double-wrap.
    if is_installed() or getattr(
        getattr(self_mod_module, "_apply_patches", None), "_runtime_guard", False
    ):
        return False

    root = self_mod_module._get_project_root()
    _GUARD = guard or SafeModificationGuard(root=root, runner=runner)
    original = self_mod_module._apply_patches
    _ORIGINAL_APPLY = original

    def _wrapped(patches):
        return guarded_apply_patches(
            self_mod_module, original, _GUARD, patches, run_tests=run_tests
        )

    _wrapped._runtime_guard = True
    self_mod_module._apply_patches = _wrapped
    log.info("Self-mod runtime guard installed")
    return True


def uninstall(self_mod_module=None) -> bool:
    """Restore the original _apply_patches. Returns True if something changed."""
    global _ORIGINAL_APPLY, _GUARD

    if self_mod_module is None:
        import self_mod as self_mod_module

    if _ORIGINAL_APPLY is None:
        return False

    self_mod_module._apply_patches = _ORIGINAL_APPLY
    _ORIGINAL_APPLY = None
    _GUARD = None
    log.info("Self-mod runtime guard uninstalled")
    return True