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
import traceback

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
from session_manager import (load_all_sessions,
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
    # Resolve "local" → actual configured model name before storing
    import config as _cfg
    if new_model == "local":
        resolved = _cfg.DEFAULT_MODEL
    else:
        resolved = llm_client.MODEL_ALIASES.get(new_model, new_model)
        # If alias resolves to a cloud model but OpenRouter isn't configured, warn
        if "/" in resolved and not llm_client.USE_OPENROUTER:
            print(f"⚠️  Model '{new_model}' needs OpenRouter (CLAUDE_CODE_USE_OPENROUTER=1)")
    with _model_lock:
        llm_client.DEFAULT_MODEL = resolved
    log.info(f"Model switched to {resolved} (alias: {new_model})")
    print(f"🔄 تم تحويل الـ Agent بنجاح إلى الموديل: {new_model} → {resolved}")

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

# ── Help menu ─────────────────────────────────────────────────────────────────
def _print_help():
    print("""
╔══════════════════════════════════════════════════════════════╗
║                    AGENT COMMANDS                            ║
╠══════════════════════════════════════════════════════════════╣
║  GENERATION                                                  ║
║  make a <game/app/website>   Start a full generation         ║
║  /resume <project>           Resume interrupted generation   ║
║  checkpoints                 List resumable generations      ║
║                                                              ║
║  SELF-MODIFICATION                                           ║
║  add <feature> to yourself   Add a new capability            ║
║  can you edit yourself       Trigger self-mod mode           ║
║  /scan                       List all project .py files      ║
║  /read <file.py>             Read a file (smart summary)     ║
║  /read <file.py> full        Read entire file                ║
║  /diff <file.py>             Diff current vs last backup     ║
║                                                              ║
║  MODEL                                                       ║
║  /model <alias>              Switch active model             ║
║  /model local                Use local ollama model          ║
║  /model or_free              Use OpenRouter free model       ║
║  /model or_deepseek          Use DeepSeek free               ║
║  /model kimi                 Use Kimi K2.5 (paid)            ║
║  /model claude               Use Claude Sonnet (paid)        ║
║                                                              ║
║  SESSION                                                     ║
║  new_chat                    Start new conversation          ║
║  attach <path>               Attach a file to context        ║
║  metrics                     Show performance dashboard      ║
║  profile                     Show timing profiler            ║
║  health                      Show domain health report       ║
║  /date                       Show today's date               ║
║  /time                       Show current time               ║
║  /weather                     Show weather info              ║
║  exit                        Quit the agent                  ║
╚══════════════════════════════════════════════════════════════╝
""", flush=True)


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

        # ── Confirmation intercept ────────────────────────────────────────────
        # Only intercept YES/NO when self_mod is explicitly waiting for an answer
        try:
            from self_mod import is_waiting_for_confirmation, provide_confirmation
            if is_waiting_for_confirmation() and user.strip().upper() in ("YES", "Y", "NO", "N"):
                provide_confirmation(user)
                continue
        except ImportError:
            pass

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

        if user.strip() == "/scan":
            from self_mod import scan_tool
            scan_tool()
            continue

        if user.strip().startswith("/read "):
            parts = user.strip().split()
            fname = parts[1] if len(parts) > 1 else ""
            full  = len(parts) > 2 and parts[2].lower() == "full"
            if fname:
                from self_mod import read_tool, read_full_tool
                (read_full_tool if full else read_tool)(fname)
            continue

        if user.strip().startswith("/diff "):
            fname = user.strip().replace("/diff", "").strip()
            if fname:
                from self_mod import diff_tool
                diff_tool(fname)
            continue

        if user.strip() == "/status":
            from tool_registry import TOOL_REGISTRY
            TOOL_REGISTRY["STATUS"](user)
            continue

        if user.strip() == "/time":
            from tool_registry import TOOL_REGISTRY
            if "TIME" in TOOL_REGISTRY:
                TOOL_REGISTRY["TIME"](user)
            else:
                import datetime
                print(f"\n🕒 Current Time: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            continue

        if user.strip() == "/weather":
            from tool_registry import TOOL_REGISTRY
            if "WEATHER" in TOOL_REGISTRY:
                TOOL_REGISTRY["WEATHER"](user)
            continue

        if user.strip() == "/date":
            from tool_registry import TOOL_REGISTRY
            if "DATE" in TOOL_REGISTRY:
                TOOL_REGISTRY["DATE"](user)
            else:
                import datetime
                print(f"\n📅 Today's Date: {datetime.datetime.now().strftime('%Y-%m-%d')}\n")
            continue

        if user.strip() == "/help":
            print("""
╔══════════════════════════════════════════════════════════╗
║                    AGENT COMMANDS                        ║
╠══════════════════════════════════════════════════════════╣
║  GENERATION                                              ║
║  make a <type> game         Generate Unity/Unreal game   ║
║  build a <type> website     Generate web project         ║
║  /resume <project>          Resume interrupted project   ║
║                                                          ║
║  SELF-MODIFICATION                                       ║
║  add <feature> to yourself  Add new capability           ║
║  edit yourself              Modify own source code       ║
║  /scan                      List all project .py files   ║
║  /read <file>               Read a source file           ║
║  /read <file> full          Read entire file             ║
║  /diff <file>               Diff file vs last backup     ║
║                                                          ║
║  FILES                                                   ║
║  attach <path>              Attach file to context       ║
║  clear                      Clear file context           ║
║                                                          ║
║  MODEL                                                   ║
║  /model <alias>             Switch model                 ║
║  /model local               Use local ollama model       ║
║  /model or_free             Use free OpenRouter model    ║
║  /model or_deepseek         Use DeepSeek free            ║
║  /model kimi                Use Kimi K2.5 (paid)         ║
║  /model claude              Use Claude Sonnet (paid)     ║
║                                                          ║
║  SYSTEM                                                  ║
║  checkpoints                Show resumable generations   ║
║  metrics                    Show performance dashboard   ║
║  health                     Show domain health report    ║
║  profile                    Show profiler report         ║
║  new_chat                   Start new conversation       ║
║  /date                      Show today's date            ║
║  /time                      Show current time            ║
║  /help                      Show this menu               ║
║  /weather                    Show weather info             ║
║  exit                       Exit the agent               ║
╚══════════════════════════════════════════════════════════╝
""", flush=True)
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

    except (KeyboardInterrupt, EOFError):
        # EOFError = stdin closed after Ctrl+C during shutdown — normal, not an error
        print("\nExiting...")
        break
    except Exception as e:
        safe_print(f"❌ Critical Error: {e}")
        safe_print(traceback.format_exc())
