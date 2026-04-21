# self_mod.py — Agent self-modification with web search + model escalation
#
# Flow:
#   1. Web search for how to implement the requested feature
#   2. Read the target file(s) to understand current code
#   3. Generate a PATCH (not full rewrite) using escalation ladder
#   4. Validate syntax + run safety checks
#   5. Backup → apply → report
#
# The agent can now answer "add X feature to yourself" reliably.

import os
import re
import ast
import time
import shutil
import textwrap

from logger     import log, safe_print
from llm_client import safe_chat, get_response
import llm_client

# ── Protected files — NEVER auto-modified ────────────────────────────────────
_PROTECTED = {
    "self_mod.py", "shutdown_manager.py", "session_manager.py",
    "state_manager.py", "logger.py", "llm_client.py", "process_registry.py",
    "recovery.py", "errors.py", "config.py",
}

# ── Files the agent may modify ────────────────────────────────────────────────
_MODIFIABLE = {
    "agent.py", "chat_handler.py", "generation_engine.py",
    "script_generator.py", "script_reviewer.py", "project_builder.py",
    "planner.py", "file_handler.py", "model_router.py",
    "project_tools.py", "model_advisor.py", "compiler_tools.py",
    "unity_pipeline.py", "tool_registry.py",
}

# Max chars to read from each source file as context for the LLM
_FILE_READ_LIMIT = 3000   # keep prompt small to avoid 402 credit errors


# ══════════════════════════════════════════════════════════════
# 1. WEB SEARCH
# ══════════════════════════════════════════════════════════════

def _web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web for implementation guidance.
    Returns a formatted string of results, or empty string on failure.
    """
    try:
        try:
            from ddgs import DDGS as _DDGS
        except ImportError:
            from duckduckgo_search import DDGS as _DDGS
        results = []
        with _DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = r.get("title", "")
                body  = r.get("body",  "")[:300]
                href  = r.get("href",  "")
                results.append(f"• {title}\n  {body}\n  {href}")
        return "\n\n".join(results) if results else ""
    except ImportError:
        safe_print("⚠️  duckduckgo-search not installed — skipping web search. Run: pip install duckduckgo-search")
        return ""
    except Exception as e:
        log.warn(f"Web search failed: {e}")
        return ""


# ══════════════════════════════════════════════════════════════
# 2. TARGET FILE DETECTION
# ══════════════════════════════════════════════════════════════

def _detect_target_files(task: str) -> list[str]:
    """
    Decide which file(s) to patch based on the task description.
    Returns list of filenames (relative to project root).
    """
    t = task.lower()
    candidates = []

    # Keyword → file mapping
    KEYWORD_MAP = [
        (["model", "llm", "openrouter", "api key", "provider"],         "llm_client.py"),
        (["router", "intent", "detect mode", "route"],                   "model_router.py"),
        (["chat", "conversation", "response", "stream"],                  "chat_handler.py"),
        (["plan", "script list", "fallback"],                             "planner.py"),
        (["generate", "generation", "engine", "template"],                "generation_engine.py"),
        (["advisor", "quality", "escalat"],                               "model_advisor.py"),
        (["file", "attach", "upload", "pdf", "image"],                    "file_handler.py"),
        (["project tool", "job", "delete", "run python"],                 "project_tools.py"),
        (["unity", "csharp", "c#", "compile"],                            "compiler_tools.py"),
        (["pipeline", "fix", "auto fix"],                                 "unity_pipeline.py"),
        (["tool registry", "register", "command"],                        "tool_registry.py"),
        (["review", "reviewer"],                                           "script_reviewer.py"),
        (["agent", "main loop", "startup"],                               "agent.py"),
    ]

    for keywords, filename in KEYWORD_MAP:
        if any(kw in t for kw in keywords):
            if filename not in _PROTECTED:
                candidates.append(filename)

    # Explicit file name mentioned?
    for f in _MODIFIABLE:
        if f.replace(".py", "").replace("_", " ") in t or f in task:
            if f not in candidates:
                candidates.append(f)

    # Filter to files that actually exist
    existing = [f for f in candidates if os.path.exists(f)]

    # Fallback: let the LLM decide from the modifiable set
    if not existing:
        existing = [f for f in _MODIFIABLE if os.path.exists(f)][:6]

    return existing[:3]   # max 3 files to keep context manageable


# ══════════════════════════════════════════════════════════════
# 3. CODE PATCH GENERATION (with escalation)
# ══════════════════════════════════════════════════════════════

def _read_file_snippet(filepath: str) -> str:
    """Read up to _FILE_READ_LIMIT chars of a source file."""
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            content = f.read(_FILE_READ_LIMIT)
        if len(content) == _FILE_READ_LIMIT:
            content += "\n# ... (file truncated)"
        return content
    except Exception:
        return ""


def _build_prompt(task: str, target_files: list[str], search_results: str) -> str:
    """Build the LLM prompt for code generation."""

    files_block = ""
    for fp in target_files:
        snippet = _read_file_snippet(fp)
        if snippet:
            files_block += f"\n\n### {fp}\n```python\n{snippet}\n```"

    search_block = (
        f"\n\nWEB SEARCH RESULTS (implementation guidance):\n{search_results}"
        if search_results else ""
    )

    return f"""You are an expert Python developer modifying an AI agent's source code.

