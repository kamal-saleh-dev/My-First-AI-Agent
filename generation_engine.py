# generation_engine.py — Full project/game generation pipeline
# All heavy logic now lives in sub-modules:
#   script_generator.py  — template routing + single-script generation
#   script_reviewer.py   — review pass + compile-fix loop
#   project_builder.py   — script saving + dotnet scaffolding

import os
import re
import sys
import time

from logger         import log, safe_print
from llm_client     import safe_chat, get_response
import llm_client
import config as _cfg
from errors         import GenerationError
from profiler       import profiler
from domain_sandbox import get_sandbox
from recovery       import RecoveryContext, get_checkpoint_manager
from metrics        import metrics
from model_router   import DOMAIN_REGISTRY
from launcher       import launch_website
from unity_pipeline import auto_fix_unity_code

# ── Sub-module imports ────────────────────────────────────────────────────────
from script_generator import (
    generate_single  as _generate_single,
    get_template,
    get_fill_template,
    _get_engine_cfg,
    WEB_ENGINES,
    BLOCK_MAP,
    ENGINE_CFG,
)
from script_reviewer import (
    review_script    as _review_script,
    compile_fix_loop as _compile_fix_loop,
)
from project_builder import (
    extract_and_save_scripts,
    post_process_dotnet as _post_process_dotnet,
)

from planner import (
    plan_scripts, apply_role_fixes, normalize_script_pairs,
    get_fallback_plan, get_unreal_fallback,
    get_cached_plan, set_cached_plan,
)


def _get_model() -> str:
    return llm_client.DEFAULT_MODEL


# ── Creation verb constants — SINGLE SOURCE OF TRUTH ─────────────────────────
# chat_handler.py imports these instead of redeclaring them.

CREATION_VERBS: list[str] = [
    "make", "create", "build", "generate", "write", "design", "setup",
    "اعمل", "انشئ", "اكتب", "ابني", "صمم",
]

_GAME_KW: list[str] = [
    "game", "لعبة", "shooter", "platformer", "runner", "racing", "puzzle",
    "rpg", "tower defense", "unity", "unreal", "اعمل لعبة", "انشئ لعبة",
    "عايز لعبة", "عاوز لعبة", "full game", "كاملة", "كامل",
]


def is_generation_request(task_lower: str, domain: str) -> tuple[bool, bool]:
    """
    Returns (is_complete_generation, is_single_script).
    Single source of truth — imported by chat_handler.py to avoid duplication.
    """
    has_verb    = any(w in task_lower for w in CREATION_VERBS)
    has_game_kw = any(w in task_lower for w in _GAME_KW)
    is_web      = domain in WEB_ENGINES

    is_full = (has_game_kw and (has_verb or has_game_kw)) or (is_web and has_verb)
    is_script = (
        any(w in task_lower for w in [
            "script", "سكريبت", "component", "class",
            "عايز لعبة", "عاوز لعبة",
        ])
        or (has_verb and has_game_kw)
        or (is_web and has_verb)
    )
    return is_full, is_script


# ═══════════════════════════════════════════════════════════
# ENGINE DETECTION
# ═══════════════════════════════════════════════════════════

def detect_engine(task: str, hint_domain: str = "general") -> str:
    """Detect target engine/framework from task text."""
    EXPLICIT: dict[str, list[str]] = {
        "unity":  ["unity", "يونتي"],
        "unreal": ["unreal", "c++", "أنريل", "ue4", "ue5"],
    }
    t = task.lower()
    for eng, kws in EXPLICIT.items():
        if any(kw in t for kw in kws):
            return eng
    if hint_domain in ("unity", "unreal", "dotnet", "react", "angular",
                        "html", "sql", "python"):
        return hint_domain
    return "unity" if "unreal" not in t else "unreal"


# ═══════════════════════════════════════════════════════════
# PROJECT NAME EXTRACTION
# ═══════════════════════════════════════════════════════════

_STOP_WORDS: set[str] = {
    "make", "create", "build", "a", "an", "the", "with", "using", "in", "for",
    "website", "site", "app", "api", "web", "game", "full", "complete", "simple",
    "server", "database", "project", "script", "unity", "unreal", "python",
    "react", "angular", "html", "sql", "fastapi", "flask", "dotnet", "asp",
}


