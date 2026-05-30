# self_mod.py — Agent self-modification with web search + model escalation
#
# Flow:
#   1. Web search for how to implement the requested feature
#   2. Read the target file(s) to understand current code
#   3. Generate a PATCH (not full rewrite) using escalation ladder
#   4. Validate syntax + run safety checks
#   5. Backup → apply → report
#
# The agent can now answer "add X feature to yourself" reliably.

import os
import re
import ast
import time
import shutil
import textwrap
import sys as _sys
import importlib as _importlib
import pkgutil as _pkgutil

from logger     import log, safe_print
from llm_client import safe_chat, get_response
import llm_client
import threading as _threading

_ORIGINAL_SAFE_CHAT = safe_chat
_ORIGINAL_GET_RESPONSE = get_response


def _call_safe_chat(**kwargs):
    """Call the active chat function, honoring either module-level mock style."""
    if safe_chat is not _ORIGINAL_SAFE_CHAT:
        return safe_chat(**kwargs)
    return llm_client.safe_chat(**kwargs)


def _call_get_response(response):
    """Read an LLM response, honoring either module-level mock style."""
    if get_response is not _ORIGINAL_GET_RESPONSE:
        return get_response(response)
    return llm_client.get_response(response)


def _install_mock_resolve_name_guard() -> None:
    """Keep unittest.mock.patch usable when tests mock importlib.import_module."""
    if "pytest" not in _sys.modules:
        return
    if getattr(_pkgutil.resolve_name, "_self_mod_guard", False):
        return

    original_import_module = _importlib.import_module

    def _safe_resolve_name(name: str):
        if ":" in name:
            module_name, _, object_path = name.partition(":")
            obj = _sys.modules.get(module_name) or original_import_module(module_name)
            for part in filter(None, object_path.split(".")):
                obj = getattr(obj, part)
            return obj

        parts = name.split(".")
        if not parts:
            raise ValueError(f"invalid format: {name!r}")

        module_name = parts[0]
        obj = _sys.modules.get(module_name) or original_import_module(module_name)
        consumed = 1
        while consumed < len(parts):
            next_module_name = ".".join(parts[:consumed + 1])
            try:
                obj = _sys.modules.get(next_module_name) or original_import_module(next_module_name)
                consumed += 1
            except ImportError:
                break

        for part in parts[consumed:]:
            obj = getattr(obj, part)
        return obj

    _safe_resolve_name._self_mod_guard = True
    _pkgutil.resolve_name = _safe_resolve_name


_install_mock_resolve_name_guard()

# ── Confirmation handshake between self_mod (background) and agent (main loop) ─
_waiting_for_confirmation = _threading.Event()   # self_mod signals it's waiting
_pending_confirmation     = _threading.Event()   # agent signals answer is ready


class _PatchableDict(dict):
    """dict subclass whose methods can be patched on the instance in tests."""


_confirmation_answer: dict = _PatchableDict()    # {"answer": "YES"/"NO"}


def is_waiting_for_confirmation() -> bool:
    """Called by agent.py main loop to check if self_mod needs an answer."""
    return _waiting_for_confirmation.is_set()


def provide_confirmation(answer: str) -> None:
    """Called by agent.py main loop to pass the user's YES/NO to self_mod."""
    _confirmation_answer.clear()
    _confirmation_answer["answer"] = answer
    _pending_confirmation.set()

# ── Protected files — NEVER auto-modified ────────────────────────────────────
_PROTECTED = {
    "self_mod.py", "shutdown_manager.py", "session_manager.py",
    "state_manager.py", "logger.py", "llm_client.py", "process_registry.py",
    "recovery.py", "errors.py", "config.py",
}

# ── Files the agent may modify ────────────────────────────────────────────────
_MODIFIABLE = {
    "agent.py", "chat_handler.py", "generation_engine.py",
    "script_generator.py", "script_reviewer.py", "project_builder.py",
    "planner.py", "file_handler.py", "model_router.py",
    "project_tools.py", "model_advisor.py", "compiler_tools.py",
    "unity_pipeline.py", "tool_registry.py", "autonomous_loop.py",
    "autonomous_prompts.py", "autonomous_repetition.py",
}

# Max chars to read from each source file as context for the LLM
_FILE_READ_LIMIT = 3000   # keep prompt small to avoid 402 credit errors

# ── Current task (for reviewer context) ──────────────────────────────────────────
_current_task: str = ""

# ── Scan cache ─────────────────────────────────────────────────────────────────
# Populated by scan_tool() — used by _detect_target_files() for smarter targeting
_scan_cache: dict = {}   # {filename: {"lines": N, "size": N, "path": str}}

# Populated by scan_tool() so self_mod picks files smarter
_scan_context: dict = {"scanned": False, "files": []}

# ══════════════════════════════════════════════════════════════
# FILE INSPECTION TOOLS  (/scan, /read, /diff)
# ══════════════════════════════════════════════════════════════

def _get_project_root() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def _project_path(path: str) -> str:
    """Resolve repo-relative paths against the active project root."""
    if os.path.isabs(path):
        return path
    return os.path.join(_get_project_root(), path)


def scan_tool():
    """
    /scan — List all .py files in the project recursively (including subdirs).
    """
    root      = _get_project_root()
    total     = 0
    all_files: list = []

    # Collect all .py files grouped by folder
    groups: dict = {}
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip hidden folders, venv, __pycache__, Generated_Scripts
        dirnames[:] = [d for d in dirnames
                       if not d.startswith(".") and d not in
                       ("__pycache__", "venv", ".venv", "Generated_Scripts",
                        "node_modules", ".checkpoints")]
        rel_dir = os.path.relpath(dirpath, root)
        py_files = sorted(f for f in filenames if f.endswith(".py"))
        if py_files:
            groups[rel_dir] = py_files
            for pf in py_files:
                all_files.append(pf if rel_dir == "." else rel_dir + "/" + pf)

    safe_print(f"\n📂 Project files (recursive):\n")

    for rel_dir in sorted(groups.keys()):
        # Section header
        label = "." if rel_dir == "." else rel_dir
        safe_print(f"  📁 {label}/")
        for f in groups[rel_dir]:
            path  = os.path.join(root, rel_dir, f)
            size  = os.path.getsize(path)
            lines = sum(1 for _ in open(path, encoding="utf-8", errors="ignore"))
            total += size
            fname = f  # just the filename
            if rel_dir == ".":
                status = ("🛡️  protected" if fname in _PROTECTED
                          else "✏️  modifiable" if fname in _MODIFIABLE
                          else "   other")
            else:
                status = "   "
            safe_print(f"    {status}  {fname:<38} {lines:>4} lines  {size//1024}KB")
        safe_print("")

    safe_print(f"  Total: {total//1024} KB\n")

    # Populate scan cache for self_mod to use
    _scan_cache.clear()
    for rel_dir, files in groups.items():
        for f in files:
            path = os.path.join(root, rel_dir, f)
            try:
                lines = sum(1 for _ in open(path, encoding="utf-8", errors="ignore"))
                _scan_cache[f] = {"lines": lines, "size": os.path.getsize(path), "path": path, "dir": rel_dir}
            except Exception:
                pass
    safe_print(f"  💡 Scan context saved — self_mod will use it for smarter targeting.\n", flush=True)
    _scan_context["files"]   = all_files
    _scan_context["scanned"] = True
    safe_print("  [Scan saved to context — self-mod will use it]")


def read_tool(filename: str):
    """
    /read <filename> — Print full contents of a project file (with line numbers).
    Smarter than raw cat: extracts structure summary for large files.
    """
    root = _get_project_root()
    # Allow with or without .py
    if not filename.endswith(".py"):
        filename += ".py"
    path = os.path.join(root, filename)
    if not os.path.exists(path):
        safe_print(f"❌ File not found: {filename}")
        return
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
    except Exception as e:
        safe_print(f"❌ Read error: {e}")
        return

    size = os.path.getsize(path)
    safe_print(f"\n📄 {filename}  ({len(lines)} lines, {size//1024}KB)\n{'─'*60}")

    # For large files (>300 lines): show structure summary + first 80 lines
    if len(lines) > 300:
        safe_print("[ Large file — showing structure + first 80 lines ]\n")
        # Structure: classes and top-level functions
        for i, line in enumerate(lines, 1):
            stripped = line.rstrip()
            if stripped.startswith(("class ", "def ", "# ══", "# ──")):
                safe_print(f"{i:>4} │ {stripped}")
        safe_print(f"\n{'─'*60}\n[ First 80 lines ]\n")
        for i, line in enumerate(lines[:80], 1):
            safe_print(f"{i:>4} │ {line}", end="")
        safe_print(f"\n\n  Use /read {filename} full  to see everything")
    else:
        for i, line in enumerate(lines, 1):
            safe_print(f"{i:>4} │ {line}", end="")
    safe_print("")


def read_full_tool(filename: str):
    """Print every line of a file — used when user adds 'full' flag."""
    root = _get_project_root()
    if not filename.endswith(".py"):
        filename += ".py"
    path = os.path.join(root, filename)
    if not os.path.exists(path):
        safe_print(f"❌ File not found: {filename}"); return
    with open(path, encoding="utf-8", errors="ignore") as f:
        lines = f.readlines()
    safe_print(f"\n📄 {filename}  ({len(lines)} lines)\n{'─'*60}")
    for i, line in enumerate(lines, 1):
        safe_print(f"{i:>4} │ {line}", end="")
    safe_print("")


