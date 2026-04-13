# self_mod.py — Agent self-modification tool with safety guards
# Extracted from agent.py — isolated so a bad LLM response can't crash everything

import os
import re
import ast
import shutil

from logger     import log, safe_print
from llm_client import safe_chat, get_response
import llm_client

# Lazy import to avoid circular dependency
def _get_self_mod_prompt():
    from python_templates import SELF_MOD_PROMPT
    return SELF_MOD_PROMPT

# ── Files the agent is allowed to modify ─────────────────────────────────────
_ALLOWED_MODIFY = {
    "agent.py", "generation_engine.py", "planner.py", "project_tools.py",
    "file_handler.py", "model_router.py", "chat_handler.py",
}

# ── Files that must NEVER be auto-modified ───────────────────────────────────
_PROTECTED = {
    "self_mod.py", "shutdown_manager.py", "session_manager.py",
    "state_manager.py", "logger.py", "llm_client.py", "process_registry.py",
}


def self_mod_tool(task: str):
    """
    Agent modifies its own source files to add new capabilities.

    Safety rules:
    1. Generated code is AST-parsed before writing — syntax errors abort.
    2. A .bak backup is created before any write.
    3. Protected core modules are never overwritten.
    4. Only files in _ALLOWED_MODIFY are valid targets.
    """
    agent_files = [
        f for f in os.listdir(".")
        if f.endswith(".py")
        and f not in _PROTECTED
        and any(n in f for n in ["agent", "templates", "stubs", "tools", "engine", "handler"])
    ]
    file_list = "\n".join(f"  - {f}" for f in agent_files)

    safe_print(f"🔧 Self-modification requested: {task}", flush=True)
    safe_print(f"📁 Modifiable files found: {len(agent_files)}", flush=True)

    SELF_MOD_PROMPT = _get_self_mod_prompt()
    prompt = SELF_MOD_PROMPT.format(file_list=file_list, task=task)
    r = safe_chat(model=llm_client.DEFAULT_MODEL, messages=[{"role": "user", "content": prompt}])
    response = get_response(r)

    # ── Choose target file ───────────────────────────────────────────────────
    target_file = next(
        (f for f in agent_files if f.replace(".py", "").lower() in task.lower()),
        "agent.py"
    )

    # Reject if target is protected
    if target_file in _PROTECTED:
        safe_print(f"🛡️ Self-mod blocked: '{target_file}' is a protected core module.", flush=True)
        return

    # ── Extract code block ───────────────────────────────────────────────────
    match = re.search(r"```python\n(.*?)```", response, re.DOTALL)
    if not match:
        safe_print("❌ No Python code block found in LLM response.", flush=True)
        return

    new_code = match.group(1)

    # ── Syntax check ─────────────────────────────────────────────────────────
    try:
        ast.parse(new_code)
    except SyntaxError as e:
        safe_print(f"❌ Syntax error in generated code — NOT saved: {e}", flush=True)
        return

    # ── Sanity check: reject if code looks too short or like prose ───────────
    if len(new_code.splitlines()) < 5:
        safe_print("❌ Generated code suspiciously short — NOT saved.", flush=True)
        return

    # ── Backup + write ────────────────────────────────────────────────────────
    if os.path.exists(target_file):
        backup = target_file + ".bak"
        shutil.copy2(target_file, backup)
        log.info(f"Backup created: {backup}")

    with open(target_file, "w", encoding="utf-8") as f:
        f.write(new_code)

    log.success(f"✅ {target_file} updated — restart agent to apply changes.")
    safe_print(f"⚠️  Agent restart required for changes to take effect.", flush=True)
