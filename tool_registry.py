# tool_registry.py — All agent tools in one registry
# Extracted from agent.py — adding a new tool means editing ONLY this file

import fnmatch
import json
import os
import shlex
import sys
from dataclasses import dataclass, field
from typing import Any

import config as _cfg
from compiler_tools import run_process
from logger        import log, safe_print
from state_manager import _state, project_context
from datetime import datetime


_SKIP_DIRS = {
    ".git", ".pytest_cache", ".checkpoints", "__pycache__",
    "venv", ".venv", "node_modules", "dist", "build",
}
_TEXT_EXTS = {
    ".py", ".txt", ".md", ".json", ".yaml", ".yml", ".toml", ".ini",
    ".cs", ".cpp", ".h", ".hpp", ".js", ".jsx", ".ts", ".tsx", ".html",
    ".css", ".sql", ".xml", ".csproj", ".sln",
}
TOOL_CATEGORIES = ("filesystem", "testing", "analysis", "project", "memory")


@dataclass
class ToolResult:
    success: bool
    data: dict = field(default_factory=dict)
    error: str = ""

    @classmethod
    def ok(cls, **data) -> "ToolResult":
        return cls(True, data=data)

    @classmethod
    def fail(cls, error: str, **data) -> "ToolResult":
        return cls(False, data=data, error=str(error))

    @classmethod
    def from_value(cls, value: Any) -> "ToolResult":
        if isinstance(value, ToolResult):
            return value
        if isinstance(value, dict):
            payload = dict(value)
            success = bool(payload.pop("success", True))
            error = str(payload.pop("error", ""))
            data = payload.pop("data", None)
            if isinstance(data, dict):
                data.update(payload)
                payload = data
            return cls(success=success, data=payload, error=error)
        if isinstance(value, str):
            try:
                parsed = json.loads(value)
                if isinstance(parsed, dict):
                    return cls.from_value(parsed)
            except Exception:
                pass
            return cls(True, data={"output": value})
        return cls(True, data={"value": value})

    def to_dict(self) -> dict:
        return {"success": self.success, "data": self.data, "error": self.error}

    def to_legacy_dict(self) -> dict:
        payload = {"success": self.success, **self.data}
        if self.error:
            payload["error"] = self.error
        return payload

    def to_json(self, legacy: bool = False) -> str:
        payload = self.to_legacy_dict() if legacy else self.to_dict()
        return json.dumps(payload, ensure_ascii=False)

    def brief(self, max_chars: int = 1000) -> str:
        text = json.dumps(self.to_dict(), ensure_ascii=False, default=str)
        return text[:max_chars] + ("..." if len(text) > max_chars else "")


class Tool:
    name: str = ""
    description: str = ""
    schema: dict = {}
    categories: tuple[str, ...] = ()
    tags: tuple[str, ...] = ()

    def execute(self, args: dict) -> str:
        """External compatibility wrapper: return legacy JSON text."""
        return self.execute_structured(args).to_json(legacy=True)

    def execute_structured(self, args: dict) -> ToolResult:
        """Internal execution path used by the autonomous loop."""
        if type(self).execute is not Tool.execute:
            return ToolResult.from_value(self.execute(args))
        return ToolResult.from_value(self._execute(args))

    def _execute(self, args: dict) -> ToolResult:
        raise NotImplementedError(f"{self.__class__.__name__} must implement _execute()")


_STRUCTURED_TOOLS: dict[str, Tool] = {}


def _workspace_root(args: dict | None = None) -> str:
    args = args or {}
    root = args.get("root") or os.getcwd()
    return os.path.abspath(str(root))


def _safe_path(path: str, root: str | None = None) -> str:
    base = os.path.abspath(root or os.getcwd())
    target = os.path.abspath(os.path.join(base, path) if not os.path.isabs(path) else path)
    try:
        common = os.path.commonpath([base, target])
    except ValueError:
        common = ""
    if common != base:
        raise ValueError(f"path escapes workspace: {path}")
    return target