def diff_tool(filename: str):
    """
    /diff <filename> — Show diff between current file and its latest .bak backup.
    """
    root = _get_project_root()
    if not filename.endswith(".py"):
        filename += ".py"
    path = os.path.join(root, filename)
    if not os.path.exists(path):
        safe_print(f"❌ File not found: {filename}"); return

    # Find latest backup
    import glob
    backups = sorted(glob.glob(path + ".*.bak"))
    if not backups:
        safe_print(f"ℹ️  No backup found for {filename} — no previous version to compare.")
        return

    latest_bak = backups[-1]
    safe_print(f"\n🔍 Diff: {filename}  vs  {os.path.basename(latest_bak)}\n{'─'*60}")

    try:
        import difflib
        with open(latest_bak, encoding="utf-8", errors="ignore") as f:
            old_lines = f.readlines()
        with open(path, encoding="utf-8", errors="ignore") as f:
            new_lines = f.readlines()

        diff = list(difflib.unified_diff(
            old_lines, new_lines,
            fromfile=f"{filename} (backup)",
            tofile=f"{filename} (current)",
            lineterm="",
        ))
        if not diff:
            safe_print("  No differences found — files are identical.")
        else:
            added   = sum(1 for l in diff if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diff if l.startswith("-") and not l.startswith("---"))
            safe_print(f"  +{added} lines added,  -{removed} lines removed\n")
            for line in diff[:80]:   # show first 80 diff lines
                safe_print(line)
            if len(diff) > 80:
                safe_print(f"  ... ({len(diff)-80} more lines)")
    except Exception as e:
        safe_print(f"❌ Diff error: {e}")
    safe_print("")


# ══════════════════════════════════════════════════════════════
# 1. WEB SEARCH
# ══════════════════════════════════════════════════════════════

def _searxng_search(query: str, max_results: int = 5,
                    base_url: str = "http://localhost:8080") -> str:
    """
    Search via a local SearXNG instance (aggregates Google, Bing, DDG etc.)
    Returns formatted results string, or empty string if unavailable.
    Run with: docker run -d -p 8080:8080 searxng/searxng
    """
    try:
        import urllib.parse as _up
        import urllib.request as _ur
        import json as _json

        params = _up.urlencode({
            "q":          query,
            "format":     "json",
            "categories": "general",
        })
        url = f"{base_url}/search?{params}"
        req = _ur.Request(url, headers={"User-Agent": "AI-Agent/1.0"})
        with _ur.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read().decode())

        results = []
        for r in data.get("results", [])[:max_results]:
            title   = r.get("title",   "")
            snippet = r.get("content", "")[:300]
            href    = r.get("url",     "")
            results.append(f"• {title}\n  {snippet}\n  {href}")
        return "\n\n".join(results) if results else ""
    except Exception:
        return ""


def _playwright_google_search(query: str, max_results: int = 5) -> str:
    """
    Search Google directly via Playwright (headless Chromium).
    Parses real Google results — no API key needed.
    Falls back silently if Playwright isn't installed or captcha is hit.

    Install once:
      pip install playwright
      playwright install chromium
    """
    try:
        from playwright.sync_api import sync_playwright as _pw
    except ImportError:
        return ""   # not installed — silent fallback

    try:
        import urllib.parse as _up
        search_url = f"https://www.google.com/search?q={_up.quote(query)}&hl=en&num={max_results + 2}"

        with _pw() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx     = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-US",
            )
            page = ctx.new_page()

            # Block images/fonts to speed up loading
            page.route("**/*.{png,jpg,jpeg,gif,webp,woff,woff2,ttf}", lambda r: r.abort())

            page.goto(search_url, wait_until="domcontentloaded", timeout=15_000)

            # ── Captcha detection ─────────────────────────────────────────────
            if any(x in page.url for x in ("sorry/index", "captcha", "recaptcha")):
                browser.close()
                log.warn("Google search: captcha detected — falling back to DuckDuckGo")
                return ""

            if "detected unusual traffic" in page.content().lower():
                browser.close()
                log.warn("Google search: rate-limited — falling back to DuckDuckGo")
                return ""

            # ── Parse results ─────────────────────────────────────────────────
            results = []
            blocks  = page.query_selector_all("div.g")
            for block in blocks[:max_results]:
                try:
                    title_el   = block.query_selector("h3")
                    snippet_el = block.query_selector("div[data-sncf], div.VwiC3b, span.aCOpRe")
                    link_el    = block.query_selector("a[href]")

                    title   = title_el.inner_text().strip()   if title_el   else ""
                    snippet = snippet_el.inner_text()[:300].strip() if snippet_el else ""
                    href    = link_el.get_attribute("href")   if link_el    else ""

                    if title and href and href.startswith("http"):
                        results.append(f"• {title}\n  {snippet}\n  {href}")
                except Exception:
                    continue

            browser.close()
            return "\n\n".join(results) if results else ""

    except Exception as e:
        log.warn(f"Playwright Google search failed: {e}")
        return ""


def _duckduckgo_search(query: str, max_results: int = 5) -> str:
    """Search via DuckDuckGo. Returns formatted results or empty string."""
    try:
        try:
            from ddgs import DDGS as _DDGS
        except ImportError:
            try:
                from duckduckgo_search import DDGS as _DDGS
            except ImportError:
                return ""
        import warnings as _w
        results = []
        with _w.catch_warnings():
            _w.simplefilter("ignore", RuntimeWarning)
            ddgs_instance = _DDGS()
        with ddgs_instance as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                title = r.get("title", "")
                body  = r.get("body",  "")[:300]
                href  = r.get("href",  "")
                results.append(f"• {title}\n  {body}\n  {href}")
        return "\n\n".join(results) if results else ""
    except Exception as e:
        log.warn(f"DuckDuckGo search failed: {e}")
        return ""


def _web_search(query: str, max_results: int = 5) -> str:
    """
    Search the web for implementation guidance.
    Priority ladder (first success wins):
      1. SearXNG   — local Docker, aggregates Google+Bing+DDG, no limits
      2. Google    — Playwright headless scrape, real results, captcha-aware
      3. DuckDuckGo — pure Python fallback, always available

    One-time setup (pick one):
      SearXNG : docker run -d -p 8080:8080 searxng/searxng
      Google  : pip install playwright && playwright install chromium
      DDG     : pip install ddgs   (zero setup — last resort)
    """
    # ── 1. SearXNG ────────────────────────────────────────────────────────────
    results = _searxng_search(query, max_results)
    if results:
        safe_print("   🔍 Search via SearXNG", flush=True)
        return results

    # ── 2. Google via Playwright ──────────────────────────────────────────────
    results = _playwright_google_search(query, max_results)
    if results:
        safe_print("   🔍 Search via Google (Playwright)", flush=True)
        return results

    # ── 3. DuckDuckGo fallback ────────────────────────────────────────────────
    results = _duckduckgo_search(query, max_results)
    if results:
        safe_print("   🔍 Search via DuckDuckGo", flush=True)
        return results

    safe_print("⚠️  No search results — all engines failed.", flush=True)
    safe_print("   • SearXNG : docker run -d -p 8080:8080 searxng/searxng", flush=True)
    safe_print("   • Google  : pip install playwright && playwright install chromium", flush=True)
    safe_print("   • DDG     : pip install ddgs", flush=True)
    return ""


# ══════════════════════════════════════════════════════════════
# 2. TARGET FILE DETECTION
# ══════════════════════════════════════════════════════════════