def extract_project_name(task: str, engine: str) -> str:
    """Extract a clean project name from the task description."""
    r = safe_chat(model=_get_model(), messages=[{
        "role": "user",
        "content": (
            "Extract the game or project name from this text. "
            "If none, reply ONLY with 'NONE'. "
            f"Text: '{task}'"
        ),
    }])
    extracted = get_response(r).strip()

    # Treat as NONE if: explicit NONE, too long, or all words are stop words / too generic
    _extracted_words = [w for w in re.sub(r"[^a-z0-9 ]", "", extracted.lower()).split()
                        if w not in _STOP_WORDS and len(w) > 2]
    _is_generic = not _extracted_words or len(extracted) >= 30 or "NONE" in extracted.upper()

    def _task_fallback() -> str:
        words = [
            w for w in re.sub(r"[^a-z0-9 ]", "", task.lower()).split()
            if w not in _STOP_WORDS and len(w) > 2
        ]
        default = "MyGame" if engine in ("unity", "unreal") else "MyProject"
        return "_".join(words[:3]).title() if words else default

    if _is_generic:
        return _task_fallback()

    engine_words = {"unity", "unreal", "godot", "pygame", "monogame", "gamemaker", "cocos"}
    proj_words = [w for w in extracted.strip().lower().split() if w not in engine_words]
    if not proj_words:
        return _task_fallback()
    name = "_".join(w.capitalize() for w in proj_words[:4])[:40] or "MyGame"
    # Strip characters invalid in Windows filenames ( : * ? " < > | / \ )
    name = re.sub(r'[\\/:*?"<>|]', "", name)
    return name or "MyGame"


# ═══════════════════════════════════════════════════════════
# PYTHON PROJECT BUILDER HELPERS  (used by project_tools.py)
# ═══════════════════════════════════════════════════════════

def build_structure(task: str, cwd: str = None) -> list[str]:
    """
    Ask LLM for a Python project file structure and create empty files.
    cwd: base directory for all created files (avoids process-wide os.chdir).
    """
    base = cwd or os.getcwd()
    print("🔨 Designing structure...")
    r = safe_chat(model=_get_model(), messages=[{
        "role": "user",
        "content": (
            f"Return ONLY python project structure for {task}. "
            "List files and folders line by line. NO explanation."
        ),
    }])
    lines = get_response(r).split("\n")
    files: list[str] = []
    for raw in lines:
        line = raw.strip()
        if not line or "```" in line or ":" in line:
            continue
        if line.startswith(("-", "*")) or "Here is" in line or "structure" in line:
            continue
        if any(c in line for c in ["*", "?", "<", ">", "|", '"']):
            continue
        try:
            full_path = os.path.join(base, line)
            if line.endswith("/") or line.endswith("\\"):
                os.makedirs(full_path, exist_ok=True)
                print("📁 Folder:", line)
            else:
                folder = os.path.dirname(full_path)
                if folder:
                    os.makedirs(folder, exist_ok=True)
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write("")
                files.append(line)
                print("📄 File:", line)
        except Exception as e:
            print(f"⚠ Skipped bad path: {line} ({e})")

    if not files:
        main_path = os.path.join(base, "main.py")
        with open(main_path, "w", encoding="utf-8") as f:
            f.write("")
        files.append("main.py")
    return files


def generate_code(files: list[str], task: str, cwd: str = None) -> None:
    """Generate Python code for each file. cwd avoids process-wide chdir."""
    base = cwd or os.getcwd()
    for file in files:
        print(f"⚙ Generating code for: {file}...")
        r = safe_chat(model=_get_model(), messages=[{
            "role": "user",
            "content": (
                f"Write ONLY python code for {file} in {task}. "
                "NO markdown blocks. NO explanation."
            ),
        }])
        code = get_response(r).replace("```python", "").replace("```", "")
        if code.strip().startswith("Here is"):
            code = "# Generated code\n" + code.split("\n", 1)[1]
        full_path = os.path.join(base, file)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(code)
        print(f"✅ Written: {file}")


