import ollama
import os
import sys
import io
import re
import json
import time
import shutil
import subprocess

# ── Heavy libs: lazy-loaded inside functions to reduce startup time ──
# cv2, pypdf, docx, openpyxl, pptx, pytesseract, PIL → imported where used
# duckduckgo_search → imported in job_tool only

# ================= CONFIG =================
DEFAULT_MODEL = "qwen2.5-coder:7b"


# ✅ إصلاح encoding على Windows لدعم الـ emoji
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace", line_buffering=True)
    sys.stdin.reconfigure(encoding="utf-8", errors="replace")
else:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
    sys.stdin.reconfigure(encoding="utf-8")

def _import_cv2():
    """Lazy import cv2 — only when image/video processing needed."""
    import cv2 as _cv2
    return _cv2

def _import_pil():
    """Lazy import PIL."""
    from PIL import ImageEnhance, ImageFilter
    return ImageEnhance, ImageFilter

def _import_pytesseract():
    """Lazy import pytesseract."""
    import pytesseract as _tess
    return _tess



# ═══════════════════════════════════════════════════════════
# STRUCTURED LOGGER
# ═══════════════════════════════════════════════════════════
import json as _json_mod
from datetime import datetime as _dt

class AgentLogger:
    LEVELS = {"DEBUG": 0, "INFO": 1, "SUCCESS": 1, "SAVE": 1, "RUN": 1, "WARN": 2, "ERROR": 3}
    ICONS  = {"DEBUG": "🔍", "INFO": "ℹ️", "WARN": "⚠️", "ERROR": "❌",
               "SUCCESS": "✅", "SAVE": "💾", "RUN": "🚀"}

    def __init__(self, min_level="INFO", log_file="agent_log.jsonl"):
        import threading
        self.min_level = min_level
        self.log_file  = log_file
        self._buf: list = []
        self._lock = threading.Lock()  # thread-safe writes

    def _write(self, level, msg, **ctx):
        if self.LEVELS.get(level, 1) < self.LEVELS.get(self.min_level, 1):
            return
        icon  = self.ICONS.get(level, "•")
        ts    = _dt.now().strftime("%H:%M:%S")
        entry = {"ts": ts, "level": level, "msg": msg, **ctx}
        with self._lock:
            self._buf.append(entry)
        print(f"{icon} {msg}", flush=True)
        try:
            if os.path.exists(self.log_file) and os.path.getsize(self.log_file) > 5*1024*1024:
                os.replace(self.log_file, self.log_file.replace(".jsonl", f"_{int(time.time())}.jsonl"))
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(_json_mod.dumps(entry, default=str, ensure_ascii=False) + "\n")
        except Exception:
            pass

    def debug(self, msg, **ctx):   self._write("DEBUG",   msg, **ctx)
    def info(self, msg, **ctx):    self._write("INFO",    msg, **ctx)
    def warn(self, msg, **ctx):    self._write("WARN",    msg, **ctx)
    def error(self, msg, **ctx):   self._write("ERROR",   msg, **ctx)
    def success(self, msg, **ctx): self._write("SUCCESS", msg, **ctx)
    def save(self, msg, **ctx):    self._write("SAVE",    msg, **ctx)
    def run(self, msg, **ctx):     self._write("RUN",     msg, **ctx)
    def last(self, n=20):          return self._buf[-n:]

log = AgentLogger()

def safe_print(*args, **kwargs):
    """print آمن يتجنب surrogate errors على Windows"""
    try:
        print(*args, **kwargs)
    except UnicodeEncodeError:
        text = " ".join(str(a) for a in args)
        cleaned = text.encode("utf-8", errors="replace").decode("utf-8")
        print(cleaned, **{k:v for k,v in kwargs.items() if k != "end"})

# ================= SAFE CHAT =================
def safe_chat(model=None, messages=None, stream=False, retries=2, timeout=120):
    """
    Wrapper لـ safe_chat() مع:
    - retry تلقائي عند فشل الاتصال
    - timeout لتجنب التجميد
    - error logging واضح
    """
    if model is None:
        model = DEFAULT_MODEL
    if messages is None:
        messages = []

    last_err = None
    for attempt in range(retries + 1):
        try:
            # ✅ بيكلم ollama.chat مباشرة — مش safe_chat نفسها
            result = ollama.chat(model=model, messages=messages, stream=stream)
            return result
        except Exception as e:
            last_err = e
            err_type = type(e).__name__
            if attempt < retries:
                wait = 2 * (attempt + 1)
                safe_print(f"⚠️ safe_chat attempt {attempt+1} failed ({err_type}): {e} — retrying in {wait}s...")
                time.sleep(wait)
            else:
                safe_print(f"❌ safe_chat failed after {retries+1} attempts: {err_type}: {e}")

    # Return empty-content response so callers don't crash
    class _FallbackMsg:
        content = f"[ERROR: Model unavailable after {retries+1} attempts — {last_err}]"
    class _FallbackResp:
        message = _FallbackMsg()
    return _FallbackResp()

def get_response(r) -> str:
    """
    Unified response extractor for safe_chat() results.
    Handles both:
      - ollama dict:    get_response(r)
      - fallback obj:   r.message.content
    Always returns a string — never raises KeyError/AttributeError.
    """
    try:
        # ollama returns a dict-like object
        if isinstance(r, dict):
            return r.get("message", {}).get("content", "") or ""
        # attribute-style (ollama response object OR our fallback)
        msg = getattr(r, "message", None)
        if msg is not None:
            return getattr(msg, "content", "") or ""
        # last resort
        return str(r)
    except Exception as e:
        safe_print(f"⚠ get_response error: {e}")
        return ""


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "agent_memory.txt")
CONTEXT_FILE = os.path.join(BASE_DIR, "project_context.json")
HISTORY_FILE = os.path.join(BASE_DIR, "chat_sessions.json")

# ================= AGENT STATE =================
from threading import Lock as _Lock
_state_lock = _Lock()   # protects shared mutable state

class AgentState:
    """
    كل الـ global state في مكان واحد.
    بدل scattered globals → class واضحة.
    """
    def __init__(self):
        self.chat_history       = []     # 🧠 ذاكرة الـ Agent
        self.project_context    = []     # context للـ project الحالي
        self.current_session_id = None   # ID الـ session الحالية
        self.current_project_name = ""   # اسم البروجكت الحالي
        self.awaiting_project_name = False  # هل Agent بينتظر اسم بروجكت؟
        self.pending_task       = ""     # الطلب اللي اتأجل لحد ما اليوزر يكتب الاسم
        self.last_user_input    = ""
        self.active_intent      = "default"

    def reset_project(self):
        self.current_project_name = ""
        self.awaiting_project_name = False
        self.pending_task = ""

# Singleton instance
_state = AgentState()

# ================= PROJECT CONTEXT (backward-compatible module-level refs) =================
# الكود القديم بيستخدم chat_history وproject_context كـ globals مباشرة
# خلينا نربطهم بالـ state object
def _get_chat_history():     return _state.chat_history
def _get_project_context():  return _state.project_context

# ✅ Lists are safe as aliases (reference types — same object)
chat_history    = _state.chat_history
project_context = _state.project_context
# ⚠️ Primitives (str, bool, None) are NOT aliased — read/write via _state directly
# e.g. use _state.current_session_id  NOT  current_session_id
# e.g. use _state.current_project_name NOT  current_project_name

# ================= MODE =================

def detect_mode(user: str) -> tuple:
    """
    Smart intent router — LLM-based with fast rule fallback.

    Priority:
    1. Hard rules for system commands — never LLM
    2. Fast keyword rules for obvious cases — saves LLM call
    3. LLM classification for ambiguous natural language
       (skipped for short messages < 4 words to avoid delay)
    """
    t = user.lower().strip()

    # ── Hard system commands (never LLM) ──
    if t.startswith("attach "):       return "ATTACH",       "general"
    if t == "clear":                  return "CLEAR",        "general"
    if t == "run":                    return "RUN",          "general"
    if t.startswith("load_session "): return "LOAD_SESSION", "general"

    # ── Fast keyword rules ──
    # Creation verbs — only count if paired with a target (game/language)
    CREATION_VERBS = [
        "make", "create", "build", "generate", "write", "design",
        "عمل", "اعمل", "عايز", "ابني", "انشئ", "اكتب", "سوّي",
    ]
    # Game/engine targets — strong signal by themselves
    GAME_TARGETS = [
        "game", "لعبة", "unity", "unreal",
        "shooter", "platformer", "racing", "puzzle", "rpg",
    ]
    JOB_KEYWORDS = [
        "job", "jobs", "hiring", "وظيفة", "وظائف", "شغل", "فرص",
        "career", "vacancy", "vacancies", "توظيف",
    ]
    DELETE_KEYWORDS = ["delete", "remove", "احذف", "امسح", "شيل"]
    LANG_KEYWORDS   = ["python", "unity", "unreal", "c#", "c++", "csharp", "dotnet", ".net", "asp.net", "aspnet"]

    has_verb   = any(kw in t for kw in CREATION_VERBS)
    has_target = any(kw in t for kw in GAME_TARGETS)
    has_lang   = any(kw in t for kw in LANG_KEYWORDS)
    has_job    = any(kw in t for kw in JOB_KEYWORDS)
    has_del    = any(kw in t for kw in DELETE_KEYWORDS)

    if has_del: return "DELETE", "general"
    if has_job: return "JOB",    "general"

    # Question/statement detection
    QUESTION_STARTS = ["what", "how", "why", "when", "who", "which",
                       "explain", "tell me", "describe", "show me", "is ", "are ",
                       "ما", "كيف", "ليه", "متى", "من", "اشرح", "وضّح", "قولي"]
    is_question = (
        any(t.startswith(q + " ") or t == q for q in QUESTION_STARTS) or
        t.endswith("?") or t.endswith("؟")
    )

    # Opinion/complaint patterns — "X is weird/great/bad" → CHAT
    OPINION_WORDS = [" is ", " are ", " was ", " seems ", " looks ", " feels ",
                     " بيعمل ", " بيحصل ", " غريب", " صعب", " سهل"]
    is_opinion = any(op in t for op in OPINION_WORDS)

    # GAME: verb required — target alone is not enough
    # "unity physics is weird"  → has_target=True but is_opinion=True → CHAT ✅
    # "make a unity game"       → has_verb=True + has_target=True → GAME ✅
    # "unity game"              → has_target=True, no verb, not opinion → GAME ✅
    is_game = (
        (has_verb and (has_target or has_lang)) or           # verb + target/lang
        (has_target and not is_question and not is_opinion)  # target alone — only if pure intent
    )
    if is_game:
        return "GAME", detect_domain(t)

    # ── SELF_MOD: deterministic — must be before LLM ──
    SELF_MOD_KEYWORDS = [
        "add feature", "improve yourself", "update yourself", "modify yourself",
        "add support for", "teach yourself", "expand yourself",
        "طور نفسك", "اضف ميزة", "حدث نفسك", "عدل نفسك",
    ]
    if any(kw in t for kw in SELF_MOD_KEYWORDS):
        return "SELF_MOD", "general"

    # ── LLM fallback — skip for short messages (< 4 words) ──
    word_count = len(t.split())
    if word_count < 4:
        return "CHAT", "general"

    try:
        prompt = f"""Classify this user message into ONE intent:
GAME     - user wants to create/build/make a game, app, or code project
JOB      - user wants job listings or career info
DELETE   - user wants to delete/remove something
RUN      - user wants to run/execute code
SELF_MOD - user wants the agent to modify/improve/expand itself
CHAT     - anything else

Reply with ONLY the intent word.
Message: "{user}"
Intent:"""

        r = safe_chat(
            model=DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            retries=1   # ✅ only 1 retry for intent — fast fail
        )
        intent = get_response(r).strip().upper().split()[0]
        if intent in ("GAME", "JOB", "DELETE", "RUN", "CHAT"):
            d = detect_domain(t) if intent == "GAME" else "general"
            return intent, d
    except Exception as e:
        safe_print(f"⚠ intent router error: {e}")

    return "CHAT", "general"




