# Safe Self-Modification — Runtime Integration (Phase C)

## Status before this step

The safety mechanism (`SafeModificationGuard`), its unit tests, and its design
doc were already in place. However, the **live** `SELF_MOD` runtime did not use
them: `self_mod._apply_patches()` wrote patches to disk with only a per-file
syntax check, so a multi-file change whose later file broke imports (or the test
suite) could be left partially applied. The milestone was therefore incomplete.

## What this step adds

A single, minimal wiring module — `self_mod_runtime_guard.py` — that routes the
real apply path through verify-and-rollback **without touching `self_mod.py`**.

```

detect_mode → SELF_MOD handler

→ _detect_target_files → _generate_patch → review loop

→ CHANGE PREVIEW → YES/NO confirmation        (all UNCHANGED)

→ _apply_patches(patches)  ◀── now wrapped by the runtime guard

```

The wrapper:

1. **Snapshots** every target file in the patch set (recording which are new).
2. Calls the **original** `_apply_patches` unchanged — its safety check, LLM
   review, `.bak` backups and per-file compile-revert all still run.
3. **Verifies** transactionally: subprocess-imports each updated module and
   (optionally) runs `pytest`.
4. On **any** failure, **rolls the whole set back atomically** (restores
   originals, deletes newly created files) and returns `[]`, which the existing
   handler already treats as “no files updated.”

## Why this is the smallest correct integration

- It intercepts the exact `_apply_patches` function used on the live path, so it
  is integration *at the call site*, not a parallel path.
- `self_mod.py` is not modified, redesigned, or rewritten.
- Everything upstream of the write (detect / generate / review / preview /
  confirmation) is untouched.
- `/auto`, `/multi`, and Adaptive Autonomy never call `_apply_patches`, so they
  are unaffected.
- Verification reuses the existing `SafeModificationGuard`; there is one guard
  implementation, not two.

## Activation

The guard is installed once, from the production entry point `agent.py`, during
startup:

```

try:

import self_mod_runtime_guard as _self_mod_guard

_self_mod_guard.install()

except Exception as _guard_err:

log.warn(f"Self-mod runtime guard not installed: {_guard_err}")

```

Because `agent.py` is never imported by the unit-test suite (its module-level
main loop would block), installing here keeps the existing tests completely
unaffected: tests that call `self_mod._apply_patches` directly still hit the
unwrapped function.

## Configuration

The guard reuses `SafeModificationGuard`'s environment configuration:

| Variable | Default | Meaning |
| --- | --- | --- |
| `AGENT_SELF_MOD_RUN_TESTS` | `1` (true) | Run `pytest` as part of verification. |
| `AGENT_SELF_MOD_VERIFY_TIMEOUT` | `30` | Per-module import-probe timeout (seconds). |
| `AGENT_SELF_MOD_TEST_TIMEOUT` | `120` | Test-run timeout (seconds). |

`install(run_tests=...)` overrides the test gate for a given activation.

## Entry-point modules

Modules that have import-time side effects or a blocking loop — `agent.py` and
`agent_gui.py` — are excluded from the import probe (importing them would hang or
restart the app). They are still snapshotted, rolled back, and covered by the
`pytest` gate. This prevents false rollbacks of otherwise-valid edits to those
files.

## Behavioral impact

- Successful self-modifications behave exactly as before.
- A self-modification that breaks imports or the test suite is now rolled back
  instead of left half-applied — the intended additive safety, with no change to
  the user-visible flow.
- The only added cost is verification time (import probe + optional full test
  run) after the user confirms, which is consistent with the existing
  “restart to apply” model.

## Out of scope (intentionally deferred)

Phase 5, Phase 7, Phase 9 sandbox infrastructure, Phase 10 self-improvement
systems, and full stack reconciliation are **not** implemented here.

## Tests

`tests/test_self_mod_runtime_guard.py` covers: idempotent install/uninstall,
successful commit, import-failure rollback, test-failure rollback, multi-file
atomic rollback, removal of newly created files on rollback, pass-through when
nothing is written, the `run_tests` gate (default, disabled, and override), and
entry-point import-probe skipping. All use a fake `self_mod` module and an
injected fake runner — no real subprocess or `pytest` invocation.