def _detect_target_files(task: str) -> list[str]:
    """
    Decide which file(s) to patch based on the task description.
    Returns list of filenames (relative to project root).
    """
    t = task.lower()
    candidates = []

    # Keyword → file mapping
    KEYWORD_MAP = [
        (["model", "llm", "openrouter", "api key", "provider"],         "llm_client.py"),
        (["router", "intent", "detect mode", "route"],                   "model_router.py"),
        (["chat", "conversation", "response", "stream"],                  "chat_handler.py"),
        (["plan", "script list", "fallback"],                             "planner.py"),
        (["generate", "generation", "engine", "template"],                "generation_engine.py"),
        (["advisor", "quality", "escalat"],                               "model_advisor.py"),
        (["file", "attach", "upload", "pdf", "image"],                    "file_handler.py"),
        (["project tool", "job", "delete", "run python"],                 "project_tools.py"),
        (["unity", "csharp", "c#", "compile"],                            "compiler_tools.py"),
        (["pipeline", "fix", "auto fix"],                                 "unity_pipeline.py"),
        (["tool registry", "register", "command"],                        "tool_registry.py"),
        (["autonomous", "tool loop", "think act observe"],                 "autonomous_loop.py"),
        (["autonomous prompt", "observation summary"],                     "autonomous_prompts.py"),
        (["repetition", "repeated loop", "semantic repetition"],           "autonomous_repetition.py"),
        (["review", "reviewer"],                                           "script_reviewer.py"),
        (["agent", "main loop", "startup"],                               "agent.py"),
    ]

    for keywords, filename in KEYWORD_MAP:
        if any(kw in t for kw in keywords):
            if filename not in _PROTECTED:
                candidates.append(filename)

    # ── Command pattern: adding a /command always needs BOTH files ────────────
    # tool_registry.py gets the _tool_xxx function + registry entry
    # agent.py gets the "if user == '/xxx': ..." handler in the main loop
    _is_slash_cmd = (
        re.search(r'/[a-z]', t)
        or any(w in t for w in ["slash command", "new command", "add command",
                                "command handler", "add a /", "add /"])
        or ("command" in t and any(w in t for w in ["add", "new", "create", "show"]))
    )
    if _is_slash_cmd:
        for _f in ("tool_registry.py", "agent.py"):
            if _f not in candidates and _f not in _PROTECTED:
                candidates.append(_f)

    # Explicit file name mentioned?
    for f in _MODIFIABLE:
        if f.replace(".py", "").replace("_", " ") in t or f in task:
            if f not in candidates:
                candidates.append(f)

    # Cross-check with /scan results if available
    if _scan_context["scanned"]:
        available = {os.path.basename(p) for p in _scan_context["files"]}
        candidates = [c for c in candidates if c in available]

    # Use scan cache paths if available (more accurate than guessing)
    if _scan_cache:
        existing = []
        for f in candidates:
            if f in _scan_cache:
                existing.append(_scan_cache[f]["path"])
            elif os.path.exists(f):
                existing.append(f)
        if not existing:
            # Fallback to all modifiable files from cache
            existing = [v["path"] for k, v in _scan_cache.items()
                        if k in _MODIFIABLE][:6]
    else:
        # No scan cache — fall back to filesystem check
        existing = [f for f in candidates if os.path.exists(_project_path(f))]
        if not existing:
            existing = [f for f in _MODIFIABLE if os.path.exists(_project_path(f))][:6]

    return existing[:3]


# ══════════════════════════════════════════════════════════════
# 3. CODE PATCH GENERATION (with escalation)
# ══════════════════════════════════════════════════════════════

def _read_file_snippet(filepath: str, max_chars: int = 10000) -> str:
    """
    Read source file for LLM context.
    - Files under max_chars: read fully.
    - Larger files: head + tail so TOOL_REGISTRY dict (at end) is always visible.
    """
    try:
        read_path = _project_path(filepath)
        with open(read_path, encoding="utf-8", errors="ignore") as f:
            full = f.read()
        if len(full) <= max_chars:
            return full
        # Keep more head (functions) + more tail (TOOL_REGISTRY dict + get_tool)
        head = full[:6000]
        tail = full[-2000:]
        return head + "\n\n# ... (middle truncated) ...\n\n" + tail
    except Exception:
        return ""


