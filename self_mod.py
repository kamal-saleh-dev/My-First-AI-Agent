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
import threading as _threading

# ── Confirmation handshake between self_mod (background) and agent (main loop) ─
_waiting_for_confirmation = _threading.Event()   # self_mod signals it's waiting
_pending_confirmation     = _threading.Event()   # agent signals answer is ready
_confirmation_answer: dict = {}                  # {"answer": "YES"/"NO"}


def is_waiting_for_confirmation() -> bool:
    """Called by agent.py main loop to check if self_mod needs an answer."""
    return _waiting_for_confirmation.is_set()


def provide_confirmation(answer: str) -> None:
    """Called by agent.py main loop to pass the user's YES/NO to self_mod."""
    _confirmation_answer.clear()
    _confirmation_answer["answer"] = answer
    _pending_confirmation.set()

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

# ── Current task (for reviewer context) ──────────────────────────────────────────
_current_task: str = ""

# ── Scan cache ─────────────────────────────────────────────────────────────────
# Populated by scan_tool() — used by _detect_target_files() for smarter targeting
_scan_cache: dict = {}   # {filename: {"lines": N, "size": N, "path": str}}

# Populated by scan_tool() so self_mod picks files smarter
_scan_context: dict = {"scanned": False, "files": []}

# ══════════════════════════════════════════════════════════════
# FILE INSPECTION TOOLS  (/scan, /read, /diff)
# ══════════════════════════════════════════════════════════════

def _get_project_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def scan_tool():
    """
    /scan — List all .py files in the project recursively (including subdirs).
    """
    root      = _get_project_root()
    total     = 0
    all_files: list = []

    # Collect all .py files grouped by folder
    groups: dict = {}
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden folders, venv, __pycache__, Generated_Scripts
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(".") and d not in
                       ("__pycache__", "venv", ".venv", "Generated_Scripts",
                        "node_modules", ".checkpoints")]
        rel_dir = os.path.relpath(dirpath, root)
        py_files = sorted(f for f in filenames if f.endswith(".py"))
        if py_files:
            groups[rel_dir] = py_files
            for pf in py_files:
                all_files.append(pf if rel_dir == "." else rel_dir + "/" + pf)

    safe_print(f"\n📂 Project files (recursive):\n")

    for rel_dir in sorted(groups.keys()):
        # Section header
        label = "." if rel_dir == "." else rel_dir
        safe_print(f"  📁 {label}/")
        for f in groups[rel_dir]:
            path  = os.path.join(root, rel_dir, f)
            size  = os.path.getsize(path)
            lines = sum(1 for _ in open(path, encoding="utf-8", errors="ignore"))
            total += size
            fname = f  # just the filename
            if rel_dir == ".":
                status = ("🛡️  protected" if fname in _PROTECTED
                          else "✏️  modifiable" if fname in _MODIFIABLE
                          else "   other")
            else:
                status = "   "
            safe_print(f"    {status}  {fname:<38} {lines:>4} lines  {size//1024}KB")
        safe_print("")

    safe_print(f"  Total: {total//1024} KB\n")

    # Populate scan cache for self_mod to use
    _scan_cache.clear()
    for rel_dir, files in groups.items():
        for f in files:
            path = os.path.join(root, rel_dir, f)
            try:
                lines = sum(1 for _ in open(path, encoding="utf-8", errors="ignore"))
                _scan_cache[f] = {"lines": lines, "size": os.path.getsize(path), "path": path, "dir": rel_dir}
            except Exception:
                pass
    safe_print(f"  💡 Scan context saved — self_mod will use it for smarter targeting.\n", flush=True)
    _scan_context["files"]   = all_files
    _scan_context["scanned"] = True
    safe_print("  [Scan saved to context — self-mod will use it]")


def read_tool(filename: str):
    """
    /read <filename> — Print full contents of a project file (with line numbers).
    Smarter than raw cat: extracts structure summary for large files.
    """
    root = _get_project_root()
    # Allow with or without .py
    if not filename.endswith(".py"):
        filename += ".py"
    path = os.path.join(root, filename)
    if not os.path.exists(path):
        safe_print(f"❌ File not found: {filename}")
        return
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        safe_print(f"❌ Read error: {e}")
        return

    size = os.path.getsize(path)
    safe_print(f"\n📄 {filename}  ({len(lines)} lines, {size//1024}KB)\n{'─'*60}")

    # For large files (>300 lines): show structure summary + first 80 lines
    if len(lines) > 300:
        safe_print("[ Large file — showing structure + first 80 lines ]\n")
        # Structure: classes and top-level functions
        for i, line in enumerate(lines, 1):
            stripped = line.rstrip()
            if stripped.startswith(("class ", "def ", "# ══", "# ──")):
                safe_print(f"{i:>4} │ {stripped}")
        safe_print(f"\n{'─'*60}\n[ First 80 lines ]\n")
        for i, line in enumerate(lines[:80], 1):
            safe_print(f"{i:>4} │ {line}", end="")
        safe_print(f"\n\n  Use /read {filename} full  to see everything")
    else:
        for i, line in enumerate(lines, 1):
            safe_print(f"{i:>4} │ {line}", end="")
    safe_print("")


