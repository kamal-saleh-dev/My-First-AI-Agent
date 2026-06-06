# state_manager.py — Agent shared mutable state
# Extracted from agent.py — single source of truth for all state

from threading import Lock

# ── State lock (used for atomic writes to _state primitives) ───────────────
_state_lock = Lock()


class AgentState:
    """
    All mutable agent state in one place.
    Lists (chat_history, project_context) are safe to alias — same object reference.
    Primitives (str, bool, None) MUST be read/written via _state directly.
    """
    def __init__(self):
        self.chat_history          = []     # conversation memory
        self.project_context       = []     # attached file context
        self.current_session_id    = None   # active session ID
        self.current_project_name  = ""     # active project name
        self.awaiting_project_name = False  # waiting for user to supply name
        self.pending_task          = ""     # task deferred until name is given
        self.last_user_input       = ""     # last raw user message
        self.active_intent         = "default"
        self.manual_model          = None   # set by /model ; None = auto-route per task

    def reset_project(self):
        """Clear per-project state after generation completes."""
        self.current_project_name  = ""
        self.awaiting_project_name = False
        self.pending_task          = ""


# ── Singleton instance ──────────────────────────────────────────────
_state = AgentState()

# ── Backward-compatible module-level aliases ───────────────────────────
# Code that does `from state_manager import chat_history` gets the same list
# object as _state.chat_history — mutations are visible everywhere.
chat_history    = _state.chat_history
project_context = _state.project_context


def _set_state(**kwargs):
    """Thread-safe writer for primitive state fields."""
    with _state_lock:
        for k, v in kwargs.items():
            setattr(_state, k, v)