def _rel(path: str, root: str) -> str:
    try:
        return os.path.relpath(path, root).replace("\\", "/")
    except ValueError:
        return path


def _looks_text(path: str) -> bool:
    return os.path.splitext(path)[1].lower() in _TEXT_EXTS


def _truncate(text: str, limit: int) -> tuple[str, bool]:
    if limit and len(text) > limit:
        return text[:limit], True
    return text, False


def _command_from_args(args: dict, default: list[str]) -> list[str]:
    cmd = args.get("command") or default
    if isinstance(cmd, str):
        return shlex.split(cmd, posix=False)
    if isinstance(cmd, list) and all(isinstance(p, str) for p in cmd):
        return cmd
    raise ValueError("command must be a string or list of strings")


def register_tool(tool: Tool, replace: bool = True) -> Tool:
    """Register a structured autonomous Tool."""
    if not isinstance(tool, Tool):
        raise TypeError("register_tool expects a Tool instance")
    if not tool.name or not isinstance(tool.name, str):
        raise ValueError("tool.name is required")
    if not replace and tool.name in _STRUCTURED_TOOLS:
        raise ValueError(f"tool already registered: {tool.name}")
    _STRUCTURED_TOOLS[tool.name] = tool
    log.debug("Structured tool registered", tool=tool.name)
    return tool


def unregister_tool(name: str) -> None:
    _STRUCTURED_TOOLS.pop(name, None)


def list_tools(serialized: bool = True) -> list:
    """Return registered structured tools, serialized for prompting by default."""
    tools = [_STRUCTURED_TOOLS[name] for name in sorted(_STRUCTURED_TOOLS)]
    if not serialized:
        return tools
    return [
        {
            "name": t.name,
            "description": t.description,
            "schema": t.schema,
            "categories": list(t.categories),
            "tags": list(t.tags),
        }
        for t in tools
    ]


class ReadFileTool(Tool):
    name = "read_file"
    description = "Read a text file from the current workspace."
    categories = ("filesystem",)
    tags = ("read", "text")
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "max_chars": {"type": "integer", "default": 20000},
        },
        "required": ["path"],
    }

    def _execute(self, args: dict) -> ToolResult:
        root = _workspace_root(args)
        target = _safe_path(str(args["path"]), root)
        max_chars = int(args.get("max_chars", 20000))
        with open(target, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(max_chars + 1)
        content, truncated = _truncate(content, max_chars)
        return ToolResult.ok(path=_rel(target, root), content=content, truncated=truncated)


class WriteFileTool(Tool):
    name = "write_file"
    description = "Write or append UTF-8 text to a file in the current workspace."
    categories = ("filesystem",)
    tags = ("write", "text")
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "content": {"type": "string"},
            "append": {"type": "boolean", "default": False},
        },
        "required": ["path", "content"],
    }

    def _execute(self, args: dict) -> ToolResult:
        root = _workspace_root(args)
        target = _safe_path(str(args["path"]), root)
        os.makedirs(os.path.dirname(target) or root, exist_ok=True)
        mode = "a" if args.get("append") else "w"
        content = str(args.get("content", ""))
        with open(target, mode, encoding="utf-8") as f:
            f.write(content)
        return ToolResult.ok(
            path=_rel(target, root), chars=len(content), append=bool(args.get("append"))
        )