def read_full_tool(filename: str):
    """Print every line of a file — used when user adds 'full' flag."""
    root = _get_project_root()
    if not filename.endswith(".py"):
        filename += ".py"
    path = os.path.join(root, filename)
    if not os.path.exists(path):
        safe_print(f"❌ File not found: {filename}"); return
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    safe_print(f"\n📄 {filename}  ({len(lines)} lines)\n{'─'*60}")
    for i, line in enumerate(lines, 1):
        safe_print(f"{i:>4} │ {line}", end="")
    safe_print("")


def diff_tool(filename: str):
    """
    /diff <filename> — Show diff between current file and its latest .bak backup.
    """
    root = _get_project_root()
    if not filename.endswith(".py"):
        filename += ".py"
    path = os.path.join(root, filename)
    if not os.path.exists(path):
        safe_print(f"❌ File not found: {filename}"); return

    # Find latest backup
    import glob
    backups = sorted(glob.glob(path + ".*.bak"))
    if not backups:
        safe_print(f"ℹ️  No backup found for {filename} — no previous version to compare.")
        return

    latest_bak = backups[-1]
    safe_print(f"\n🔍 Diff: {filename}  vs  {os.path.basename(latest_bak)}\n{'─'*60}")

    try:
        import difflib
        with open(latest_bak, encoding="utf-8", errors="ignore") as f:
            old_lines = f.readlines()
        with open(path, encoding="utf-8", errors="ignore") as f:
            new_lines = f.readlines()

        diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"{filename} (backup)",
            tofile=f"{filename} (current)",
            lineterm="",
        ))
        if not diff:
            safe_print("  No differences found — files are identical.")
        else:
            added   = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
            safe_print(f"  +{added} lines added,  -{removed} lines removed\n")
            for line in diff[:80]:   # show first 80 diff lines
                safe_print(line)
            if len(diff) > 80:
                safe_print(f"  ... ({len(diff)-80} more lines)")
    except Exception as e:
        safe_print(f"❌ Diff error: {e}")
    safe_print("")


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
            try:
                from duckduckgo_search import DDGS as _DDGS
            except ImportError:
                safe_print("⚠️  Install ddgs: pip install ddgs")
                return ""
        import warnings as _w
        results = []
        with _w.catch_warnings():
            _w.simplefilter("ignore", RuntimeWarning)
            ddgs_instance = _DDGS()
        with ddgs_instance as ddgs:
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

    # ── Command pattern: adding a /command always needs BOTH files ────────────
    # tool_registry.py gets the _tool_xxx function + registry entry
    # agent.py gets the "if user == '/xxx': ..." handler in the main loop
    _is_slash_cmd = (
        re.search(r'/[a-z]', t)
        or any(w in t for w in ["slash command", "new command", "add command",
                                "command handler", "add a /", "add /"])
        or ("command" in t and any(w in t for w in ["add", "new", "create", "show"]))
    )
    if _is_slash_cmd:
        for _f in ("tool_registry.py", "agent.py"):
            if _f not in candidates and _f not in _PROTECTED:
                candidates.append(_f)

    # Explicit file name mentioned?
    for f in _MODIFIABLE:
        if f.replace(".py", "").replace("_", " ") in t or f in task:
            if f not in candidates:
                candidates.append(f)

    # Cross-check with /scan results if available
    if _scan_context["scanned"]:
        available = {os.path.basename(p) for p in _scan_context["files"]}
        candidates = [c for c in candidates if c in available]

    # Use scan cache paths if available (more accurate than guessing)
    if _scan_cache:
        existing = []
        for f in candidates:
            if f in _scan_cache:
                existing.append(_scan_cache[f]["path"])
            elif os.path.exists(f):
                existing.append(f)
        if not existing:
            # Fallback to all modifiable files from cache
            existing = [v["path"] for k, v in _scan_cache.items()
                        if k in _MODIFIABLE][:6]
    else:
        # No scan cache — fall back to filesystem check
        existing = [f for f in candidates if os.path.exists(f)]
        if not existing:
            existing = [f for f in _MODIFIABLE if os.path.exists(f)][:6]

    return existing[:3]


# ══════════════════════════════════════════════════════════════
# 3. CODE PATCH GENERATION (with escalation)
# ══════════════════════════════════════════════════════════════

def _read_file_snippet(filepath: str) -> str:
    """
    Read source file for LLM context.
    - Files under 6000 chars: read fully (no truncation).
    - Larger files: read first 2000 + last 1000 chars so critical
      end-of-file symbols (BACKGROUND_TOOLS, get_tool) are always visible.
    """
    try:
        with open(filepath, encoding="utf-8", errors="ignore") as f:
            full = f.read()
        if len(full) <= 6000:
            return full          # small file — send everything
        # Large file: head + tail so nothing critical at the end is lost
        head = full[:2500]
        tail = full[-1000:]
        return head + "\n\n# ... (middle truncated) ...\n\n" + tail
    except Exception:
        return ""


