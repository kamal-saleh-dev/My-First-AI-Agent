# chat_handler.py — Conversation + generation dispatcher
# Extracted from agent.py — single responsibility: handle one user turn

import os
import sys
import json

from logger import log, safe_print
from state_manager import _state, chat_history, project_context
from llm_client import safe_chat, get_response
import llm_client
from model_router import detect_domain

# ── Import shared constants from generation_engine (single source of truth) ───
# Previously these were duplicated here — now we import to avoid drift.
from generation_engine import CREATION_VERBS as _CREATION_VERBS, WEB_ENGINES as _WEB_DOMAINS
from generation_engine import is_generation_request as _is_generation_request

def _get_model() -> str:
    return llm_client.DEFAULT_MODEL

# ── System prompt builder ─────────────────────────────────────────

def _build_system_prompt(intent: str, working_context: list,
                         domain: str, images: list, videos: list) -> str:
    """Return the right system prompt for this turn."""
    if intent == "compare":
        if videos: return "You are an expert video analyst. Compare the attached videos explicitly."
        if images: return "You are an expert visual analyst. Compare the attached images explicitly."
        return "You are an expert data analyst. Compare the attached files explicitly."
    if intent == "summarize":
        return "You are an expert summarizer. Provide a concise, highly accurate summary of the provided files."
    if intent == "detect_issues":
        return "You are an expert debugger and reviewer. Analyze the provided files to find any bugs, errors, or issues."

    # Default / generation
    if working_context:
        return "You are an elite Game Dev & AI assistant. Answer accurately based on the attached files."

    if domain == "unity":
        return (
            "You are a senior Unity C# developer.\n"
            "Generate ONLY valid Unity C# scripts. Must inherit from MonoBehaviour.\n"
            "No Unreal code. No explanations outside code blocks."
        )
    if domain == "unreal":
        from unreal_templates import UNREAL_SYSTEM_PROMPT
        return UNREAL_SYSTEM_PROMPT
    if domain == "python":
        return (
            "You are a senior Python developer.\n"
            "Generate clean runnable Python code only. No markdown explanations."
        )
    return (
        "You are an autonomous AI agent with full access to your own source code.\n"
        "You CAN modify yourself — use the self-modification system to add new features.\n\n"
        "YOUR KEY SOURCE FILES:\n"
        "  - agent.py            : main loop + all /commands (scan, status, time, help...)\n"
        "  - agent_gui.py        : the GUI window (hologram, chat, sidebar, commands menu)\n"
        "  - chat_handler.py     : conversation + generation dispatcher\n"
        "  - model_router.py     : intent detection (what mode to use)\n"
        "  - self_mod.py         : self-modification system (scan, read, diff, patch)\n"
        "  - tool_registry.py    : all tool functions + TOOL_REGISTRY dict\n"
        "  - generation_engine.py: game/web project generation pipeline\n"
        "  - planner.py          : script planning for game generation\n"
        "  - model_advisor.py    : model escalation ladder\n"
        "  - llm_client.py       : LLM calls + model aliases\n"
        "  - agents/             : multi-agent package (built, not yet wired into runtime)\n"
        "  - plugins/            : Unity/Unreal/Web/Python domain plugins\n"
        "  - tests/              : pytest test files\n\n"
        "When asked about which file does X, answer from the list above.\n"
        "Answer naturally and clearly in the same language the user is speaking."
    )

# ── Context reader ───────────────────────────────────────────────

def _read_text_context(working_context: list) -> str:
    text_context = ""
    for item in working_context:
        if item["type"] in ("image", "video"):
            continue
        text_context += f"\n--- File: {os.path.basename(item['path'])} ---\n"
        if "data" in item:
            text_context += json.dumps(item["data"])
        else:
            try:
                with open(item["path"], "r", encoding="utf-8", errors="ignore") as f:
                    text_context += f.read(1500)
            except Exception as e:
                safe_print(f"⚠ context read error: {e}")
    return text_context

# ── Stream output helper ─────────────────────────────────────────

def _stream_response(stream) -> str:
    """Print a streaming response token-by-token. Returns full text."""
    sys.stdout.write("\n🤖 Agent: ")
    sys.stdout.flush()
    full = ""

    # Guard: safe_chat may return _FallbackResp (not iterable) on total failure
    if not hasattr(stream, "__iter__") or hasattr(stream, "message"):
        full = get_response(stream)
        sys.stdout.write(full)
    else:
        try:
            for chunk in stream:
                word = (
                    chunk.get("message", {}).get("content", "")
                    if isinstance(chunk, dict)
                    else getattr(getattr(chunk, "message", None), "content", "") or ""
                )
                full += word
                sys.stdout.write(word)
                sys.stdout.flush()
        except TypeError:
            full = get_response(stream)
            sys.stdout.write(full)

    sys.stdout.write("\n\n")
    sys.stdout.flush()
    return full

# ── Main chat dispatcher ─────────────────────────────────────────

