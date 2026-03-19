# planner.py — Script planning, role normalization, fallback logic
import re, hashlib, json, time

# ─── Planning cache ────────────────────────────────────────────
_planning_cache: dict = {}

def _cache_key(task: str) -> str:
    return hashlib.md5(task.lower().strip().encode()).hexdigest()[:12]

def get_cached_plan(task: str):
    """Return cached script pairs or None."""
    return _planning_cache.get(_cache_key(task))

def set_cached_plan(task: str, pairs: list):
    """Cache planning result — max 300 entries (evict oldest)."""
    if len(_planning_cache) >= 300:
        # Remove oldest 50 entries
        for key in list(_planning_cache.keys())[:50]:
            del _planning_cache[key]
    _planning_cache[_cache_key(task)] = pairs


# ─── Role normalization ────────────────────────────────────────
def apply_role_fixes(script_pairs: list, task: str) -> list:
    """
    Correct script roles based on name keywords.
    Ensures templates match the actual script purpose.
    """
    is_racing = any(w in task.lower() for w in
                    ["racing","race","car","kart","drift","circuit","lap"])
    NON_WAVE_MANAGER = ["inventory","quest","dialog","save","level","audio","input",
                        "camera","loot","shop","item","board","grid","match","race","lap"]
    NON_PICKUP_COLL  = ["gem","tile","block","card","piece","cell","slot","square"]
    NON_HEALTH       = ["result","score","timer","race","lap","wave","spawn","manager",
                        "controller","ai","opponent","camera","menu","hud","leaderboard"]

    fixed = []
    for name, role in script_pairs:
        nl = name.lower()

        # ── Hard overrides ──────────────────────
        if "gamemanager" in nl or nl == "gamemanager":
            role = "manager"
        elif any(w in nl for w in ["checkpoint","collectible","coin","pickup"])              and not any(w in nl for w in NON_PICKUP_COLL):
            role = "collectible"
        elif any(w in nl for w in ["hud","ui","score","timer","results","display","board"]):
            role = "ui"
        elif any(w in nl for w in ["spawner","spawn"]):
            role = "spawner"
        elif any(w in nl for w in ["car","vehicle","kart"]) and is_racing:
            role = "vehicle"
        elif any(w in nl for w in ["opponent","ai","bot"]) and is_racing:
            role = "opponent"
        elif any(w in nl for w in ["enemy","zombie","monster","alien"]):
            role = "enemy"
        elif any(w in nl for w in ["powerup","pickup","boost","shield"]):
            role = "powerup"
        elif any(w in nl for w in ["health","hp","life","bar"])              and not any(w in nl for w in NON_HEALTH):
            role = "health"
        elif any(w in nl for w in ["player","ship","survivor","hero","character"])              and not is_racing:
            role = "player"
        # Downgrade generic manager if not wave-based
        elif role == "manager"              and any(w in nl for w in NON_WAVE_MANAGER):
            role = "generic"

        fixed.append((name, role))
    return fixed