class EditFileTool(Tool):
    name = "edit_file"
    description = "Edit a file by text replacement or by replacing a 1-based line range."
    categories = ("filesystem",)
    tags = ("edit", "patch")
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string"},
            "old_text": {"type": "string"},
            "new_text": {"type": "string"},
            "count": {"type": "integer", "default": 1},
            "start_line": {"type": "integer"},
            "end_line": {"type": "integer"},
            "replacement": {"type": "string"},
        },
        "required": ["path"],
    }

    def _execute(self, args: dict) -> ToolResult:
        root = _workspace_root(args)
        target = _safe_path(str(args["path"]), root)
        with open(target, "r", encoding="utf-8", errors="ignore") as f:
            original = f.read()

        replacements = 0
        if "old_text" in args:
            old = str(args.get("old_text", ""))
            new = str(args.get("new_text", ""))
            if not old:
                raise ValueError("old_text cannot be empty")
            count = int(args.get("count", 1))
            replacements = original.count(old) if count <= 0 else min(original.count(old), count)
            updated = original.replace(old, new, count if count > 0 else -1)
        elif "start_line" in args and "replacement" in args:
            lines = original.splitlines(keepends=True)
            start = int(args["start_line"])
            end = int(args.get("end_line", start))
            if start < 1 or end < start or end > len(lines):
                raise ValueError("invalid line range")
            replacement = str(args.get("replacement", ""))
            if replacement and not replacement.endswith(("\n", "\r")):
                replacement += "\n"
            lines[start - 1:end] = [replacement] if replacement else []
            updated = "".join(lines)
            replacements = end - start + 1
        else:
            raise ValueError("provide old_text/new_text or start_line/replacement")

        with open(target, "w", encoding="utf-8") as f:
            f.write(updated)
        return ToolResult.ok(path=_rel(target, root), replacements=replacements)


class SearchFilesTool(Tool):
    name = "search_files"
    description = "Search text files for a literal query."
    categories = ("filesystem", "analysis")
    tags = ("search", "text")
    schema = {
        "type": "object",
        "properties": {
            "query": {"type": "string"},
            "path": {"type": "string", "default": "."},
            "glob": {"type": "string", "default": "*"},
            "max_results": {"type": "integer", "default": 50},
        },
        "required": ["query"],
    }

    def _execute(self, args: dict) -> ToolResult:
        root = _workspace_root(args)
        start = _safe_path(str(args.get("path", ".")), root)
        query = str(args.get("query", ""))
        pattern = str(args.get("glob", "*"))
        max_results = int(args.get("max_results", 50))
        if not query:
            raise ValueError("query is required")
        matches = []
        for dirpath, dirnames, filenames in os.walk(start):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fname in filenames:
                full = os.path.join(dirpath, fname)
                if not fnmatch.fnmatch(fname, pattern) or not _looks_text(full):
                    continue
                try:
                    with open(full, "r", encoding="utf-8", errors="ignore") as f:
                        for line_no, line in enumerate(f, 1):
                            if query in line:
                                matches.append({
                                    "path": _rel(full, root),
                                    "line": line_no,
                                    "text": line.strip()[:300],
                                })
                                if len(matches) >= max_results:
                                    return ToolResult.ok(query=query, matches=matches)
                except OSError:
                    continue
        return ToolResult.ok(query=query, matches=matches)


class ScanProjectTool(Tool):
    name = "scan_project"
    description = "List project files and high-level metadata."
    categories = ("project", "filesystem", "analysis")
    tags = ("scan", "metadata")
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": "."},
            "max_files": {"type": "integer", "default": 200},
        },
    }

    def _execute(self, args: dict) -> ToolResult:
        root = _workspace_root(args)
        start = _safe_path(str(args.get("path", ".")), root)
        max_files = int(args.get("max_files", 200))
        files = []
        skipped = 0
        for dirpath, dirnames, filenames in os.walk(start):
            dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
            for fname in sorted(filenames):
                full = os.path.join(dirpath, fname)
                if len(files) >= max_files:
                    skipped += 1
                    continue
                try:
                    files.append({
                        "path": _rel(full, root),
                        "size": os.path.getsize(full),
                        "ext": os.path.splitext(fname)[1].lower(),
                    })
                except OSError:
                    skipped += 1
        return ToolResult.ok(root=_rel(start, root), files=files, skipped=skipped)