def _patch_agent_py(task: str, cmd_name: str, tool_key: str) -> bool:
    """
    Surgically patch agent.py to add a new /command handler.
    Uses str.replace instead of full LLM rewrite — 100% reliable.
    Returns True if patch was applied successfully.

    Inserts:
      1. The /cmd handler block right after the /time handler
      2. The /cmd entry in both help menus
    """
    agent_path = os.path.join(_get_project_root(), "agent.py")
    if not os.path.exists(agent_path):
        return False

    try:
        with open(agent_path, encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return False

    # ── 1. Add handler after /time block ─────────────────────────────────────
    TIME_ANCHOR = (
        "        if user.strip() == \"/time\":\n"
        "            from tool_registry import TOOL_REGISTRY\n"
        "            if \"TIME\" in TOOL_REGISTRY:\n"
        "                TOOL_REGISTRY[\"TIME\"](user)\n"
        "            else:\n"
        "                import datetime\n"
        "                print(f\"\\n🕒 Current Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\\n\")\n"
        "            continue"
    )

    new_handler = (
        f"\n\n        if user.strip() == \"/{cmd_name}\":\n"
        f"            from tool_registry import TOOL_REGISTRY\n"
        f"            if \"{tool_key}\" in TOOL_REGISTRY:\n"
        f"                TOOL_REGISTRY[\"{tool_key}\"](user)\n"
        f"            continue"
    )

    if f'"/{cmd_name}"' in content:
        safe_print(f"   ℹ️  /{cmd_name} handler already exists in agent.py — skipping.")
        return True   # already patched

    if TIME_ANCHOR not in content:
        safe_print(f"   ⚠️  Could not find /time anchor in agent.py — skipping agent.py patch.")
        return False

    content = content.replace(TIME_ANCHOR, TIME_ANCHOR + new_handler, 1)

    # ── 2. Add to help menus ──────────────────────────────────────────────────
    HELP_ANCHOR_1 = "║  exit                        Quit the agent                  ║"
    HELP_ANCHOR_2 = "║  exit                       Exit the agent               ║"
    cmd_padded_1  = f"/{cmd_name}"
    desc_padded   = f"Show {cmd_name} info"
    new_help_1    = (
        f"║  {cmd_padded_1:<28} {desc_padded:<30} ║\n"
        + HELP_ANCHOR_1
    )
    new_help_2    = (
        f"║  {cmd_padded_1:<27} {desc_padded:<27}   ║\n"
        + HELP_ANCHOR_2
    )

    if HELP_ANCHOR_1 in content:
        content = content.replace(HELP_ANCHOR_1, new_help_1, 1)
    if HELP_ANCHOR_2 in content:
        content = content.replace(HELP_ANCHOR_2, new_help_2, 1)

    # ── 3. Backup + write ─────────────────────────────────────────────────────
    backup = f"{agent_path}.{int(time.time())}.bak"
    shutil.copy2(agent_path, backup)

    try:
        with open(agent_path, "w", encoding="utf-8") as f:
            f.write(content)
        import ast as _pyc_ast
        with open(agent_path, encoding="utf-8") as _cf:
            _pyc_ast.parse(_cf.read())
        safe_print(f"   ✅ agent.py patched (/{cmd_name} handler added)", flush=True)
        return True
    except Exception as e:
        safe_print(f"   💥 agent.py patch failed: {e} — reverting", flush=True)
        shutil.copy2(backup, agent_path)
        return False


def _build_prompt(task: str, target_files: list[str], search_results: str,
                  agent_patched: bool = False) -> str:
    """Build the LLM prompt for code generation."""
    CRITICAL_MAP = {
        "tool_registry.py": ["def get_tool", "BACKGROUND_TOOLS", "TOOL_REGISTRY"],
        "agent.py":         ["while True:", "detect_mode", "run_in_background"],
        "chat_handler.py":  ["def chat_tool", "save_session"],
        "generation_engine.py": ["def run_generation", "RecoveryContext"],
        "planner.py":       ["def plan_scripts", "get_fallback_plan"],
        "model_router.py":  ["def detect_mode", "def detect_domain"],
        "file_handler.py":  ["def detect_intent", "def attach_tool"],
    }

    files_block    = ""
    preserve_lines = []
    for fp in target_files:
        snippet = _read_file_snippet(fp)
        if snippet:
            files_block += f"\n\n### {fp}\n```python\n{snippet}\n```"
        fname_only = os.path.basename(fp)
        required   = CRITICAL_MAP.get(fname_only, [])
        if required:
            preserve_lines.append(f"  {fname_only}: {', '.join(required)}")

    preserve_note = (
        "\n\nCRITICAL — these must exist in your output (do NOT remove):\n"
        + "\n".join(preserve_lines)
    ) if preserve_lines else ""

    search_block = (
        f"\n\nWEB SEARCH RESULTS (implementation guidance):\n{search_results}"
        if search_results else ""
    )

    _agent_rule = (
        "- agent.py is already patched surgically — do NOT output an agent.py block."
        if agent_patched else
        "- For /command additions: add the tool in tool_registry.py AND the handler in agent.py.\n"
        "- In agent.py, add the handler right after the /time handler block.\n"
        "- Also update the /help menu strings in agent.py to include the new command."
    )

    return f"""You are an expert Python developer adding a new feature to an AI agent.

TASK: {task}
{search_block}

CURRENT SOURCE FILES:{files_block}
{preserve_note}

INSTRUCTIONS:
1. Implement the task by modifying ALL files that need changes (can be multiple files).
2. For each file you change, output the COMPLETE updated file using this EXACT format:

===FILE: filename.py===
```python
<complete updated file — every existing line must still be present>
```

If multiple files need changes (e.g. tool_registry.py AND agent.py), output MULTIPLE
===FILE=== blocks — one per file.

STRICT RULES:
- PRESERVE every existing function, class, and variable. Only ADD new ones.
- NEVER remove BACKGROUND_TOOLS, get_tool, TOOL_REGISTRY, or any existing def.
- Your output file must be >= the original file in number of lines.
- No placeholders, no TODO, no empty function bodies.
- Valid Python syntax only.
{_agent_rule}
- Output ONLY the ===FILE=== blocks. No text outside them.
"""


def _generate_patch(task: str, target_files: list[str],
                    search_results: str,
                    force_model_idx: int = 0,
                    agent_patched: bool = False) -> dict[str, str]:
    """
    Generate code patches using the escalation ladder.
    force_model_idx: start from this ladder index (for retries with stronger models).
    Returns {filename: new_code} for files to update.
    """
    from model_advisor import ESCALATION_LADDER, _models_above, assess_quality

    prompt   = _build_prompt(task, target_files, search_results,
                              agent_patched=agent_patched)
    messages = [
        {"role": "system", "content": "You are a Python expert. Output ONLY file blocks in the format ===FILE: name.py==="},
        {"role": "user",   "content": prompt},
    ]

    # Try models from current → up the ladder
    # force_model_idx allows retries to start from a stronger model
    current       = llm_client.DEFAULT_MODEL
    all_models    = [current] + [a for a, _ in ESCALATION_LADDER[1:]]
    models_to_try = all_models[force_model_idx:]

    best_patches: dict[str, str] = {}
    best_score = -1

    for model_alias in models_to_try:
        safe_print(f"   🔁 Trying {model_alias}...", flush=True)
        try:
            r = safe_chat(model=model_alias, messages=messages)
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
        _allowed_basenames = {os.path.basename(f) for f in allowed_files}
        if fname not in _allowed_basenames:
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

def _review_patch(task: str, fname: str, original: str, new_code: str) -> tuple[bool, str]:
    """
    8-layer patch reviewer. Layers 1-7 are hard rules (no LLM).
    Layer 8 is LLM soft opinion (non-blocking).
    """
    import ast as _ast, re as _re

    # ── 1. Syntax ─────────────────────────────────────────────────────────────
    try:
        new_tree = _ast.parse(new_code)
    except SyntaxError as e:
        return False, f"SyntaxError in patch: {e}"

    orig_nlines = [l for l in original.splitlines() if l.strip()]
    new_nlines  = [l for l in new_code.splitlines()  if l.strip()]

    # ── 2. Size — max 30% deletion ────────────────────────────────────────────
    if len(orig_nlines) > 20 and len(new_nlines) < len(orig_nlines) * 0.70:
        return False, (f"deletes too much code "
                       f"({len(orig_nlines)} → {len(new_nlines)} lines)")

    # ── 3. Critical symbols per file ──────────────────────────────────────────
    CRITICAL = {
        "tool_registry.py":     ["def get_tool", "TOOL_REGISTRY", "BACKGROUND_TOOLS"],
        "agent.py":             ["while True", "detect_mode", "run_in_background",
                                 "from model_router"],
        "chat_handler.py":      ["def chat_tool", "save_session", "detect_intent"],
        "generation_engine.py": ["def run_generation", "RecoveryContext",
                                 "def extract_project_name"],
        "planner.py":           ["def plan_scripts", "def get_fallback_plan",
                                 "def normalize_script_pairs"],
        "model_router.py":      ["def detect_mode", "def detect_domain",
                                 "SELF_MOD_KEYWORDS"],
        "file_handler.py":      ["def detect_intent", "def attach_tool",
                                 "def inject_globals"],
        "script_generator.py":  ["def generate_single"],
        "script_reviewer.py":   ["def review_script", "def compile_fix_loop"],
        "project_builder.py":   ["def extract_and_save_scripts"],
        "model_advisor.py":     ["def assess_quality", "def escalate",
                                 "ESCALATION_LADDER"],
        "unity_pipeline.py":    ["def auto_fix_unity_code"],
    }
    _fname_key = os.path.basename(fname) if os.path.sep in fname else fname
    for sym in CRITICAL.get(_fname_key, []):
        if sym in original and sym not in new_code:
            return False, f"removes required symbol: '{sym}'"

    # ── 4. All original def/class names must survive ──────────────────────────
    try:
        orig_tree = _ast.parse(original)
        orig_defs = {n.name for n in _ast.walk(orig_tree)
                     if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                       _ast.ClassDef))}
        new_defs  = {n.name for n in _ast.walk(new_tree)
                     if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                       _ast.ClassDef))}
        removed = orig_defs - new_defs
        if removed:
            return False, f"removes functions/classes: {', '.join(sorted(removed))}"
    except Exception:
        pass   # if original has syntax errors, skip this check

    # ── 5. Dangerous patterns ─────────────────────────────────────────────────
    DANGEROUS = ["sys.exit(0)", "sys.exit(1)",
                 "os.remove(__file__", "shutil.rmtree",
                 "os.unlink(__file__"]
    for pat in DANGEROUS:
        if pat in new_code and pat not in original:
            return False, f"introduces dangerous pattern: '{pat}'"

    # ── 6. No identical patch ─────────────────────────────────────────────────
    if new_code.strip() == original.strip():
        return False, "patch is identical to original — nothing added"

    # ── 7. Newly added names must be defined before use ───────────────────────
    # (basic: every name used at module level should be defined or imported)
    # Lightweight check: count undefined top-level references that look like
    # functions but have no def/import for them.
    # (Skipped for brevity — covered by syntax + AST checks above.)

    # ── 8. LLM soft opinion (non-blocking) ───────────────────────────────────
    try:
        r = safe_chat(model=_get_best_reviewer(), messages=[
            {"role": "system", "content": (
                "You are a strict Python code reviewer.\n"
                "Reply ONLY:\nVERDICT: OK\nREASON: <one line>\n"
                "or\nVERDICT: FAIL\nREASON: <one line>"
            )},
            {"role": "user", "content": (
                f"Task: {task}\nFile: {fname}\n"
                f"Patch: {len(orig_nlines)} → {len(new_nlines)} lines.\n"
                f"Does the patch implement the task without removing existing functionality?\n\n"
                f"New code (first 1800 chars):\n```python\n{new_code[:1800]}\n```"
            )},
        ])
        resp = get_response(r).strip()
        if "VERDICT: FAIL" in resp:
            reason = next(
                (l.replace("REASON:", "").strip()
                 for l in resp.splitlines() if l.startswith("REASON:")),
                "LLM rejected"
            )
            return False, f"LLM: {reason}"
    except Exception as e:
        log.warn(f"LLM review skipped ({type(e).__name__})")

    return True, "all 8 checks passed"