def auto_run_and_fix(task_description: str, initial_code: str,
                     max_attempts: int = 3) -> tuple[str, str]:
    """
    Run Python code in a sandbox, auto-fix errors up to max_attempts.
    Returns (final_code, output_or_error_message).
    """
    import subprocess as _sp
    temp_file    = "sandbox_test.py"
    current_code = initial_code

    for attempt in range(1, max_attempts + 1):
        print(f"🧪 Testing code (Attempt {attempt})...")
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(current_code)
        try:
            result = _sp.run(
                [sys.executable, temp_file],
                capture_output=True, text=True,
                timeout=_cfg.PYTHON_SANDBOX_TIMEOUT,
            )
            if result.returncode == 0:
                print(f"✅ Success on attempt {attempt}!")
                return current_code, result.stdout

            print(f"❌ Attempt {attempt} failed. Refactoring...")
            fix_prompt = (
                f"FIX THIS PYTHON CODE.\nTASK: {task_description}\n"
                f"ERROR: {result.stderr}\nCODE TO FIX:\n{current_code}\n\n"
                "RULES: Return ONLY the raw code. No markdown, no explanations."
            )
            r = safe_chat(model=_get_model(),
                          messages=[{"role": "user", "content": fix_prompt}])
            raw = get_response(r).replace("```python", "").replace("```", "").strip()
            # Only accept if it looks like real Python (≥2 lines + keyword)
            if (
                ("def " in raw or "class " in raw or "import " in raw)
                and len(raw.splitlines()) >= 2
            ):
                current_code = raw

        except _sp.TimeoutExpired:
            return current_code, "❌ Execution timed out (Possible infinite loop)."
        except Exception as e:
            return current_code, f"❌ System Error: {str(e)}"

    return current_code, "⚠️ Could not fix code after max attempts."


# ═══════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════

