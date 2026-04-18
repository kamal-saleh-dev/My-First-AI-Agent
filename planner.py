# planner.py — Script planning, role normalization, fallback logic
import re
import hashlib
import json
import time
import os as _os

import config as _cfg
from errors import PlanningError, CacheError

# ── Planning cache (persistent JSON) ─────────────────────────────────────────

_CACHE_FILE      = _cfg.PLAN_CACHE_FILE
_planning_cache: dict = {}
_cache_loaded         = False   # ← lazy flag: load only on first access


def _cache_key(task: str) -> str:
    return hashlib.md5(task.lower().strip().encode()).hexdigest()[:12]


def _ensure_cache_loaded() -> None:
    """Load cache from disk exactly once — on first actual use, not at import."""
    global _planning_cache, _cache_loaded
    if _cache_loaded:
        return
    _cache_loaded = True
    try:
        if _os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                _planning_cache = json.load(f)
    except Exception:
        _planning_cache = {}


def _save_cache() -> None:
    """Persist cache to disk (atomic write). Never blocks planning on failure."""
    try:
        tmp = _CACHE_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_planning_cache, f, ensure_ascii=False)
        _os.replace(tmp, _CACHE_FILE)
    except Exception:
        pass


def get_cached_plan(task: str):
    """Return cached script pairs or None."""
    _ensure_cache_loaded()
    return _planning_cache.get(_cache_key(task))


def set_cached_plan(task: str, pairs: list) -> None:
    """Cache planning result (max PLAN_CACHE_MAX entries), then persist."""
    _ensure_cache_loaded()
    if len(_planning_cache) >= _cfg.PLAN_CACHE_MAX:
        for key in list(_planning_cache.keys())[: _cfg.PLAN_CACHE_EVICT]:
            del _planning_cache[key]
    _planning_cache[_cache_key(task)] = pairs
    _save_cache()


# ── Role normalization ────────────────────────────────────────────────────────

def apply_role_fixes(script_pairs: list, task: str) -> list:
    """
    Correct script roles based on name keywords.
    Ensures templates match the actual script purpose.
    """
    t = task.lower()
    is_racing = any(w in t for w in ["racing", "race", "car", "kart", "drift", "circuit", "lap"])

    NON_WAVE_MANAGER = [
        "inventory", "quest", "dialog", "save", "level", "audio", "input",
        "camera", "loot", "shop", "item", "board", "grid", "match", "race", "lap",
    ]
    NON_PICKUP_COLL = ["gem", "tile", "block", "card", "piece", "cell", "slot", "square"]
    NON_HEALTH      = [
        "result", "score", "timer", "race", "lap", "wave", "spawn", "manager",
        "controller", "ai", "opponent", "camera", "menu", "hud", "leaderboard",
    ]

    fixed = []
    for name, role in script_pairs:
        nl = name.lower()

        if "gamemanager" in nl or nl == "gamemanager":
            role = "game_manager"
        elif any(w in nl for w in ["checkpoint", "collectible", "coin", "pickup"]) \
                and not any(w in nl for w in NON_PICKUP_COLL):
            role = "collectible"
        elif any(w in nl for w in ["hud", "ui", "score", "timer", "results", "display", "board"]):
            role = "ui"
        elif any(w in nl for w in ["spawner", "spawn"]):
            role = "spawner"
        elif any(w in nl for w in ["car", "vehicle", "kart"]) and is_racing:
            role = "vehicle"
        elif any(w in nl for w in ["opponent", "ai", "bot"]) and is_racing:
            role = "opponent"
        elif any(w in nl for w in ["enemy", "zombie", "monster", "alien"]):
            role = "enemy"
        elif any(w in nl for w in ["powerup", "pickup", "boost", "shield"]):
            role = "powerup"
        elif any(w in nl for w in ["health", "hp", "life", "bar"]) \
                and not any(w in nl for w in NON_HEALTH):
            role = "health"
        elif any(w in nl for w in ["player", "ship", "survivor", "hero", "character"]) \
                and not is_racing:
            role = "player"
        elif role == "manager" and any(w in nl for w in NON_WAVE_MANAGER):
            role = "generic"

        fixed.append((name, role))
    return fixed


# ── Script pair normalization ─────────────────────────────────────────────────

def normalize_script_pairs(raw: str, engine: str = "unity") -> list:
    """
    Parse LLM planning response into (name, role) pairs.
    Handles comma-separated, newline-separated, numbered lists.
    """
    raw = re.sub(r"[\r]+", "\n", raw)
    raw = re.sub(r"\d+[.)]\s*", "", raw)
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
            name  = parts[0].strip()
            role  = parts[1].strip().lower().split()[0] if parts[1].strip() else "generic"
            if name and len(name) < 40 and name[0].isupper():
                pairs.append((name, role))
        elif item and len(item) < 40 and item[0].isupper():
            pairs.append((item, "generic"))
    return pairs