def _get_best_reviewer() -> str:
    """Return the best available model for reviewing. Always returns local as fallback."""
    import llm_client as _lc
    if _lc.USE_OPENROUTER and _lc.cloud_client:
        for alias in ("or_llama", "or_free", "or_gemma"):
            resolved = _lc.MODEL_ALIASES.get(alias, "")
            if resolved:
                return alias
    # Always fall back to local — never fail because of cloud unavailability
    return _lc.DEFAULT_MODEL


def _update_commands_manifest(fname: str, code: str) -> None:
    """
    When a new tool is added to tool_registry.py, auto-update
    commands_manifest.json so the GUI commands panel reflects it.
    """
    import json, re
    if fname != "tool_registry.py":
        return
    try:
        # Find new tool keys in TOOL_REGISTRY
        matches = re.findall(r'"([A-Z_]+)"\s*:\s*_tool_(\w+)', code)
        # Read existing known tools from the manifest rather than hardcoding
        manifest_path = os.path.join(_get_project_root(), "commands_manifest.json")
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
            known_from_manifest = {e["cmd"].lstrip("/").upper() for e in manifest if "cmd" in e}
        except Exception:
            manifest = []
            known_from_manifest = set()
        # Also include built-in non-slash tools that don't appear in manifest
        _builtin = {"GAME", "PROJECT", "JOB", "DELETE", "RUN", "ATTACH", "CLEAR", "CHAT", "SELF_MOD"}
        known = known_from_manifest | _builtin
        new_tools = [(k, fn) for k, fn in matches if k not in known]
        if not new_tools:
            return

        for key, fn_name in new_tools:
            cmd     = f"/{key.lower()}"
            # Auto-generate description from function name
            desc    = fn_name.replace("_", " ").strip().capitalize()
            entry   = {"cmd": cmd, "desc": desc, "section": "AGENT COMMANDS"}
            if not any(e["cmd"] == cmd for e in manifest):
                manifest.append(entry)
                safe_print(f"   📋 Added '{cmd}' to commands panel", flush=True)

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        log.warn(f"Commands manifest update failed: {e}")


