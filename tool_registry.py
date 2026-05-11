# tool_registry.py — All agent tools in one registry
# Extracted from agent.py — adding a new tool means editing ONLY this file

import os
from logger        import log, safe_print
from state_manager import _state, project_context
from datetime import datetime

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
}


BACKGROUND_TOOLS = {"GAME", "PROJECT", "JOB", "SELF_MOD", "CHAT"}


def get_tool(mode: str):
    """Return the callable for the given mode. Resolves lazy getters."""
    fn = TOOL_REGISTRY.get(mode)
    if fn is None:
        return _get_chat_tool()
    if fn is _get_chat_tool:
        return _get_chat_tool()
    return fn