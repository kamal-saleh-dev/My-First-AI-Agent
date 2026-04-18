# script_reviewer.py — Review pass + compile-fix loop for generated scripts
# Extracted from generation_engine.py
# Responsibility: take raw LLM output → review → return improved code

import re
import config as _cfg
from llm_client import safe_chat, get_response
from unity_pipeline import auto_fix_unity_code
from compiler_tools import compile_check_csharp, llm_fix_compile_errors
from script_generator import WEB_ENGINES, BLOCK_MAP


# ── Role-specific Unity review rules ─────────────────────────────────────────

_ROLE_RULES: dict[str, str] = {
    "player":      "- Player moves with WASD/arrows using Rigidbody2D.velocity — do NOT use transform.Translate",
    "enemy":       "- Asteroid enemies move DOWNWARD (Vector3.down) — do NOT chase player",
    "powerup":     "- PowerUps FALL DOWN (Vector3.down) — NEVER move up",
    "background":  "- Background scrolls LEFT (negative X direction)",
    "spawner":     "- Use spawnPoints array for spawn positions",
    "projectile":  "- Bullet moves in transform.up direction — Destroy after 3 seconds",
    "collectible": "- Collectible stays STILL — Use OnTriggerEnter2D to detect player",
}

_WEB_REVIEW_RULES: dict[str, str] = {
    "html":       "- Replace generic placeholders with real content\n- Ensure all href links point to actual sibling files\n- Keep Bootstrap structure intact",
    "css":        "- Remove any non-CSS lines\n- Keep all :root variables\n- No placeholders",
    "javascript": "- Replace placeholder API endpoints with realistic ones\n- No TODO comments or empty functions",
    "react":      "- Replace all placeholder text with real content\n- Ensure imports are correct",
    "angular":    "- Replace all placeholder text with real content\n- Ensure @Component selector is correct",
    "sql":        "- Replace generic table/column names with domain-appropriate names\n- Ensure all FK references are valid",
    "python":     "- Replace placeholder functions with real implementations\n- No TODO or pass-only functions",
    "dotnet":     "- Replace placeholder controller actions with real implementations\n- No TODO comments",
}


# ── Public API ────────────────────────────────────────────────────────────────

def review_script(script_name: str, script_role: str, engine: str,
                  code_response: str, model_name: str) -> str:
    """
    Run one review/fix pass on a generated script.
    Returns improved code string (falls back to original on failure).
    """
    if engine == "unreal":
        return _review_unreal(script_name, script_role, code_response, model_name)

    if engine in WEB_ENGINES:
        block_type = BLOCK_MAP.get(engine, "html")
        return _review_web(script_name, engine, code_response, model_name, block_type)

    # Unity / default
    extra_rule = _ROLE_RULES.get(script_role, "")
    review_prompt = (
        f"Fix ALL bugs in this Unity C# script named {script_name} (role: {script_role}):\n\n"
        f"ROLE-SPECIFIC RULES (CRITICAL):\n{extra_rule}\n\n"
        "GENERAL BUGS TO FIX:\n"
        "1. Variables used but never declared → declare them\n"
        "2. FindGameObjectsWithTag without GameObject. prefix → fix it\n"
        "3. Null check WRONG: if (x != null) x = GetComponent → RIGHT: if (x == null) x = GetComponent\n"
        "4. Empty method bodies → implement real logic\n"
        f"5. Class name MUST stay exactly: {script_name}\n\n"
        "Return the FIXED script as ONE ```csharp block.\n\n"
        f"Script to fix:\n{code_response}"
    )
    r = safe_chat(model=model_name, messages=[
        {"role": "system", "content": "Unity C# bug fixer. Return ONLY one ```csharp block."},
        {"role": "user",   "content": review_prompt},
    ])
    reviewed = get_response(r)
    if "```" not in reviewed:
        return code_response

    result = auto_fix_unity_code(reviewed)
    # Enforce class name didn't change
    result = re.sub(
        r"(public\s+class\s+)\w+(\s*:\s*MonoBehaviour)",
        rf"\g<1>{script_name}\2",
        result,
    )
    return result


# ── Private helpers ───────────────────────────────────────────────────────────