# ── Fallback plans ────────────────────────────────────────────────────────────

FALLBACK_PLANS: dict[str, list] = {
    "racing":       [("CarController","vehicle"),   ("OpponentAI","opponent"),
                     ("RaceManager","manager"),      ("RaceHUD","ui"),
                     ("CheckpointScript","collectible")],
    "kart":         [("KartController","vehicle"),  ("KartOpponent","opponent"),
                     ("RaceItem","powerup"),         ("LapManager","manager"),
                     ("KartHUD","ui")],
    "shooter":      [("ShipController","player"),   ("EnemySpawner","spawner"),
                     ("EnemyScript","enemy"),        ("PowerUpScript","powerup"),
                     ("GameManager","manager")],
    "runner":       [("LaneSwitcher","lane_switcher"),("ObstacleSpawner","spawner"),
                     ("BackgroundScroller","background"),("UIManager","ui"),
                     ("GameManager","manager")],
    "rpg":          [("PlayerController","player"),  ("EnemyScript","enemy"),
                     ("GameManager","manager"),       ("HealthBar","health"),
                     ("UIManager","ui")],
    "zombie":       [("SurvivorController","player"),("ZombieSpawner","spawner"),
                     ("ZombieScript","enemy"),        ("HealthBar","health"),
                     ("GameManager","manager")],
    "tower":        [("Tower","tower"),              ("PathFollower","path_follower"),
                     ("WaveManager","wave_manager"), ("GameManager","manager"),
                     ("UIManager","ui")],
    "platformer":   [("PlatformerPlayer","platformer_player"),("EnemyScript","enemy"),
                     ("CheckpointSystem","checkpoint_system"),("GameManager","manager"),
                     ("UIManager","ui")],
    "fighting":     [("PlayerController","player"),  ("ComboSystem","combo_system"),
                     ("EnemyScript","enemy"),         ("HealthBar","health"),
                     ("GameManager","manager")],
    "stealth":      [("StealthPlayer","stealth_player"),("GuardAI","guard_ai"),
                     ("GameManager","manager"),        ("UIManager","ui"),
                     ("InteractionSystem","interaction")],
    "horror":       [("PlayerController","player"),  ("MonsterAI","monster_ai"),
                     ("FlashlightBattery","flashlight_battery"),("GameManager","manager"),
                     ("UIManager","ui")],
    "roguelike":    [("PlayerController","player"),  ("RoguelikeRoom","roguelike_room"),
                     ("GameManager","manager"),       ("HealthBar","health"),
                     ("UIManager","ui")],
    "moba":         [("MobaHero","moba_hero"),       ("MobaTower","moba_tower"),
                     ("EnemyScript","enemy"),         ("HealthBar","health"),
                     ("UIManager","ui")],
    "battle_royale":[("PlayerController","player"),  ("ZoneShrink","zone_shrink"),
                     ("LootSpawner","loot_spawner"),  ("HealthBar","health"),
                     ("UIManager","ui")],
    "idle":         [("IdleManager","idle_manager"),  ("UIManager","ui"),
                     ("GameManager","manager")],
    "fishing":      [("FishingController","fishing"), ("GameManager","manager"),
                     ("UIManager","ui")],
    "cooking":      [("CookingSystem","cooking"),     ("GameManager","manager"),
                     ("UIManager","ui")],
    "flight":       [("FlightController","flight"),   ("EnemySpawner","spawner"),
                     ("GameManager","manager"),        ("UIManager","ui"),
                     ("HealthBar","health")],
    "default":      [("PlayerController","player"),   ("EnemySpawner","spawner"),
                     ("EnemyScript","enemy"),          ("GameManager","manager"),
                     ("UIManager","ui")],
}


