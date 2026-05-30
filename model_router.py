# model_router.py — Intent detection, domain detection, request routing
# Extracted from agent.py — single source of truth for all routing logic

import llm_client
from llm_client  import safe_chat, get_response
from logger      import safe_print


# ── Domain Registry ───────────────────────────────────────────────────────────
# Imported lazily via lambdas to avoid circular imports at module load time.
# To add a new domain: add ONE entry here — routing is automatic everywhere.
def _build_domain_registry() -> dict:
    from dotnet_templates  import (DOTNET_PLANNING_PROMPT, DOTNET_FULLSTACK_PLANNING_PROMPT,
                                   get_dotnet_ext as _get_dotnet_ext)
    from react_templates   import REACT_PLANNING_PROMPT,   get_react_ext
    from angular_templates import ANGULAR_PLANNING_PROMPT, get_angular_ext
    from html_templates    import HTML_PLANNING_PROMPT,    get_html_ext
    from sql_templates     import SQL_PLANNING_PROMPT
    from python_templates  import PYTHON_PLANNING_PROMPT

    return {
        "unity": {
            "keywords": ["unity", "يونتي"],
            "planning": None,
            "get_ext": lambda n, r: ".cs",
            "lang": "Unity C#",
            "launchable": False,
            "validator": "unity",
        },
        "unreal": {
            "keywords": ["unreal", "c++", "أنريل"],
            "planning": None,
            "get_ext": lambda n, r: ".h",
            "lang": "Unreal C++",
            "launchable": False,
            "validator": "unreal",
        },
        "dotnet": {
            "keywords": ["dotnet", ".net", "asp.net", "aspnet", "web api", "webapi"],
            "planning": lambda task: (
                DOTNET_FULLSTACK_PLANNING_PROMPT
                if any(w in task.lower() for w in ["website", "web app", "mvc", "razor", "موقع", "frontend"])
                else DOTNET_PLANNING_PROMPT
            ).format(task=task),
            "get_ext": lambda n, r: _get_dotnet_ext(n, r),
            "lang": "ASP.NET Core C#",
            "launchable": True,
        },
        "react": {
            "keywords": ["react", "reactjs", "react.js", "vite", "nextjs", "next.js"],
            "planning": lambda t: REACT_PLANNING_PROMPT.format(task=t),
            "get_ext": lambda n, r: get_react_ext(n, r),
            "lang": "React.js",
            "launchable": True,
        },
        "angular": {
            "keywords": ["angular", "angularjs", "ng "],
            "planning": lambda t: ANGULAR_PLANNING_PROMPT.format(task=t),
            "get_ext": lambda n, r: get_angular_ext(n, r),
            "lang": "Angular TypeScript",
            "launchable": True,
        },
        "html": {
            "keywords": ["html", "html5", "vanilla js", "static site", "plain website"],
            "planning": lambda t: HTML_PLANNING_PROMPT.format(task=t),
            "get_ext": lambda n, r: get_html_ext(n, r),
            "lang": "HTML/CSS/JS",
            "launchable": True,
        },
        "sql": {
            "keywords": ["sql", "database", "postgres", "postgresql", "mysql",
                         "sqlite", "db schema", "قاعدة بيانات"],
            "planning": lambda t: SQL_PLANNING_PROMPT.format(task=t),
            "get_ext": lambda n, r: ".sql",
            "lang": "SQL",
            "launchable": False,
        },
        "python": {
            "keywords": ["python", "بايثون", "fastapi", "flask", "script", "pip"],
            "planning": lambda t: PYTHON_PLANNING_PROMPT.format(task=t),
            "get_ext": lambda n, r: ".py",
            "lang": "Python",
            "launchable": False,
        },
    }


# Build once at import time
DOMAIN_REGISTRY = _build_domain_registry()


# ── Domain detection ──────────────────────────────────────────────────────────
def detect_domain(task: str) -> str:
    """Detect domain from task text. Returns domain key or 'general'."""
    t = task.lower()
    for domain in ["unity", "unreal", "dotnet", "react", "angular", "html", "sql", "python"]:
        if any(kw in t for kw in DOMAIN_REGISTRY[domain]["keywords"]):
            return domain
    return "general"


# Alias kept for backward compatibility
detect_requested_language = detect_domain