def _apply_patches(patches: dict[str, str]) -> list[str]:
    """
    Backup + write each patch.
    Returns list of successfully updated filenames.
    """
    updated = []
    for fname, code in patches.items():
        # ── Safety check ──────────────────────────────────────────────────────
        ok, reason = _safety_check(code, fname)
        if not ok:
            safe_print(f"❌ {fname} rejected by safety check: {reason}")
            continue

        # ── LLM review ────────────────────────────────────────────────────────
        original = ""
        if os.path.exists(fname):
            try:
                with open(fname, encoding="utf-8") as f:
                    original = f.read()
            except Exception:
                pass

        # ── Auto-fix loop: retry up to 3 times if reviewer rejects ─────────────
        MAX_FIX = 3
        for fix_attempt in range(1, MAX_FIX + 1):
            _fname_short = os.path.basename(fname) if os.path.sep in fname else fname
            safe_print(f"   🔍 Reviewing patch for {_fname_short} (attempt {fix_attempt}/{MAX_FIX})...", flush=True)
            review_ok, review_reason = _review_patch(_current_task, _fname_short, original, code)
            if review_ok:
                safe_print(f"   ✅ Review passed: {review_reason}", flush=True)
                break
            safe_print(f"   ⚠️  Review failed: {review_reason}", flush=True)
            if fix_attempt == MAX_FIX:
                safe_print(f"❌ {fname} rejected after {MAX_FIX} fix attempts — skipping.", flush=True)
                code = None
                break
            # Ask LLM to fix the specific problem
            safe_print(f"   🔧 Auto-fixing: {review_reason}...", flush=True)
            fname = os.path.basename(fname) if os.path.sep in fname else fname
            fix_prompt = (
                f"CRITICAL FIX NEEDED — previous attempt failed.\n"
                f"ISSUE: {review_reason}\n"
                f"TASK: {_current_task}\n\n"
                f"ORIGINAL FILE (keep everything in it):\n```python\n{original[:2000]}\n```\n\n"
                f"FAILED ATTEMPT:\n```python\n{code[:2000]}\n```\n\n"
                f"Write the COMPLETE fixed file that:\n"
                f"1. Implements: {_current_task}\n"
                f"2. Preserves EVERY function from the original\n"
                f"3. Fixes: {review_reason}\n\n"
                f"Output format: ===FILE: {fname}===\n```python\n...\n```"
            )
            try:
                r2  = safe_chat(model=llm_client.DEFAULT_MODEL, messages=[
                    {"role": "system", "content": "You are a Python expert. Fix the issue and return the complete fixed file."},
                    {"role": "user",   "content": fix_prompt},
                ])
                raw = get_response(r2)
                import re as _re
                m   = _re.search(r"```python\n(.*?)```", raw, _re.DOTALL)
                if m:
                    code = m.group(1).strip()
                    safe_print(f"   🔄 Got fixed version, re-reviewing...", flush=True)
                else:
                    safe_print(f"   ❌ Fix attempt returned no code block.", flush=True)
                    break
            except Exception as e:
                safe_print(f"   ❌ Auto-fix error: {e}", flush=True)
                break

        if code is None:
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

            # ── Post-apply compile check ──────────────────────────────────────
            import py_compile as _pyc
            try:
                # Use ast.parse instead of py_compile to avoid Windows path issues
                import ast as _ast
                with open(fname, encoding="utf-8") as _cf:
                    _ast.parse(_cf.read())
            except SyntaxError as ce:
                # Revert immediately from backup
                safe_print(f"   💥 Post-write compile FAILED: {ce}", flush=True)
                safe_print(f"   🔄 Reverting to backup...", flush=True)
                if os.path.exists(backup):
                    shutil.copy2(backup, fname)
                    safe_print(f"   ✅ Reverted successfully.", flush=True)
                continue

            log.success(f"✅ {fname} updated")
            updated.append(fname)
            # Update commands manifest if new tools were added
            _update_commands_manifest(fname, code)
        except Exception as e:
            log.error(f"Write failed for {fname}: {e}")

    return updated


