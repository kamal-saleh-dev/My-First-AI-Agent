# model_advisor.py — Model Advisor & Escalation System
#
# If the current model produces low-quality code, automatically retries
# with a stronger model. Keeps trying up the ladder until quality passes
# or all models are exhausted — then returns the best result seen.
#
# Escalation ladder (weakest → strongest):
#   local  →  free_cloud  →  kimi  →  claude
#
# Integration: called from script_generator.generate_single() after generation.

import re
from typing import Optional
from logger import log, safe_print


# ── Escalation ladder ─────────────────────────────────────────────────────────
# Each level is (alias_key, display_name).
# Aliases are resolved via MODEL_ALIASES in llm_client.py.

ESCALATION_LADDER: list[tuple[str, str]] = [
    ("local",      "Local model"),                      # دايماً شغال، مجاني
    ("or_qwen",    "Qwen3 8B Free"),                   # free، سريع
    ("or_deepseek","DeepSeek R1 0528 Free"),            # free، reasoning قوي
    ("or_llama",   "Llama 3.3 70B Free"),              # free، confirmed working
    ("or_free",    "OpenRouter Auto Free"),             # free، بيختار أحسن model تلقائي
    ("gpt54",      "GPT-5.4"),                          # paid
    ("kimi",       "Kimi K2.5"),                        # paid
    ("claude",     "Claude Sonnet"),                    # paid، الأقوى
]

# Map a raw model name → ladder position (for "above current" lookup)
def _ladder_index(model_name: str) -> int:
    """Return the ladder position of model_name, or -1 if not on the ladder."""
    import llm_client
    aliases = getattr(llm_client, "MODEL_ALIASES", {})

    # Resolve the model name to a canonical full ID
    canonical = aliases.get(model_name, model_name)

    for i, (alias, _) in enumerate(ESCALATION_LADDER):
        if alias == model_name:
            return i
        resolved = aliases.get(alias, alias)
        if resolved == canonical or resolved == model_name:
            return i

    # Unknown model → treat as "local" (bottom of ladder)
    return 0


def _models_above(current_model: str) -> list[str]:
    """Return alias keys for every ladder level above current_model."""
    idx = _ladder_index(current_model)
    return [alias for alias, _ in ESCALATION_LADDER[idx + 1:]]


# ── Quality scoring ───────────────────────────────────────────────────────────

# Each issue reduces score. Weights chosen so any single bad issue triggers escalation.
_ISSUE_WEIGHTS: dict[str, int] = {
    "no_code_block":   60,   # model returned no code at all
    "too_short":       40,   # suspiciously short code
    "placeholder":     35,   # TODO / placeholder comments remain
    "compile_error":   25,   # each compile error (capped)
    "validation_fail": 50,   # validate_code() rejected it
}

_ESCALATE_THRESHOLD = 30   # score below this → escalate


def assess_quality(code: str, engine: str,
                   script_name: str = "",
                   generated_context: dict = None,
                   script_names: list = None) -> tuple[int, list[str]]:
    """
    Score code quality 0–100 (100 = perfect).
    Returns (score, [issue descriptions]).
    """
    issues: list[str] = []
    penalty = 0

    # ── 1. Code block present? ────────────────────────────────────────────────
    has_block = bool(re.search(r"```", code))
    if not has_block:
        issues.append("no_code_block: model returned no fenced code block")
        penalty += _ISSUE_WEIGHTS["no_code_block"]

    # ── Extract raw code for further checks ───────────────────────────────────
    raw = re.sub(r"```[a-zA-Z]*\n?", "", code).replace("```", "").strip()

    # ── 2. Too short? ─────────────────────────────────────────────────────────
    lines = [l for l in raw.splitlines() if l.strip()]
    if len(lines) < 12:
        issues.append(f"too_short: only {len(lines)} non-empty lines")
        penalty += _ISSUE_WEIGHTS["too_short"]

    # ── 3. Placeholders / TODO ────────────────────────────────────────────────
    PLACEHOLDER_PATTERNS = [
        r"//\s*(TODO|FIXME|your logic|your code|add logic|implement here|replace this|assuming)",
        r"/\*\s*(TODO|placeholder|implement)\s*\*/",
        r"pass\s*#\s*(TODO|placeholder)",
        r"raise\s+NotImplementedError",
    ]
    for pat in PLACEHOLDER_PATTERNS:
        if re.search(pat, raw, re.IGNORECASE):
            issues.append("placeholder: unimplemented TODO/placeholder found")
            penalty += _ISSUE_WEIGHTS["placeholder"]
            break   # count once

    # ── 4. Validation (syntax / structural) ───────────────────────────────────
    try:
        from compiler_tools import validate_code
        ok, _ = validate_code(raw, script_name or "script")
        if not ok:
            issues.append("validation_fail: validate_code() rejected the output")
            penalty += _ISSUE_WEIGHTS["validation_fail"]
    except Exception:
        pass

    # ── 5. Compile errors (Unity only, requires dotnet) ───────────────────────
    if engine == "unity" and script_name and generated_context is not None:
        try:
            from compiler_tools import compile_check_csharp
            errors = compile_check_csharp(
                script_name, code,
                generated_context or {},
                planned_scripts=script_names or [],
            )
            if errors:
                capped = min(len(errors), 4)   # cap at 4 so score doesn't go negative
                issues.append(f"compile_errors: {len(errors)} error(s) — {errors[0][:80]}")
                penalty += _ISSUE_WEIGHTS["compile_error"] * capped
        except Exception:
            pass   # dotnet unavailable — skip

    score = max(0, 100 - penalty)
    return score, issues


