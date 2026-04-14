import os
import sys
import shutil
import subprocess
import urllib.parse
import webbrowser
import warnings
from logger import log, safe_print
from llm_client import safe_chat, get_response
import llm_client
import config as _cfg

warnings.filterwarnings("ignore", category=RuntimeWarning)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE = os.path.join(BASE_DIR, "agent_memory.txt")

def _get_model() -> str:
    return llm_client.DEFAULT_MODEL

def save_last_project(path):
    with open(MEMORY_FILE, "w", encoding="utf-8") as f:
        f.write(path)

def load_last_project():
    if not os.path.exists(MEMORY_FILE):
        return None
    with open(MEMORY_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()

def run_python(file_path):
    print(f"\n🚀 Running: {file_path}")
    folder = os.path.dirname(file_path)
    script = os.path.basename(file_path)

    try:
        subprocess.run([sys.executable, script], timeout=_cfg.PYTHON_RUN_TIMEOUT, cwd=folder)
    except subprocess.TimeoutExpired:
        print("⚠ Program timed out (loop or waiting for input).")
    except Exception as e:
        print(f"❌ Run Error: {e}")

def delete_tool(task):
    import re
    name = re.sub(r'^\ *(delete|remove)\ +', '', task, flags=re.IGNORECASE).strip()
    target = os.path.abspath(name)

    if os.path.exists(target):
        try:
            shutil.rmtree(target)
            print(f"🗑️ Deleted: {target}")
            last = load_last_project()
            if last and name in last:
                if os.path.exists(MEMORY_FILE):
                    os.remove(MEMORY_FILE)
        except Exception as e:
            print(f"❌ Error deleting: {e}")
    else:
        print(f"❌ Folder '{name}' not found.")

def project_tool(task):
    from generation_engine import build_structure, generate_code
    folder_name = "_".join(w.capitalize() for w in task.replace("build","").strip().split())[:40].replace(" ","_")
    if not folder_name: folder_name = "project"

    project_path = os.path.join(os.getcwd(), folder_name)

    if os.path.exists(project_path):
        print(f"⚠ Folder '{folder_name}' already exists. Updating inside it.")

    os.makedirs(project_path, exist_ok=True)
    print(f"📁 Project Path: {project_path}")

    # Thread-safe: pass project_path explicitly, never call os.chdir()
    # os.chdir() is process-wide and causes race conditions in background threads
    files = build_structure(task, cwd=project_path)
    generate_code(files, task, cwd=project_path)

    chosen = None
    priority = ["main.py", "app.py", "run.py", f"{folder_name}.py"]
    for p in priority:
        if p in files:
            chosen = p
            break
    if not chosen and files:
        chosen = files[0]

    if chosen:
        abs_path = os.path.join(project_path, chosen)
        save_last_project(abs_path)
        print("🔥 Project completed.")
        run_python(abs_path)
    else:
        print("❌ No files generated to run.")

def job_tool(task):
    print("🧠 Analyzing job market...")

    prompt = f"""Extract job details from this request: '{task}'.
    Default Title: Game Developer OR Python AI
    Default Platform: Upwork
    Default Location: Remote OR Egypt
    Reply ONLY with this exact format: TITLE | PLATFORM | LOCATION
    CRITICAL RULE: DO NOT write 'Here are the details', do not use markdown like **, and DO NOT add any conversational text. JUST the raw format."""

    try:
        r = safe_chat(model=_get_model(), messages=[{"role": "user", "content": prompt}])
        ans = get_response(r).strip()

        if ":" in ans: ans = ans.split(":")[-1]
        ans = ans.replace('**', '').replace('"', '').strip()

        parts = ans.split('|')
        title    = parts[0].strip() if len(parts) > 0 else "Game Developer"
        platform = parts[1].strip().lower() if len(parts) > 1 else "upwork"
        location = parts[2].strip() if len(parts) > 2 else "Remote"

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