# env_check.py — Preflight dependency checker
# Run before agent starts to detect missing tools early

import os, sys, subprocess, time

# ─── Colors (Windows-safe) ────────────────────────────────────
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
RESET  = "\033[0m"
BOLD   = "\033[1m"

def _c(color, text): return f"{color}{text}{RESET}"

# ─── Core checker ─────────────────────────────────────────────
def check_tool(name: str, cmd: list, parse_version=None,
               required=True, hint="") -> dict:
    """
    Check if a CLI tool is available.
    Returns: {name, ok, version, required, hint}
    """
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=6)
        out = (r.stdout + r.stderr).strip().split("\n")[0]
        version = parse_version(out) if parse_version else out[:60]
        return {"name": name, "ok": True, "version": version,
                "required": required, "hint": hint}
    except FileNotFoundError:
        return {"name": name, "ok": False, "version": None,
                "required": required, "hint": hint}
    except subprocess.TimeoutExpired:
        return {"name": name, "ok": False, "version": "timeout",
                "required": required, "hint": hint}
    except Exception as e:
        return {"name": name, "ok": False, "version": str(e)[:40],
                "required": required, "hint": hint}


def check_ollama_models() -> dict:
    """Check if ollama is running AND has at least one model."""
    try:
        import ollama as _ol
        models = _ol.list().get("models", [])
        names  = [m.get("name", "?") for m in models[:3]]
        return {"name": "ollama models", "ok": bool(models),
                "version": ", ".join(names) or "no models found",
                "required": False,
                "hint": "Run: ollama pull qwen2.5-coder:7b"}
    except Exception as e:
        return {"name": "ollama models", "ok": False,
                "version": str(e)[:60], "required": True,
                "hint": "Install ollama from https://ollama.ai"}


def check_python_package(pkg: str, import_name: str = None,
                         required=True, hint="") -> dict:
    """Check if a Python package is importable."""
    mod = import_name or pkg
    try:
        m = __import__(mod)
        ver = getattr(m, "__version__", "installed")
        return {"name": f"pip:{pkg}", "ok": True, "version": ver,
                "required": required, "hint": hint}
    except ImportError:
        return {"name": f"pip:{pkg}", "ok": False, "version": None,
                "required": required,
                "hint": hint or f"pip install {pkg}"}


# ─── Full dependency list ──────────────────────────────────────
def run_all_checks() -> list:
    checks = [
        # ── Core runtime ──
        check_tool(
            "Python", [sys.executable, "--version"],
            parse_version=lambda s: s,
            required=True, hint=""
        ),
        check_tool(
            "ollama",
            ["ollama", "--version"],
            parse_version=lambda s: s.split()[-1] if s else "?",
            required=True,
            hint="Install from https://ollama.ai"
        ),
        check_ollama_models(),

        # ── Web / Node ──
        check_tool(
            "npm", ["npm", "--version"],
            parse_version=lambda s: f"v{s.strip()}",
            required=False,
            hint="Install Node.js from https://nodejs.org"
        ),
        check_tool(
            "node", ["node", "--version"],
            required=False,
            hint="Install Node.js from https://nodejs.org"
        ),
        check_tool(
            "Angular CLI (ng)", ["ng", "version", "--skip-confirmation"],
            parse_version=lambda s: s.split("\n")[0][:40],
            required=False,
            hint="npm install -g @angular/cli"
        ),

        # ── .NET ──
        check_tool(
            "dotnet", ["dotnet", "--version"],
            parse_version=lambda s: f"v{s.strip()}",
            required=False,
            hint="Install from https://dotnet.microsoft.com"
        ),

        # ── OCR ──
        check_tool(
            "Tesseract OCR",
            ["tesseract", "--version"],
            parse_version=lambda s: s.split("\n")[0],
            required=False,
            hint="Install from https://github.com/UB-Mannheim/tesseract/wiki"
        ),

        # ── Python packages ──
        check_python_package("ollama",     required=True,  hint="pip install ollama"),
        check_python_package("customtkinter", "customtkinter", required=False, hint="pip install customtkinter"),
        check_python_package("pypdf",      required=False, hint="pip install pypdf"),
        check_python_package("python-docx","docx",         required=False, hint="pip install python-docx"),
        check_python_package("openpyxl",   required=False, hint="pip install openpyxl"),
        check_python_package("python-pptx","pptx",         required=False, hint="pip install python-pptx"),
        check_python_package("opencv-python","cv2",        required=False, hint="pip install opencv-python"),
        check_python_package("pytesseract",required=False, hint="pip install pytesseract"),
        check_python_package("duckduckgo-search","duckduckgo_search",
                             required=False, hint="pip install duckduckgo-search"),
        check_python_package("pillow","PIL", required=False, hint="pip install pillow"),
    ]
    return checks


# ─── Report ───────────────────────────────────────────────────
def print_report(checks: list) -> bool:
    """Print colored report. Returns True if all required deps OK."""
    print(f"\n{BOLD}{'─'*55}{RESET}")
    print(f"{BOLD} 🔍 Agent Dependency Check{RESET}")
    print(f"{BOLD}{'─'*55}{RESET}")

    required_ok = True
    groups = {
        "Core":             ["Python", "ollama", "ollama models"],
        "Web / Node":       ["npm", "node", "Angular CLI (ng)"],
        ".NET":             ["dotnet"],
        "OCR":              ["Tesseract OCR"],
        "Python packages":  [c["name"] for c in checks if c["name"].startswith("pip:")],
    }

    for group, names in groups.items():
        group_checks = [c for c in checks if c["name"] in names]
        if not group_checks: continue
        print(f"\n  {BOLD}{group}{RESET}")
        for c in group_checks:
            if c["ok"]:
                icon = _c(GREEN, "✅")
                ver  = _c(GREEN, c["version"] or "ok")
            elif not c["required"]:
                icon = _c(YELLOW, "⚡")
                ver  = _c(YELLOW, "not installed (optional)")
            else:
                icon = _c(RED, "❌")
                ver  = _c(RED, "MISSING")
                required_ok = False

            line = f"    {icon} {c['name']:25} {ver}"
            print(line)

            if not c["ok"] and c.get("hint"):
                print(f"       {_c(YELLOW, '→')} {c['hint']}")

    print(f"\n{BOLD}{'─'*55}{RESET}")
    if required_ok:
        print(_c(GREEN, f"  ✅ All required dependencies OK\n"))
    else:
        print(_c(RED, f"  ❌ Some REQUIRED dependencies are missing!\n"))
    return required_ok


def check_and_exit_if_missing():
    """Run checks silently — only exits if critical deps missing."""
    import sys as _sys, io as _io
    _buf = _io.StringIO()
    _old_out, _old_err = _sys.stdout, _sys.stderr
    _sys.stdout = _sys.stderr = _buf
    try:
        return run_env_check_once(exit_on_missing=True)
    except SystemExit:
        raise
    except Exception:
        return True   # don't block startup on check error
    finally:
        _sys.stdout, _sys.stderr = _old_out, _old_err


# ─── Run-once guard ───────────────────────────────────────────
_checked = False

def run_env_check_once(exit_on_missing: bool = True) -> bool:
    """Run checks exactly once at startup. Skips on subsequent calls."""
    global _checked
    if _checked:
        return True
    _checked = True
    checks = run_all_checks()
    ok = print_report(checks)
    if not ok and exit_on_missing:
        import sys as _sys
        print("  ❌ Agent cannot start — install missing required dependencies.\n")
        _sys.exit(1)
    return ok

# ─── Standalone run ───────────────────────────────────────────
if __name__ == "__main__":
    checks = run_all_checks()
    print_report(checks)