class CompileProjectTool(Tool):
    name = "compile_project"
    description = "Compile or build the project using a detected or provided command."
    categories = ("project", "testing")
    tags = ("compile", "build")
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": "."},
            "command": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
            "timeout": {"type": "integer", "default": 60},
        },
    }

    def _execute(self, args: dict) -> ToolResult:
        root = _workspace_root(args)
        cwd = _safe_path(str(args.get("path", ".")), root)
        command = args.get("command")
        if command:
            cmd = _command_from_args(args, [])
        else:
            names = set(os.listdir(cwd))
            has_dotnet = any(n.endswith((".sln", ".csproj")) for n in names)
            if has_dotnet:
                cmd = ["dotnet", "build", "--nologo"]
            elif "package.json" in names:
                cmd = ["npm", "run", "build"]
            elif any(n.endswith(".py") for n in names) or "pyproject.toml" in names:
                cmd = [sys.executable, "-m", "compileall", "-q", "."]
            else:
                return ToolResult.fail("no supported build target found", cwd=_rel(cwd, root))
        result = run_process(cmd, cwd=cwd, timeout=int(args.get("timeout", 60)))
        if result.get("success"):
            return ToolResult.ok(cwd=_rel(cwd, root), command=cmd, result=result)
        return ToolResult.fail(
            result.get("stderr") or "compile command failed",
            cwd=_rel(cwd, root), command=cmd, result=result,
        )


class RunTestsTool(Tool):
    name = "run_tests"
    description = "Run the project test command, defaulting to pytest tests -q."
    categories = ("testing", "project")
    tags = ("pytest", "tests")
    schema = {
        "type": "object",
        "properties": {
            "path": {"type": "string", "default": "."},
            "command": {"oneOf": [{"type": "string"}, {"type": "array", "items": {"type": "string"}}]},
            "timeout": {"type": "integer", "default": 120},
        },
    }

    def _execute(self, args: dict) -> ToolResult:
        root = _workspace_root(args)
        cwd = _safe_path(str(args.get("path", ".")), root)
        cmd = _command_from_args(args, [sys.executable, "-m", "pytest", "tests", "-q"])
        result = run_process(cmd, cwd=cwd, timeout=int(args.get("timeout", 120)))
        if result.get("success"):
            return ToolResult.ok(cwd=_rel(cwd, root), command=cmd, result=result)
        return ToolResult.fail(
            result.get("stderr") or "test command failed",
            cwd=_rel(cwd, root), command=cmd, result=result,
        )


class AnalyzeErrorsTool(Tool):
    name = "analyze_errors"
    description = "Summarize compiler, test, or traceback errors from text or a file."
    categories = ("analysis",)
    tags = ("errors", "diagnostics")
    schema = {
        "type": "object",
        "properties": {
            "text": {"type": "string"},
            "path": {"type": "string"},
            "max_items": {"type": "integer", "default": 20},
        },
    }

    def _execute(self, args: dict) -> ToolResult:
        root = _workspace_root(args)
        text = str(args.get("text", ""))
        if not text and args.get("path"):
            target = _safe_path(str(args["path"]), root)
            with open(target, "r", encoding="utf-8", errors="ignore") as f:
                text = f.read()
        if not text:
            raise ValueError("text or path is required")
        max_items = int(args.get("max_items", 20))
        findings = []
        for line in text.splitlines():
            stripped = line.strip()
            lower = stripped.lower()
            if (
                "traceback" in lower
                or "assertionerror" in lower
                or "syntaxerror" in lower
                or "error cs" in lower
                or lower.startswith("failed ")
                or " failed" in lower
            ):
                findings.append(stripped[:500])
                if len(findings) >= max_items:
                    break
        category = "unknown"
        if any("error cs" in f.lower() for f in findings):
            category = "csharp_compile"
        elif any("traceback" in f.lower() or "syntaxerror" in f.lower() for f in findings):
            category = "python_runtime"
        elif any("failed" in f.lower() or "assertionerror" in f.lower() for f in findings):
            category = "test_failure"
        return ToolResult.ok(category=category, findings=findings, count=len(findings))


