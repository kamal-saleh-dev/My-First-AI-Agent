# tests/test_planner.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch, MagicMock
from planner import (
    normalize_script_pairs, apply_role_fixes,
    get_fallback_plan, get_unreal_fallback,
    get_cached_plan, set_cached_plan, _cache_key,
)


# ── normalize_script_pairs ────────────────────────────────────────────────────

class TestNormalizeScriptPairs:
    def test_comma_separated(self):
        raw = "PlayerController:player, EnemyScript:enemy, GameManager:manager"
        pairs = normalize_script_pairs(raw)
        assert ("PlayerController", "player") in pairs
        assert ("EnemyScript", "enemy") in pairs
        assert ("GameManager", "manager") in pairs

    def test_newline_separated(self):
        raw = "PlayerController:player\nEnemyScript:enemy"
        pairs = normalize_script_pairs(raw)
        assert len(pairs) == 2

    def test_numbered_list_stripped(self):
        raw = "1. PlayerController:player\n2. EnemyScript:enemy"
        pairs = normalize_script_pairs(raw)
        assert ("PlayerController", "player") in pairs

    def test_empty_input(self):
        assert normalize_script_pairs("") == []

    def test_no_role_defaults_to_generic(self):
        raw = "PlayerController"
        pairs = normalize_script_pairs(raw)
        assert pairs == [("PlayerController", "generic")]

    def test_lowercase_names_excluded(self):
        raw = "playercontroller:player"
        pairs = normalize_script_pairs(raw)
        assert pairs == []   # names must start with uppercase


# ── apply_role_fixes ──────────────────────────────────────────────────────────

class TestApplyRoleFixes:
    def test_gamemanager_always_game_manager(self):
        pairs = [("GameManager", "generic")]
        result = apply_role_fixes(pairs, "space shooter")
        assert result[0][1] == "game_manager"

    def test_hud_becomes_ui(self):
        pairs = [("HUD", "generic")]
        result = apply_role_fixes(pairs, "platformer")
        assert result[0][1] == "ui"

    def test_spawner_role(self):
        pairs = [("EnemySpawner", "generic")]
        result = apply_role_fixes(pairs, "shooter")
        assert result[0][1] == "spawner"

    def test_vehicle_in_racing(self):
        pairs = [("CarController", "generic")]
        result = apply_role_fixes(pairs, "racing game with cars")
        assert result[0][1] == "vehicle"

    def test_non_wave_manager_downgraded(self):
        pairs = [("InventoryManager", "manager")]
        result = apply_role_fixes(pairs, "rpg game")
        assert result[0][1] == "generic"

    def test_enemy_role(self):
        pairs = [("ZombieScript", "generic")]
        result = apply_role_fixes(pairs, "zombie survival")
        assert result[0][1] == "enemy"


# ── get_fallback_plan ─────────────────────────────────────────────────────────

class TestGetFallbackPlan:
    def test_racing_returns_vehicle(self):
        plan = get_fallback_plan("make a racing game")
        roles = [r for _, r in plan]
        assert "vehicle" in roles

    def test_shooter_returns_player(self):
        plan = get_fallback_plan("space shooter game")
        roles = [r for _, r in plan]
        assert "player" in roles

    def test_tower_defense(self):
        plan = get_fallback_plan("tower defense game")
        roles = [r for _, r in plan]
        assert "wave_manager" in roles

    def test_default_fallback_has_five_scripts(self):
        plan = get_fallback_plan("some random game")
        assert len(plan) == 5

    def test_all_pairs_are_tuples(self):
        plan = get_fallback_plan("platformer")
        assert all(isinstance(p, tuple) and len(p) == 2 for p in plan)


# ── Planning cache ────────────────────────────────────────────────────────────

class TestPlanningCache:
    def test_cache_key_deterministic(self):
        assert _cache_key("hello") == _cache_key("hello")
        assert _cache_key("hello") == _cache_key("HELLO")  # case-insensitive

    def test_set_and_get(self):
        task  = "__test_cache_entry_unique__"
        pairs = [("TestScript", "player")]
        set_cached_plan(task, pairs)
        assert get_cached_plan(task) == pairs

    def test_missing_key_returns_none(self):
        assert get_cached_plan("__definitely_not_cached__") is None