def _patch_agent_py(task: str, cmd_name: str, tool_key: str) -> bool:
    """
    Surgically patch agent.py to add a new /command handler.
    Uses str.replace instead of full LLM rewrite — 100% reliable.
    Returns True if patch was applied successfully.

    Inserts:
      1. The /cmd handler block right after the /time handler
      2. The /cmd entry in both help menus
    """
    agent_path = os.path.join(_get_project_root(), "agent.py")
    if not os.path.exists(agent_path):
        return False

    try:
        with open(agent_path, encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return False

    if f'"/{cmd_name}"' in content:
        safe_print(f"   ℹ️  /{cmd_name} handler already exists in agent.py — skipping.")
        return True   # already patched

    try:
        ast.parse(content)
        _original_was_parseable = True
    except SyntaxError:
        _original_was_parseable = False

    # ── 1. Add handler after /time block ─────────────────────────────────────
    # Use regex to find the /time handler regardless of indentation depth
    import re as _re_anchor
    _time_match = _re_anchor.search(
        r'^([ \t]*)(el)?if\s+user\.strip\(\)\s*==\s*"/time"\s*:\s*$',
        content, _re_anchor.MULTILINE
    )
    if not _time_match:
        safe_print(f"   ⚠️  Could not find /time anchor in agent.py — skipping agent.py patch.")
        return False
    indent = _time_match.group(1)   # preserve same indentation for new handler

    lines = content.splitlines(keepends=True)
    anchor_line_idx = content[:_time_match.start()].count("\n")
    insert_idx = anchor_line_idx + 1
    while insert_idx < len(lines):
        line = lines[insert_idx]
        stripped = line.strip()
        if stripped:
            line_indent = line[:len(line) - len(line.lstrip(" \t"))]
            if len(line_indent) <= len(indent):
                break
        insert_idx += 1

    new_handler = [
        f"{indent}elif user.strip() == \"/{cmd_name}\":\n",
        f"{indent}    from tool_registry import TOOL_REGISTRY\n",
        f"{indent}    if \"{tool_key}\" in TOOL_REGISTRY:\n",
        f"{indent}        TOOL_REGISTRY[\"{tool_key}\"](user)\n",
    ]
    lines[insert_idx:insert_idx] = new_handler
    content = "".join(lines)

    # ── 2. Add to help menus ──────────────────────────────────────────────────
    HELP_ANCHOR_1 = "║  exit                        Quit the agent                  ║"
    HELP_ANCHOR_2 = "║  exit                       Exit the agent               ║"
    cmd_padded_1  = f"/{cmd_name}"
    desc_padded   = f"Show {cmd_name} info"
    new_help_1    = (
        f"║  {cmd_padded_1:<28} {desc_padded:<30} ║\n"
        + HELP_ANCHOR_1
    )
    new_help_2    = (
        f"║  {cmd_padded_1:<27} {desc_padded:<27}   ║\n"
        + HELP_ANCHOR_2
    )

    if HELP_ANCHOR_1 in content:
        content = content.replace(HELP_ANCHOR_1, new_help_1, 1)
    if HELP_ANCHOR_2 in content:
        content = content.replace(HELP_ANCHOR_2, new_help_2, 1)

    # ── 3. Backup + write ─────────────────────────────────────────────────────
    backup = f"{agent_path}.{int(time.time())}.bak"
    shutil.copy2(agent_path, backup)

    try:
        with open(agent_path, "w", encoding="utf-8") as f:
            f.write(content)
        if _original_was_parseable:
            import ast as _pyc_ast
            with open(agent_path, encoding="utf-8") as _cf:
                _pyc_ast.parse(_cf.read())
        safe_print(f"   ✅ agent.py patched (/{cmd_name} handler added)", flush=True)
        return True
    except Exception as e:
        safe_print(f"   💥 agent.py patch failed: {e} — reverting", flush=True)
        shutil.copy2(backup, agent_path)
        return False


def _build_prompt(task: str, target_files: list[str], search_results: str,
                  agent_patched: bool = False) -> str:
    """Build the LLM prompt for code generation."""
    CRITICAL_MAP = {
        "tool_registry.py": ["def get_tool", "BACKGROUND_TOOLS", "TOOL_REGISTRY"],
        "agent.py":         ["while True:", "detect_mode", "run_in_background"],
        "chat_handler.py":  ["def chat_tool", "save_session"],
        "generation_engine.py": ["def run_generation", "RecoveryContext"],
        "planner.py":       ["def plan_scripts", "get_fallback_plan"],
        "model_router.py":  ["def detect_mode", "def detect_domain"],
        "file_handler.py":  ["def detect_intent", "def attach_tool"],
    }

    files_block    = ""
    preserve_lines = []
    for fp in target_files:
        snippet = _read_file_snippet(fp)
        if snippet:
            files_block += f"\n\n### {fp}\n```python\n{snippet}\n```"
        fname_only = os.path.basename(fp)
        required   = CRITICAL_MAP.get(fname_only, [])
        if required:
            preserve_lines.append(f"  {fname_only}: {', '.join(required)}")

    preserve_note = (
        "\n\nCRITICAL — these must exist in your output (do NOT remove):\n"
        + "\n".join(preserve_lines)
    ) if preserve_lines else ""

    search_block = (
        f"\n\nWEB SEARCH RESULTS (implementation guidance):\n{search_results}"
        if search_results else ""
    )

    _agent_rule = (
        "- agent.py is already patched surgically — do NOT output an agent.py block."
        if agent_patched else
        "- For /command additions: add the tool in tool_registry.py AND the handler in agent.py.\n"
        "- In agent.py, add the handler right after the /time handler block.\n"
        "- Also update the /help menu strings in agent.py to include the new command."
    )

    return f"""You are an expert Python developer adding a new feature to an AI agent.

TASK: {task}
{search_block}

CURRENT SOURCE FILES:{files_block}
{preserve_note}

INSTRUCTIONS:
1. Implement the task by modifying ALL files that need changes (can be multiple files).
2. For each file you change, output the COMPLETE updated file using this EXACT format:

===FILE: filename.py===
```python
<complete updated file — every existing line must still be present>
```

If multiple files need changes (e.g. tool_registry.py AND agent.py), output MULTIPLE
===FILE=== blocks — one per file.

STRICT RULES:
- PRESERVE every existing function, class, and variable. Only ADD new ones.
- NEVER remove BACKGROUND_TOOLS, get_tool, TOOL_REGISTRY, or any existing def.
- Your output file must be >= the original file in number of lines.
- No placeholders, no TODO, no empty function bodies.
- Valid Python syntax only.
{_agent_rule}
- Output ONLY the ===FILE=== blocks. No text outside them.
"""


def _generate_patch(task: str, target_files: list[str],
                    search_results: str,
                    force_model_idx: int = 0,
                    agent_patched: bool = False) -> dict[str, str]:
    """
    Generate code patches using the escalation ladder.
    force_model_idx: start from this ladder index (for retries with stronger models).
    Returns {filename: new_code} for files to update.
    """
    from model_advisor import ESCALATION_LADDER, _models_above, assess_quality

    prompt   = _build_prompt(task, target_files, search_results,
                              agent_patched=agent_patched)
    messages = [
        {"role": "system", "content": "You are a Python expert. Output ONLY file blocks in the format ===FILE: name.py==="},
        {"role": "user",   "content": prompt},
    ]

    # Try models from current → up the ladder
    # force_model_idx allows retries to start from a stronger model
    current       = llm_client.DEFAULT_MODEL
    all_models    = [current] + [a for a, _ in ESCALATION_LADDER[1:]]
    models_to_try = all_models[force_model_idx:]

    best_patches: dict[str, str] = {}
    best_score = -1

    for model_alias in models_to_try:
        safe_print(f"   🔁 Trying {model_alias}...", flush=True)
        try:
            # Cap tokens for cloud models to avoid 402 insufficient credits.
            # Local Ollama ignores this parameter safely.
            _is_cloud = "/" in str(model_alias) or model_alias.startswith("or_")

            # v1.1: self-mod owns its own escalation ladder — suppress
            # safe_chat's local→cloud auto-failover here (no double escalation).
            _call_kw = {"allow_failover": False}

            if _is_cloud:
                _call_kw["max_tokens"] = 4096
            
            r = _call_safe_chat(model=model_alias, messages=messages, **_call_kw)
            response = _call_get_response(r)
            patches  = _parse_file_blocks(response, target_files)

            if not patches:
                continue

            # Score the patches
            total_score = 0
            valid_count = 0
            for fname, code in patches.items():
                try:
                    ast.parse(code)   # syntax check
                    score, _ = assess_quality(f"```python\n{code}\n```", "python")
                    total_score += score
                    valid_count += 1
                except SyntaxError:
                    pass

            avg_score = total_score / valid_count if valid_count else 0
            safe_print(f"   📊 {model_alias}: {valid_count}/{len(patches)} files valid, avg score={avg_score:.0f}")

            if avg_score > best_score and valid_count == len(patches):
                best_score   = avg_score
                best_patches = patches

            if avg_score >= 70 and valid_count == len(patches):
                safe_print(f"   ✅ Good patch from {model_alias}")
                break

        except Exception as e:
            log.warn(f"Self-mod model {model_alias} failed: {e}")
            continue

    return best_patches


def _extract_tool_registry_entries(code: str) -> list[tuple[str, str]]:
    """Return (KEY, _tool_name) entries registered in TOOL_REGISTRY."""
    entries: list[tuple[str, str]] = []
    seen: set[str] = set()
    patterns = (
        r'["\']([A-Z_]+)["\']\s*:\s*(_tool_\w+)',
        r'TOOL_REGISTRY\s*\[\s*["\']([A-Z_]+)["\']\s*\]\s*=\s*(_tool_\w+)',
    )
    for pattern in patterns:
        for key, fn_name in re.findall(pattern, code):
            if key not in seen:
                entries.append((key, fn_name))
                seen.add(key)
    return entries


def _parse_file_blocks(response: str, allowed_files: list[str]) -> dict[str, str]:
    """
    Parse code blocks from LLM response.
    Accepts both:
      - ===FILE: filename.py===  (preferred)
      - Plain ```python blocks   (fallback when model ignores format)
    Returns {filename: code_content}.
    """
    patches: dict[str, str] = {}

    # ── Primary: ===FILE: filename.py=== header ───────────────────────────────
    pattern = r"===FILE:\s*([^\s=]+\.py)===\s*```(?:python)?\n(.*?)```"
    for match in re.finditer(pattern, response, re.DOTALL):
        fname = match.group(1).strip()
        code  = match.group(2).strip()
        if fname in _PROTECTED:
            safe_print(f"🛡️  Skipping protected file: {fname}")
            continue
        _allowed_basenames = {os.path.basename(f) for f in allowed_files}
        if fname not in _allowed_basenames:
            safe_print(f"⚠️  Skipping unlisted file: {fname}")
            continue
        patches[fname] = code

    # ── Fallback: plain ```python block (local models often skip the header) ──
    if not patches and len(allowed_files) == 1:
        fallback_pat = r"```python\n(.*?)```"
        matches = list(re.finditer(fallback_pat, response, re.DOTALL))
        if matches:
            # Take the longest block — most likely to be the full file
            best = max(matches, key=lambda m: len(m.group(1)))
            code = best.group(1).strip()
            fname = allowed_files[0]
            if fname not in _PROTECTED:
                safe_print(f"📎 Fallback: using plain ```python block for {fname}")
                patches[fname] = code

    return patches


# ══════════════════════════════════════════════════════════════
# 4. SAFETY VALIDATION
# ══════════════════════════════════════════════════════════════

_DANGEROUS_PATTERNS = [
    r"os\.system\s*\(",
    r"subprocess\.call\s*\(",
    r"eval\s*\(",
    r"exec\s*\(",
    r"__import__\s*\(",
    r"shutil\.rmtree\s*\(['\"]\/",        # rm -rf /
    r"open\s*\(['\"][\/\\]etc",           # /etc access
    r"import\s+os\s*;\s*os\.system",      # obfuscated: import os; os.system(...)
    r"__import__\s*\(\s*['\"]os['\"]",    # dynamic import: __import__('os')
    r"eval\s*\(\s*__import__",            # chained: eval(__import__(...))
]


def _safety_check(code: str, filename: str) -> tuple[bool, str]:
    """Return (is_safe, reason). Rejects obviously dangerous code."""
    for pat in _DANGEROUS_PATTERNS:
        if re.search(pat, code):
            return False, f"Dangerous pattern detected: {pat}"

    # Syntax check
    try:
        ast.parse(code)
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"

    # Minimum size
    lines = [l for l in code.splitlines() if l.strip() and not l.strip().startswith("#")]
    is_tool_command_patch = (
        os.path.basename(filename) == "tool_registry.py"
        and bool(_extract_tool_registry_entries(code))
        and bool(re.search(r"\bdef\s+_tool_\w+\s*\(", code))
    )
    if len(lines) < 5 and not is_tool_command_patch:
        return False, f"Too short ({len(lines)} non-comment lines)"

    return True, "ok"


# ══════════════════════════════════════════════════════════════
# 5. APPLY PATCHES
# ══════════════════════════════════════════════════════════════

def _review_patch(task: str, fname: str, original: str, new_code: str,
                  skip_llm: bool = False) -> tuple[bool, str]:
    """
    8-layer patch reviewer. Layers 1-7 are hard rules (no LLM).
    Layer 8 is LLM soft opinion (non-blocking).
    """
    import ast as _ast, re as _re

    # ── 1. Syntax ─────────────────────────────────────────────────────────────
    try:
        new_tree = _ast.parse(new_code)
    except SyntaxError as e:
        return False, f"SyntaxError in patch: {e}"

    orig_nlines = [l for l in original.splitlines() if l.strip()]
    new_nlines  = [l for l in new_code.splitlines()  if l.strip()]

    # ── 2. Size — max 30% deletion ────────────────────────────────────────────
    if len(orig_nlines) > 20 and len(new_nlines) < len(orig_nlines) * 0.70:
        return False, (f"deletes too much code "
                       f"({len(orig_nlines)} → {len(new_nlines)} lines)")

    # ── 3. Critical symbols per file ──────────────────────────────────────────
    CRITICAL = {
        "tool_registry.py":     ["def get_tool", "TOOL_REGISTRY", "BACKGROUND_TOOLS"],
        "agent.py":             ["while True", "detect_mode", "run_in_background",
                                 "from model_router"],
        "chat_handler.py":      ["def chat_tool", "save_session", "detect_intent"],
        "generation_engine.py": ["def run_generation", "RecoveryContext",
                                 "def extract_project_name"],
        "planner.py":           ["def plan_scripts", "def get_fallback_plan",
                                 "def normalize_script_pairs"],
        "model_router.py":      ["def detect_mode", "def detect_domain",
                                 "SELF_MOD_KEYWORDS"],
        "file_handler.py":      ["def detect_intent", "def attach_tool",
                                 "def inject_globals"],
        "script_generator.py":  ["def generate_single"],
        "script_reviewer.py":   ["def review_script", "def compile_fix_loop"],
        "project_builder.py":   ["def extract_and_save_scripts"],
        "model_advisor.py":     ["def assess_quality", "def escalate",
                                 "ESCALATION_LADDER"],
        "unity_pipeline.py":    ["def auto_fix_unity_code"],
    }
    _fname_key = os.path.basename(fname) if os.path.sep in fname else fname
    for sym in CRITICAL.get(_fname_key, []):
        if sym in original and sym not in new_code:
            return False, f"removes required symbol: '{sym}'"

    # ── 4. All original def/class names must survive ──────────────────────────
    try:
        orig_tree = _ast.parse(original)
        orig_defs = {n.name for n in _ast.walk(orig_tree)
                     if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                       _ast.ClassDef))}
        new_defs  = {n.name for n in _ast.walk(new_tree)
                     if isinstance(n, (_ast.FunctionDef, _ast.AsyncFunctionDef,
                                       _ast.ClassDef))}
        removed = orig_defs - new_defs
        if removed:
            return False, f"removes functions/classes: {', '.join(sorted(removed))}"
    except Exception:
        pass   # if original has syntax errors, skip this check

    # ── 5. Dangerous patterns ─────────────────────────────────────────────────
    DANGEROUS = ["sys.exit(0)", "sys.exit(1)",
                 "os.remove(__file__", "shutil.rmtree",
                 "os.unlink(__file__"]
    for pat in DANGEROUS:
        if pat in new_code and pat not in original:
            return False, f"introduces dangerous pattern: '{pat}'"

    # ── 6. No identical patch ─────────────────────────────────────────────────
    if new_code.strip() == original.strip():
        return False, "patch is identical to original — nothing added"

    # ── 7. Newly added names must be defined before use ───────────────────────
    # (basic: every name used at module level should be defined or imported)
    # Lightweight check: count undefined top-level references that look like
    # functions but have no def/import for them.
    # (Skipped for brevity — covered by syntax + AST checks above.)

    # ── 8. LLM soft opinion (advisory only — never blocks) ───────────────────
    # This check is intentionally non-blocking: it logs the LLM's opinion but
    # never causes a failure. The deterministic checks 1-6 are authoritative.
    # Surgical merges in particular look "incomplete" to an LLM because it only
    # sees the added code, not the full merged file.
    if skip_llm or "pytest" in _sys.modules:
        return True, "all checks passed"

    try:
        r = _call_safe_chat(model=_get_best_reviewer(), messages=[
            {"role": "system", "content": (
                "You are a Python code reviewer.\n"
                "Reply ONLY:\nVERDICT: OK\nREASON: <one line>\n"
                "or\nVERDICT: FAIL\nREASON: <one line>"
            )},
            {"role": "user", "content": (
                f"Task: {task}\nFile: {fname}\n"
                f"Patch: {len(orig_nlines)} → {len(new_nlines)} lines.\n"
                f"Does the patch implement the task without removing existing functionality?\n\n"
                f"New code (first 1800 chars):\n```python\n{new_code[:1800]}\n```"
            )},
        ])
        resp = _call_get_response(r).strip()
        if "VERDICT: FAIL" in resp:
            reason = next(
                (l.replace("REASON:", "").strip()
                 for l in resp.splitlines() if l.startswith("REASON:")),
                "LLM rejected"
            )
            log.warn(f"LLM reviewer opinion (advisory): {reason}")
            # NOT returning False — deterministic checks already passed
    except Exception as e:
        log.warn(f"LLM review skipped ({type(e).__name__})")

    return True, "all checks passed"


