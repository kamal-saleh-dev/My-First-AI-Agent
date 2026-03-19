# python_templates.py — Python project templates
# The agent uses these to generate Python scripts, APIs, tools, and self-modifications

PYTHON_SYSTEM_PROMPT = """You are a senior Python developer.
RULES:
- Write clean, production-ready Python 3.10+
- Use type hints and docstrings
- Return ONLY one ```python code block per file
- No explanations outside code blocks
- Follow PEP 8 style
- Use proper error handling with try/except
"""

PYTHON_PLANNING_PROMPT = """You are a senior Python architect.
List the files needed to build: {task}

Output ONLY this format (one per line):
FileName:role

Roles: script, class, api, cli, util, config, test, main

RULES:
- Always include a main entry point
- Max 6 files
- Keep it simple and runnable

Example for "web scraper":
main:main
scraper:class
utils:util
config:config
"""

PYTHON_TEMPLATES = {

    "main": """#!/usr/bin/env python3
\"\"\"
{name} — Main entry point
\"\"\"

def main():
    print("🚀 {name} started")
    # Add your logic here

if __name__ == "__main__":
    main()
""",

    "script": """#!/usr/bin/env python3
\"\"\"
{name}.py — {name} script
\"\"\"
import os
import sys
import json
from pathlib import Path
from typing import Optional, List, Dict, Any


def run(input_data: Any = None) -> Any:
    \"\"\"Main function — add your logic here.\"\"\"
    print(f"Running {name}...")
    return None


def load_file(path: str) -> str:
    \"\"\"Read a file safely.\"\"\"
    try:
        return Path(path).read_text(encoding="utf-8")
    except FileNotFoundError:
        print(f"❌ File not found: {{path}}")
        return ""
    except Exception as e:
        print(f"❌ Error reading {{path}}: {{e}}")
        return ""


def save_file(path: str, content: str) -> bool:
    \"\"\"Write to a file safely.\"\"\"
    try:
        Path(path).write_text(content, encoding="utf-8")
        print(f"💾 Saved: {{path}}")
        return True
    except Exception as e:
        print(f"❌ Error saving {{path}}: {{e}}")
        return False


if __name__ == "__main__":
    run()
""",

    "class": """\"\"\"
{name}.py — {name} class definition
\"\"\"
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class {name}:
    \"\"\"
    {name} — add description here.
    \"\"\"
    id: int = 0
    name: str = ""
    description: str = ""
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        pass

    def to_dict(self) -> Dict[str, Any]:
        \"\"\"Convert to dictionary.\"\"\"
        return {{
            "id":          self.id,
            "name":        self.name,
            "description": self.description,
            "is_active":   self.is_active,
            "created_at":  self.created_at.isoformat(),
            "metadata":    self.metadata,
        }}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "{name}":
        \"\"\"Create instance from dictionary.\"\"\"
        return cls(
            id=data.get("id", 0),
            name=data.get("name", ""),
            description=data.get("description", ""),
            is_active=data.get("is_active", True),
        )

    def validate(self) -> tuple[bool, str]:
        \"\"\"Validate the object. Returns (is_valid, message).\"\"\"
        if not self.name:
            return False, "Name is required"
        return True, "Valid"

    def __repr__(self) -> str:
        return f"{name}(id={{self.id}}, name={{self.name!r}})"
""",

    "api": """\"\"\"
{name}.py — FastAPI application
\"\"\"
from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime
import uvicorn

app = FastAPI(title="{name}", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Models ────────────────────────────────────────────────
class ItemBase(BaseModel):
    name: str
    description: Optional[str] = ""

class ItemCreate(ItemBase):
    pass

class ItemResponse(ItemBase):
    id: int
    is_active: bool = True
    created_at: datetime = datetime.now()

    class Config:
        from_attributes = True

# ─── In-memory store (replace with DB) ────────────────────
items_db: List[dict] = []
next_id = 1

# ─── Routes ───────────────────────────────────────────────
@app.get("/")
def root():
    return {{"message": "Welcome to {name} API", "version": "1.0.0"}}

@app.get("/items", response_model=List[ItemResponse])
def get_all():
    return items_db

@app.get("/items/{{item_id}}", response_model=ItemResponse)
def get_by_id(item_id: int):
    item = next((i for i in items_db if i["id"] == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item

@app.post("/items", response_model=ItemResponse, status_code=201)
def create(item: ItemCreate):
    global next_id
    new_item = {{**item.dict(), "id": next_id, "is_active": True, "created_at": datetime.now()}}
    items_db.append(new_item)
    next_id += 1
    return new_item

@app.put("/items/{{item_id}}", response_model=ItemResponse)
def update(item_id: int, item: ItemCreate):
    for i, existing in enumerate(items_db):
        if existing["id"] == item_id:
            items_db[i] = {{**existing, **item.dict()}}
            return items_db[i]
    raise HTTPException(status_code=404, detail="Item not found")

@app.delete("/items/{{item_id}}")
def delete(item_id: int):
    global items_db
    items_db = [i for i in items_db if i["id"] != item_id]
    return {{"message": "Deleted"}}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
""",

    "cli": """\"\"\"
{name}.py — Command Line Interface
\"\"\"
import argparse
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(
        prog="{name}",
        description="{name} — CLI tool"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # run command
    run_p = subparsers.add_parser("run", help="Run the main task")
    run_p.add_argument("input", nargs="?", help="Input file or value")
    run_p.add_argument("-o", "--output", help="Output file")
    run_p.add_argument("-v", "--verbose", action="store_true", help="Verbose output")

    # list command
    list_p = subparsers.add_parser("list", help="List items")
    list_p.add_argument("--filter", help="Filter by name")

    # config command
    cfg_p = subparsers.add_parser("config", help="Show/set config")
    cfg_p.add_argument("key", nargs="?", help="Config key")
    cfg_p.add_argument("value", nargs="?", help="Config value")

    return parser.parse_args()


def cmd_run(args):
    print(f"▶ Running {name}...")
    if args.verbose:
        print(f"  Input:  {{args.input}}")
        print(f"  Output: {{args.output}}")


def cmd_list(args):
    print("📋 Items:")
    items = ["Item 1", "Item 2", "Item 3"]
    for item in items:
        if not args.filter or args.filter.lower() in item.lower():
            print(f"  - {{item}}")


def cmd_config(args):
    if args.key and args.value:
        print(f"⚙️  Set {{args.key}} = {{args.value}}")
    elif args.key:
        print(f"⚙️  {{args.key}} = (not set)")
    else:
        print("⚙️  Config:")
        print("  debug = false")
        print("  output_dir = ./output")


def main():
    args = parse_args()

    commands = {{
        "run":    cmd_run,
        "list":   cmd_list,
        "config": cmd_config,
    }}

    if args.command in commands:
        commands[args.command](args)
    else:
        print("❌ Unknown command. Use --help for usage.")
        sys.exit(1)


if __name__ == "__main__":
    main()
""",

    "util": """\"\"\"
{name}.py — Utility functions
\"\"\"
import os
import json
import hashlib
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

# ─── Logging ──────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)


# ─── File utilities ────────────────────────────────────────
def read_json(path: str) -> Dict[str, Any]:
    \"\"\"Read and parse a JSON file.\"\"\"
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        log.error(f"Failed to read {{path}}: {{e}}")
        return {{}}


def write_json(path: str, data: Any, indent: int = 2) -> bool:
    \"\"\"Write data to a JSON file.\"\"\"
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        return True
    except Exception as e:
        log.error(f"Failed to write {{path}}: {{e}}")
        return False


def ensure_dir(path: str) -> str:
    \"\"\"Create directory if it doesn't exist. Returns path.\"\"\"
    Path(path).mkdir(parents=True, exist_ok=True)
    return path


# ─── String utilities ──────────────────────────────────────
def slugify(text: str) -> str:
    \"\"\"Convert text to a safe filename/slug.\"\"\"
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\\w\\s-]', '', text)
    text = re.sub(r'[\\s_-]+', '_', text)
    return text


def truncate(text: str, max_len: int = 100, suffix: str = "...") -> str:
    \"\"\"Truncate text to max_len characters.\"\"\"
    if len(text) <= max_len:
        return text
    return text[:max_len - len(suffix)] + suffix


def hash_string(text: str) -> str:
    \"\"\"Return MD5 hash of a string.\"\"\"
    return hashlib.md5(text.encode()).hexdigest()


# ─── Time utilities ────────────────────────────────────────
def now_str(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return datetime.now().strftime(fmt)


def timestamp() -> int:
    return int(datetime.now().timestamp())
""",

    "config": """\"\"\"
{name}.py — Configuration management
\"\"\"
import os
import json
from pathlib import Path
from typing import Any, Optional
from dataclasses import dataclass, asdict


CONFIG_FILE = Path(__file__).parent / "config.json"


@dataclass
class Config:
    # App settings
    app_name:   str  = "{name}"
    version:    str  = "1.0.0"
    debug:      bool = False

    # Paths
    output_dir: str  = "./output"
    data_dir:   str  = "./data"

    # API settings (if needed)
    api_host:   str  = "localhost"
    api_port:   int  = 8000

    # Model settings
    model:      str  = "qwen2.5-coder:7b"
    temperature: float = 0.7
    max_tokens: int  = 2000


def load_config(path: str = str(CONFIG_FILE)) -> Config:
    \"\"\"Load config from JSON file, fallback to defaults.\"\"\"
    if Path(path).exists():
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            cfg = Config()
            for k, v in data.items():
                if hasattr(cfg, k):
                    setattr(cfg, k, v)
            return cfg
        except Exception as e:
            print(f"⚠ Config load error: {{e}} — using defaults")
    return Config()


def save_config(cfg: Config, path: str = str(CONFIG_FILE)) -> bool:
    \"\"\"Save config to JSON file.\"\"\"
    try:
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(cfg), f, indent=2)
        return True
    except Exception as e:
        print(f"❌ Config save error: {{e}}")
        return False


def get(key: str, default: Any = None) -> Any:
    \"\"\"Quick access to a config value.\"\"\"
    cfg = load_config()
    return getattr(cfg, key, default)


# Singleton instance
config = load_config()
""",

    "test": """\"\"\"
test_{name}.py — Unit tests
\"\"\"
import unittest
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))


class Test{name}(unittest.TestCase):

    def setUp(self):
        \"\"\"Setup before each test.\"\"\"
        pass

    def tearDown(self):
        \"\"\"Cleanup after each test.\"\"\"
        pass

    def test_basic(self):
        \"\"\"Basic sanity test.\"\"\"
        self.assertTrue(True)

    def test_example(self):
        \"\"\"Example test — replace with real tests.\"\"\"
        result = 2 + 2
        self.assertEqual(result, 4)

    def test_string_ops(self):
        text = "{name}"
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)


class Test{name}Edge(unittest.TestCase):

    def test_empty_input(self):
        \"\"\"Test with empty/None input.\"\"\"
        value = None
        self.assertIsNone(value)

    def test_boundary(self):
        \"\"\"Test boundary conditions.\"\"\"
        items = list(range(100))
        self.assertEqual(len(items), 100)
        self.assertEqual(items[0], 0)
        self.assertEqual(items[-1], 99)


if __name__ == "__main__":
    unittest.main(verbosity=2)
""",
}