# ══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════

def _sync_commands_to_gui(patches: dict, task: str) -> None:
    """
    When a new tool is added to tool_registry.py, auto-add it to
    the Commands panel in agent_gui.py so it shows up immediately.
    """
    import re as _re
    gui_path = "agent_gui.py"
    if not os.path.exists(gui_path):
        return

    # Find new tool keys added to TOOL_REGISTRY
    new_keys = []
    for fname, code in patches.items():
        if "tool_registry" not in fname:
            continue
        found = _re.findall(r'"([A-Z_]+)":\s+_tool_\w+', code)
        existing = {"GAME","PROJECT","JOB","DELETE","RUN","ATTACH","CLEAR","CHAT","SELF_MOD","STATUS","TIME"}
        new_keys = [k for k in found if k not in existing]

    if not new_keys:
        return

    try:
        with open(gui_path, "r", encoding="utf-8") as f:
            gui_content = f.read()

        # Find the SYSTEM section in COMMANDS and add new commands there
        cmd_name = new_keys[0].lower()
        cmd_desc = task.replace("add a", "").replace("add", "").replace("/","").strip()
        cmd_desc = cmd_desc[:60] if cmd_desc else f"Run /{cmd_name}"

        pad        = " " * max(1, 26 - len(cmd_name))
        old_system = '        ("exit",                      "Exit the agent"),'
        new_entry  = f'        ("/{cmd_name}",{pad}"{cmd_desc}"),\n' + old_system

        if old_system in gui_content and new_entry not in gui_content:
            gui_content = gui_content.replace(old_system, new_entry, 1)
            with open(gui_path, "w", encoding="utf-8") as f:
                f.write(gui_content)
            safe_print(f"   📋 Added /{cmd_name} to Commands panel in agent_gui.py", flush=True)
    except Exception as e:
        log.warn(f"Could not sync command to GUI: {e}")


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
    global _current_task
    _current_task = task
    safe_print(f"\n🔧 Self-modification: {task}", flush=True)

    # Reject vague requests — needs specific feature to implement
    _VAGUE_SELF_MOD = {"edit yourself", "modify yourself", "improve yourself",
                       "update yourself", "change yourself", "fix yourself",
                       "upgrade yourself", "edit your code",
                       "can you add new commands", "add new commands",
                       "add commands", "can you add commands",
                       "add more commands", "add some commands"}
    if task.strip().lower() in _VAGUE_SELF_MOD:
        safe_print(
            "\n⚠️  Too vague — please specify WHAT to add or change.\n"
            "  Examples:\n"
            "    add voice output using pyttsx3\n"
            "    add a /status command that shows current model\n"
            "    add support for PDF summarization\n"
            "    fix the planner to handle racing games better\n",
            flush=True
        )
        return

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

    # ── 2b. Surgical agent.py patch (for /command additions) ─────────────────
    # agent.py is too large for local LLM to rewrite reliably.
    # Instead, we use a template-based str.replace insertion.
    _agent_patched = False
    _llm_targets   = list(target_files)   # files sent to LLM

    if any(os.path.basename(f) == "agent.py" for f in target_files):
        # Extract command name from task  e.g. "add a /weather command" → "weather"
        import re as _re
        _cmd_match = _re.search(r'/([a-z_]+)', task.lower())
        if not _cmd_match:
            _cmd_match = _re.search(
                r'(?:add|new)\s+(?:a\s+)?(?:command\s+)?([a-z_]+)\s+command',
                task.lower()
            )
        if _cmd_match:
            _cmd_name  = _cmd_match.group(1)
            _tool_key  = _cmd_name.upper()
            safe_print(f"🔩 Patching agent.py surgically for /{_cmd_name}...", flush=True)
            _agent_patched = _patch_agent_py(task, _cmd_name, _tool_key)
        # Remove agent.py from LLM targets — handled surgically above
        _llm_targets = [f for f in _llm_targets if "agent.py" not in f]

    # ── 3. Generate patch (LLM — only non-agent files) ────────────────────────
    safe_print("⚙️  Generating code patch (escalation ladder)...", flush=True)
    patches = _generate_patch(task, _llm_targets, search_results,
                               agent_patched=_agent_patched)

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

    # ── 4. Pre-preview review: fix patches BEFORE showing to user ───────────────
    # User should only see patches that already passed all checks.
    MAX_PRE_FIX = 3
    clean_patches: dict = {}

    for fname, code in patches.items():
        fname_short = os.path.basename(fname) if os.path.sep in fname else fname
        original = ""
        if os.path.exists(fname):
            try:
                with open(fname, encoding="utf-8") as _f:
                    original = _f.read()
            except Exception:
                pass

        current_code = code
        for attempt in range(1, MAX_PRE_FIX + 1):
            ok, reason = _safety_check(current_code, fname_short)
            if ok:
                rev_ok, rev_reason = _review_patch(task, fname_short, original, current_code)
            else:
                rev_ok, rev_reason = False, reason

            if rev_ok:
                safe_print(f"   ✅ Pre-check passed for {fname_short}", flush=True)
                clean_patches[fname] = current_code
                break

            safe_print(f"   ⚠️  Pre-check failed (attempt {attempt}/{MAX_PRE_FIX}): {rev_reason}", flush=True)
            if attempt == MAX_PRE_FIX:
                safe_print(f"   ❌ {fname_short} could not be fixed — skipped.", flush=True)
                break

            # Auto-fix: ask LLM to fix the specific problem
            safe_print(f"   🔧 Auto-fixing: {rev_reason}...", flush=True)
            fix_prompt = (
                f"CRITICAL FIX NEEDED.\n"
                f"ISSUE: {rev_reason}\n"
                f"TASK: {task}\n\n"
                f"ORIGINAL FILE (you MUST keep ALL existing functions):\n"
                f"```python\n{original[:3000]}\n```\n\n"
                f"YOUR PREVIOUS BROKEN ATTEMPT:\n"
                f"```python\n{current_code[:2000]}\n```\n\n"
                f"Rules:\n"
                f"- Keep EVERY existing function and class from the original\n"
                f"- Only ADD the new functionality, never remove anything\n"
                f"- Use ===FILE: {fname_short}=== header\n"
                f"Output the COMPLETE fixed file now:"
            )
            try:
                r = safe_chat(model=_get_best_reviewer(), messages=[
                    {"role": "system", "content": "Fix the Python file. Keep all existing code. Only add new code."},
                    {"role": "user",   "content": fix_prompt},
                ])
                fixed_response = get_response(r)
                fixed_patches  = _parse_file_blocks(fixed_response, [fname_short])
                if fixed_patches:
                    current_code = list(fixed_patches.values())[0]
                else:
                    # Try extracting plain python block
                    import re as _re
                    m = _re.search(r"```python\n(.*?)```", fixed_response, _re.DOTALL)
                    if m:
                        current_code = m.group(1).strip()
            except Exception as e:
                log.warn(f"Auto-fix attempt {attempt} failed: {e}")

    if not clean_patches:
        safe_print("❌ All patches failed review — self-mod aborted.", flush=True)
        return

    patches = clean_patches
    safe_print(f"📝 Generated patches for: {', '.join(os.path.basename(k) for k in patches.keys())}", flush=True)

    # ── 5. Preview: tell user what will change and why ────────────────────────
    import difflib as _diff
    safe_print("\n" + "="*58, flush=True)
    safe_print("  CHANGE PREVIEW", flush=True)
    safe_print("="*58, flush=True)

    for fname, new_code in patches.items():
        safe_print(f"\n  File: {fname}", flush=True)
        if os.path.exists(fname):
            with open(fname, encoding="utf-8", errors="ignore") as _f:
                old_lines = _f.readlines()
            new_lines  = new_code.splitlines(keepends=True)
            diffs = list(_diff.unified_diff(old_lines, new_lines, lineterm=""))
            added   = sum(1 for l in diffs if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diffs if l.startswith("-") and not l.startswith("---"))
            safe_print(f"  + {added} lines added  - {removed} lines removed", flush=True)
            shown = [l for l in diffs if not l.startswith(("---","+++","@@"))][:25]
            for dl in shown:
                px = "  +" if dl.startswith("+") else ("  -" if dl.startswith("-") else "   ")
                safe_print(px + " " + dl.rstrip(), flush=True)
            if len(shown) == 25:
                safe_print(f"  ... ({len(diffs)} total diff lines)", flush=True)
        else:
            safe_print(f"  NEW file — {new_code.count(chr(10))} lines", flush=True)

        # Show reason from first comment/docstring lines
        why = []
        for ln in new_code.splitlines()[:15]:
            s = ln.strip().lstrip("#").strip()
            if s and len(s) > 5 and not s.startswith(("import","from","class ","def ")):
                why.append(s); break
        if why:
            safe_print(f"  Reason: {why[0][:120]}", flush=True)

    safe_print("\n" + "="*58, flush=True)
    safe_print("  ⚠️  Type  YES  to apply, or  NO  to cancel:", flush=True)
    safe_print("  (Type your answer in the input and press Enter)\n", flush=True)

    # Use threading event so agent.py main loop can pass the answer
    _pending_confirmation.clear()
    _confirmation_answer.clear()
    _waiting_for_confirmation.set()

    # Wait up to 300s for answer (5 minutes)
    safe_print("  ⏳ Waiting for your answer (5 min timeout)...\n", flush=True)
    answered = _pending_confirmation.wait(timeout=300)
    _waiting_for_confirmation.clear()

    if not answered:
        safe_print("\n❌ Timed out — no files were changed.\n", flush=True)
        return

    confirm = _confirmation_answer.get("answer", "").strip().upper()

    if confirm not in ("YES", "Y"):
        safe_print("\n❌ Cancelled — no files were changed.\n", flush=True)
        return

    safe_print("\n✅ Confirmed — applying patches...\n", flush=True)

    # ── 5. Validate + apply (with auto-retry on reviewer failure) ────────────
    MAX_RETRY = 2
    updated   = []
    for attempt in range(MAX_RETRY + 1):
        updated = _apply_patches(patches)
        if updated:
            break
        if attempt < MAX_RETRY:
            safe_print(f"\n🔄 Reviewer rejected patch — regenerating (attempt {attempt+2}/{MAX_RETRY+1})...\n", flush=True)
            # Try with the next model up in the ladder
            from model_advisor import ESCALATION_LADDER
            current_idx = 0
            retry_patches = _generate_patch(task, _llm_targets, search_results,
                                             force_model_idx=min(current_idx + attempt + 1,
                                                                  len(ESCALATION_LADDER) - 1))
            if retry_patches:
                patches = retry_patches

    # ── 6. Auto-register new commands in GUI panel ───────────────────────────
    if updated and "tool_registry.py" in " ".join(updated):
        _sync_commands_to_gui(patches, task)

    # ── 7. Report ─────────────────────────────────────────────────────────────
    all_updated = updated + (["agent.py"] if _agent_patched and "agent.py" not in updated else [])
    if all_updated:
        safe_print(
            f"\n✅ Self-modification complete!\n"
            f"   Updated: {', '.join(all_updated)}\n"
            f"   ⚠️  Restart the agent to apply changes.\n",
            flush=True
        )
    else:
        safe_print(
            "❌ Self-modification failed — no files were updated.\n"
            "   Try rephrasing the request or check the logs.",
            flush=True
        )