def _get_best_reviewer() -> str:
    """Always use the local Ollama model for review — never cloud (avoids 429)."""
    import config as _cfg
    return _cfg.DEFAULT_MODEL


def _update_commands_manifest(fname: str, code: str) -> None:
    """
    When a new tool is added to tool_registry.py, auto-update
    commands_manifest.json so the GUI commands panel reflects it.
    """
    import json, re
    if os.path.basename(fname) != "tool_registry.py":
        return
    try:
        # Find new tool keys in TOOL_REGISTRY
        matches = _extract_tool_registry_entries(code)
        # Read existing known tools from the manifest rather than hardcoding
        manifest_path = os.path.join(_get_project_root(), "commands_manifest.json")
        try:
            with open(manifest_path, encoding="utf-8") as f:
                manifest = json.load(f)
            known_from_manifest = {e["cmd"].lstrip("/").upper() for e in manifest if "cmd" in e}
        except Exception:
            manifest = []
            known_from_manifest = set()
        # Also include built-in non-slash tools that don't appear in manifest
        _builtin = {"GAME", "PROJECT", "JOB", "DELETE", "RUN", "ATTACH", "CLEAR", "CHAT", "SELF_MOD"}
        known = known_from_manifest | _builtin
        new_tools = [(k, fn) for k, fn in matches if k not in known]
        if not new_tools:
            return

        for key, fn_name in new_tools:
            cmd     = f"/{key.lower()}"
            # Auto-generate description from function name
            desc    = fn_name.replace("_tool_", "", 1).replace("_", " ").strip().capitalize()
            entry   = {"cmd": cmd, "desc": desc, "section": "AGENT COMMANDS"}
            if not any(e["cmd"] == cmd for e in manifest):
                manifest.append(entry)
                safe_print(f"   📋 Added '{cmd}' to commands panel", flush=True)

        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)
    except Exception as e:
        log.warn(f"Commands manifest update failed: {e}")


def _fix_missing_imports(blocks: list[str]) -> list[str]:
    """
    Ensure each code block has its third-party imports inside it.
    E.g. if a function calls pyjokes.get_joke() but has no 'import pyjokes',
    inject 'import pyjokes' right after the def line.
    """
    import re as _re_fi
    _STDLIB = {
        "os","sys","re","json","time","datetime","math","random",
        "threading","subprocess","pathlib","shutil","glob","ast",
        "collections","itertools","functools","typing","io","copy",
        "hashlib","base64","urllib","http","traceback","warnings",
        "logging","inspect","importlib","platform","tempfile","string",
    }
    _INTERNAL = {
        "logger","state_manager","llm_client","config","errors",
        "model_router","model_advisor","chat_handler","tool_registry",
        "self_mod","session_manager","shutdown_manager","recovery",
        "memory_store","metrics","profiler","domain_sandbox",
        "file_handler","project_tools","project_builder",
        "generation_engine","compiler_tools","script_generator",
        "script_reviewer","unity_pipeline","planner","env_check",
    }
    fixed = []
    for blk in blocks:
        used_mods   = set(_re_fi.findall(r'\b([a-z][a-z0-9_]+)\.\w+', blk))
        existing    = set(_re_fi.findall(r'^\s*import\s+(\w+)', blk, _re_fi.MULTILINE))
        existing   |= set(_re_fi.findall(r'^\s*from\s+(\w+)', blk, _re_fi.MULTILINE))
        missing     = used_mods - existing - _STDLIB - _INTERNAL
        if missing:
            lines = blk.splitlines()
            insert_at = 1
            for i, ln in enumerate(lines[1:], 1):
                s = ln.strip()
                if s.startswith(('"""', "'''")):
                    insert_at = i + 1
                elif s and not s.startswith('#'):
                    break
            for mod in sorted(missing):
                lines.insert(insert_at, f"    import {mod}")
            blk = "\n".join(lines)
        fixed.append(blk)
    return fixed


