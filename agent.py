"""
agent.py — Entry point only.
All logic lives in dedicated modules:
  chat_handler.py     — conversation + generation
  session_manager.py  — history, context, project memory
  shutdown_manager.py — signals, atexit, background executor
  tool_registry.py    — TOOL_REGISTRY + get_tool()
  self_mod.py         — self-modification (isolated)
  model_router.py     — intent + domain detection
  llm_client.py       — LLM calls
  state_manager.py    — shared mutable state
  logger.py           — structured logging
"""

import sys
import os

# Encoding fix — must run before any print
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stdin.reconfigure(encoding="utf-8")

from logger          import log, safe_print
from state_manager   import _state, chat_history, project_context
import llm_client

from model_router    import detect_mode
from file_handler    import detect_intent, inject_globals as _fh_inject
from session_manager import (save_session, load_all_sessions,
                              save_project_context, load_project_context)
from shutdown_manager import run_in_background, register_shutdown_hooks
from tool_registry   import get_tool, BACKGROUND_TOOLS
from env_check       import check_and_exit_if_missing
from metrics         import metrics
from profiler        import profiler
from domain_sandbox  import print_health_report
from recovery        import get_checkpoint_manager

# Thread-safe model switch
from threading import Lock as _Lock
_model_lock = _Lock()

def _switch_model(new_model: str):
    with _model_lock:
        llm_client.DEFAULT_MODEL = new_model
    log.info(f"Model switched to {new_model}")
    print(f"🔄 تم تحويل الـ Agent بنجاح إلى الموديل: {new_model}")

# Startup
check_and_exit_if_missing()
register_shutdown_hooks()

_fh_inject(
    safe_chat=llm_client.safe_chat,
    get_response=llm_client.get_response,
    log=log,
    _state=_state,
    project_context=project_context,
    safe_print=safe_print,
    save_project_context=save_project_context,
)

load_project_context()
log.success("AGENT READY — type your request")

# Main loop
while True:
    try:
        user = input().strip()
        _state.last_user_input = user

        if user.startswith("/model "):
            _switch_model(user.replace("/model", "").strip())
            continue

        if user in ("⛔ STOP_AGENT", "STOP_AGENT"):
            print("⛔ Stopped.", flush=True)
            continue

        if user.lower() == "exit":
            break

        if not user:
            continue

        intent = detect_intent(user)
        if intent != "default":
            _state.active_intent = intent

        if user.startswith("load_session "):
            sid = user.replace("load_session ", "").strip()
            for s in load_all_sessions():
                if s["id"] == sid:
                    chat_history.clear()
                    chat_history.extend(s["messages"])
                    _state.current_session_id = sid
                    break
            continue

        if user == "new_chat":
            chat_history.clear()
            _state.current_session_id = None
            continue

        if user.strip() == "metrics":
            metrics.print_dashboard()
            metrics.save()
            continue

        if user.strip() == "profile":
            profiler.report()
            continue

        if user.strip() == "health":
            print_health_report()
            continue

        if user.strip() == "checkpoints":
            get_checkpoint_manager().print_resumable()
            continue

        if user.startswith("/resume "):
            project_name = user.replace("/resume", "").strip()
            from chat_handler import chat_tool
            cp = get_checkpoint_manager().load(project_name)
            if cp:
                safe_print(f"♻️  Resuming '{project_name}'...")
                run_in_background(chat_tool, cp.task,
                                  **{"_hint_domain": cp.engine, "_resume": True})
            else:
                safe_print(f"❌ No resumable checkpoint found for '{project_name}'")
            continue

        mode, detected_domain = detect_mode(user)
        tool = get_tool(mode)

        if mode in BACKGROUND_TOOLS:
            kw = {"_hint_domain": detected_domain} if detected_domain != "general" else {}
            run_in_background(tool, user, **kw)
        else:
            tool(user)

    except KeyboardInterrupt:
        print("\nExiting...")
        break
    except Exception as e:
        safe_print(f"❌ Critical Error: {e}")