def run_generation(task: str, engine: str, model_name: str,
                   project_name: str, save_session_fn=None,
                   resume: bool = False) -> str:
    """
    Full generation pipeline: plan → generate → review → save → launch.
    Returns summary string.
    """
    IS_WEB  = engine in WEB_ENGINES
    icon    = "🌐" if IS_WEB else "🎮"
    label   = {
        "dotnet": "موقع", "react": "موقع", "angular": "موقع",
        "html": "موقع", "sql": "قاعدة بيانات", "python": "مشروع",
    }.get(engine, "لعبة")

    get_sandbox(engine)  # register domain in sandbox for health tracking

    print(f"\n{icon} Planning {engine.capitalize()} files...", flush=True)

    # ── Planning ───────────────────────────────────────────────────────────────
    with profiler.track("planning", engine=engine):
        from dotnet_templates import DOTNET_PLANNING_PROMPT, DOTNET_FULLSTACK_PLANNING_PROMPT
        script_pairs = plan_scripts(
            task, engine, safe_chat, get_response,
            _get_model(), DOMAIN_REGISTRY,
            DOTNET_PLANNING_PROMPT, DOTNET_FULLSTACK_PLANNING_PROMPT,
        )

    # Filter out any script whose name is essentially the project name or the task title.
    # Checks against BOTH project_name and task significant words so "Space Shooter"
    # is caught even when project_name ends up as a generic fallback like "Game".
    _proj_slug   = re.sub(r"[^a-z0-9]", "", project_name.lower())
    _proj_words  = set(re.sub(r"[^a-z0-9]", " ", project_name.lower()).split())
    _task_sig    = set(w for w in re.sub(r"[^a-z0-9]", " ", task.lower()).split()
                       if w not in _STOP_WORDS and len(w) > 2)  # significant task words

    def _is_project_name(n: str) -> bool:
        slug   = re.sub(r"[^a-z0-9]", "", n.lower())
        words  = set(re.sub(r"[^a-z0-9]", " ", n.lower()).split())
        nospace = n.replace(" ", "").lower()
        return (
            slug == _proj_slug                                         # exact slug
            or words == _proj_words                                    # exact word set
            or nospace == project_name.replace(" ", "").lower()       # no-space compare
            or (len(words) >= 2 and words.issubset(_proj_words))      # subset of project
            or (len(words) >= 2 and words.issubset(_task_sig))        # subset of task words
        )
    script_pairs = [(n, r) for n, r in script_pairs if not _is_project_name(n)]
    script_pairs = script_pairs[:8]
    script_names = [p[0] for p in script_pairs]

    eng_cfg = _get_engine_cfg(engine)
    print(f"📋 Scripts to generate: {', '.join(script_names)}", flush=True)

    saved:             list[str] = []
    failed:            list[str] = []
    generated_context: dict      = {}
    gen_start                    = time.time()

    # ── BUG FIX: entire generation loop is INSIDE the with block ──────────────
    # Previously the for loop was outside, making ctx.mark_started/done no-ops
    # and /resume completely broken.
    # resume param is passed explicitly from chat_tool (via /resume command).
    if not resume:
        resume = get_checkpoint_manager().load(project_name) is not None
    with RecoveryContext(
        task, engine, project_name, script_pairs, model_name, resume=resume
    ) as ctx:

        for script_name, script_role in ctx.remaining:
            # ── Check stop signal between scripts (Ctrl+C / shutdown) ─────────
            from shutdown_manager import stop_event
            if stop_event.is_set():
                log.info(f"Generation stopped by shutdown — {len(saved)} scripts saved.")
                break

            # ── Optional delay for testing checkpoint/resume (AGENT_SCRIPT_DELAY=5) ──
            if _cfg.SCRIPT_DELAY > 0:
                import time as _t
                print(f"⏳ [test delay {_cfg.SCRIPT_DELAY}s] — press Ctrl+C now to test checkpoint...", flush=True)
                _t.sleep(_cfg.SCRIPT_DELAY)
                if stop_event.is_set():
                    log.info(f"Generation stopped during delay — {len(saved)} scripts saved.")
                    break

            print(f"\n⚙️ Writing {script_name} ({engine}) ...", flush=True)
            ctx.mark_started(script_name)

            # 1. Generate
            code_response, used_template = _generate_single(
                script_name, script_role, engine, task,
                script_pairs, eng_cfg, generated_context, model_name,
            )

            # 2. Auto-fix Unity syntax
            if engine == "unity":
                code_response = auto_fix_unity_code(code_response)

            # 3. Review pass (skip if template was used verbatim)
            if not used_template:
                print(f"🔍 Reviewing {script_name} ...", flush=True)
                code_response = _review_script(
                    script_name, script_role, engine, code_response, model_name
                )

            # 4. Compile-fix loop (Unity only)
            if engine == "unity" and not used_template:
                code_response = _compile_fix_loop(
                    script_name, code_response,
                    generated_context, script_names, model_name,
                )

            # 5. Save
            forced_ext = (
                DOMAIN_REGISTRY[engine]["get_ext"](script_name, script_role)
                if engine in DOMAIN_REGISTRY and engine not in ("unity", "unreal")
                else None
            )
            success = extract_and_save_scripts(
                code_response, project_name,
                forced_name=script_name,
                forced_ext=forced_ext,
            )

            if success:
                profiler.record(f"script_saved[{engine}]", time.time() - gen_start)
                ext = (
                    DOMAIN_REGISTRY[engine]["get_ext"](script_name, script_role)
                    if engine in DOMAIN_REGISTRY and engine not in ("unity", "unreal")
                    else ".cs" if engine == "unity" else ""
                )
                saved.append(script_name + ext)
                # Store compact signatures for subsequent scripts' context
                m = re.search(r"```(?:csharp|cs)?\n(.*?)```", code_response, re.DOTALL)
                if m:
                    sigs = [
                        l for l in m.group(1).split("\n")
                        if re.match(
                            r"\s*(public|private|void|float|int|bool|string|class|using)", l
                        )
                    ]
                    generated_context[script_name] = "\n".join(sigs[:20])
                ctx.mark_done(script_name)
            else:
                failed.append(script_name)
                ctx.mark_failed(script_name)

    # ── Post-processing ────────────────────────────────────────────────────────
    if engine == "dotnet":
        _post_process_dotnet(project_name)

    gen_time = round(time.time() - gen_start, 1)
    log.info(f"⏱ Generation done in {gen_time}s — saved={len(saved)}")
    metrics.record_generation(bool(saved), engine, gen_time)
    metrics.save()

    summary = f"{icon} تم إنشاء {label} {project_name}!\n\n"
    for s in saved:
        summary += f"   ✅ {s}\n"
    for s in failed:
        summary += f"   ❌ {s} فشل\n"
    summary += f"\n[ 💾 الملفات في: Generated_Scripts/{project_name.replace(' ', '_')} ]"

    print(f"\n🤖 Agent: {summary}\n\n", flush=True)

    if engine in ("html", "react", "angular", "dotnet"):
        print("🌐 فاتح الـ website في الـ browser...", flush=True)
        launch_website(project_name, engine)

    if save_session_fn:
        save_session_fn()

    return summary