def _review_unreal(script_name: str, script_role: str,
                   code_response: str, model_name: str) -> str:
    # ── Bug fix: load system prompt via the lazy loader, not a bare name ──────
    from script_generator import _unreal_tpl
    sys_prompt, _, _guct = _unreal_tpl()

    blocks = re.findall(r"```[a-zA-Z]*\n?(.*?)```", code_response, re.DOTALL)
    if len(blocks) < 2:
        print(f"⚠ Only {len(blocks)} block — forcing header+cpp for {script_name}...", flush=True)
        fp = (
            f"Write EXACTLY TWO ```cpp blocks for Unreal class {script_name}.\n"
            f'Block 1 = HEADER (.h): #pragma once, #include "CoreMinimal.h", '
            f'{script_name}.generated.h, UCLASS, GENERATED_BODY(), declarations\n'
            f'Block 2 = CPP (.cpp): #include "{script_name}.h", ALL function implementations\n\n'
            "Output ONLY two code blocks, nothing else."
        )
        r2 = safe_chat(model=model_name, messages=[
            {"role": "system", "content": sys_prompt},
            {"role": "user",   "content": fp},
        ])
        code_response = get_response(r2)

    ref_cpp  = _guct(script_name, script_role)
    ref_note = (
        f"\n\nREFERENCE IMPLEMENTATION (adapt to {script_name}):\n```cpp\n{ref_cpp[:600]}\n```"
        if ref_cpp else ""
    )
    review_prompt = (
        f"Fix this Unreal C++ file: {script_name}\n\n"
        "MANDATORY FIXES:\n"
        "1. #pragma once at top of header\n"
        "2. GENERATED_BODY() in class body\n"
        "3. .generated.h MUST match class name\n"
        "4. ALL float/int UPROPERTY must have REAL C++ = defaults\n"
        "5. EVERY function in CPP must be declared in header\n"
        "6. REPLACE ALL placeholders with REAL code\n"
        "7. Die(): AActor subclass → Destroy(); UActorComponent → GetOwner()->Destroy();\n"
        '8. IsValid: if (IsValid(MyVar)) — NEVER "if (MyVar IsValid())"\n'
        "9. UFUNCTION() macro belongs in HEADER only\n"
        "10. ALL floats initialized with = not Meta=(DefaultValue)\n\n"
        f"Return ONLY the fixed ```cpp blocks (header first, then cpp).\n"
        f"{ref_note}\n\n{code_response}"
    )
    r_rev = safe_chat(model=model_name, messages=[
        {"role": "system", "content": sys_prompt},
        {"role": "user",   "content": review_prompt},
    ])
    reviewed = get_response(r_rev)
    return reviewed if "```" in reviewed else code_response


def _review_web(script_name: str, engine: str,
                code_response: str, model_name: str, block_type: str) -> str:
    rules = _WEB_REVIEW_RULES.get(engine, "- Fix any placeholders or generic content")
    review_prompt = (
        f"Review and fix this {engine} file named {script_name}:\n\n"
        f"RULES TO ENFORCE:\n{rules}\n\n"
        f"Return ONLY one ```{block_type} code block. No explanations.\n\n"
        f"File to fix:\n{code_response}"
    )
    r = safe_chat(model=model_name, messages=[
        {"role": "system", "content": f"You are a senior {engine} developer. Fix code issues and return only a code block."},
        {"role": "user",   "content": review_prompt},
    ])
    reviewed = get_response(r)
    return reviewed if "```" in reviewed else code_response


def compile_fix_loop(script_name: str, code_response: str,
                     generated_context: dict, script_names: list,
                     model_name: str,
                     max_attempts: int = None) -> str:
    """
    Unity-only: run compile-check → LLM fix → repeat up to max_attempts.
    Returns best available code string.
    """
    if max_attempts is None:
        max_attempts = _cfg.COMPILE_FIX_ATTEMPTS

    for attempt in range(max_attempts):
        errors = compile_check_csharp(
            script_name, code_response, generated_context, planned_scripts=script_names
        )
        if not errors:
            return code_response

        print(
            f"🔧 Compile errors ({len(errors)}) — fixing attempt {attempt + 1}/{max_attempts}...",
            flush=True,
        )
        for e in errors[:5]:
            print(f"   {e}", flush=True)

        ctx = ""
        if generated_context:
            ctx_parts = []
            for pn, pc in generated_context.items():
                sigs = [
                    l.strip() for l in pc.split("\n")
                    if any(l.strip().startswith(k) for k in [
                        "public class", "public enum", "public void",
                        "public int", "public float", "public bool", "public static",
                    ])
                ]
                ctx_parts.append(f"// {pn}.cs:\n" + "\n".join(f"  {s}" for s in sigs[:10]))
            ctx = "CONTEXT (existing scripts):\n" + "\n\n".join(ctx_parts)

        fixed = llm_fix_compile_errors(script_name, code_response, errors, model_name, ctx)
        if "```" in fixed:
            code_response = auto_fix_unity_code(fixed)
            code_response = re.sub(
                r"(public\s+class\s+)\w+(\s*:\s*MonoBehaviour)",
                rf"\g<1>{script_name}\2",
                code_response,
            )

    remaining = compile_check_csharp(
        script_name, code_response, generated_context, planned_scripts=script_names
    )
    if remaining:
        print(
            f"⚠️ {script_name} still has {len(remaining)} error(s) after {max_attempts} attempts",
            flush=True,
        )
    return code_response