def chat_tool(task: str, _hint_domain: str = "general", _resume: bool = False):
    """
    Main conversation + generation dispatcher.
    Responsibilities:
        1. Resolve context (files, images, videos)
        2. Route to: generation pipeline | single script | stream chat | file Q&A
        3. Update chat_history and save session
    """
    from file_handler import detect_intent, select_relevant_files
    from session_manager import save_session, smart_trim_history

    if task:
        task = task.strip()
        if task == "Analyze and describe the attached files in detail.":
            task = ""

    # ── Waiting for project name ────────────────────────────────────
    if _state.awaiting_project_name and task:
        _state.current_project_name = task
        _state.awaiting_project_name = False
        print(
            f"\n🤖 Agent: عظيم! تم تحديد اسم البروجكت: '{_state.current_project_name}'."
            " جاري كتابة السكريبت...\n"
        )
        task = _state.pending_task

    if not task:
        count = len(project_context)
        file_word = "file" if count == 1 else "files"
        print(f"📎 Successfully attached {count} {file_word} to project context!")
        if count >= 2:
            print("Tell me what you want to do with them (e.g., compare, summarize).")
        else:
            print("Ask a specific question about this file.")
        _state.active_intent = "default"
        return

    # ── Intent + domain (computed ONCE) ──────────────────────────────
    intent = detect_intent(task)
    _state.active_intent = intent
    domain = _hint_domain if _hint_domain != "general" else detect_domain(task.lower())

    # ── Context resolution ────────────────────────────────────────
    working_context = select_relevant_files(task, project_context)
    images = [i["path"] for i in working_context if i["type"] == "image"]
    videos = [i["path"] for i in working_context if i["type"] == "video"]
    text_ctx = _read_text_context(working_context)

    # اختيار الموديل: اليدوي (/model) له الأولوية، وإلا توجيه تلقائي محلي
    if images:
        model_name = "local_vision"
    elif getattr(_state, "manual_model", None):
        model_name = _state.manual_model
    else:
        from model_router import select_model
        model_name = select_model(intent, domain, task)

    # ── System prompt ────────────────────────────────────────────
    system_prompt = _build_system_prompt(intent, working_context, domain, images, videos)

    # ── Prepend file context to task ───────────────────────────────
    task_with_ctx = (
        f"Context from text files:\n{text_ctx}\n\nUser Task: {task}"
        if text_ctx else task
    )

    # ── History management ────────────────────────────────────────
    chat_history.append({"role": "user", "content": task_with_ctx})
    chat_history[:] = smart_trim_history(chat_history, max_tokens=3000)
    messages = [{"role": "system", "content": system_prompt}] + chat_history

    # ── Force generation pipeline for web/code domains ────────────────────
    if domain in _WEB_DOMAINS and any(w in task.lower() for w in _CREATION_VERBS):
        text_ctx = ""
        images = []
        videos = []

    try:
        # ── No attached files — text-only branch ────────────────────────
        if not text_ctx and not images and not videos:
            _t = task.lower()

            # Python quick-run: generate + sandbox test
            is_python = any(w in _t for w in ["python", "بايثون", "script"])
            is_unity = any(w in _t for w in ["unity", "c#", "combat", "game"])
            if is_python and not is_unity and any(w in _t for w in ["code", "برنامج", "كود"]):
                from generation_engine import auto_run_and_fix
                r = safe_chat(model=model_name, messages=messages)
                initial = get_response(r).replace("```python", "").replace("```", "").strip()
                fixed, output = auto_run_and_fix(task, initial)
                chat_history.append({"role": "assistant", "content": f"```python\n{fixed}\n```"})
                print(f"\n🤖 Agent (Python Verified):\n```python\n{fixed}\n```\n📝 Output: {output}\n")
                return

            # Full generation (game, web app, db…)
            is_full_gen, is_script = _is_generation_request(_t, domain)

            if is_full_gen and is_script:
                from generation_engine import run_generation, detect_engine, extract_project_name
                engine = detect_engine(task, domain)
                if not _state.current_project_name:
                    _state.current_project_name = extract_project_name(task, engine)
                summary = run_generation(
                    task=task, engine=engine, model_name=model_name,
                    project_name=_state.current_project_name,
                    save_session_fn=save_session,
                    resume=_resume,
                )
                chat_history.append({"role": "assistant", "content": summary})
                _state.current_project_name = ""
                return

            # Single script
            if is_script:
                from generation_engine import extract_and_save_scripts, extract_project_name
                if not _state.current_project_name:
                    _state.current_project_name = extract_project_name(task, "unity")
                r = safe_chat(model=model_name, messages=messages)
                code = get_response(r)
                ok = extract_and_save_scripts(code, _state.current_project_name)
                clean = (
                    "عاش يا هندسة! 🫡 الأكواد اتبرمجت واتقسمت صح.\n\n"
                    f"[ 💾 تم حفظ الملفات بنجاح في:"
                    f" Generated_Scripts/{_state.current_project_name.replace(' ','_')} ]"
                    if ok else "⚠️ تم إيقاف الحفظ بسبب أخطاء في الكود."
                )
                print(f"\n🤖 Agent: {clean}\n\n")
                sys.stdout.flush()
                chat_history.append({"role": "assistant", "content": clean})
                _state.current_project_name = ""
                save_session()
                return

            # Plain streaming chat
            stream = safe_chat(model=model_name, messages=messages, stream=True)
            full = _stream_response(stream)
            chat_history.append({"role": "assistant", "content": full})
            save_session()

        else:
            # ── With attached files ─────────────────────────────────
            chat_history[-1]["images"] = images if images else None
            r = safe_chat(
                model=model_name,
                messages=[{"role": "system", "content": system_prompt}] + chat_history,
            )
            result = get_response(r)
            print(f"\n🤖 Agent: {result}\n\n")
            sys.stdout.flush()
            chat_history.append({"role": "assistant", "content": result})
            save_session()

        sys.stdout.flush()

    except Exception as e:
        log.error(f"chat_tool error: {e}")
        if chat_history:
            chat_history.pop()