# ── Intent / mode detection ───────────────────────────────────────────────────
def detect_mode(user: str) -> tuple:
    """
    Smart intent router — rule-based fast path, LLM fallback for ambiguous cases.

    Priority:
      1. Hard system commands  (never LLM)
      2. Fast keyword rules    (saves LLM call for obvious cases)
      3. LLM classification    (skipped for short messages < 4 words)

    Returns: (mode: str, domain: str)
    """
    t = user.lower().strip()

    # ── 1. Hard system commands ───────────────────────────────────────────────
    if t.startswith("attach "):       return "ATTACH",       "general"
    if t == "clear":                  return "CLEAR",        "general"
    if t == "run":                    return "RUN",          "general"
    if t.startswith("/auto ") or t.startswith("/autonomous "):
        return "AUTO", "general"
    
    if t.startswith("/multi ") or t.startswith("/multiagent "):
        return "MULTI", "general"

    if t.startswith("load_session "): 
        return "LOAD_SESSION", "general"

    # ── 2. Keyword sets ───────────────────────────────────────────────────────
    CREATION_VERBS = [
        "make", "create", "build", "generate", "write", "design",
        "عمل", "اعمل", "عايز", "ابني", "انشئ", "اكتب", "سوّي",
    ]
    GAME_TARGETS = [
        "game", "لعبة", "unity", "unreal",
        "shooter", "platformer", "racing", "puzzle", "rpg",
        "tower defense", "moba", "battle royale", "roguelike", "roguelite",
        "fighting", "stealth", "horror", "idle", "fishing", "cooking",
        "flight", "kart", "runner", "brawler", "strategy", "simulation",
        "sandbox", "survival", "dungeon", "metroidvania", "vr game", "ar game",
    ]
    JOB_KEYWORDS = [
        "job", "jobs", "hiring", "وظيفة", "وظائف", "شغل", "فرص",
        "career", "vacancy", "vacancies", "توظيف",
    ]
    DELETE_KEYWORDS = ["delete", "remove", "احذف", "امسح", "شيل"]
    LANG_KEYWORDS   = [
        "python", "بايثون", "unity", "unreal", "c#", "c++", "csharp", "dotnet", ".net",
        "asp.net", "aspnet", "fastapi", "flask", "django", "react", "angular",
        "html", "sql", "postgres", "server", "api",
    ]
    # NEW: explicit run/execute words — RUN intent is only trusted when one is present
    RUN_KEYWORDS = [
        "run ", "execute", "launch", "operate", "start the",
        "شغّل", "شغل المشروع", "نفذ", "نفّذ", "تشغيل",
    ]
    # NEW: small code-snippet indicators — a snippet is conversational (CHAT),
    # not a full project (GAME) and not a run command (RUN)
    SNIPPET_WORDS = [
        "function", "func ", "method", "snippet", "algorithm", "regex",
        "one-liner", "دالة", "فانكشن", "ميثود", "خوارزمية", "مثال كود",
        "كود صغير", "سكربت صغير",
    ]
    SELF_MOD_KEYWORDS = [
        # Direct modification commands
        "add feature", "improve yourself", "update yourself", "modify yourself",
        "add support for", "teach yourself", "expand yourself",
        "edit yourself", "change yourself", "fix yourself",
        "add to yourself", "upgrade yourself", "update your code",
        # "add a X" patterns — adding something to the agent
        "add a command", "add a tool", "add new feature", "add a feature",
        "add a /", "add support", "add the ability", "add an option",
        "add a status", "add a mode", "add a function", "add a feature",
        "add a new", "add new",
        # Capability questions
        "can you edit yourself", "can you modify yourself",
        "can you improve yourself", "can you update yourself",
        "can you change yourself",
        # Arabic
        "طور نفسك", "اضف ميزة", "حدث نفسك", "عدل نفسك",
        "تقدر تعدل نفسك", "تقدر تحسن نفسك", "عايزك تضيف",
    ]
    QUESTION_STARTS = [
        "what", "how", "why", "when", "who", "which", "explain", "tell me",
        "describe", "show me", "is ", "are ", "ما", "كيف", "ليه", "متى", "من",
        "اشرح", "وضّح", "قولي", "أفضل", "افضل", "ما هي", "ماهي", "ما هو",
        "ما الفرق", "what is", "what are", "which is", "compare", "difference",
    ]
    OPINION_WORDS = [
        " is ", " are ", " was ", " seems ", " looks ", " feels ",
        " بيعمل ", " بيحصل ", " غريب", " صعب", " سهل",
    ]

    has_verb    = any(kw in t for kw in CREATION_VERBS)
    has_target  = any(kw in t for kw in GAME_TARGETS)
    has_lang    = any(kw in t for kw in LANG_KEYWORDS)
    has_job     = any(kw in t for kw in JOB_KEYWORDS)
    has_del     = any(kw in t for kw in DELETE_KEYWORDS)
    has_run     = any(kw in t for kw in RUN_KEYWORDS)      # NEW
    has_snippet = any(kw in t for kw in SNIPPET_WORDS)     # NEW

    is_question = (
        any(t.startswith(q + " ") or t.startswith(q) or t == q for q in QUESTION_STARTS)
        or t.endswith("?") or t.endswith("؟")
    )
    is_opinion  = any(op in t for op in OPINION_WORDS)

    if has_del:
        return "DELETE", "general"

    if has_job and not is_question:
        return "JOB", "general"

    # Vague/exploratory phrasing → chat first, don't auto-generate
    _VAGUE = [
        "i want to make", "i want to create", "i want to build",
        "thinking about", "i'm thinking", "what do you think",
        "can you help", "how do i", "how to make", "unique", "some kind of",
        "عاوز اعمل", "فكرة", "ممكن تساعدني", "ازاي اعمل",
    ]
    # Specific genres that confirm intent
    _SPECIFIC = [
        "shooter", "platformer", "rpg", "puzzle", "runner",
        "tower defense", "horror", "fighting", "survival", "endless",
        "zombie", "لعبة شوتر", "منصات",
    ]
    _is_vague = any(ph in t for ph in _VAGUE) and not any(s in t for s in _SPECIFIC)

    is_game = (
        (has_verb and (has_target or has_lang))
        or (has_target and not is_question and not is_opinion)
    )

    # NEW: a small code snippet/function request is conversational, NOT a project
    # build and NOT a run command. Catch it before is_game so a single function
    # doesn't trigger the full generation pipeline.
    if has_verb and has_snippet and not has_run and not has_target:
        return "CHAT", detect_domain(t)

    if is_game and not _is_vague:
        return "GAME", detect_domain(t)
    if is_game and _is_vague:
        # Treat as CHAT so the agent asks clarifying questions
        return "CHAT", detect_domain(t)

    if any(kw in t for kw in SELF_MOD_KEYWORDS):
        return "SELF_MOD", "general"

    # ── 3. Short messages → CHAT ─────────────────────────────────────────────
    if len(t.split()) < 4:
        return "CHAT", "general"

    # ── 4. Clear questions → always CHAT, never send to LLM classifier ───────
    if is_question:
        return "CHAT", detect_domain(t)

    try:
        prompt = (
            'Classify this user message into ONE intent:\n'
            'GAME     - user wants to create/build/make/design/generate a game, app, website, database, API, or code project\n'
            'JOB      - user wants job listings, vacancies, or career info (NOT general programming questions)\n'
            'DELETE   - user wants to delete/remove something\n'
            'RUN      - user wants to RUN or EXECUTE already-existing code\n'
            'SELF_MOD - user wants the agent to modify/improve/expand itself\n'
            'CHAT     - anything else\n\n'
            'Reply with ONLY the intent word.\n'
            f'Message: "{user}"\n'
            'Intent:'
        )
        r = safe_chat(
            model=llm_client.DEFAULT_MODEL,
            messages=[{"role": "user", "content": prompt}],
            retries=1,
        )
        intent = get_response(r).strip().upper().split()[0]
        if intent in ("GAME", "JOB", "DELETE", "RUN", "CHAT"):
            # NEW GUARD: only trust RUN when the user actually asked to run/execute.
            # Stops weak local models from sending generation requests to _tool_run.
            if intent == "RUN" and not has_run:
                intent = "CHAT"
            if intent == "JOB" and is_question:
                intent = "CHAT"
            d = detect_domain(t) if intent == "GAME" else "general"
            return intent, d
    except Exception as e:
        safe_print(f"⚠ intent router error: {e}")

    return "CHAT", "general"