# ── Escalation engine ─────────────────────────────────────────────────────────

def escalate(
    task: str,
    script_name: str,
    script_role: str,
    engine: str,
    current_model: str,
    current_code: str,
    eng_cfg: dict,
    script_pairs: list,
    generated_context: dict,
    model_name: str,            # same as current_model (kept for clarity)
) -> tuple[str, str]:
    """
    Try each model above current_model in the escalation ladder.
    Returns (best_code, model_alias_used).

    If no escalation candidate is available (e.g. no OpenRouter key),
    returns (current_code, current_model) unchanged.
    """
    from llm_client import safe_chat, get_response, MODEL_ALIASES
    import llm_client

    candidates = _models_above(current_model)
    if not candidates:
        return current_code, current_model

    # Track best result across all attempts
    best_code  = current_code
    best_score, best_issues = assess_quality(
        current_code, engine, script_name, generated_context, [p[0] for p in script_pairs]
    )
    best_model = current_model

    safe_print(
        f"🔼 Advisor: '{script_name}' scored {best_score}/100 "
        f"({', '.join(i.split(':')[0] for i in best_issues)}) "
        f"— escalating..."
    )

    for alias in candidates:
        # Skip if this model needs OpenRouter but it's not configured
        resolved = MODEL_ALIASES.get(alias, alias)
        needs_cloud = "/" in resolved   # OpenRouter models have provider/name format
        if needs_cloud:
            if not getattr(llm_client, "USE_OPENROUTER", False):
                log.warn(f"Advisor: skipping {alias} — OpenRouter not configured")
                continue
            if not getattr(llm_client, "cloud_client", None):
                log.warn(f"Advisor: skipping {alias} — cloud_client not initialized")
                continue

        safe_print(f"   🔁 Trying {alias} ({resolved[:40]})...", flush=True)

        try:
            new_code = _regenerate(
                alias, task, script_name, script_role, engine, eng_cfg,
                script_pairs, generated_context, safe_chat, get_response,
            )

            score, issues = assess_quality(
                new_code, engine, script_name,
                generated_context, [p[0] for p in script_pairs],
            )
            safe_print(f"   📊 {alias}: score={score}/100")

            if score > best_score:
                best_code  = new_code
                best_score = score
                best_model = alias
                best_issues = issues

            if score >= (100 - _ESCALATE_THRESHOLD):
                safe_print(f"   ✅ Quality OK with {alias} (score={score})")
                break   # good enough — stop escalating

        except Exception as e:
            log.warn(f"Advisor: {alias} failed — {e}")
            continue

    if best_model != current_model:
        safe_print(f"   🏆 Best result: {best_model} (score={best_score}/100)")
    else:
        safe_print(f"   ⚠️ All escalations failed — keeping original (score={best_score}/100)")

    return best_code, best_model


# ── Re-generation helper ──────────────────────────────────────────────────────

def _regenerate(alias: str, task: str, script_name: str, script_role: str,
                engine: str, eng_cfg: dict, script_pairs: list,
                generated_context: dict, safe_chat, get_response) -> str:
    """Ask a specific model to regenerate a single script from scratch."""
    from script_generator import BLOCK_MAP, WEB_ENGINES, _build_context_block

    block_type    = BLOCK_MAP.get(engine, "csharp")
    context_block = _build_context_block(generated_context)

    if engine in WEB_ENGINES:
        prompt = (
            f"Write a complete, production-ready {eng_cfg['lang']} file "
            f"named {script_name} for: {task}\n\n"
            f"ROLE: {script_role}\n\n"
            "RULES:\n"
            "1. NO placeholders, NO TODO, NO empty functions\n"
            f"2. Return ONLY one ```{eng_cfg['block']} code block"
        )
    else:
        prompt = (
            f"Write a complete {eng_cfg['lang']} script named {script_name} "
            f"for this game: {task}\n\n"
            f"ROLE: {script_role}\n\n"
            f"{context_block}\n\n"
            "RULES:\n"
            f"1. public class {script_name} : MonoBehaviour\n"
            "2. NO placeholders, NO TODO, NO empty methods\n"
            "3. Declare ALL variables before use\n"
            f"4. Return ONLY one ```{block_type} code block"
        )

    r = safe_chat(model=alias, messages=[
        {"role": "system", "content": eng_cfg["system"]},
        {"role": "user",   "content": prompt},
    ])
    return get_response(r)
