# tool_registry.py — All agent tools in one registry
# Extracted from agent.py — adding a new tool means editing ONLY this file

import os
from logger        import log, safe_print
from state_manager import _state, project_context

# ── Lazy tool imports (avoid heavy startup cost) ──────────────────────────────

def _get_chat_tool():
    from chat_handler import chat_tool
    return chat_tool

def _get_project_tools():
    from project_tools import run_python, delete_tool, project_tool, job_tool
    return run_python, delete_tool, project_tool, job_tool

def _get_file_tools():
    from file_handler import attach_tool
    return attach_tool

# ── Individual tool wrappers ──────────────────────────────────────────────────

def _tool_run(user: str):
    from session_manager import load_last_project
    run_python, _, _, _ = _get_project_tools()
    last = load_last_project()
    if last and os.path.exists(last):
        run_python(last)
    else:
        print("❌ No valid project history found.")

def _tool_clear(user: str):
    from session_manager import CONTEXT_FILE
    project_context.clear()
    if os.path.exists(CONTEXT_FILE):
        os.remove(CONTEXT_FILE)
    print("🧹 Project context cleared.")

def _tool_attach(user: str):
    attach_tool = _get_file_tools()
    attach_tool(user.replace("attach", "", 1).strip())

def _tool_self_mod(task: str):
    from self_mod import self_mod_tool
    self_mod_tool(task)

def _tool_delete(task: str):
    _, delete_tool, _, _ = _get_project_tools()
    delete_tool(task)

def _tool_project(task: str):
    _, _, project_tool, _ = _get_project_tools()
    project_tool(task)

def _tool_job(task: str):
    _, _, _, job_tool = _get_project_tools()
    job_tool(task)

# ── Registry ─────────────────────────────────────────────────────────────────
# To add a new tool: add one entry here and implement the function above.

TOOL_REGISTRY: dict = {
    "GAME":     _get_chat_tool,   # resolved lazily at call time
    "PROJECT":  _tool_project,
    "JOB":      _tool_job,
    "DELETE":   _tool_delete,
    "RUN":      _tool_run,
    "ATTACH":   _tool_attach,
    "CLEAR":    _tool_clear,
    "CHAT":     _get_chat_tool,   # resolved lazily at call time
    "SELF_MOD": _tool_self_mod,
}

BACKGROUND_TOOLS = {"GAME", "PROJECT", "JOB", "SELF_MOD", "CHAT"}


def get_tool(mode: str):
    """Return the callable for the given mode. Resolves lazy getters."""
    fn = TOOL_REGISTRY.get(mode)
    if fn is None:
        return _get_chat_tool()
    # Lazy getter — call it to get the actual tool
    if fn is _get_chat_tool:
        return _get_chat_tool()
    return fn