for _tool in (
    ReadFileTool(), WriteFileTool(), EditFileTool(), SearchFilesTool(),
    CompileProjectTool(), RunTestsTool(), ScanProjectTool(), AnalyzeErrorsTool(),
):
    register_tool(_tool)

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


def _tool_status(user: str):
    import llm_client
    try:
        import psutil as _ps, os as _os
        mem     = _ps.Process(_os.getpid()).memory_info().rss / 1024 / 1024
        mem_str = f"{mem:.1f} MB"
    except ImportError:
        mem_str = "install psutil: pip install psutil"
    print(f"\n📊 Agent Status")
    print(f"   🤖 Model   : {llm_client.DEFAULT_MODEL}")
    print(f"   💾 Memory  : {mem_str}")
    print(f"   📁 Context : {len(project_context)} file(s) attached")
    print()

def _tool_time(user: str):
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n🕒 Current Time")
    print(f"   🕒 Time     : {current_time}")
    print()


def _tool_date(user: str):  # New tool for showing today's date
    current_date = datetime.now().strftime("%Y-%m-%d")
    print(f"\n📅 Today's Date")
    print(f"   📅 Date     : {current_date}")
    print()

def _tool_memory(user: str):
    """
    /memory              — show recent memories + stats
    /memory search <q>   — search memory for a query
    /memory clear        — delete all memories (asks confirmation)
    /memory export       — export to memory_export.json
    """
    from memory_store import memory
    parts = user.strip().split(maxsplit=2)
    sub   = parts[1].lower() if len(parts) > 1 else ""

    if sub == "search":
        query = " ".join(parts[2:]) if len(parts) > 2 else ""
        if not query:
            print("❌ Usage: /memory search <query>")
        else:
            memory.print_search(query)
    elif sub == "clear":
        # Don't use input() — it blocks the GUI thread.
        # Require explicit "/memory clear confirm" instead.
        if len(parts) > 2 and parts[2].lower() == "confirm":
            memory.clear()
        else:
            print("⚠️  This will delete ALL memories permanently.")
            print("   To confirm: /memory clear confirm")
    elif sub == "export":
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "memory_export.json")
        memory.export(path)
    else:
        memory.print_recent(n=10)


def _tool_auto(task: str):
    prompt = task.strip()
    for prefix in ("/auto", "/autonomous"):
        if prompt.lower().startswith(prefix):
            prompt = prompt[len(prefix):].strip()
            break
    if not prompt:
        safe_print("Usage: /auto <engineering task>")
        safe_print("⚡AGENT_IDLE", flush=True)
        return

    from autonomous_loop import AutonomousExecutor

    safe_print("\nAutonomous loop started...\n")
    state = AutonomousExecutor().execute(prompt)
    if state.status == "completed":
        safe_print(f"\nAgent: {state.final_answer}\n")
    else:
        safe_print(f"\nAutonomous loop stopped: {state.failure_reason}\n")
    safe_print("⚡AGENT_IDLE", flush=True)