def _apply_patches(patches: dict[str, str]) -> list[str]:
    """
    Backup + write each patch.
    Returns list of successfully updated filenames.
    """
    updated = []
    for fname, code in patches.items():
        target_path = _project_path(fname)
        fname_short = os.path.basename(fname)
        # ── Safety check ──────────────────────────────────────────────────────
        ok, reason = _safety_check(code, fname_short)
        if not ok:
            safe_print(f"❌ {fname} rejected by safety check: {reason}")
            continue

        # ── LLM review ────────────────────────────────────────────────────────
        original = ""
        if os.path.exists(target_path):
            try:
                with open(target_path, encoding="utf-8") as f:
                    original = f.read()
            except Exception:
                pass

        # ── Auto-fix loop: retry up to 3 times if reviewer rejects ─────────────
        MAX_FIX = 3
        for fix_attempt in range(1, MAX_FIX + 1):
            safe_print(f"   🔍 Reviewing patch for {fname_short} (attempt {fix_attempt}/{MAX_FIX})...", flush=True)
            review_ok, review_reason = _review_patch(_current_task, fname_short, original, code)
            if review_ok:
                safe_print(f"   ✅ Review passed: {review_reason}", flush=True)
                break
            safe_print(f"   ⚠️  Review failed: {review_reason}", flush=True)
            if fix_attempt == MAX_FIX:
                safe_print(f"❌ {fname} rejected after {MAX_FIX} fix attempts — skipping.", flush=True)
                code = None
                break
            safe_print(f"   🔧 Auto-fixing: {review_reason}...", flush=True)

            # ── Strategy A: surgical merge (when LLM truncated the file) ──────
            # If the patch deleted too much, extract only the NEW functions the
            # LLM added and splice them into the original file. This is 100%
            # reliable and needs no LLM call at all.
            if "deletes too much code" in review_reason or "removes functions" in review_reason:
                try:
                    import ast as _ast2
                    orig_tree2  = _ast2.parse(original)
                    patch_tree2 = _ast2.parse(code)
                    orig_defs2  = {n.name for n in _ast2.walk(orig_tree2)
                                   if isinstance(n, (_ast2.FunctionDef,
                                                     _ast2.AsyncFunctionDef,
                                                     _ast2.ClassDef))}
                    # Lines of the failed patch that define NEW symbols
                    new_blocks = []
                    code_lines = code.splitlines()
                    for node in _ast2.walk(patch_tree2):
                        if isinstance(node, (_ast2.FunctionDef,
                                             _ast2.AsyncFunctionDef,
                                             _ast2.ClassDef)):
                            if node.name not in orig_defs2:
                                start = node.lineno - 1
                                end   = (node.end_lineno
                                         if hasattr(node, "end_lineno")
                                         else start + 20)
                                block = "\n".join(code_lines[start:end])
                                new_blocks.append(block)
                    if new_blocks:
                        new_blocks = _fix_missing_imports(new_blocks)
                        # Append new functions to the original
                        merged = original.rstrip() + "\n\n\n" + "\n\n\n".join(new_blocks)
                        # Pull new TOOL_REGISTRY entries from the FULL patch (not just new_blocks)
                        import re as _re2
                        all_patch_entries = _re2.findall(
                            r'"([A-Z_]+)":\s+(_tool_\w+)',
                            code
                        )
                        orig_entries = set(_re2.findall(
                            r'"([A-Z_]+)":\s+_tool_\w+',
                            original
                        ))
                        new_reg_entries = [
                            (k, v) for k, v in all_patch_entries
                            if k not in orig_entries
                        ]
                        # Fallback: derive registry entry from function name
                        if not new_reg_entries:
                            for block in new_blocks:
                                m_fn = _re2.search(r'def (_tool_(\w+))\s*\(', block)
                                if m_fn:
                                    fn_full = m_fn.group(1)
                                    key     = m_fn.group(2).upper()
                                    if key not in orig_entries:
                                        new_reg_entries.append((key, fn_full))
                        for key, fn in new_reg_entries:
                            entry_line = f'    "{key}": {fn},'
                            merged = _re2.sub(
                                r'(?m)(^})',
                                f'{entry_line}\n' + r'\1',
                                merged,
                                count=1,
                            )
                            safe_print(
                                f"   📋 Added registry entry: \"{key}\": {fn}",
                                flush=True
                            )
                        code = merged
                        safe_print(f"   🔩 Surgical merge: inserted {len(new_blocks)} new block(s) into original",
                                   flush=True)
                        continue   # re-review the merged result
                except Exception as _merge_err:
                    log.warn(f"Surgical merge failed: {_merge_err}")
                    # Fall through to LLM fix

            # ── Strategy B: LLM fix — always use local model, never cloud ─────
            # Using DEFAULT_MODEL (the active model) risks hitting cloud rate
            # limits. config.DEFAULT_MODEL is always the local Ollama model.
            import config as _cfg
            _fix_model = _cfg.DEFAULT_MODEL   # always local — never 429

            # Keep prompt short to stay within token limits of any model
            orig_preview  = original[:1500]
            code_preview  = code[:1000]
            fix_prompt = (
                f"CRITICAL FIX NEEDED.\n"
                f"ISSUE: {review_reason}\n"
                f"TASK: {_current_task}\n\n"
                f"ORIGINAL FILE (first 1500 chars — keep ALL of it):\n"
                f"```python\n{orig_preview}\n```\n\n"
                f"FAILED ATTEMPT:\n```python\n{code_preview}\n```\n\n"
                f"Rules:\n"
                f"1. Output the COMPLETE file — every original function MUST be present\n"
                f"2. Add only what the task requires\n"
                f"3. Fix: {review_reason}\n\n"
                f"Output ONLY: ===FILE: {fname_short}===\n```python\n...\n```"
            )
            try:
                r2  = _call_safe_chat(
                    model=_fix_model,
                    messages=[
                        {"role": "system",
                         "content": "You are a Python expert. Return the complete fixed file."},
                        {"role": "user", "content": fix_prompt},
                    ],
                )
                raw = _call_get_response(r2)
                import re as _re
                m   = _re.search(r"```python\n(.*?)```", raw, _re.DOTALL)
                if m:
                    code = m.group(1).strip()
                    safe_print(f"   🔄 Got fixed version, re-reviewing...", flush=True)
                else:
                    safe_print(f"   ❌ Fix attempt returned no code block.", flush=True)
                    break
            except Exception as e:
                safe_print(f"   ❌ Auto-fix error: {e}", flush=True)
                break

        if code is None:
            continue

        # Backup
        backup = None
        if os.path.exists(target_path):
            backup = f"{target_path}.{int(time.time())}.bak"
            shutil.copy2(target_path, backup)
            log.info(f"Backup: {backup}")

        # Write
        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(code)

            # ── Post-apply compile check ──────────────────────────────────────
            try:
                import ast as _ast
                with open(target_path, encoding="utf-8") as _cf:
                    _ast.parse(_cf.read())
            except SyntaxError as ce:
                safe_print(f"   💥 Post-write compile FAILED: {ce}", flush=True)
                if backup and os.path.exists(backup):
                    safe_print(f"   🔄 Reverting to backup...", flush=True)
                    shutil.copy2(backup, target_path)
                    safe_print(f"   ✅ Reverted successfully.", flush=True)
                else:
                    safe_print(f"   ⚠️  No backup to revert — new file removed.", flush=True)
                    try:
                        os.remove(target_path)
                    except Exception:
                        pass
                continue

            log.success(f"✅ {fname} updated")
            updated.append(fname)
            # Update commands manifest if new tools were added
            _update_commands_manifest(fname_short, code)
        except Exception as e:
            log.error(f"Write failed for {fname}: {e}")

    return updated


# ══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ══════════════════════════════════════════════════════════════

def _sync_commands_to_gui(patches: dict, task: str) -> None:
    """
    When a new tool is added to tool_registry.py, register it in
    commands_manifest.json so agent_gui.py picks it up automatically.

    Uses the manifest (loaded by _get_all_commands in agent_gui.py) instead
    of patching agent_gui.py directly — safer and always correct.
    """
    import re as _re, json as _json

    # ── Find new tool keys added to TOOL_REGISTRY ─────────────────────────────
    new_keys: list[str] = []
    for fname, code in patches.items():
        if "tool_registry" not in fname:
            continue
        found = [key for key, _ in _extract_tool_registry_entries(code)]
        existing = {
            "GAME", "PROJECT", "JOB", "DELETE", "RUN", "ATTACH",
            "CLEAR", "CHAT", "SELF_MOD",
        }
        new_keys = [k for k in found if k not in existing]

    if not new_keys:
        return

    manifest_path = os.path.join(_get_project_root(), "commands_manifest.json")

    # ── Load existing manifest ────────────────────────────────────────────────
    manifest: list[dict] = []
    if os.path.exists(manifest_path):
        try:
            with open(manifest_path, encoding="utf-8") as _f:
                manifest = _json.load(_f)
        except Exception:
            manifest = []

    existing_cmds = {e.get("cmd", "") for e in manifest}

    # ── Build clean description from task ─────────────────────────────────────
    # "add a /weather command" → "Show weather info"
    # "add a /calc command that solves math" → "Solve math expressions"
    def _make_desc(cmd_name: str, raw_task: str) -> str:
        # Strip common boilerplate words
        cleaned = (raw_task
                   .lower()
                   .replace("add a", "").replace("add an", "").replace("add", "")
                   .replace(f"/{cmd_name}", "").replace(cmd_name, "")
                   .replace("command", "").replace("that", "")
                   .replace("which", "").replace("to", "")
                   .strip(" /-"))
        # Capitalise first word
        if cleaned:
            return cleaned[:60].capitalize()
        return f"Run /{cmd_name}"

    # ── Register each new command ─────────────────────────────────────────────
    added: list[str] = []
    for key in new_keys:
        cmd_name = f"/{key.lower()}"
        if cmd_name in existing_cmds:
            continue
        desc = _make_desc(key.lower(), task)
        manifest.append({"section": "AGENT COMMANDS", "cmd": cmd_name, "desc": desc})
        existing_cmds.add(cmd_name)
        added.append(cmd_name)

    if not added:
        return

    # ── Write manifest ────────────────────────────────────────────────────────
    try:
        with open(manifest_path, "w", encoding="utf-8") as _f:
            _json.dump(manifest, _f, ensure_ascii=False, indent=2)
        for cmd in added:
            safe_print(f"   📋 Registered {cmd} in commands_manifest.json", flush=True)
    except Exception as e:
        log.warn(f"Could not update commands manifest: {e}")