# ═══════════════════════════════════════════════════════════════
# DOMAIN REGISTRY — single source of truth for all domains
# To add a new domain: add ONE entry here — routing is automatic
# ═══════════════════════════════════════════════════════════════
DOMAIN_REGISTRY = {
    "unity":   {"keywords": ["unity","يونتي"],           "planning": None,  "get_ext": lambda n,r: ".cs",   "lang": "Unity C#",         "launchable": False, "validator": "unity"},
    "unreal":  {"keywords": ["unreal","c++","أنريل"],    "planning": None,  "get_ext": lambda n,r: ".h",    "lang": "Unreal C++",       "launchable": False, "validator": "unreal"},
    "dotnet":  {
        "keywords": ["dotnet",".net","asp.net","aspnet","web api","webapi"],
        "planning": lambda task: (DOTNET_FULLSTACK_PLANNING_PROMPT
                                  if any(w in task.lower() for w in ["website","web app","mvc","razor","موقع","frontend"])
                                  else DOTNET_PLANNING_PROMPT).format(task=task),
        "get_ext":  lambda n,r: _get_dotnet_ext(n, r),
        "lang": "ASP.NET Core C#",  "launchable": True,
    },
    "react":   {"keywords": ["react","reactjs","react.js","vite","nextjs","next.js"],  "planning": lambda t: REACT_PLANNING_PROMPT.format(task=t),    "get_ext": lambda n,r: get_react_ext(n,r),    "lang": "React.js",            "launchable": True},
    "angular": {"keywords": ["angular","angularjs","ng "],                              "planning": lambda t: ANGULAR_PLANNING_PROMPT.format(task=t),  "get_ext": lambda n,r: get_angular_ext(n,r),  "lang": "Angular TypeScript",  "launchable": True},
    "html":    {"keywords": ["html","html5","vanilla js","static site","plain website"],"planning": lambda t: HTML_PLANNING_PROMPT.format(task=t),     "get_ext": lambda n,r: get_html_ext(n,r),     "lang": "HTML/CSS/JS",         "launchable": True},
    "sql":     {"keywords": ["sql","database","postgres","postgresql","mysql","sqlite","db schema","قاعدة بيانات"], "planning": lambda t: SQL_PLANNING_PROMPT.format(task=t),    "get_ext": lambda n,r: ".sql", "lang": "SQL",    "launchable": False},
    "python":  {"keywords": ["python","بايثون","fastapi","flask","script","pip"],       "planning": lambda t: PYTHON_PLANNING_PROMPT.format(task=t),   "get_ext": lambda n,r: ".py",  "lang": "Python", "launchable": False},
}

def detect_requested_language(task: str) -> str:
    return detect_domain(task)

def detect_domain(task: str) -> str:
    """Detect domain from task using DOMAIN_REGISTRY. Single source of truth."""
    t = task.lower()
    for domain in ["unity","unreal","dotnet","react","angular","html","sql","python"]:
        if any(kw in t for kw in DOMAIN_REGISTRY[domain]["keywords"]):
            return domain
    return "general"

# ================= MEMORY =================

def save_last_project(path):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write(path)

def load_last_project():
    if not os.path.exists(MEMORY_FILE):
        return None
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

# ================= CONTEXT MEMORY =================