def _tool_weather(user: str):
    """Show current weather for a city.  Usage: /weather <city>
    Uses Open-Meteo + Nominatim — 100% free, no API key needed.
    """
    import urllib.request as _ur
    import urllib.parse   as _up
    import json           as _json

    # ── 1. Parse city name ────────────────────────────────────────────────────
    parts = user.strip().split(maxsplit=1)
    city  = parts[1].strip() if len(parts) > 1 else ""
    if not city:
        print("❌ Usage: /weather <city>   e.g. /weather Cairo")
        return

    # ── 2. Geocode city → lat/lon (Nominatim, free) ───────────────────────────
    try:
        geo_url = (
            "https://nominatim.openstreetmap.org/search?"
            + _up.urlencode({"q": city, "format": "json", "limit": "1"})
        )
        req = _ur.Request(geo_url,
                          headers={"User-Agent": "AI-Agent-Weather/1.0"})
        with _ur.urlopen(req, timeout=8) as r:
            geo = _json.loads(r.read().decode())
    except Exception as e:
        print(f"❌ Geocoding failed: {e}")
        return

    if not geo:
        print(f"❌ City not found: '{city}'")
        return

    lat        = geo[0]["lat"]
    lon        = geo[0]["lon"]
    city_label = geo[0].get("display_name", city).split(",")[0]

    # ── 3. Fetch weather (Open-Meteo, free, no key) ───────────────────────────
    try:
        wx_url = (
            "https://api.open-meteo.com/v1/forecast?"
            + _up.urlencode({
                "latitude":   lat,
                "longitude":  lon,
                "current":    "temperature_2m,relative_humidity_2m,"
                              "apparent_temperature,precipitation,"
                              "wind_speed_10m,weathercode",
                "wind_speed_unit": "kmh",
                "timezone":   "auto",
            })
        )
        with _ur.urlopen(wx_url, timeout=8) as r:
            wx = _json.loads(r.read().decode())
    except Exception as e:
        print(f"❌ Weather fetch failed: {e}")
        return

    c    = wx.get("current", {})
    temp = c.get("temperature_2m",      "?")
    feel = c.get("apparent_temperature","?")
    hum  = c.get("relative_humidity_2m","?")
    wind = c.get("wind_speed_10m",      "?")
    prec = c.get("precipitation",       0)
    code = c.get("weathercode",         0)

    # WMO weather code → description
    _WMO = {
        0:"Clear sky", 1:"Mainly clear", 2:"Partly cloudy", 3:"Overcast",
        45:"Foggy", 48:"Icy fog",
        51:"Light drizzle", 53:"Drizzle", 55:"Heavy drizzle",
        61:"Light rain", 63:"Rain", 65:"Heavy rain",
        71:"Light snow", 73:"Snow", 75:"Heavy snow",
        80:"Rain showers", 81:"Showers", 82:"Violent showers",
        95:"Thunderstorm", 96:"Thunderstorm + hail",
    }
    desc = _WMO.get(int(code), f"Code {code}")

    print(f"\n🌤️  Weather in {city_label}")
    print(f"   🌡️  Temperature : {temp}°C  (feels like {feel}°C)")
    print(f"   🌦️  Condition   : {desc}")
    print(f"   💧 Humidity    : {hum}%")
    print(f"   💨 Wind        : {wind} km/h")
    if prec:
        print(f"   🌧️  Precipitation: {prec} mm")
    print()


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
    "STATUS":   _tool_status,
    "TIME":     _tool_time,
    "DATE":     _tool_date,      # Added new tool for showing today's date
    "WEATHER":  _tool_weather,   # New tool for checking weather
    "MEMORY":   _tool_memory,    # RAG memory — view, search, clear
    "AUTO":     _tool_auto,      # Autonomous think-act-observe loop
}


BACKGROUND_TOOLS = {"GAME", "PROJECT", "JOB", "SELF_MOD", "CHAT", "AUTO"}


def get_tool(mode: str, *, structured: bool = False):
    """Return a structured Tool or legacy command callable.

    structured=True is used by autonomous_loop.py and never falls back to chat.
    The default keeps the original agent command behavior intact.
    """
    if structured:
        return _STRUCTURED_TOOLS.get(mode)
    if mode in _STRUCTURED_TOOLS:
        return _STRUCTURED_TOOLS[mode]
    fn = TOOL_REGISTRY.get(mode)
    if fn is None:
        return _get_chat_tool()
    if fn is _get_chat_tool:
        return _get_chat_tool()
    return fn