PYTHON_TEMPLATED_ROLES = set(PYTHON_TEMPLATES.keys())

PYTHON_ROLE_KEYWORDS = {
    "main":   ["main", "app", "run", "start", "entry"],
    "script": ["script", "tool", "process", "worker"],
    "class":  ["model", "entity", "object", "data", "manager"],
    "api":    ["api", "server", "fastapi", "flask", "backend", "endpoint"],
    "cli":    ["cli", "command", "terminal", "argparse"],
    "util":   ["util", "helper", "common", "shared", "tools"],
    "config": ["config", "settings", "conf", "env"],
    "test":   ["test", "spec", "unittest", "pytest"],
}

# ─── Self-modification templates ──────────────────────────────────────────────
# These are used when the agent wants to add new capabilities to itself

SELF_MOD_PROMPT = """You are an AI agent that can modify its own Python source files to add new capabilities.

CURRENT AGENT FILES:
{file_list}

TASK: {task}

RULES:
- Read the relevant file first to understand the current code
- Make MINIMAL changes — only add what's needed
- Keep existing functionality intact
- Return the COMPLETE modified file as one ```python code block
- Add a comment # ADDED: <description> near new code
- Never remove existing features
- Test mentally that your changes won't break imports or syntax
"""

def get_python_role(name: str) -> str:
    nl = name.lower()
    for role, keywords in PYTHON_ROLE_KEYWORDS.items():
        if any(kw in nl for kw in keywords):
            return role
    if nl.startswith("test_"):   return "test"
    if nl.endswith("_config"):   return "config"
    if nl.endswith("_utils"):    return "util"
    return "script"

def get_python_template(name: str, role: str = None) -> str:
    if role is None:
        role = get_python_role(name)
    tpl = PYTHON_TEMPLATES.get(role, PYTHON_TEMPLATES["script"])
    return tpl.format(name=name)