def get_fallback_plan(task: str) -> list:
    t = task.lower()
    if any(w in t for w in ["kart", "mario kart"]):                  return FALLBACK_PLANS["kart"]
    if any(w in t for w in ["racing", "race", "car", "drift"]):      return FALLBACK_PLANS["racing"]
    if any(w in t for w in ["shooter", "space", "galaxy", "star",
                             "shmup"]):                               return FALLBACK_PLANS["shooter"]
    if any(w in t for w in ["endless runner", "subway", "temple run",
                             "lane"]):                                return FALLBACK_PLANS["runner"]
    if any(w in t for w in ["tower defense", "tower", "turret"]):     return FALLBACK_PLANS["tower"]
    if any(w in t for w in ["platformer", "platform", "jump",
                             "side scroll"]):                         return FALLBACK_PLANS["platformer"]
    if any(w in t for w in ["fighting", "beat em up", "brawler",
                             "hack and slash", "combat"]):            return FALLBACK_PLANS["fighting"]
    if any(w in t for w in ["stealth", "sneak", "guard"]):           return FALLBACK_PLANS["stealth"]
    if any(w in t for w in ["horror", "scary", "monster", "fear",
                             "survival horror"]):                     return FALLBACK_PLANS["horror"]
    if any(w in t for w in ["roguelike", "roguelite", "dungeon run",
                             "rogue"]):                               return FALLBACK_PLANS["roguelike"]
    if any(w in t for w in ["moba", "league", "dota", "hero"]):      return FALLBACK_PLANS["moba"]
    if any(w in t for w in ["battle royale", "pubg", "fortnite",
                             "br"]):                                  return FALLBACK_PLANS["battle_royale"]
    if any(w in t for w in ["idle", "clicker", "incremental"]):      return FALLBACK_PLANS["idle"]
    if any(w in t for w in ["fishing", "fish", "rod"]):              return FALLBACK_PLANS["fishing"]
    if any(w in t for w in ["cooking", "chef", "kitchen", "recipe"]):return FALLBACK_PLANS["cooking"]
    if any(w in t for w in ["flight", "airplane", "fly", "pilot",
                             "dogfight"]):                            return FALLBACK_PLANS["flight"]
    if any(w in t for w in ["rpg", "adventure", "quest", "dungeon",
                             "dungeon crawler"]):                     return FALLBACK_PLANS["rpg"]
    if any(w in t for w in ["zombie", "survival", "dead",
                             "apocalypse"]):                          return FALLBACK_PLANS["zombie"]
    if any(w in t for w in ["runner", "endless", "temple"]):         return FALLBACK_PLANS["runner"]
    return FALLBACK_PLANS["default"]


# ── Unreal-specific fallback plans ────────────────────────────────────────────

UNREAL_FALLBACK_PLANS: dict[str, list] = {
    "shooter":   [("ShooterCharacter","shooter_character"),("EnemyAI","enemy_ai"),
                  ("WaveSpawner","wave_spawner"),("WeaponSystem","weapon"),
                  ("MyGameMode","game_mode")],
    "rpg":       [("RPGCharacter","rpg_character"),("EnemyAI","enemy_ai"),
                  ("QuestManager","quest"),("InventorySystem","inventory"),
                  ("MyGameMode","game_mode")],
    "boss":      [("PlayerCharacter","shooter_character"),("BossCharacter","boss_fight"),
                  ("HealthComponent","health_component"),("WaveSpawner","wave_spawner"),
                  ("MyGameMode","game_mode")],
    "stealth":   [("StealthCharacter","stealth_system"),("NPC_AI","npc_ai"),
                  ("AIPerception","ai_perception"),("HealthComponent","health_component"),
                  ("MyGameMode","game_mode")],
    "vehicle":   [("VehicleCharacter","vehicle_component"),("WaveManager","wave_manager"),
                  ("HealthComponent","health_component"),("MyGameMode","game_mode"),
                  ("Leaderboard","leaderboard")],
    "survival":  [("PlayerCharacter","shooter_character"),("StaminaSystem","stamina_system"),
                  ("InventorySystem","inventory"),("WeatherSystem","weather_system"),
                  ("MyGameMode","game_mode")],
    "horror":    [("PlayerCharacter","shooter_character"),("EnemyAI","enemy_ai"),
                  ("AIPerception","ai_perception"),("StatusEffect","status_effect"),
                  ("MyGameMode","game_mode")],
    "default":   [("PlayerCharacter","shooter_character"),("EnemyAI","enemy_ai"),
                  ("HealthComponent","health_component"),("MyGameMode","game_mode"),
                  ("WaveSpawner","wave_spawner")],
}


def get_unreal_fallback(task: str) -> list:
    t = task.lower()
    if any(w in t for w in ["boss", "raid", "dungeon boss", "final boss"]): return UNREAL_FALLBACK_PLANS["boss"]
    if any(w in t for w in ["stealth", "sneak", "infiltrate"]):             return UNREAL_FALLBACK_PLANS["stealth"]
    if any(w in t for w in ["vehicle", "car", "tank", "drive", "racing"]): return UNREAL_FALLBACK_PLANS["vehicle"]
    if any(w in t for w in ["survival", "survive", "open world",
                             "crafting"]):                                   return UNREAL_FALLBACK_PLANS["survival"]
    if any(w in t for w in ["horror", "scary", "monster", "terror"]):       return UNREAL_FALLBACK_PLANS["horror"]
    if any(w in t for w in ["rpg", "adventure", "quest", "dungeon"]):       return UNREAL_FALLBACK_PLANS["rpg"]
    if any(w in t for w in ["shooter", "fps", "tps", "combat", "action"]): return UNREAL_FALLBACK_PLANS["shooter"]
    return UNREAL_FALLBACK_PLANS["default"]