def save_project_context():
    try:
        with open(CONTEXT_FILE, "w", encoding="utf-8") as f:
            json.dump(project_context, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print("⚠ Context save error:", e)


def load_project_context():
    if not os.path.exists(CONTEXT_FILE):
        return
    try:
        with open(CONTEXT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        # ✅ keep same list object so alias stays valid
        _state.project_context.clear()
        _state.project_context.extend(data)
        print(f"🧠 Loaded project context ({len(_state.project_context)} files)")
    except Exception as e:
        print("⚠ Context load error:", e)

# ================= SMART TRIM =================
def estimate_tokens(text):
    return len(text) // 4

def smart_trim_history(history, max_tokens=3000):
    if not history:
        return history
    if sum(estimate_tokens(m.get("content","")) for m in history) <= max_tokens:
        return history
    MIN_KEEP = 4
    trimmed = list(history)
    while len(trimmed) > MIN_KEEP:
        if sum(estimate_tokens(m.get("content","")) for m in trimmed) <= max_tokens:
            break
        removed = False
        for i, msg in enumerate(trimmed[:-MIN_KEEP]):
            if not any(k in msg.get("content","") for k in ["```","Generated_Scripts","💾"]):
                trimmed.pop(i); removed = True; break
        if not removed:
            trimmed.pop(0)
    return trimmed

# ================= SESSION HISTORY =================
import time as _time

def _session_title(msg):
    words = msg.strip().split()[:6]
    t = " ".join(words)
    return (t[:45]+"...") if len(t)>45 else t or "New Chat"

def load_all_sessions():
    if not os.path.exists(HISTORY_FILE):
        return []
    try:
        with open(HISTORY_FILE,"r",encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        safe_print(f"⚠ load_all_sessions error: {e}")
        return []

def save_session():
    if not chat_history: return
    if not _state.current_session_id:
        _state.current_session_id = str(int(_time.time()))
    sessions = load_all_sessions()
    title = _session_title(next((m["content"] for m in chat_history if m["role"]=="user"),"New Chat"))
    for s in sessions:
        if s["id"] == _state.current_session_id:
            s["messages"] = chat_history; s["title"] = title; break
    else:
        sessions.append({"id":_state.current_session_id,"title":title,"timestamp":_state.current_session_id,"messages":chat_history})
    if len(sessions) > 30: sessions = sessions[-30:]
    try:
        with _state_lock:
            tmp = HISTORY_FILE + ".tmp"
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(sessions, f, ensure_ascii=False, indent=2)
            os.replace(tmp, HISTORY_FILE)  # atomic — prevents corruption on crash
    except Exception as e:
        safe_print(f"⚠ save_session error: {e}")

# ================= HELPERS =================

def is_valid_path(name):
    invalid = ["*", "?", "<", ">", "|", "\""]
    for c in invalid:
        if c in name:
            return False
    return True

def clean_line(line):
    line = line.strip()
    if not line: return None
    if "```" in line: return None
    if ":" in line: return None
    if line.startswith("-") or line.startswith("*"): return None
    if "Here is" in line or "structure" in line: return None # فلترة إضافية
    if not is_valid_path(line): return None
    return line


# ================= BUILD =================

def build_structure(task):
    print("🔨 Designing structure...")
    r = safe_chat(
        model=DEFAULT_MODEL,
        messages=[{
            "role":"user",
            "content":f"Return ONLY python project structure for {task}. List files and folders line by line. NO explanation."
        }]
    )

    lines = get_response(r).split("\n")
    files = []

    for raw in lines:
        line = clean_line(raw)
        if not line: continue

        try:
            if line.endswith("/") or line.endswith("\\"):
                os.makedirs(line, exist_ok=True)
                print("📁 Folder:", line)
            else:
                folder = os.path.dirname(line)
                if folder:
                    os.makedirs(folder, exist_ok=True)
                
                # إنشاء ملف فارغ
                with open(line, "w", encoding="utf-8") as f:
                    f.write("")
                
                files.append(line)
                print("📄 File:", line)

        except Exception as e:
            print(f"⚠ Skipped bad path: {line} ({e})")

    # لو مفيش ملفات اتعملت، نعمل ملف رئيسي اجباري
    if len(files) == 0:
        with open("main.py", "w", encoding="utf-8") as f:
            f.write("")
        files.append("main.py")

    return files


# ================= GENERATE =================

def generate_code(files, task):
    for file in files:
        print(f"⚙ Generating code for: {file}...")
        
        prompt = f"Write ONLY python code for {file} in {task}. NO markdown blocks. NO explanation."
        
        r = safe_chat(
            model=DEFAULT_MODEL,
            messages=[{"role":"user", "content": prompt}]
        )

        code = get_response(r)
        # تنظيف إضافي للكود
        code = code.replace("```python", "").replace("```", "")
        if code.strip().startswith("Here is"): # لو الذكاء الاصطناعي رغي
            code = "# Generated code\n" + code.split("\n", 1)[1]

        with open(file, "w", encoding="utf-8") as f:
            f.write(code)
        
        print(f"✅ Written: {file}")


# ================= RUN =================

def run_python(file_path):
    print(f"\n🚀 Running: {file_path}")
    folder = os.path.dirname(file_path)
    script = os.path.basename(file_path)

    try:
        subprocess.run(
            [sys.executable, script], # استخدام بايثون الحالي
            timeout=15, # وقت أطول للمدخلات
            cwd=folder
        )
    except subprocess.TimeoutExpired:
        print("⚠ Program timed out (loop or waiting for input).")
    except Exception as e:
        print(f"❌ Run Error: {e}")

def auto_run_and_fix(task_description, initial_code):
    temp_file = "sandbox_test.py"
    current_code = initial_code
    attempts = 0
    max_attempts = 3 # هيحاول يصلح نفسه لحد 3 مرات

    while attempts < max_attempts:
        attempts += 1
        print(f"🧪 Testing code (Attempt {attempts})...")
        
        with open(temp_file, "w", encoding="utf-8") as f:
            f.write(current_code)

        try:
            result = subprocess.run(
                [sys.executable, temp_file],
                capture_output=True,
                text=True,
                timeout=5 # وقت قليل عشان لو فيه Infinite Loop
            )

            if result.returncode == 0:
                print(f"✅ Success on attempt {attempts}!")
                return current_code, result.stdout
            
            # لو فشل، نبعت الـ Error للموديل
            print(f"❌ Attempt {attempts} failed. Refactoring...")
            error_msg = result.stderr
            
            fix_prompt = f"""FIX THIS PYTHON CODE.
            TASK: {task_description}
            ERROR: {error_msg}
            CODE TO FIX:
            {current_code}
            
            RULES: Return ONLY the raw code. No markdown, no explanations."""
            
            response = safe_chat(model=DEFAULT_MODEL, messages=[{"role": "user", "content": fix_prompt}])
            raw_content = get_response(response)
            
            # تنظيف صارم للكود من أي رغي جانبي
            current_code = raw_content.replace("```python", "").replace("```", "").strip()
            if "import" not in current_code and "print" not in current_code: # حماية لو رد بكلام رغي
                 current_code = initial_code # ارجع للأصل لو الموديل خرف

        except subprocess.TimeoutExpired:
            return current_code, "❌ Execution timed out (Possible infinite loop)."
        except Exception as e:
            return current_code, f"❌ System Error: {str(e)}"

    return current_code, "⚠️ Could not fix code after 3 attempts."
    
# ================= DELETE =================

def delete_tool(task):
    name = task.replace("delete", "").replace("remove", "").strip()
    
    # محاولة الحذف من المسار الحالي
    target = os.path.abspath(name)
    
    if os.path.exists(target):
        try:
            shutil.rmtree(target)
            print(f"🗑️ Deleted: {target}")
            
            # تنظيف الذاكرة
            last = load_last_project()
            if last and name in last:
                if os.path.exists(MEMORY_FILE):
                    os.remove(MEMORY_FILE)
        except Exception as e:
            print(f"❌ Error deleting: {e}")
    else:
        print(f"❌ Folder '{name}' not found.")


# ================= PROJECT =================

def project_tool(task):
    folder_name = task.replace("build", "").strip().replace(" ", "_").lower()
    if not folder_name: folder_name = "project"

    # إنشاء المشروع في المكان الحالي اللي اليوزر واقف فيه
    project_path = os.path.join(os.getcwd(), folder_name)
    
    if os.path.exists(project_path):
        print(f"⚠ Folder '{folder_name}' already exists. Updating inside it.")
    
    os.makedirs(project_path, exist_ok=True)
    print(f"📁 Project Path: {project_path}")

    cwd = os.getcwd()
    os.chdir(project_path)

    files = build_structure(task)
    generate_code(files, task)

    # اختيار ملف التشغيل بذكاء
    chosen = None
    priority = ["main.py", "app.py", "run.py", f"{folder_name}.py"]
    
    for p in priority:
        if p in files:
            chosen = p
            break
            
    if not chosen and files:
        chosen = files[0]

    if chosen:
        abs_path = os.path.abspath(chosen)
        save_last_project(abs_path)
        
        # العودة للمسار الأصلي قبل التشغيل لتجنب الأخطاء
        os.chdir(cwd)
        run_python(abs_path)
        print("🔥 Project completed.")
    else:
        print("❌ No files generated to run.")
        os.chdir(cwd)

# ================= JOB =================
import warnings
import urllib.parse
import webbrowser
warnings.filterwarnings("ignore", category=RuntimeWarning)

def job_tool(task):
    from duckduckgo_search import DDGS
    print("🧠 Analyzing job market...")
    
    # 🔥 Prompt صارم جداً مع مثال واضح
    prompt = f"""Extract job details from this request: '{task}'. 
    Default Title: Game Developer OR Python AI
    Default Platform: Upwork
    Default Location: Remote OR Egypt
    Reply ONLY with this exact format: TITLE | PLATFORM | LOCATION
    Example: Game Developer | Upwork | Remote
    CRITICAL RULE: DO NOT write 'Here are the details', do not use markdown like **, and DO NOT add any conversational text. JUST the raw format."""
    
    try:
        r = safe_chat(model=DEFAULT_MODEL, messages=[{"role": "user", "content": prompt}])
        ans = get_response(r).strip()
        
        # 🛡️ فلتر أمان بايثون (عشان لو الموديل رغى برضه، نقص كلامه)
        if ":" in ans:
            ans = ans.split(":")[-1] # لو كتب نقطتين، بناخد اللي بعدهم بس
        ans = ans.replace('**', '').replace('"', '').strip()
        
        parts = ans.split('|')
        title = parts[0].strip() if len(parts) > 0 else "Game Developer"
        platform = parts[1].strip().lower() if len(parts) > 1 else "upwork"
        location = parts[2].strip() if len(parts) > 2 else "Remote"
        
        # تنظيف أخير للعنوان لو لسه فيه أي شوائب
        if title.lower().startswith("here are") or title.lower().startswith("extracted"):
            title = "Game Developer OR Python AI"
            
        print(f"🚀 Opening {platform.title()} for {title} roles...")
        
        title_encoded = urllib.parse.quote(title)
        
        if "upwork" in platform:
            url = f"https://www.upwork.com/nx/search/jobs/?q={title_encoded}&sort=recency"
        else:
            loc_encoded = urllib.parse.quote(location)
            url = f"https://www.linkedin.com/jobs/search/?keywords={title_encoded}&location={loc_encoded}"
            
        webbrowser.open(url)
        print("✅ Browser opened with real-time job listings!")
        
    except Exception as e:
        print(f"❌ Error setting up job search: {e}")

# ================= CHAT (FULLY AUTONOMOUS) =================

def self_correct(draft_response, user_query):
    #print("🧠 Reflection Layer: Reviewing and polishing the response...")
    
    # رسالة تظهر وقت الـ (Idle) عشان تفهم إن التأخير ده بسبب تحميل الموديل
    #print("⏳ Swapping models in memory (Loading Llama 3)...", flush=True) 
    
    prompt = f"""You are a professional Content Editor. You are reviewing a draft response from an AI assistant.
    
    USER QUERY: "{user_query}"
    DRAFT RESPONSE: "{draft_response}"

    YOUR STRICT MISSION:
    1. Clean up the language and make it sound natural and professional.
    2. Keep the core information and meaning of the draft EXACTLY as it is. Do NOT fabricate or add new information.
    3. If the draft describes files, images, or code, DO NOT say you cannot see them. Trust the draft completely.
    4. NEVER apologize or say "I am an AI", "As an AI", or "I have limitations". 
    5. Just return the polished, final version of the response directly.

    FINAL OUTPUT ONLY. NO INTRODUCTIONS. NO CHATTY TEXT."""
    
    try:
        # 🔥 تفعيل خاصية الـ Streaming
        stream = safe_chat(model=DEFAULT_MODEL, messages=[{"role": "user", "content": prompt}], stream=True)
        
        # بنطبع البداية ونجبر الشاشة تطلعها فوراً
        sys.stdout.write("\n🤖 Agent: ")
        sys.stdout.flush()
        
        final_reply = ""
        for chunk in stream:
            word = chunk['message']['content']
            # بنكتب الكلمة ونجبر الشاشة تعرضها في نفس اللحظة (غصب عن التيرمنال)
            sys.stdout.write(word)
            sys.stdout.flush()
            final_reply += word
            
        sys.stdout.write("\n\n")
        sys.stdout.flush()
        
        return final_reply
        
    except Exception as e:
        print(f"\n⚠️ Reflection failed: {e}")
        return draft_response

# Compiler tools → compiler_tools.py
from compiler_tools import (
    detect_programming_domain, validate_unity, validate_python,
    validate_code, compile_check_csharp, llm_fix_compile_errors,
    LANGUAGE_RULES
)
from unity_pipeline import auto_fix_unity_code, auto_clean_unity_code
from unreal_templates import validate_unreal, auto_fix_unreal_header, UNREAL_SYSTEM_PROMPT, save_unreal_scripts
from unity_templates import (UNIVERSAL_TEMPLATES, TEMPLATED_ROLES, GAME_SPECIFIC_ROLES,
    FILL_TEMPLATES, ROLE_FILL_RULES)
from dotnet_templates import (DOTNET_TEMPLATES, DOTNET_TEMPLATED_ROLES,
    DOTNET_SYSTEM_PROMPT, DOTNET_PLANNING_PROMPT, DOTNET_FULLSTACK_PLANNING_PROMPT,
    get_dotnet_template, get_dotnet_role, get_dotnet_ext as _get_dotnet_ext)
from react_templates import (REACT_TEMPLATES, REACT_TEMPLATED_ROLES,
    REACT_SYSTEM_PROMPT, REACT_PLANNING_PROMPT,
    get_react_template, get_react_role, get_react_ext)
from angular_templates import (ANGULAR_TEMPLATES, ANGULAR_TEMPLATED_ROLES,
    ANGULAR_SYSTEM_PROMPT, ANGULAR_PLANNING_PROMPT,
    get_angular_template, get_angular_role, get_angular_ext)
from html_templates import (HTML_TEMPLATES, HTML_TEMPLATED_ROLES,
    HTML_SYSTEM_PROMPT, HTML_PLANNING_PROMPT,
    get_html_template, get_html_role, get_html_ext)
from sql_templates import (SQL_TEMPLATES, SQL_TEMPLATED_ROLES,
    SQL_SYSTEM_PROMPT, SQL_PLANNING_PROMPT,
    get_sql_template, get_sql_role)
from python_templates import (PYTHON_TEMPLATES, PYTHON_TEMPLATED_ROLES,
    PYTHON_SYSTEM_PROMPT, PYTHON_PLANNING_PROMPT, SELF_MOD_PROMPT,
    get_python_template, get_python_role)

def extract_and_save_scripts(text, project_name, forced_name=None, forced_ext=None):

    pattern = r"```(?:[a-zA-Z0-9+#]*)\n?(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL | re.IGNORECASE)

    if not matches:
        return False

    safe_project_name = re.sub(r'[\\/*?:"<>|]', "", project_name).strip().replace(" ", "_")
    folder_name = os.path.join("Generated_Scripts", safe_project_name)
    os.makedirs(folder_name, exist_ok=True)

    # ==========================================
    # 🔥 Detect Domain From First Block
    # ==========================================
    first_domain = detect_programming_domain(matches[0])

    if first_domain in LANGUAGE_RULES:
        rule = LANGUAGE_RULES[first_domain]

        # ==========================================
        # 🚀 MULTI-FILE (Unreal) → unreal_templates.py
        # ==========================================
        if rule["type"] == "multi":
            return save_unreal_scripts(matches, folder_name)

    # ==========================================
    # 📁 SINGLE FILE LANGUAGES
    # ==========================================
    all_valid = True

    for i, code in enumerate(matches):
        code = code.strip()

        # تطبيق الإصلاح الشامل على Unity scripts
        domain_check = detect_programming_domain(code)
        if domain_check == "unity":
            code = auto_fix_unity_code(code)

        is_valid, result = validate_code(code, project_name)
        if not is_valid:
            print(f"\n❌ Validation Failed: {result}")
            all_valid = False
            continue

        # لو validate_unity رجعت الكود المصلوح، استخدمه
        # فقط لو الـ result فيه كود حقيقي (مش مجرد رسالة validation)
        if isinstance(result, str) and len(result) > 50 and (
            "using " in result or "class " in result or "def " in result or
            "#include" in result or "<" in result
        ):
            code = result

        domain = detect_programming_domain(code)

        if domain not in LANGUAGE_RULES:
            extension = ".txt"
        else:
            rule = LANGUAGE_RULES[domain]
            extension = rule["extensions"][0]

        # ✅ forced_ext overrides domain detection (for .NET .cshtml / .css / .js)
        if forced_ext:
            extension = forced_ext

        # 🔍 Extract Class Name — أو استخدم الاسم المحدد مسبقاً
        if forced_name:
            class_name = forced_name
        else:
            class_match = re.search(
                r"class\s+(?:[A-Za-z0-9_]+\s+)?([A-Za-z_][A-Za-z0-9_]*)",
                code
            )
            class_name = class_match.group(1) if class_match else f"Script_{i}"

        file_name = f"{class_name}{extension}"
        file_path = os.path.join(folder_name, file_name)

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(code)

        log.save(f"Script saved: {file_path}")

    return all_valid


# ═══════════════════════════════════════════════════════════
# WEBSITE LAUNCHER — opens generated website in browser
# ═══════════════════════════════════════════════════════════
import webbrowser, subprocess, threading, time

# Website launcher → launcher.py
try:
    from launcher import launch_website, _write_react_package_json
except ImportError:
    # Fallback if launcher.py is missing or outdated
    import webbrowser, subprocess, threading, time as _time
    def _write_react_package_json(folder):
        import json, os
        pkg = {"name": os.path.basename(folder).lower(), "version": "1.0.0",
               "scripts": {"dev": "vite", "build": "vite build"},
               "dependencies": {"react": "^18.2.0", "react-dom": "^18.2.0"},
               "devDependencies": {"@vitejs/plugin-react": "^4.0.0", "vite": "^5.0.0"}}
        with open(os.path.join(folder, "package.json"), "w") as f:
            json.dump(pkg, f, indent=2)
    def launch_website(project_folder, engine):
        import os
        folder = os.path.join("Generated_Scripts", project_folder.replace(" ", "_"))
        def _launch():
            if engine == "html":
                index = os.path.join(folder, "index.html")
                if os.path.exists(index):
                    webbrowser.open(f"file:///{os.path.abspath(index)}")
            elif engine == "dotnet":
                env = os.environ.copy()
                env["ASPNETCORE_URLS"] = "http://localhost:5000"
                r = subprocess.run(["dotnet", "restore"], cwd=folder, capture_output=True, timeout=120)
                if r.returncode != 0:
                    print(f"❌ dotnet restore failed", flush=True); return
                b = subprocess.run(["dotnet", "build", "--no-restore", "-c", "Release"],
                                   cwd=folder, capture_output=True, timeout=120)
                if b.returncode != 0:
                    errs = [l for l in b.stdout.decode().split("\n") if "error" in l.lower()]
                    print(f"❌ dotnet build failed:\n" + "\n".join(errs[:5]), flush=True); return
                proc = subprocess.Popen(["dotnet", "run", "--no-build", "-c", "Release",
                                         "--urls", "http://localhost:5000"],
                                        cwd=folder, stdout=subprocess.PIPE,
                                        stderr=subprocess.PIPE, env=env)
                import urllib.request as _ur
                _started = False
                for _ in range(40):  # wait up to 20s
                    _time.sleep(0.5)
                    if proc.poll() is not None: break
                    try:
                        resp = _ur.urlopen("http://localhost:5000", timeout=2)
                        if resp.status < 500:
                            _started = True; break
                    except Exception as ex:
                        # ConnectionRefused = not ready yet, keep waiting
                        # Other errors (404 etc) = server IS up
                        if "404" in str(ex) or "403" in str(ex) or "302" in str(ex):
                            _started = True; break
                if _started or (proc.poll() is None and _ >= 10):
                    webbrowser.open("http://localhost:5000")
                    print("✅ .NET app running at http://localhost:5000", flush=True)
                else:
                    out = proc.stderr.read().decode()[:300] if proc.poll() is not None else "timeout"
                    print(f"❌ dotnet run failed: {out}", flush=True)
        threading.Thread(target=_launch, daemon=True).start()
from planner import plan_scripts, normalize_script_pairs, apply_role_fixes, get_fallback_plan
from env_check import check_and_exit_if_missing
from metrics  import metrics

def chat_tool(task, _hint_domain: str = "general"):
    """_hint_domain: pre-detected domain — avoids double detection."""
    global chat_history
    
    if task:
        task = task.strip()
        
    if task == "Analyze and describe the attached files in detail.":
        task = ""

    # =========================================================
    if _state.awaiting_project_name and task:
        _state.current_project_name = task
        _state.awaiting_project_name = False
        print(f"\n🤖 Agent: عظيم! تم تحديد اسم البروجكت: '{_state.current_project_name}'. جاري كتابة السكريبت...\n")
        task = _state.pending_task 
    # =========================================================

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

    intent = detect_intent(task)
    _state.active_intent = intent
    working_context = select_relevant_files(task, project_context)
    
    images = [item["path"] for item in working_context if item["type"] == "image"]
    videos = [item["path"] for item in working_context if item["type"] == "video"]
    text_context = ""
    
    for item in working_context:
        if item["type"] not in ["image", "video"]:
            text_context += f"\n--- File: {os.path.basename(item['path'])} ---\n"
            if "data" in item:
                text_context += json.dumps(item["data"])
            else:
                try:
                    with open(item["path"], "r", encoding="utf-8", errors="ignore") as f:
                        text_context += f.read(1500)
                except Exception as e:
                    safe_print(f"⚠ stream error: {e}")

    model_name = "llava" if images else DEFAULT_MODEL
    
    status_parts = []
    if images: status_parts.append(f"{len(images)} images")
    if videos: status_parts.append(f"{len(videos)} videos")
    
    other_files_count = len(working_context) - len(images) - len(videos)
    if other_files_count > 0:
        status_parts.append(f"{other_files_count} text/data files")

    if status_parts:
        report = " and ".join(status_parts)
        print(f"🤔 Thinking about {report}...")

    # 3. توجيه الذكاء الاصطناعي بناءً على النية اللي اكتشفها
    if intent == "compare":
        if videos:
            system_prompt = "You are an expert video analyst. Compare the attached videos explicitly."
        elif images:
            system_prompt = "You are an expert visual analyst. Compare the attached images explicitly."
        else:
            system_prompt = "You are an expert data analyst. Compare the attached files explicitly."
    elif intent == "summarize":
        system_prompt = "You are an expert summarizer. Provide a concise, highly accurate summary of the provided files."
    elif intent == "detect_issues":
        system_prompt = "You are an expert debugger and reviewer. Analyze the provided files to find any bugs, errors, or issues."
    else:
        if len(working_context) > 0:
            system_prompt = "You are an elite Game Dev & AI assistant. Answer accurately based on the attached files."
        else:

            language = detect_domain(task)

            if language == "unity":
                system_prompt = """
                You are a senior Unity C# developer.
                Generate ONLY valid Unity C# scripts.
                Must inherit from MonoBehaviour.
                No Unreal code.
                No explanations outside code blocks.
                """

            elif language == "unreal":
                system_prompt = UNREAL_SYSTEM_PROMPT

            elif language == "python":
                system_prompt = """
                You are a senior Python developer.
                Generate clean runnable Python code only.
                No markdown explanations.
                """

            else:
                system_prompt = "You are a helpful AI assistant. Answer naturally and clearly in the same language the user is speaking."

    if text_context:
        task = f"Context from text files:\n{text_context}\n\nUser Task: {task}"

    try:
        chat_history.append({"role": "user", "content": task})
        chat_history[:] = smart_trim_history(chat_history, max_tokens=3000)
        messages_to_send = [{"role": "system", "content": system_prompt}] + chat_history

        if not text_context and not images and not videos:
            is_unity = any(word in task.lower() for word in ["unity", "c#", "combat", "game"])
            is_python = any(word in task.lower() for word in ["python", "بايثون", "script"])

            if is_python and not is_unity and any(word in task.lower() for word in ["code", "برنامج", "كود"]):
                r = safe_chat(model=model_name, messages=messages_to_send)
                initial_code = get_response(r).replace("```python", "").replace("```", "").strip()
                
                fixed_code, output = auto_run_and_fix(task, initial_code)
                
                chat_history.append({"role": "assistant", "content": f"```python\n{fixed_code}\n```"})
                print(f"\n🤖 Agent (Python Verified):\n```python\n{fixed_code}\n```\n📝 Output: {output}\n")
            
            else:
                is_script_request = (
                    any(word in task.lower() for word in [
                        "script", "سكريبت", "component", "class",
                        "عايز لعبة", "عاوز لعبة"
                    ]) or
                    # verb alone counts only if there's also a game/code keyword
                    (any(w in task.lower() for w in ["make", "create", "build", "generate", "write", "code", "كود", "برمج", "اكتب", "اعمل", "انشئ"])
                     and any(w in task.lower() for w in ["game", "لعبة", "script", "سكريبت", "unity", "unreal", "shooter", "platformer", "racing", "runner", "puzzle", "rpg"]))
                )

                # ========== COMPLETE GAME DETECTION ==========
                _t = task.lower()
                _has_game_kw = any(w in _t for w in [
                    "game", "لعبة", "shooter", "platformer", "runner",
                    "racing", "puzzle", "rpg", "tower defense",
                    "unity", "unreal", "اعمل لعبة", "انشئ لعبة",
                    "عايز لعبة", "عاوز لعبة", "full game", "كاملة", "كامل"
                ])
                _has_verb = any(w in _t for w in [
                    "make", "create", "build", "generate", "write",
                    "اعمل", "انشئ", "اكتب", "عايز", "عاوز", "ابني"
                ])
                is_complete_game = _has_game_kw and (_has_verb or _has_game_kw)

                if is_complete_game and is_script_request:
                    # ========== اكتشاف الـ Game Engine ==========
                    task_lower = task.lower()

                    # Skip game pipeline for non-game domains
                    _web_domain = detect_domain(task_lower)
                    if _web_domain in ("dotnet", "react", "angular", "html", "sql", "python"):
                        is_complete_game = False  # route to web/db generation instead

                # ========== WEB / DB GENERATION PATH ==========
                if not is_complete_game:
                    _detected_web = detect_domain(task.lower())
                    if _detected_web in ("dotnet", "react", "angular", "html", "sql", "python") and \
                       any(w in task.lower() for w in ["make","create","build","generate","write","اعمل","انشئ","اكتب","ابني"]):
                        is_complete_game = True
                        is_script_request = True  # force generation path
                        # inject detected domain so game pipeline uses it
                        _hint_domain = _detected_web

                if is_complete_game and is_script_request:
                    task_lower = task.lower()

                    # Check for EXPLICIT engine keyword — not just "game" or "shooter"
                    EXPLICIT_ENGINES = {
                        "unity": ["unity", "يونتي"],
                        "unreal": ["unreal", "c++", "أنريل", "ue4", "ue5"],
                    }
                    detected_engine = None
                    for eng, keywords in EXPLICIT_ENGINES.items():
                        if any(kw in task_lower for kw in keywords):
                            detected_engine = eng
                            break

                    # Also check _hint_domain if it's a specific engine
                    if not detected_engine and _hint_domain in ("unity", "unreal"):
                        detected_engine = _hint_domain

                    # Web/DB domains — use directly, no need to ask
                    if not detected_engine and _hint_domain in ("dotnet", "react", "angular", "html", "sql", "python"):
                        detected_engine = _hint_domain

                    # No explicit engine found — ask user
                    if not detected_engine:
                        print("❓ Which game engine? (unity / unreal)", flush=True)
                        engine_input = input().strip().lower()
                        if "unreal" in engine_input or "c++" in engine_input:
                            detected_engine = "unreal"
                        else:
                            detected_engine = "unity"

                    # استخرج اسم البروجكت
                    WEB_DOMAINS = ("dotnet", "react", "angular", "html", "sql", "python")
                    if not _state.current_project_name:
                        name_prompt = f"Extract the game or project name from this text. If none, reply ONLY with 'NONE'. Text: '{task}'"
                        r = safe_chat(model=DEFAULT_MODEL, messages=[{"role": "user", "content": name_prompt}])
                        extracted = get_response(r).strip()
                        if "NONE" in extracted.upper() or len(extracted) >= 30:
                            if detected_engine in WEB_DOMAINS:
                                # For web/db: auto-generate name from first meaningful words
                                import re as _re
                                stop = {"make","create","build","a","an","the","with","using","in","for","website","site","app","api","web"}
                                words = [w for w in _re.sub(r'[^a-z0-9 ]','',task.lower()).split() if w not in stop]
                                _state.current_project_name = "_".join(words[:3]).title() if words else "MyProject"
                            else:
                                print("❓ What's the name of your project?", flush=True)
                                _state.current_project_name = input().strip()
                                if not _state.current_project_name:
                                    _state.current_project_name = "MyGame"
                        else:
                            _state.current_project_name = extracted

                    # اطلب من الـ LLM يقرر السكريبتات المطلوبة
                    _p_icon  = "🌐" if detected_engine in WEB_DOMAINS else "🎮"
                    _p_label = "files" if detected_engine in WEB_DOMAINS else "game scripts"
                    print(f"\n{_p_icon} Planning {detected_engine.capitalize()} {_p_label}...", flush=True)

                    engine_labels = {
                        "unity":  ("Unity C#", "MonoBehaviour", ".cs"),
                        "unreal": ("Unreal C++", "AActor / UObject", ".h/.cpp"),
                        "dotnet": ("ASP.NET Core C#", "Controller/Service/Model", ".cs"),
                    }
                    eng_lang, eng_base, eng_ext = engine_labels.get(detected_engine, ("C#", "Class", ".cs"))

                    # ✅ DOMAIN_REGISTRY — planning prompts
                    _dcfg = DOMAIN_REGISTRY.get(detected_engine, {})
                    if _dcfg.get("planning"):
                        plan_prompt = _dcfg["planning"](task)
                    else:
                        plan_prompt = f"""You are a {eng_lang} game architect. List exactly 4-5 scripts needed for this game.

GAME REQUEST: {task}
ENGINE: {detected_engine.capitalize()} ({eng_lang})

For each script, reply in this format:
ScriptName:role

Where role is ONE of: player, vehicle, enemy, opponent, spawner, manager, ui, background, collectible, projectile, powerup, health

CRITICAL RULES:
- ScriptName must NEVER be the same as the game title
- Each script must have a UNIQUE role — no duplicates
- Scripts must match the EXACT game genre — do NOT mix genres
- For racing → vehicle + opponent roles; NEVER player or enemy
- For endless runner → player (jump only) + spawner + background; NEVER vehicle or opponent
- For flappy bird style → player (tap jump) + spawner (pipes) + background
- For tower defense → no vehicle, no player movement; tower shoots at enemies on a path
- For puzzle/match-3 → board/grid logic; no spawner coroutine, no enemies
- Reply ONLY as comma-separated pairs, nothing else

EXAMPLES BY GENRE:
- Space Shooter: ShipController:player, EnemySpawner:spawner, EnemyScript:enemy, PowerUpScript:powerup, GameManager:manager
- Endless Runner: RunnerController:player, ObstacleSpawner:spawner, BackgroundScroller:background, UIManager:ui, HealthBar:health
- Racing: CarController:vehicle, OpponentAI:opponent, CheckpointScript:collectible, RaceManager:manager, RaceHUD:ui
- Platformer: PlayerPlatformer:player, PlatformSpawner:spawner, CoinCollectible:collectible, GameManager:manager, HealthBar:health
- RPG/Action: PlayerController:player, EnemyScript:enemy, GameManager:manager, HealthBar:health, UIManager:ui
- Flappy Bird: BirdController:player, PipeSpawner:spawner, BackgroundScroller:background, GameManager:manager, ScoreDisplay:ui
- Tower Defense: TowerController:player, EnemyWaveSpawner:spawner, EnemyScript:enemy, TowerProjectile:projectile, GameManager:manager
- Zombie Survival: SurvivorController:player, ZombieSpawner:spawner, ZombieScript:enemy, HealthBar:health, GameManager:manager
- Match-3 Puzzle: BoardManager:manager, GemScript:collectible, MatchDetector:generic, ScoreManager:ui, UIManager:ui"""

                    r = safe_chat(model=DEFAULT_MODEL, messages=[{"role": "user", "content": plan_prompt}])
                    scripts_raw = get_response(r).strip()

                    # .NET: parse "FileName:role" (newline-separated)
                    # Game: parse "Name:role" (comma-separated)
                    if detected_engine == "dotnet":
                        import re as _re
                        scripts_raw_norm = _re.sub(r'[\r]+', '\n', scripts_raw)
                        script_pairs = []
                        for line in scripts_raw_norm.split('\n'):
                            line = line.strip()
                            if ':' in line:
                                parts = line.split(':', 1)
                                name = parts[0].strip()
                                role = parts[1].strip().lower()
                                if name:
                                    script_pairs.append((name, role))
                        if not script_pairs:
                            script_pairs = [
                                ("ProductController", "controller"),
                                ("Product", "model"),
                                ("AppDbContext", "dbcontext"),
                                ("ProductService", "service"),
                                ("Program", "program"),
                            ]
                        script_pairs = script_pairs[:6]
                        script_names = [p[0] for p in script_pairs]
                        _gen_start = time.time()
                    else:
                        import re as _re
                        scripts_raw = _re.sub(r'[\n\r]+', ',', scripts_raw)
                        scripts_raw = _re.sub(r'\d+[\.\)]\s*', '', scripts_raw)
                        scripts_raw = _re.sub(r'^[-*•]\s*', '', scripts_raw, flags=_re.MULTILINE)
                        scripts_raw = _re.sub(r',{2,}', ',', scripts_raw)

                        # parse "Name:role" pairs
                        script_pairs = []
                        for item in scripts_raw.split(","):
                            item = item.strip().strip('"').strip("'")
                            if not item:
                                continue
                            if ":" in item:
                                parts = item.split(":", 1)
                                name = parts[0].strip()
                                role = parts[1].strip().lower()
                                role = role.split()[0] if role else "generic"
                                if name and len(name) < 40 and name[0].isupper():
                                    script_pairs.append((name, role))
                            elif item and len(item) < 40 and item[0].isupper():
                                script_pairs.append((item, "generic"))

                        # fallback defaults
                        if len(script_pairs) < 2:
                            print("⚠️ Planning response unclear, using defaults...", flush=True)
                            game_lower = task.lower()
                            if any(w in game_lower for w in ["racing","race","car","kart"]):
                                script_pairs = [("CarController","vehicle"),("OpponentAI","opponent"),("RaceManager","manager"),("Scoreboard","ui"),("CheckpointScript","collectible")]
                            elif any(w in game_lower for w in ["shooter","space","galaxy","star"]):
                                script_pairs = [("ShipController","player"),("EnemySpawner","spawner"),("EnemyScript","enemy"),("PowerUpScript","powerup"),("GameManager","manager")]
                            elif any(w in game_lower for w in ["runner","endless","temple","subway"]):
                                script_pairs = [("RunnerController","player"),("ObstacleSpawner","spawner"),("BackgroundScroller","background"),("UIManager","ui"),("HealthBar","health")]
                            elif any(w in game_lower for w in ["rpg","adventure","quest","dungeon"]):
                                script_pairs = [("PlayerController","player"),("EnemyScript","enemy"),("GameManager","manager"),("HealthBar","health"),("UIManager","ui")]
                            else:
                                script_pairs = [("PlayerController","player"),("EnemySpawner","spawner"),("EnemyScript","enemy"),("GameManager","manager"),("UIManager","ui")]

                    # Fix 1: remove any script named exactly after the project/game
                    project_key = _state.current_project_name.lower().replace(" ","").replace("_","")
                    script_pairs = [
                        (n, r) for n, r in script_pairs
                        if n.lower().replace(" ","").replace("_","") != project_key
                    ]

                    # Fix 2: detect puzzle/board games — templates mostly don't apply
                    puzzle_keywords = ["match","puzzle","board","grid","tile","gem","block","tetris","sudoku","chess","card"]
                    is_puzzle_game = any(w in task.lower() for w in puzzle_keywords)

                    # Fix 3: manager template is wave-based — non-wave managers → LLM
                    NON_WAVE_MANAGER_KEYWORDS = ["inventory","quest","dialog","save","level","audio","input","camera","loot","shop","store","item","board","grid","tile","match","puzzle","race","lap","checkpoint","round","turn"]
                    # Fix 4: collectible template (rotating pickup) doesn't fit puzzle gems/tiles
                    NON_PICKUP_COLLECTIBLE_KEYWORDS = ["gem","tile","block","card","piece","cell","slot","square"]

                    fixed_pairs = []
                    is_racing_game = any(w in task.lower() for w in ["racing","race","car","kart","drift","circuit","lap"])
                    # Keywords that indicate a script is NOT a health bar
                    NON_HEALTH_KEYWORDS = ["result","results","score","timer","race","lap","checkpoint","wave","spawn","manager","controller","ai","opponent","camera","audio","menu","ui","hud","leaderboard","settings","save","load","level","quest","dialog","inventory"]
                    for name, role in script_pairs:
                        name_lower = name.lower()
                        # Fix: manager template is wave-based
                        if role == "manager" and any(kw in name_lower for kw in NON_WAVE_MANAGER_KEYWORDS):
                            role = "generic"
                        if role == "manager" and is_racing_game:
                            role = "generic"
                        # Fix: collectible template doesn't fit puzzle gems/tiles
                        if role == "collectible" and (is_puzzle_game or any(kw in name_lower for kw in NON_PICKUP_COLLECTIBLE_KEYWORDS)):
                            role = "generic"
                        # Fix: health template only for actual health/HP bars
                        if role == "health" and any(kw in name_lower for kw in NON_HEALTH_KEYWORDS):
                            role = "ui" if any(kw in name_lower for kw in ["timer","score","hud","ui","result","results","leaderboard"]) else "generic"
                        # Fix: collectible template wrong for racing checkpoints
                        if role == "collectible" and is_racing_game and any(kw in name_lower for kw in ["checkpoint","trigger","gate","zone"]):
                            role = "generic"
                        # ✅ Puzzle gem script → gem template
                        if is_puzzle_game and any(kw in name_lower for kw in ["gem","tile","piece","card","block","cell"]) and role in ("generic","collectible","player"):
                            role = "gem"
                        # ✅ Puzzle board manager → board template
                        if is_puzzle_game and any(kw in name_lower for kw in ["board","grid","map"]) and role in ("generic","manager"):
                            role = "board"
                        # ✅ Name-based upgrades: generic scripts with clear purpose → better template
                        # UI-named generics → ui template
                        if role == "generic" and any(kw in name_lower for kw in ["hud","ui","score","timer","results","result","leaderboard","display","panel","overlay"]):
                            role = "ui"
                        # Spawner-named generics → spawner template
                        if role == "generic" and any(kw in name_lower for kw in ["spawner","spawn","generator","wave"]):
                            role = "spawner"
                        # Projectile-named generics → projectile template
                        if role == "generic" and any(kw in name_lower for kw in ["bullet","projectile","missile","shot","laser"]):
                            role = "projectile"
                        # Health-named generics → health template
                        if role == "generic" and any(kw in name_lower for kw in ["healthbar","health_bar","hpbar"]):
                            role = "health"
                        # Player/vehicle named → correct template
                        if role == "generic" and any(kw in name_lower for kw in ["player","ship","survivor","hero","character"]) and not is_racing_game:
                            role = "player"
                        if role == "generic" and any(kw in name_lower for kw in ["car","vehicle","kart","bike","truck","racer"]):
                            role = "vehicle"
                        if role == "generic" and any(kw in name_lower for kw in ["opponent","rival","npc","bot","ai"]):
                            role = "opponent"
                        if role == "generic" and any(kw in name_lower for kw in ["enemy","zombie","monster","alien","ghost","boss"]):
                            role = "enemy"
                        if role == "generic" and any(kw in name_lower for kw in ["powerup","power_up","pickup","boost","item","drop"]):
                            role = "powerup"
                        # Checkpoint scripts → collectible template (trigger-based)
                        if role == "generic" and "checkpoint" in name_lower:
                            role = "collectible"
                        # GameManager always → manager template (wave/score/gameover)
                        if name_lower == "gamemanager":
                            role = "manager"
                        # Tower script → enemy template (has TakeDamage, health, etc.)
                        if role == "generic" and any(kw in name_lower for kw in ["tower","turret","cannon","defense"]) and not is_racing_game:
                            role = "enemy"
                        # Coin/star/key/gem pickup (non-puzzle) → collectible
                        if role == "generic" and any(kw in name_lower for kw in ["coin","star","key","diamond","crystal","orb"]):
                            role = "collectible"
                        # NPC → enemy template base (has movement, health)
                        if role == "generic" and any(kw in name_lower for kw in ["npc","villager","merchant","guard"]):
                            role = "enemy"
                        fixed_pairs.append((name, role))
                    script_pairs = fixed_pairs

                    script_pairs = script_pairs[:6]
                    script_names = [p[0] for p in script_pairs]

                    # ===== Universal Role Templates =====
                    # Templates loaded from unity_templates.py and dotnet_templates.py

                    def get_template(sname, role="generic"):
                        if detected_engine == "dotnet":
                            return get_dotnet_template(sname, role)
                        if detected_engine == "react":
                            return get_react_template(sname, role)
                        if detected_engine == "angular":
                            return get_angular_template(sname, role)
                        if detected_engine == "html":
                            return get_html_template(sname, role)
                        if detected_engine == "sql":
                            return get_sql_template(sname, role)
                        if detected_engine == "python":
                            return get_python_template(sname, role)
                        if role in TEMPLATED_ROLES:
                            tpl = UNIVERSAL_TEMPLATES.get(role)
                            if tpl:
                                return tpl.format(name=sname)
                        return None

                    def get_fill_template(sname, role, task_desc):
                        """Returns a compilable skeleton for game-specific roles"""
                        if role not in FILL_TEMPLATES:
                            return None
                        # Build empty fill values so template always compiles
                        fill_defaults = {
                            "fill_update": "// update logic here",
                            "fill_fixed_update": "// physics here",
                            "fill_extra": "// extra methods",
                            "fill_attack": "// attack logic",
                            "fill_collision": "// collision logic",
                            "fill_effect": "// apply power-up effect",
                            "fill_fields": "// fields here",
                            "fill_start": "// init here",
                            "fill_methods": "// methods here",
                        }
                        skeleton = FILL_TEMPLATES[role].format(name=sname, **fill_defaults)
                        return skeleton



                    # ==========================================================

                    ENGINE_PROMPTS = {
                        "unity": {
                            "system": """You are a senior Unity C# developer.
RULES:
- Use C# with MonoBehaviour
- All variables used must be declared first
- Return ONLY one ```csharp code block""",
                            "lang": "Unity C#",
                            "block": "csharp",
                            "skip_template": False
                        },
                        "unreal": {
                            "system": UNREAL_SYSTEM_PROMPT,
                            "lang": "Unreal C++",
                            "block": "cpp",
                            "skip_template": True
                        },
                        "dotnet": {
                            "system": DOTNET_SYSTEM_PROMPT,
                            "lang": "ASP.NET Core C#",
                            "block": "csharp",
                            "skip_template": False
                        },
                        "dotnet_web": {
                            "system": DOTNET_SYSTEM_PROMPT,
                            "lang": "ASP.NET Core MVC",
                            "block": "csharp",
                            "skip_template": False
                        },
                        "react": {
                            "system": REACT_SYSTEM_PROMPT,
                            "lang": "React.js",
                            "block": "jsx",
                            "skip_template": False
                        },
                        "sql": {
                            "system": SQL_SYSTEM_PROMPT,
                            "lang": "SQL",
                            "block": "sql",
                            "skip_template": False
                        },
                        "angular": {
                            "system": ANGULAR_SYSTEM_PROMPT,
                            "lang": "Angular TypeScript",
                            "block": "typescript",
                            "skip_template": False
                        },
                        "html": {
                            "system": HTML_SYSTEM_PROMPT,
                            "lang": "HTML/CSS/JS",
                            "block": "html",
                            "skip_template": False
                        },
                        "python": {
                            "system": PYTHON_SYSTEM_PROMPT,
                            "lang": "Python",
                            "block": "python",
                            "skip_template": False
                        }
                    }
                    eng_cfg = ENGINE_PROMPTS[detected_engine]
                    system_unity = eng_cfg["system"]

                    _gen_start = time.time()
                    print(f"📋 Scripts to generate: {', '.join(script_names)}", flush=True)

                    saved = []
                    failed = []
                    generated_scripts_context = {}  # name → code, for cross-script awareness

                    for script_name, script_role in script_pairs:
                        print(f"\n⚙️ Writing {script_name} ({detected_engine}) ...", flush=True)

                        template = None if eng_cfg["skip_template"] else get_template(script_name, script_role)
                        used_template = False
                        if template:
                            print(f"📐 Using template [{script_role}] for {script_name}", flush=True)
                            code_response = "```csharp\n" + template + "\n```"
                            used_template = True
                            # store template code for context too
                            generated_scripts_context[script_name] = template
                        else:
                            # ✅ NEW: Fill-Template approach for game-specific roles
                            # 1. Get compilable skeleton with FILL markers
                            # 2. LLM fills ONLY the logic sections
                            # 3. Structure always compiles ✅

                            # Build context from already-generated scripts
                            context_block = ""
                            if generated_scripts_context:
                                context_parts = []
                                for prev_name, prev_code in generated_scripts_context.items():
                                    sig_lines = []
                                    for line in prev_code.split('\n'):
                                        stripped = line.strip()
                                        if any(stripped.startswith(k) for k in ['public class','public enum','public interface','public void','public int','public float','public bool','public string','public List','public static','private void','    public']):
                                            sig_lines.append('  ' + stripped)
                                    context_parts.append(f"// {prev_name}.cs signatures:\n" + '\n'.join(sig_lines[:15]))
                                context_block = "ALREADY GENERATED SCRIPTS (use these exact signatures — do NOT redeclare their enums/classes):\n" + '\n\n'.join(context_parts)

                            skeleton = get_fill_template(script_name, script_role, task)
                            fill_rules = ROLE_FILL_RULES.get(script_role, "")

                            if skeleton and detected_engine == "unity":
                                # Fill-template prompt: LLM completes the skeleton
                                fill_prompt = f"""You are a Unity C# developer. Complete this script for the game: {task}

SCRIPT NAME: {script_name}
ROLE: {script_role}

{context_block}

HERE IS THE SKELETON — replace every // FILL: comment with real working code:

```csharp
{skeleton}
```

{fill_rules.format(task=task, name=script_name) if fill_rules else ""}

RULES:
- Keep ALL existing method signatures exactly as they are
- Replace EVERY // FILL: ... line with real implementation
- Do NOT add new class declarations or enums that exist in other scripts above
- Do NOT leave any // FILL: markers in the output
- Return ONLY one ```csharp code block"""

                                r = safe_chat(model=model_name, messages=[
                                    {"role": "system", "content": system_unity},
                                    {"role": "user", "content": fill_prompt}
                                ])
                                code_response = get_response(r)

                                # If LLM still left FILL markers → use skeleton directly (compiles safely)
                                if "// FILL:" in code_response or "```" not in code_response:
                                    print(f"⚠️ LLM left FILL markers in {script_name} — using skeleton", flush=True)
                                    code_response = "```csharp\n" + skeleton + "\n```"

                            else:
                                # Fallback: generate from scratch (non-unity or unknown role)
                                single_prompt = f"""Write a {eng_cfg['lang']} script named {script_name} for this game: {task}

ROLE: {script_role}

{context_block}

UNIVERSAL RULES:
1. Use correct namespaces
2. Class declaration: public class {script_name} : MonoBehaviour
3. Array initialization in Start() or Awake() — NEVER at field declaration
4. Do NOT redeclare enums/classes from other scripts above
5. Only call methods that actually exist in the other scripts above
6. Declare ALL variables before using them
7. NO empty method bodies, NO placeholders, NO TODO
8. Return ONLY one ```{eng_cfg['block']} code block"""

                                r = safe_chat(model=model_name, messages=[
                                    {"role": "system", "content": system_unity},
                                    {"role": "user", "content": single_prompt}
                                ])
                                code_response = get_response(r)

                                placeholder_signs = ["// add", "// todo", "// replace", "/* ", "your logic", "your code", "implement here", "add logic", "assuming"]
                                if any(p in code_response.lower() for p in placeholder_signs):
                                    print(f"⚠️ Placeholder in {script_name}, regenerating...", flush=True)
                                    r2 = safe_chat(model=model_name, messages=[
                                        {"role": "system", "content": system_unity},
                                        {"role": "user", "content": f"Rewrite {script_name} with NO placeholders and NO empty methods. Real code only.\nPrevious: {code_response}"}
                                    ])
                                    code_response = get_response(r2)


                        code_response = auto_fix_unity_code(code_response)

                        # ✅ Skip LLM review for template-based scripts — templates are already clean
                        if used_template:
                            pass  # Template is correct — no review needed
                        else:
                            print(f"🔍 Reviewing {script_name} ...", flush=True)
                            # build role-specific review rules
                            role_rules = {
                                "player":     "- Player moves with WASD/arrows using Rigidbody2D.velocity — do NOT use transform.Translate\n- Shoot with Fire1 button, NOT Space melee attack for shooter games",
                                "enemy":      "- Asteroid/obstacle/meteor enemies move DOWNWARD (Vector3.down / negative Y velocity) — do NOT chase player\n- Chasing enemies use player.position - transform.position normalized",
                                "powerup":    "- PowerUps FALL DOWN (Vector3.down, negative Y) toward player — NEVER move up\n- Destroy when position.y < -Camera.main.orthographicSize - 2f (below screen)\n- DO NOT change Vector3.down to Vector3.up",
                                "background": "- Background scrolls LEFT (negative X direction)\n- Use Camera.main.orthographicSize for world-space boundaries, NOT Screen.width",
                                "spawner":    "- Use spawnPoints array for spawn positions\n- Never spawn at fixed hardcoded positions",
                                "projectile": "- Bullet moves in transform.up direction (upward for player bullets)\n- Destroy after 3 seconds or on trigger hit",
                                "collectible":"- Collectible stays STILL, never moves itself\n- Use OnTriggerEnter2D to detect player",
                            }
                            extra_rule = role_rules.get(script_role, "")

                            review_prompt = f"""Fix ALL bugs in this Unity C# script named {script_name} (role: {script_role}):

ROLE-SPECIFIC RULES (CRITICAL — do not violate these):
{extra_rule}

GENERAL BUGS TO FIX:
1. Variables used but never declared → declare them with default values
2. FindGameObjectsWithTag without GameObject. prefix → fix it
3. Index out of range → add bounds check
4. Type mismatches (int vs float) → cast correctly
5. Null check WRONG pattern:
   WRONG: if (x != null) x = GetComponent<...>();
   RIGHT:  if (x == null) x = GetComponent<...>();
6. Instantiate result stored back into prefab variable → use separate instance variable
7. Empty method bodies → implement real logic (no empty CheckForMatches, no empty Update)
8. Missing System. prefix → Enum.GetValues → System.Enum.GetValues, List<> → System.Collections.Generic.List<>
9. Type array mismatch → if array is GemType[,] do NOT assign non-GemType values to it
10. Class name MUST stay exactly: {script_name}

Return the FIXED script as ONE ```csharp block. Keep class name as {script_name}.

Script to fix:
{code_response}"""
                            r_review = safe_chat(model=model_name, messages=[
                                {"role": "system", "content": "Unity C# bug fixer. Return ONLY one ```csharp block."},
                                {"role": "user", "content": review_prompt}
                            ])
                            reviewed = get_response(r_review)
                            if "```" in reviewed:
                                code_response = auto_fix_unity_code(reviewed)

                            # ✅ تأكد إن اسم الكلاس = script_name (Unity only)
                            if detected_engine == "unity":
                                code_response = re.sub(
                                    r'(public\s+class\s+)\w+(\s*:\s*MonoBehaviour)',
                                    rf'\g<1>{script_name}\2',
                                    code_response
                                )

                        # ====== ✅ Compile Validation (dotnet build) ======
                        if detected_engine == "unity" and not used_template:
                            MAX_FIX_ATTEMPTS = 3
                            for attempt in range(MAX_FIX_ATTEMPTS):
                                errors = compile_check_csharp(
                                    script_name,
                                    code_response,
                                    generated_scripts_context,
                                    planned_scripts=script_names
                                )
                                if not errors:
                                    break  # نظيف ✅
                                print(f"🔧 Compile errors ({len(errors)}) — fixing attempt {attempt+1}/{MAX_FIX_ATTEMPTS}...", flush=True)
                                for e in errors[:5]:
                                    print(f"   {e}", flush=True)

                                # ابعت للـ LLM يصلح
                                ctx = ""
                                if generated_scripts_context:
                                    ctx_parts = []
                                    for pn, pc in generated_scripts_context.items():
                                        sigs = [l.strip() for l in pc.split('\n') if any(l.strip().startswith(k) for k in ['public class','public enum','public void','public int','public float','public bool','public static'])]
                                        ctx_parts.append(f"// {pn}.cs:\n" + '\n'.join(f"  {s}" for s in sigs[:10]))
                                    ctx = "CONTEXT (existing scripts):\n" + '\n\n'.join(ctx_parts)

                                fixed = llm_fix_compile_errors(script_name, code_response, errors, model_name, ctx)
                                if "```" in fixed:
                                    code_response = auto_fix_unity_code(fixed)
                                    code_response = re.sub(
                                        r'(public\s+class\s+)\w+(\s*:\s*MonoBehaviour)',
                                        rf'\g<1>{script_name}\2',
                                        code_response
                                    )
                            else:
                                # بعد 3 محاولات لو لسه فيه errors — سجل تحذير بس احفظ
                                remaining = compile_check_csharp(script_name, code_response, generated_scripts_context, planned_scripts=script_names)
                                if remaining:
                                    print(f"⚠️ {script_name} لسه فيه {len(remaining)} error(s) بعد {MAX_FIX_ATTEMPTS} محاولات", flush=True)

                        success = extract_and_save_scripts(
                            code_response,
                            _state.current_project_name,
                            forced_name=script_name,
                            forced_ext=(
                                DOMAIN_REGISTRY[detected_engine]["get_ext"](script_name, script_role)
                                if detected_engine in DOMAIN_REGISTRY
                                and detected_engine not in ("unity", "unreal")
                                else None
                            )
                        )
                        if success:
                            # Include correct file extension in saved list
                            if detected_engine in DOMAIN_REGISTRY and detected_engine not in ("unity","unreal"):
                                _ext = DOMAIN_REGISTRY[detected_engine]["get_ext"](script_name, script_role)
                            elif detected_engine == "unity":
                                _ext = ".cs"
                            else:
                                _ext = ""
                            saved.append(script_name + _ext)
                            # extract raw code for cross-script context
                            import re as _re2
                            _m = _re2.search(r'```(?:csharp|cs)?\n(.*?)```', code_response, _re2.DOTALL)
                            if _m:
                                full = _m.group(1)
                                sigs = [l for l in full.split("\n") if re.match(r"\s*(public|private|void|float|int|bool|string|class|using)", l)]
                                generated_scripts_context[script_name] = "\n".join(sigs[:20])
                        else:
                            failed.append(script_name)

                    # ملخص النتيجة
                    _gen_time = round(time.time() - _gen_start, 1)
                    log.info(f"⏱ Generation done in {_gen_time}s — saved={len(saved)}")
                    metrics.record_generation(bool(saved), detected_engine, _gen_time)
                    metrics.save()
                    _WEB_DOM = ("dotnet","react","angular","html","sql","python")
                    if detected_engine in _WEB_DOM:
                        _sum_icon  = "🌐"
                        _sum_label = "موقع" if detected_engine in ("dotnet","react","angular","html") else "قاعدة بيانات" if detected_engine == "sql" else "مشروع"
                    else:
                        _sum_icon  = "🎮"
                        _sum_label = "لعبة"
                    summary = f"{_sum_icon} تم إنشاء {_sum_label} {_state.current_project_name}!\n\n"
                    # Use correct extension per file
                    for s in saved:
                        summary += f"   ✅ {s}\n"
                    if failed:
                        for s in failed:
                            summary += f"   ❌ {s} فشل\n"
                    summary += f"\n[ 💾 الملفات في: Generated_Scripts/{_state.current_project_name.replace(' ', '_')} ]"

                    print(f"\n🤖 Agent: {summary}\n\n", flush=True)
                    chat_history.append({"role": "assistant", "content": summary})

                    # ✅ Create .csproj for dotnet projects if missing
                    if detected_engine == "dotnet":
                        import os as _os
                        _proj_folder = _os.path.join("Generated_Scripts", _state.current_project_name.replace(" ","_"))
                        _csproj_path = _os.path.join(_proj_folder, f"{_state.current_project_name}.csproj")
                        if not _os.path.exists(_csproj_path):
                            _csproj = """<Project Sdk="Microsoft.NET.Sdk.Web">
  <PropertyGroup>
    <TargetFramework>net8.0</TargetFramework>
    <Nullable>enable</Nullable>
    <ImplicitUsings>enable</ImplicitUsings>
  </PropertyGroup>
  <ItemGroup>
    <PackageReference Include="Microsoft.EntityFrameworkCore" Version="8.0.0" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.Sqlite" Version="8.0.0" />
    <PackageReference Include="Microsoft.EntityFrameworkCore.Design" Version="8.0.0">
      <PrivateAssets>all</PrivateAssets>
      <IncludeAssets>runtime; build; native; contentfiles; analyzers</IncludeAssets>
    </PackageReference>
    <PackageReference Include="Microsoft.AspNetCore.Mvc.NewtonsoftJson" Version="8.0.0" />
  </ItemGroup>
</Project>
"""
                            _program_cs = """using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllersWithViews();
builder.Services.AddDbContext<AppDbContext>(opt =>
    opt.UseSqlite("Data Source=app.db"));

var app = builder.Build();

if (!app.Environment.IsDevelopment())
{
    app.UseExceptionHandler("/Home/Error");
    app.UseHsts();
}

app.UseHttpsRedirection();
app.UseStaticFiles();
app.UseRouting();
app.UseAuthorization();

// Auto-create DB on startup
using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<AppDbContext>();
    db.Database.EnsureCreated();
}

app.MapControllerRoute(
    name: "default",
    pattern: "{controller=Products}/{action=Index}/{id?}");

app.Run();
"""
                            try:
                                with open(_csproj_path, "w", encoding="utf-8") as _f:
                                    _f.write(_csproj)
                                _prog = _os.path.join(_proj_folder, "Program.cs")
                                if not _os.path.exists(_prog):
                                    with open(_prog, "w", encoding="utf-8") as _f:
                                        _f.write(_program_cs)
                                # Create minimal Views structure so dotnet build doesn't fail
                                _views_dir = _os.path.join(_proj_folder, "Views", "Shared")
                                _os.makedirs(_views_dir, exist_ok=True)
                                _layout_path = _os.path.join(_views_dir, "_Layout.cshtml")
                                if not _os.path.exists(_layout_path):
                                    _layout_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>@ViewData["Title"] - MyApp</title>
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" />
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">MyApp</a>
        </div>
    </nav>
    <main class="container mt-4">
        @RenderBody()
    </main>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    @await RenderSectionAsync("Scripts", required: false)
</body>
</html>
"""
                                    with open(_layout_path, "w", encoding="utf-8") as _f:
                                        _f.write(_layout_html)
                                _viewstart = _os.path.join(_proj_folder, "Views", "_ViewStart.cshtml")
                                if not _os.path.exists(_viewstart):
                                    with open(_viewstart, "w", encoding="utf-8") as _f:
                                        _f.write('@{ Layout = "_Layout"; }\n')
                                _viewimports = _os.path.join(_proj_folder, "Views", "_ViewImports.cshtml")
                                if not _os.path.exists(_viewimports):
                                    with open(_viewimports, "w", encoding="utf-8") as _f:
                                        _f.write("@using Microsoft.AspNetCore.Mvc.Razor\n@addTagHelper *, Microsoft.AspNetCore.Mvc.TagHelpers\n")
                                print(f"\U0001f4c4 Created {_state.current_project_name}.csproj + Views scaffold", flush=True)
                            except Exception as _e:
                                print(f"⚠ csproj error: {_e}", flush=True)

                    # ✅ Auto-launch website in browser for web engines
                    if detected_engine in ("html", "react", "angular", "dotnet"):
                        print(f"🌐 فاتح الـ website في الـ browser...", flush=True)
                        launch_website(_state.current_project_name, detected_engine)

                    _state.current_project_name = ""
                    save_session()

                # ========== SINGLE SCRIPT ==========
                elif is_script_request:
                    if not _state.current_project_name:
                        name_check_prompt = f"Extract the game or project name from this text. If none is mentioned, reply ONLY with 'NONE'. Text: '{task}'"
                        r = safe_chat(model=DEFAULT_MODEL, messages=[{"role": "user", "content": name_check_prompt}])
                        extracted_name = get_response(r).strip()
                        if "NONE" in extracted_name.upper() or len(extracted_name) >= 30:
                            print("❓ What's the name of your game project?", flush=True)
                            _state.current_project_name = input().strip()
                            if not _state.current_project_name:
                                _state.current_project_name = "MyGame"
                        else:
                            _state.current_project_name = extracted_name
                    
                    r = safe_chat(model=model_name, messages=messages_to_send)
                    full_response = get_response(r)

                    success = extract_and_save_scripts(full_response, _state.current_project_name)

                    if success:
                        clean_text = f"""عاش يا هندسة! 🫡 الأكواد اتبرمجت واتقسمت صح.

                    [ 💾 تم حفظ الملفات بنجاح في: Generated_Scripts/{_state.current_project_name.replace(' ', '_')} ]
                    """
                    else:
                        clean_text = "⚠️ تم إيقاف الحفظ بسبب أخطاء في الكود."

                    print(f"\n🤖 Agent: {clean_text}\n\n")
                    sys.stdout.flush()
                    chat_history.append({"role": "assistant", "content": clean_text})
                    _state.current_project_name = ""
                    save_session()
                    
                else:
                    stream = safe_chat(model=model_name, messages=messages_to_send, stream=True)
                    sys.stdout.write("\n🤖 Agent: ")
                    sys.stdout.flush()
                    
                    full_response = ""
                    for chunk in stream:
                        word = chunk['message']['content']
                        full_response += word
                        sys.stdout.write(word)
                        sys.stdout.flush()
                    sys.stdout.write("\n\n")
                    sys.stdout.flush()
                    chat_history.append({"role": "assistant", "content": full_response})
                    save_session()
        
        else:
            chat_history[-1]["images"] = images if images else None
            messages_with_files = [{"role": "system", "content": system_prompt}] + chat_history
            r = safe_chat(model=model_name, messages=messages_with_files)
            result = get_response(r)
            print(f"\n🤖 Agent: {result}\n\n")
            sys.stdout.flush()
            chat_history.append({"role": "assistant", "content": result})
            save_session()
            
        sys.stdout.flush()

    except Exception as e:
        print(f"❌ Error: {e}")
        if chat_history:
            chat_history.pop()

# ================= FILE TYPE DETECTOR =================

# File handlers → file_handler.py
from file_handler import (
    detect_file_type, detect_intent, select_relevant_files, brain_prompt,
    handle_code_file, handle_image_file, handle_video_file,
    handle_pdf_file, handle_word_file, handle_excel_file, handle_ppt_file,
    attach_tool, inject_globals as _fh_inject
)

def self_mod_tool(task: str):
    """Agent modifies its own source files to add new capabilities."""
    import os

    # List agent files
    agent_files = [f for f in os.listdir('.') if f.endswith('.py') and
                   any(n in f for n in ['agent', 'templates', 'stubs'])]
    file_list = "\n".join(f"  - {f}" for f in agent_files)

    print(f"🔧 Self-modification requested: {task}", flush=True)
    print(f"📁 Agent files found: {len(agent_files)}", flush=True)

    # Build prompt
    prompt = SELF_MOD_PROMPT.format(
        file_list=file_list,
        task=task
    )

    r = safe_chat(
        model=DEFAULT_MODEL,
        messages=[{"role": "user", "content": prompt}]
    )
    response = get_response(r)

    # Extract which file to modify
    target_file = None
    for f in agent_files:
        if f.replace('.py','').lower() in task.lower():
            target_file = f
            break
    if not target_file:
        target_file = "agent.py"

    # Extract code and save
    import re as _re
    match = _re.search(r"```python\n(.*?)```", response, _re.DOTALL)
    if match:
        new_code = match.group(1)
        # Syntax check before writing
        try:
            import ast as _ast
            _ast.parse(new_code)
            if os.path.exists(target_file):
                import shutil as _sh
                _sh.copy2(target_file, target_file + ".bak")
                log.info(f"Backup: {target_file}.bak")
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(new_code)
            log.success(f"{target_file} updated — restart to apply")
        except SyntaxError as e:
            print(f"❌ Syntax error in generated code — NOT saved: {e}", flush=True)
    else:
        print("❌ No Python code block found in response.", flush=True)


# ═══════════════════════════════════════════════════════════
# BACKGROUND EXECUTOR
# ═══════════════════════════════════════════════════════════
import threading as _threading

_current_task = None
_task_lock = _threading.Lock()

def run_in_background(fn, *args, **kwargs):
    global _current_task
    def _wrapper():
        try:
            fn(*args, **kwargs)
        except Exception as e:
            log.error(f"Task error in {fn.__name__}: {e}")
    with _task_lock:
        t = _threading.Thread(target=_wrapper, daemon=True, name=f"agent-{fn.__name__}")
        _current_task = t
        t.start()

def is_task_running():
    return _current_task is not None and _current_task.is_alive()


# ═══════════════════════════════════════════════════════════
# SIGNAL HANDLING + SUBPROCESS REGISTRY
# ═══════════════════════════════════════════════════════════
import signal, atexit

child_processes: list = []   # registry of all spawned subprocesses

def _register_process(proc):
    """Add process to registry so shutdown can clean it up."""
    child_processes.append(proc)
    return proc

def handle_shutdown(signum=None, frame=None):
    """Graceful shutdown — save state and terminate child processes."""
    try:
        log.info("Shutting down agent gracefully...")
        # Save metrics and session
        try:
            metrics.save()
        except Exception:
            pass
        try:
            save_session()
        except Exception:
            pass
        # Terminate child processes (prevent zombies)
        for p in child_processes:
            try:
                if p.poll() is None:
                    p.terminate()
            except Exception:
                pass
        log.info("Shutdown complete.")
    except Exception:
        pass

# Register for all exit scenarios
signal.signal(signal.SIGINT,  handle_shutdown)
signal.signal(signal.SIGTERM, handle_shutdown)
atexit.register(handle_shutdown)

# ═══════════════════════════════════════════════════════════
# TOOL REGISTRY — all tools in one place
# To add a new tool: add entry here + implement the function
# ═══════════════════════════════════════════════════════════
def _tool_run(user):
    last = load_last_project()
    if last and os.path.exists(last):
        run_python(last)
    else:
        print("❌ No valid project history found.")

def _tool_clear(user):
    project_context.clear()
    if os.path.exists(CONTEXT_FILE):
        os.remove(CONTEXT_FILE)
    print("🧹 Project context cleared.")

def _tool_attach(user):
    file_path = user.replace("attach", "", 1).strip()
    attach_tool(file_path)

TOOL_REGISTRY = {
    "GAME":    chat_tool,      # Unity / Unreal / .NET / React generation
    "PROJECT": project_tool,   # Python project builder
    "JOB":     job_tool,       # job search
    "DELETE":  delete_tool,    # delete files/projects
    "RUN":     _tool_run,      # run python project
    "ATTACH":  _tool_attach,   # attach file to context
    "CLEAR":   _tool_clear,    # clear project context
    "CHAT":    chat_tool,      # general chat / LLM
    "SELF_MOD": self_mod_tool,  # agent modifies its own files
}

# ── Preflight check ──────────────────────────────────────────
check_and_exit_if_missing()

# ── Inject globals into file_handler ────────────────────────
_fh_inject(
    safe_chat=safe_chat, get_response=get_response,
    DEFAULT_MODEL=DEFAULT_MODEL, log=log,
    _state=_state, project_context=project_context, safe_print=safe_print
)

log.success("AGENT READY — type your request")

while True:
    try:
        user = input().strip()
        _state.last_user_input = user

        # ✅ Stop signal from GUI
        if user == "⛔ STOP_AGENT" or user == "STOP_AGENT":
            print("⛔ Stopped.", flush=True)
            continue

        intent = detect_intent(user)
        if intent != "default":
            _state.active_intent = intent

        if user.lower() == "exit": break
        if not user: continue

        # ── Session commands (before mode detection) ──
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

        # ── Route to tool ──
        mode, detected_domain = detect_mode(user)  # ✅ one-pass intent+domain
        tool = TOOL_REGISTRY.get(mode, chat_tool)

        BACKGROUND_TOOLS = {"GAME", "PROJECT", "JOB", "SELF_MOD", "CHAT"}
        if mode in BACKGROUND_TOOLS:
            _kw = {"_hint_domain": detected_domain} if (tool is chat_tool and detected_domain != "general") else {}
            run_in_background(tool, user, **_kw)
        else:
            tool(user)

    except KeyboardInterrupt:
        print("\nExiting...")
        break
    except Exception as e:
        print(f"❌ Critical Error: {e}")
