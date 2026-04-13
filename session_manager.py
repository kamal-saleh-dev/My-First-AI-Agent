# session_manager.py — Chat session + project context persistence
# Extracted from agent.py — single responsibility: load/save sessions and context

import os
import json
import time as _time

from state_manager import _state, _state_lock, chat_history, project_context
from logger        import safe_print
import config as _cfg

import config as _cfg2
BASE_DIR      = _cfg2.BASE_DIR
MEMORY_FILE   = _cfg2.MEMORY_FILE
CONTEXT_FILE  = _cfg2.CONTEXT_FILE
HISTORY_FILE  = _cfg2.HISTORY_FILE

# ── Project memory (last run path) ────────────────────────────────────────────

def save_last_project(path: str):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write(path)

def load_last_project() -> str | None:
    if not os.path.exists(MEMORY_FILE):
        return None
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

# ── Project context (attached files) ─────────────────────────────────────────

def save_project_context():
    try:
        with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
            json.dump(project_context, f, ensure_ascii=False, indent=2)
    except Exception as e:
        safe_print(f"⚠ Context save error: {e}")

def load_project_context():
    if not os.path.exists(CONTEXT_FILE):
        return
    try:
        with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        _state.project_context.clear()
        _state.project_context.extend(data)
        safe_print(f"🧠 Loaded project context ({len(_state.project_context)} files)")
    except Exception as e:
        safe_print(f"⚠ Context load error: {e}")

# ── Token estimation + history trimming ───────────────────────────────────────

def estimate_tokens(text: str) -> int:
    return len(text) // 4

def smart_trim_history(history: list, max_tokens: int = _cfg.HISTORY_MAX_TOKENS) -> list:
    """Trim oldest non-critical messages to stay under token budget."""
    if not history:
        return history
    if sum(estimate_tokens(m.get("content", "")) for m in history) <= max_tokens:
        return history
    MIN_KEEP = _cfg.HISTORY_MIN_KEEP
    trimmed = list(history)
    while len(trimmed) > MIN_KEEP:
        if sum(estimate_tokens(m.get("content", "")) for m in trimmed) <= max_tokens:
            break
        removed = False
        for i, msg in enumerate(trimmed[:-MIN_KEEP]):
            if not any(k in msg.get("content", "") for k in ["```", "Generated_Scripts", "💾"]):
                trimmed.pop(i)
                removed = True
                break
        if not removed:
            trimmed.pop(0)
    return trimmed

# ── Session persistence ───────────────────────────────────────────────────────

def _session_title(msg: str) -> str:
    words = msg.strip().split()[:6]
    t = " ".join(words)
    return (t[:45] + "...") if len(t) > 45 else t or "New Chat"

def load_all_sessions() -> list:
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        safe_print(f"⚠ load_all_sessions error: {e}")
        return []

def save_session():
    """Atomically persist current chat_history to HISTORY_FILE."""
    if not chat_history:
        return
    if not _state.current_session_id:
        _state.current_session_id = str(int(_time.time()))
    sessions = load_all_sessions()
    title = _session_title(
        next((m["content"] for m in chat_history if m["role"] == "user"), "New Chat")
    )
    for s in sessions:
        if s["id"] == _state.current_session_id:
            s["messages"] = chat_history
            s["title"] = title
            break
    else:
        sessions.append({
            "id":        _state.current_session_id,
            "title":     title,
            "timestamp": _state.current_session_id,
            "messages":  chat_history,
        })
    if len(sessions) > _cfg.HISTORY_MAX_SESSIONS:
        sessions = sessions[-_cfg.HISTORY_MAX_SESSIONS:]
    try:
        with _state_lock:
            tmp = HISTORY_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)
            os.replace(tmp, HISTORY_FILE)
    except Exception as e:
        safe_print(f"⚠ save_session error: {e}")