# ─── Script pair normalization ─────────────────────────────────
def normalize_script_pairs(raw: str, engine: str = "unity") -> list:
    """
    Parse LLM planning response into (name, role) pairs.
    Handles comma-separated, newline-separated, numbered lists.
    """
    raw = re.sub(r"[\r]+", "\n", raw)
    raw = re.sub(r"\d+[\.)\]]\s*", "", raw)
    raw = re.sub(r"^[-*•]\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"[\n\r]+", ",", raw)
    raw = re.sub(r",{2,}", ",", raw)

    pairs = []
    for item in raw.split(","):
        item = item.strip().strip('"').strip("'")
        if not item:
            continue
        if ":" in item:
            parts = item.split(":", 1)
            name = parts[0].strip()
            role = parts[1].strip().lower().split()[0] if parts[1].strip() else "generic"
            if name and len(name) < 40 and name[0].isupper():
                pairs.append((name, role))
        elif item and len(item) < 40 and item[0].isupper():
            pairs.append((item, "generic"))
    return pairs


# ─── Fallback plans ────────────────────────────────────────────
FALLBACK_PLANS = {
    "racing":    [("CarController","vehicle"),("OpponentAI","opponent"),
                  ("RaceManager","manager"),("RaceHUD","ui"),("CheckpointScript","collectible")],
    "shooter":   [("ShipController","player"),("EnemySpawner","spawner"),
                  ("EnemyScript","enemy"),("PowerUpScript","powerup"),("GameManager","manager")],
    "runner":    [("RunnerController","player"),("ObstacleSpawner","spawner"),
                  ("BackgroundScroller","background"),("UIManager","ui"),("HealthBar","health")],
    "rpg":       [("PlayerController","player"),("EnemyScript","enemy"),
                  ("GameManager","manager"),("HealthBar","health"),("UIManager","ui")],
    "zombie":    [("SurvivorController","player"),("ZombieSpawner","spawner"),
                  ("ZombieScript","enemy"),("HealthBar","health"),("GameManager","manager")],
    "default":   [("PlayerController","player"),("EnemySpawner","spawner"),
                  ("EnemyScript","enemy"),("GameManager","manager"),("UIManager","ui")],
}

def get_fallback_plan(task: str) -> list:
    t = task.lower()
    if any(w in t for w in ["racing","race","car","kart"]):     return FALLBACK_PLANS["racing"]
    if any(w in t for w in ["shooter","space","galaxy","star"]): return FALLBACK_PLANS["shooter"]
    if any(w in t for w in ["runner","endless","temple"]):       return FALLBACK_PLANS["runner"]
    if any(w in t for w in ["rpg","adventure","quest","dungeon"]):return FALLBACK_PLANS["rpg"]
    if any(w in t for w in ["zombie","survival","dead"]):         return FALLBACK_PLANS["zombie"]
    return FALLBACK_PLANS["default"]


# ─── Main planning function ────────────────────────────────────
def plan_scripts(task: str, engine: str, safe_chat, get_response,
                 DEFAULT_MODEL: str, DOMAIN_REGISTRY: dict,
                 DOTNET_PLANNING_PROMPT: str,
                 DOTNET_FULLSTACK_PLANNING_PROMPT: str) -> list:
    """
    Plan which scripts/files to generate.
    Returns list of (name, role) pairs.
    Uses cache to avoid re-planning same task.
    """
    # Cache hit
    cached = get_cached_plan(task)
    if cached:
        return cached

    domain_cfg = DOMAIN_REGISTRY.get(engine, {})

    # Build planning prompt
    if domain_cfg.get("planning"):
        prompt = domain_cfg["planning"](task)
    else:
        # Game planning prompt
        engine_labels = {
            "unity":  ("Unity C#",        "MonoBehaviour", ".cs"),
            "unreal": ("Unreal C++",      "AActor/UObject", ".h/.cpp"),
            "godot":  ("Godot GDScript",  "Node",           ".gd"),
        }
        eng_lang = engine_labels.get(engine, ("C#","Class",".cs"))[0]
        prompt = f"""You are a {eng_lang} game architect. List exactly 4-5 scripts needed for this game.

GAME REQUEST: {task}
ENGINE: {engine.capitalize()} ({eng_lang})

Format: ScriptName:role (comma-separated)
Roles: player, vehicle, enemy, opponent, spawner, manager, ui, background, collectible, powerup, health, generic

RULES:
- ScriptName must NOT be same as game title
- No duplicate roles
- Match game genre exactly
- Racing: vehicle+opponent, NOT player/enemy

Examples:
Space Shooter: ShipController:player, EnemySpawner:spawner, EnemyScript:enemy, PowerUpScript:powerup, GameManager:manager
Racing: CarController:vehicle, OpponentAI:opponent, CheckpointScript:collectible, RaceManager:manager, RaceHUD:ui"""

    t_start = time.time()
    try:
        r = safe_chat(model=DEFAULT_MODEL, messages=[{"role":"user","content":prompt}])
        raw = get_response(r).strip()
    except Exception as e:
        print(f"⚠ Planning LLM error: {e} — using fallback", flush=True)
        return get_fallback_plan(task)

    planning_time = round(time.time() - t_start, 2)
    print(f"⏱ Planning: {planning_time}s", flush=True)

    # Parse
    if engine in ("dotnet","react","angular","html","sql","python"):
        # newline-separated
        pairs = []
        for line in raw.split("\n"):
            line = line.strip()
            if ":" in line:
                name, role = line.split(":",1)
                if name.strip():
                    pairs.append((name.strip(), role.strip().lower()))
        if not pairs:
            pairs = get_fallback_plan(task) if engine == "unity" else []
    else:
        pairs = normalize_script_pairs(raw, engine)
        if len(pairs) < 2:
            pairs = get_fallback_plan(task)
        # Apply role corrections for game engines
        pairs = apply_role_fixes(pairs, task)

    # Remove script named same as project
    project_key = re.sub(r"[^a-z0-9]", "", task.lower()[:20])
    pairs = [(n,r) for n,r in pairs if re.sub(r"[^a-z0-9]","",n.lower()) != project_key]
    pairs = pairs[:6]

    set_cached_plan(task, pairs)
    return pairs