TASK: {task}
{search_block}

CURRENT SOURCE FILES:{files_block}

INSTRUCTIONS:
1. Implement the requested feature by modifying ONE file shown above.
2. Output the COMPLETE updated file using this format:

===FILE: filename.py===
```python
<complete updated file content here>
```

STRICT RULES:
- You MUST use the ===FILE: filename.py=== header exactly as shown.
- Keep ALL existing code — only ADD what is needed for the task.
- No placeholders, no TODO, no empty functions.
- Valid Python syntax only.
- Output ONLY the file block. No explanations.
"""


def _generate_patch(task: str, target_files: list[str],
                    search_results: str) -> dict[str, str]:
    """
    Generate code patches using the escalation ladder.
    Returns {filename: new_code} for files to update.
    """
    from model_advisor import ESCALATION_LADDER, _models_above, assess_quality

    prompt   = _build_prompt(task, target_files, search_results)
    messages = [
        {"role": "system", "content": "You are a Python expert. Output ONLY file blocks in the format ===FILE: name.py==="},
        {"role": "user",   "content": prompt},
    ]

    # Try models from current → up the ladder
    current = llm_client.DEFAULT_MODEL
    models_to_try = [current] + _models_above(current)

    best_patches: dict[str, str] = {}
    best_score = -1

    for model_alias in models_to_try:
        safe_print(f"   🔁 Trying {model_alias}...", flush=True)
        try:
            # Limit output tokens for cloud models to avoid 402 credit errors
            import llm_client as _lc
            _resolved = _lc.MODEL_ALIASES.get(model_alias, model_alias)
            _is_cloud  = "/" in _resolved
            _kwargs    = {"max_tokens": 2000} if _is_cloud else {}
            r        = safe_chat(model=model_alias, messages=messages, **_kwargs)
            response = get_response(r)
            patches  = _parse_file_blocks(response, target_files)

            if not patches:
                continue

            # Score the patches
            total_score = 0
            valid_count = 0
            for fname, code in patches.items():
                try:
                    ast.parse(code)   # syntax check
                    score, _ = assess_quality(f"```python\n{code}\n```", "python")
                    total_score += score
                    valid_count += 1
                except SyntaxError:
                    pass

            avg_score = total_score / valid_count if valid_count else 0
            safe_print(f"   📊 {model_alias}: {valid_count}/{len(patches)} files valid, avg score={avg_score:.0f}")

            if avg_score > best_score and valid_count == len(patches):
                best_score   = avg_score
                best_patches = patches

            if avg_score >= 70 and valid_count == len(patches):
                safe_print(f"   ✅ Good patch from {model_alias}")
                break

        except Exception as e:
            log.warn(f"Self-mod model {model_alias} failed: {e}")
            continue

    return best_patches


def _parse_file_blocks(response: str, allowed_files: list[str]) -> dict[str, str]:
    """
    Parse code blocks from LLM response.
    Accepts both:
      - ===FILE: filename.py===  (preferred)
      - Plain ```python blocks   (fallback when model ignores format)
    Returns {filename: code_content}.
    """
    patches: dict[str, str] = {}

    # ── Primary: ===FILE: filename.py=== header ───────────────────────────────
    pattern = r"===FILE:\s*([^\s=]+\.py)===\s*```(?:python)?\n(.*?)```"
    for match in re.finditer(pattern, response, re.DOTALL):
        fname = match.group(1).strip()
        code  = match.group(2).strip()
        if fname in _PROTECTED:
            safe_print(f"🛡️  Skipping protected file: {fname}")
            continue
        if fname not in _MODIFIABLE and fname not in allowed_files:
            safe_print(f"⚠️  Skipping unlisted file: {fname}")
            continue
        patches[fname] = code

    # ── Fallback: plain ```python block (local models often skip the header) ──
    if not patches and len(allowed_files) == 1:
        fallback_pat = r"```python\n(.*?)```"
        matches = list(re.finditer(fallback_pat, response, re.DOTALL))
        if matches:
            # Take the longest block — most likely to be the full file
            best = max(matches, key=lambda m: len(m.group(1)))
            code = best.group(1).strip()
            fname = allowed_files[0]
            if fname not in _PROTECTED:
                safe_print(f"📎 Fallback: using plain ```python block for {fname}")
                patches[fname] = code

    return patches