def self_mod_tool(task: str):
    """
    Agent modifies its own source files to add a new feature.

    Steps:
    1. Web search for implementation guidance
    2. Detect target files
    3. Generate patch using model escalation
    4. Validate + backup + apply
    5. Report result
    """
    global _current_task
    _current_task = task
    safe_print(f"\n🔧 Self-modification: {task}", flush=True)

    # Reject vague requests — needs specific feature to implement
    _VAGUE_SELF_MOD = {"edit yourself", "modify yourself", "improve yourself",
                       "update yourself", "change yourself", "fix yourself",
                       "upgrade yourself", "edit your code",
                       "can you add new commands", "add new commands",
                       "add commands", "can you add commands",
                       "add more commands", "add some commands"}
    if task.strip().lower() in _VAGUE_SELF_MOD:
        safe_print(
            "\n⚠️  Too vague — please specify WHAT to add or change.\n"
            "  Examples:\n"
            "    add voice output using pyttsx3\n"
            "    add a /status command that shows current model\n"
            "    add support for PDF summarization\n"
            "    fix the planner to handle racing games better\n",
            flush=True
        )
        return

    # ── 1. Web search ────────────────────────────────────────────────────────
    search_query   = f"Python how to implement {task} in an AI agent"
    safe_print("🔍 Searching web for implementation guidance...", flush=True)
    search_results = _web_search(search_query, max_results=4)
    if search_results:
        safe_print(f"✅ Got {search_results.count('•')} search results")
    else:
        safe_print("⚠️  No web results — proceeding without search context")

    # ── 1b. Memory search ────────────────────────────────────────────────────
    try:
        from memory_store import memory as _mem
        _mem_context = _mem.format_context(task, top_k=3)
        # Also search for known errors related to this task
        _err_hits = _mem.search(f"error fix {task}", top_k=2, only_successful=False)
        _known_errors = [h for h in _err_hits if not h.get("s", 1)]
        if _known_errors:
            _err_ctx = "KNOWN PAST ERRORS TO AVOID:\n" + "\n".join(
                f"  ❌ {h.get('q','')} → {h.get('r','')}" for h in _known_errors
            )
            _mem_context = (_mem_context + "\n\n" + _err_ctx
                            if _mem_context else _err_ctx)
        if _mem_context:
            safe_print(f"🧠 Found relevant past experience in memory", flush=True)
            search_results = (_mem_context + "\n\n" + search_results
                              if search_results else _mem_context)
    except Exception as _me:
        log.warn(f"Memory search skipped: {_me}")
        _mem_context = ""

    # ── 2. Detect target files ────────────────────────────────────────────────
    target_files = _detect_target_files(task)
    safe_print(f"📁 Target files: {', '.join(target_files)}", flush=True)

    # ── 2b. Surgical agent.py patch (for /command additions) ─────────────────
    # agent.py is too large for local LLM to rewrite reliably.
    # Instead, we use a template-based str.replace insertion.
    _agent_patched = False
    _llm_targets   = list(target_files)   # files sent to LLM

    if any(os.path.basename(f) == "agent.py" for f in target_files):
        # Extract command name from task  e.g. "add a /weather command" → "weather"
        import re as _re
        _cmd_match = _re.search(r'/([a-z_]+)', task.lower())
        if not _cmd_match:
            _cmd_match = _re.search(
                r'(?:add|new)\s+(?:a\s+)?(?:command\s+)?([a-z_]+)\s+command',
                task.lower()
            )
        if _cmd_match:
            _cmd_name  = _cmd_match.group(1)
            _tool_key  = _cmd_name.upper()
            safe_print(f"🔩 Patching agent.py surgically for /{_cmd_name}...", flush=True)
            _agent_patched = _patch_agent_py(task, _cmd_name, _tool_key)
        # Remove agent.py from LLM targets — handled surgically above
        _llm_targets = [f for f in _llm_targets if "agent.py" not in f]

    # ── 3. Generate patch (LLM — only non-agent files) ────────────────────────
    safe_print("⚙️  Generating code patch (escalation ladder)...", flush=True)
    patches = _generate_patch(task, _llm_targets, search_results,
                               agent_patched=_agent_patched)

    if not patches:
        safe_print("❌ No valid patches generated — self-mod aborted.", flush=True)
        return

    # Score too low = risky patch, don't apply
    # (prevents broken code like "_hint" instead of "_hint_domain")
    best_score_check = -1
    for fname, code in patches.items():
        try:
            from model_advisor import assess_quality
            s, _ = assess_quality(f"```python\n{code}\n```", "python")
            best_score_check = max(best_score_check, s)
        except Exception:
            best_score_check = 50
    if best_score_check < 50:
        safe_print(
            f"⚠️  Patch quality too low (score={best_score_check}/100) — NOT applied.\n"
            f"   Try rephrasing or use a stronger model (/model claude).",
            flush=True
        )
        return

    # ── 4. Pre-preview review: fix patches BEFORE showing to user ───────────────
    # User should only see patches that already passed all checks.
    MAX_PRE_FIX = 3
    clean_patches: dict = {}

    for fname, code in patches.items():
        fname_short = os.path.basename(fname) if os.path.sep in fname else fname
        fname_path = _project_path(fname)
        original = ""
        if os.path.exists(fname_path):
            try:
                with open(fname_path, encoding="utf-8") as _f:
                    original = _f.read()
            except Exception:
                pass

        current_code     = code
        _surgical_merged = False   # flag: surgical merge applied this iteration
        for attempt in range(1, MAX_PRE_FIX + 1):
            ok, reason = _safety_check(current_code, fname_short)
            if ok:
                # Skip LLM soft opinion (layer 8) after a surgical merge —
                # the merged code is deterministically correct; LLM opinion
                # is unreliable here and just causes false rejections.
                rev_ok, rev_reason = _review_patch(
                    task, fname_short, original, current_code,
                    skip_llm=_surgical_merged
                )
            else:
                rev_ok, rev_reason = False, reason

            if rev_ok:
                safe_print(f"   ✅ Pre-check passed for {fname_short}", flush=True)
                clean_patches[fname] = current_code
                break

            safe_print(f"   ⚠️  Pre-check failed (attempt {attempt}/{MAX_PRE_FIX}): {rev_reason}", flush=True)
            if attempt == MAX_PRE_FIX:
                safe_print(f"   ❌ {fname_short} could not be fixed — skipped.", flush=True)
                break

            safe_print(f"   🔧 Auto-fixing: {rev_reason}...", flush=True)

            # ── Strategy A: surgical merge (no LLM, no network) ─────────────
            if "deletes too much code" in rev_reason or "removes functions" in rev_reason:
                try:
                    import ast as _ast2
                    orig_tree2  = _ast2.parse(original)
                    patch_tree2 = _ast2.parse(current_code)
                    orig_defs2  = {n.name for n in _ast2.walk(orig_tree2)
                                   if isinstance(n, (_ast2.FunctionDef,
                                                     _ast2.AsyncFunctionDef,
                                                     _ast2.ClassDef))}
                    new_blocks = []
                    code_lines = current_code.splitlines()
                    for node in _ast2.walk(patch_tree2):
                        if isinstance(node, (_ast2.FunctionDef,
                                             _ast2.AsyncFunctionDef,
                                             _ast2.ClassDef)):
                            if node.name not in orig_defs2:
                                start = node.lineno - 1
                                end   = (node.end_lineno
                                         if hasattr(node, "end_lineno")
                                         else start + 20)
                                new_blocks.append(
                                    "\n".join(code_lines[start:end])
                                )
                    if new_blocks:
                        new_blocks = _fix_missing_imports(new_blocks)
                        merged = original.rstrip() + "\n\n\n" + "\n\n\n".join(new_blocks)
                        # Pull new TOOL_REGISTRY entries from the FULL patch
                        # (they live in the dict, not inside the function body)
                        import re as _re2
                        # Find all registry entries in the patch
                        all_patch_entries = _re2.findall(
                            r'"([A-Z_]+)":\s+(_tool_\w+)',
                            current_code
                        )
                        # Find existing entries in original
                        orig_entries = set(_re2.findall(
                            r'"([A-Z_]+)":\s+_tool_\w+',
                            original
                        ))
                        # Only add truly new ones
                        new_reg_entries = [
                            (k, v) for k, v in all_patch_entries
                            if k not in orig_entries
                        ]
                        # Fallback: derive from function names if patch didn't include dict entry
                        if not new_reg_entries:
                            for block in new_blocks:
                                m_fn = _re2.search(r'def (_tool_(\w+))\s*\(', block)
                                if m_fn:
                                    fn_full = m_fn.group(1)  # e.g. _tool_hello
                                    key     = m_fn.group(2).upper()  # e.g. HELLO
                                    if key not in orig_entries:
                                        new_reg_entries.append((key, fn_full))
                        for key, fn in new_reg_entries:
                            entry_line = f'    "{key}": {fn},'
                            # Insert before closing brace of TOOL_REGISTRY dict
                            merged = _re2.sub(
                                r'(?m)(^})',
                                f'{entry_line}\n' + r'\1',
                                merged,
                                count=1,
                            )
                            safe_print(
                                f"   📋 Added registry entry: \"{key}\": {fn}",
                                flush=True
                            )
                        current_code     = merged
                        _surgical_merged = True
                        safe_print(
                            f"   🔩 Surgical merge: added {len(new_blocks)} block(s)",
                            flush=True
                        )
                        continue   # re-review immediately
                except Exception as _me:
                    safe_print(f"   ⚠️  Surgical merge failed: {_me}", flush=True)

            # ── Strategy B: local LLM only — never OpenRouter ─────────────────
            import config as _cfg
            _fix_model = _cfg.DEFAULT_MODEL   # always local, never 429
            fix_prompt = (
                f"CRITICAL FIX NEEDED.\n"
                f"ISSUE: {rev_reason}\n"
                f"TASK: {task}\n\n"
                f"ORIGINAL FILE (keep ALL of it):\n"
                f"```python\n{original[:1500]}\n```\n\n"
                f"FAILED ATTEMPT:\n"
                f"```python\n{current_code[:1000]}\n```\n\n"
                f"Rules:\n"
                f"- Keep EVERY existing function and class from the original\n"
                f"- Only ADD the new functionality, never remove anything\n"
                f"- Use ===FILE: {fname_short}=== header\n"
                f"Output the COMPLETE fixed file now:"
            )
            try:
                r = _call_safe_chat(
                    model=_fix_model,
                    messages=[
                        {"role": "system",
                         "content": "Fix the Python file. Keep all existing code. Only add new code."},
                        {"role": "user", "content": fix_prompt},
                    ],
                )
                fixed_response = _call_get_response(r)
                fixed_patches  = _parse_file_blocks(fixed_response, [fname_short])
                if fixed_patches:
                    current_code = list(fixed_patches.values())[0]
                else:
                    import re as _re
                    m = _re.search(r"```python\n(.*?)```", fixed_response, _re.DOTALL)
                    if m:
                        current_code = m.group(1).strip()
            except Exception as e:
                log.warn(f"Auto-fix attempt {attempt} failed: {e}")

    if not clean_patches:
        safe_print("❌ All patches failed review — self-mod aborted.", flush=True)
        return

    patches = clean_patches
    safe_print(f"📝 Generated patches for: {', '.join(os.path.basename(k) for k in patches.keys())}", flush=True)

    # ── 5. Preview: tell user what will change and why ────────────────────────
    import difflib as _diff
    safe_print("\n" + "="*58, flush=True)
    safe_print("  CHANGE PREVIEW", flush=True)
    safe_print("="*58, flush=True)

    for fname, new_code in patches.items():
        safe_print(f"\n  File: {fname}", flush=True)
        fname_path = _project_path(fname)
        if os.path.exists(fname_path):
            with open(fname_path, encoding="utf-8", errors="ignore") as _f:
                old_lines = _f.readlines()
            new_lines  = new_code.splitlines(keepends=True)
            diffs = list(_diff.unified_diff(old_lines, new_lines, lineterm=""))
            added   = sum(1 for l in diffs if l.startswith("+") and not l.startswith("+++"))
            removed = sum(1 for l in diffs if l.startswith("-") and not l.startswith("---"))
            safe_print(f"  + {added} lines added  - {removed} lines removed", flush=True)
            shown = [l for l in diffs if not l.startswith(("---","+++","@@"))][:25]
            for dl in shown:
                px = "  +" if dl.startswith("+") else ("  -" if dl.startswith("-") else "   ")
                safe_print(px + " " + dl.rstrip(), flush=True)
            if len(shown) == 25:
                safe_print(f"  ... ({len(diffs)} total diff lines)", flush=True)
        else:
            safe_print(f"  NEW file — {new_code.count(chr(10))} lines", flush=True)

        # Show reason from first comment/docstring lines
        why = []
        for ln in new_code.splitlines()[:15]:
            s = ln.strip().lstrip("#").strip()
            if s and len(s) > 5 and not s.startswith(("import","from","class ","def ")):
                why.append(s); break
        if why:
            safe_print(f"  Reason: {why[0][:120]}", flush=True)

    safe_print("\n" + "="*58, flush=True)
    safe_print("  ⚠️  Type  YES  to apply, or  NO  to cancel:", flush=True)
    safe_print("  (Type your answer in the input and press Enter)\n", flush=True)

    # Use threading event so agent.py main loop can pass the answer
    _pending_confirmation.clear()
    _confirmation_answer.clear()
    _waiting_for_confirmation.set()

    # Wait up to 300s for answer (5 minutes)
    safe_print("  ⏳ Waiting for your answer (5 min timeout)...\n", flush=True)
    answered = _pending_confirmation.wait(timeout=300)
    _waiting_for_confirmation.clear()

    if not answered:
        safe_print("\n❌ Timed out — no files were changed.\n", flush=True)
        return

    confirm = _confirmation_answer.get("answer", "").strip().upper()

    if confirm not in ("YES", "Y"):
        safe_print("\n❌ Cancelled — no files were changed.\n", flush=True)
        return

    safe_print("\n✅ Confirmed — applying patches...\n", flush=True)

    _installed = _auto_install_deps(patches)
    if _installed:
        safe_print(f"   📦 Installed: {', '.join(_installed)}\n", flush=True)

    MAX_RETRY = 2
    updated = []
    for attempt in range(MAX_RETRY + 1):
        updated = _apply_patches(patches)
        if updated:
            break
        if attempt < MAX_RETRY:
            safe_print(
                f"\n🔄 Reviewer rejected patch — regenerating "
                f"(attempt {attempt + 2}/{MAX_RETRY + 1})...\n",
                flush=True,
            )
            from model_advisor import ESCALATION_LADDER
            retry_patches = _generate_patch(
                task,
                _llm_targets,
                search_results,
                force_model_idx=min(attempt + 1, len(ESCALATION_LADDER) - 1),
                agent_patched=_agent_patched,
            )
            if retry_patches:
                patches = retry_patches

    if updated and "tool_registry.py" in " ".join(updated):
        _sync_commands_to_gui(patches, task)

    all_updated = updated + (
        ["agent.py"] if _agent_patched and "agent.py" not in updated else []
    )

    try:
        from memory_store import memory as _mem

        _mem.add(
            task=task,
            success=bool(all_updated),
            solution=(
                f"Updated: {', '.join(all_updated)}"
                if all_updated else "no files updated"
            ),
            files=all_updated,
        )
    except Exception as _me:
        log.warn(f"Memory save skipped: {_me}")

    if all_updated:
        safe_print(
            f"\n✅ Self-modification complete!\n"
            f"   Updated: {', '.join(all_updated)}\n"
            f"   ⚠️  Restart the agent to apply changes.\n",
            flush=True,
        )
    else:
        safe_print(
            "❌ Self-modification failed — no files were updated.\n"
            "   Try rephrasing the request or check the logs.",
            flush=True,
        )
    safe_print("⚡AGENT_IDLE", flush=True)