# ── Main planning function ────────────────────────────────────────────────────

def plan_scripts(task: str, engine: str, safe_chat, get_response,
                 DEFAULT_MODEL: str, DOMAIN_REGISTRY: dict,
                 DOTNET_PLANNING_PROMPT: str,
                 DOTNET_FULLSTACK_PLANNING_PROMPT: str) -> list:
    """
    Plan which scripts/files to generate.
    Returns list of (name, role) pairs.
    Uses cache to avoid re-planning the same task.
    """
    cached = get_cached_plan(task)   # lazy-loads cache on first call
    if cached:
        return cached

    domain_cfg = DOMAIN_REGISTRY.get(engine, {})

    # Build planning prompt
    if domain_cfg.get("planning"):
        prompt = domain_cfg["planning"](task)
    else:
        engine_labels = {
            "unity":  ("Unity C#",       "MonoBehaviour", ".cs"),
            "unreal": ("Unreal C++",     "AActor/UObject", ".h/.cpp"),
            "godot":  ("Godot GDScript", "Node", ".gd"),
        }
        eng_lang = engine_labels.get(engine, ("C#", "Class", ".cs"))[0]
        prompt = (
            f"You are a {eng_lang} game architect. List exactly 4-5 scripts needed for this game.\n\n"
            f"GAME REQUEST: {task}\n"
            f"ENGINE: {engine.capitalize()} ({eng_lang})\n\n"
            "Format: ScriptName:role (comma-separated)\n"
            "Roles: player, vehicle, enemy, opponent, spawner, manager, ui, background,"
            " collectible, powerup, health, generic\n\n"
            "RULES:\n"
            "- ScriptName must NOT be same as game title\n"
            "- No duplicate roles\n"
            "- Match game genre exactly\n"
            "- Racing: vehicle+opponent, NOT player/enemy\n\n"
            "Examples:\n"
            "Space Shooter: ShipController:player, EnemySpawner:spawner, EnemyScript:enemy,"
            " PowerUpScript:powerup, GameManager:manager\n"
            "Racing: CarController:vehicle, OpponentAI:opponent, CheckpointScript:collectible,"
            " RaceManager:manager, RaceHUD:ui"
        )

    t_start = time.time()
    try:
        r   = safe_chat(model=DEFAULT_MODEL, messages=[{"role": "user", "content": prompt}])
        raw = get_response(r).strip()
    except Exception as e:
        print(f"⚠ Planning LLM error: {e} — using fallback", flush=True)
        return get_fallback_plan(task)

    print(f"⏱ Planning: {round(time.time() - t_start, 2)}s", flush=True)

    # Parse response
    if engine in ("dotnet", "react", "angular", "html", "sql", "python"):
        pairs: list = []
        for line in raw.split("\n"):
            line = line.strip()
            if ":" in line:
                name, role = line.split(":", 1)
                if name.strip():
                    pairs.append((name.strip(), role.strip().lower()))
        if not pairs:
            pairs = []   # web engines have no keyword fallback
    else:
        pairs = normalize_script_pairs(raw, engine)
        if len(pairs) < 2:
            if engine == "unreal":
                try:
                    pairs = get_unreal_fallback(task)
                except Exception:
                    pairs = [("PlayerCharacter", "generic"),
                             ("EnemyAI", "generic"), ("GameMode", "generic")]
            else:
                pairs = get_fallback_plan(task)
        pairs = apply_role_fixes(pairs, task)

    # Remove script named same as project
    project_key = re.sub(r"[^a-z0-9]", "", task.lower()[:20])
    pairs = [(n, r) for n, r in pairs
             if re.sub(r"[^a-z0-9]", "", n.lower()) != project_key]
    pairs = pairs[:6]

    # Unity: always ensure GameManager + HealthBar
    if engine == "unity":
        NON_ESSENTIAL = ["powerup", "background", "collectible", "generic"]

        has_gm = any("gamemanager" in n.lower() for n, _ in pairs)
        if not has_gm:
            drop_idx = next(
                (i for i, (_, r) in enumerate(pairs) if r in NON_ESSENTIAL), -1
            )
            if drop_idx >= 0:
                pairs.pop(drop_idx)
            pairs.append(("GameManager", "game_manager"))

        has_hb = any(
            "healthbar" in n.lower() or r == "health" for n, r in pairs
        )
        if not has_hb:
            drop_idx = next(
                (i for i, (_, r) in enumerate(pairs) if r in NON_ESSENTIAL), -1
            )
            if drop_idx >= 0:
                pairs.pop(drop_idx)
            pairs.append(("HealthBar", "health"))

        pairs = pairs[:8]

    set_cached_plan(task, pairs)
    return pairs