# ══════════════════════════════════════════════════════════════
# 4. SAFETY VALIDATION
# ══════════════════════════════════════════════════════════════

_DANGEROUS_PATTERNS = [
    r"os\.system\s*\(",
    r"subprocess\.call\s*\(",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__\s*\(",
    r"shutil\.rmtree\s*\(['\"]\/",        # rm -rf /
    r"open\s*\(['\"][\/\\]etc",           # /etc access
]


def _safety_check(code: str, filename: str) -> tuple[bool, str]:
    """Return (is_safe, reason). Rejects obviously dangerous code."""
    for pat in _DANGEROUS_PATTERNS:
        if re.search(pat, code):
            return False, f"Dangerous pattern detected: {pat}"

    # Syntax check
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"

    # Minimum size
    lines = [l for l in code.splitlines() if l.strip() and not l.strip().startswith("#")]
    if len(lines) < 5:
        return False, f"Too short ({len(lines)} non-comment lines)"

    return True, "ok"


# ══════════════════════════════════════════════════════════════
# 5. APPLY PATCHES
# ══════════════════════════════════════════════════════════════

def _apply_patches(patches: dict[str, str]) -> list[str]:
    """
    Backup + write each patch.
    Returns list of successfully updated filenames.
    """
    updated = []
    for fname, code in patches.items():
        ok, reason = _safety_check(code, fname)
        if not ok:
            safe_print(f"❌ {fname} rejected: {reason}")
            continue

        # Backup
        if os.path.exists(fname):
            backup = f"{fname}.{int(time.time())}.bak"
            shutil.copy2(fname, backup)
            log.info(f"Backup: {backup}")

        # Write
        try:
            with open(fname, "w", encoding="utf-8") as f:
                f.write(code)
            log.success(f"✅ {fname} updated")
            updated.append(fname)
        except Exception as e:
            log.error(f"Write failed for {fname}: {e}")

    return updated


# ══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════

def self_mod_tool(task: str):
    """
    Agent modifies its own source files to add a new feature.

    Steps:
    1. Web search for implementation guidance
    2. Detect target files
    3. Generate patch using model escalation
    4. Validate + backup + apply
    5. Report result
    """
    safe_print(f"\n🔧 Self-modification: {task}", flush=True)

    # ── 1. Web search ────────────────────────────────────────────────────────
    search_query   = f"Python how to implement {task} in an AI agent"
    safe_print("🔍 Searching web for implementation guidance...", flush=True)
    search_results = _web_search(search_query, max_results=4)
    if search_results:
        safe_print(f"✅ Got {search_results.count('•')} search results")
    else:
        safe_print("⚠️  No web results — proceeding without search context")

    # ── 2. Detect target files ────────────────────────────────────────────────
    target_files = _detect_target_files(task)
    safe_print(f"📁 Target files: {', '.join(target_files)}", flush=True)

    # ── 3. Generate patch ─────────────────────────────────────────────────────
    safe_print("⚙️  Generating code patch (escalation ladder)...", flush=True)
    patches = _generate_patch(task, target_files, search_results)

    if not patches:
        safe_print("❌ No valid patches generated — self-mod aborted.", flush=True)
        return

    # Score too low = risky patch, don't apply
    # (prevents broken code like "_hint" instead of "_hint_domain")
    best_score_check = -1
    for fname, code in patches.items():
        try:
            from model_advisor import assess_quality
            s, _ = assess_quality(f"```python\n{code}\n```", "python")
            best_score_check = max(best_score_check, s)
        except Exception:
            best_score_check = 50
    if best_score_check < 65:
        safe_print(
            f"⚠️  Patch quality too low (score={best_score_check}/100) — NOT applied.\n"
            f"   Try rephrasing or use a stronger model (/model claude).",
            flush=True
        )
        return

    safe_print(f"📝 Generated patches for: {', '.join(patches.keys())}", flush=True)

    # ── 4. Validate + apply ───────────────────────────────────────────────────
    updated = _apply_patches(patches)

    # ── 5. Report ─────────────────────────────────────────────────────────────
    if updated:
        safe_print(
            f"\n✅ Self-modification complete!\n"
            f"   Updated: {', '.join(updated)}\n"
            f"   ⚠️  Restart the agent to apply changes.\n",
            flush=True
        )
    else:
        safe_print(
            "❌ Self-modification failed — no files were updated.\n"
            "   Try rephrasing the request or check the logs.",
            flush=True
        )