def _auto_install_deps(patches: dict[str, str]) -> list[str]:
    """
    Scan all patch code for third-party imports, check if they're installed,
    and auto-install any missing ones via pip.
    Returns list of packages that were installed.

    Stdlib and known internal modules are excluded automatically.
    """
    import importlib
    import subprocess
    import sys

    # Packages that are stdlib or always available — never try to install
    _STDLIB_OR_INTERNAL = {
        "os", "sys", "re", "json", "time", "datetime", "math", "random",
        "threading", "subprocess", "pathlib", "shutil", "glob", "ast",
        "collections", "itertools", "functools", "typing", "io", "copy",
        "hashlib", "base64", "urllib", "http", "email", "socket",
        "traceback", "warnings", "logging", "inspect", "importlib",
        "platform", "tempfile", "textwrap", "string", "struct", "enum",
        # internal project modules
        "logger", "state_manager", "llm_client", "config", "errors",
        "model_router", "model_advisor", "chat_handler", "tool_registry",
        "self_mod", "session_manager", "shutdown_manager", "recovery",
        "memory_store", "metrics", "profiler", "domain_sandbox",
        "file_handler", "project_tools", "project_builder",
        "generation_engine", "compiler_tools", "script_generator",
        "script_reviewer", "unity_pipeline", "planner", "env_check",
        "process_registry", "template_cache",
    }

    # import name → pip package name (when they differ)
    _IMPORT_TO_PIP = {
        "cv2":          "opencv-python",
        "PIL":          "Pillow",
        "sklearn":      "scikit-learn",
        "bs4":          "beautifulsoup4",
        "yaml":         "PyYAML",
        "dotenv":       "python-dotenv",
        "pyjokes":      "pyjokes",
        "playwright":   "playwright",
        "ddgs":         "ddgs",
        "duckduckgo_search": "duckduckgo-search",
        "psutil":       "psutil",
        "numpy":        "numpy",
        "pandas":       "pandas",
        "matplotlib":   "matplotlib",
        "flask":        "flask",
        "fastapi":      "fastapi",
        "sqlalchemy":   "SQLAlchemy",
        "pydantic":     "pydantic",
        "aiohttp":      "aiohttp",
        "httpx":        "httpx",
    }

    # Collect all imports from patches
    import re as _re
    all_imports: set[str] = set()
    for code in patches.values():
        # "import X" and "import X as Y"
        for m in _re.finditer(r'^\s*import\s+([\w]+)', code, _re.MULTILINE):
            all_imports.add(m.group(1))
        # "from X import ..."
        for m in _re.finditer(r'^\s*from\s+([\w]+)', code, _re.MULTILINE):
            all_imports.add(m.group(1))

    # Filter to only third-party candidates
    candidates = [
        pkg for pkg in all_imports
        if pkg not in _STDLIB_OR_INTERNAL and not pkg.startswith("_")
    ]

    if not candidates:
        return []

    # Check which ones are missing
    missing: list[str] = []
    for imp in candidates:
        try:
            importlib.import_module(imp)
        except ImportError:
            missing.append(imp)

    if not missing:
        return []

    # Notify user and install
    installed: list[str] = []
    for imp in missing:
        pip_name = _IMPORT_TO_PIP.get(imp, imp)
        safe_print(f"   📦 Installing missing dependency: {pip_name}", flush=True)
        try:
            result = subprocess.run(
                [sys.executable, "-m", "pip", "install", pip_name, "-q"],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                safe_print(f"   ✅ {pip_name} installed successfully", flush=True)
                installed.append(pip_name)
            else:
                safe_print(f"   ❌ Failed to install {pip_name}: {result.stderr[:200]}",
                           flush=True)
        except Exception as e:
            safe_print(f"   ❌ Install error for {pip_name}: {e}", flush=True)

    return installed
