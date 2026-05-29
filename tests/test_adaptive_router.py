"""Unit tests for the adaptive model router."""

import config as cfg
from adaptive_router import AdaptiveModelRouter

def test_escalation_zero_keeps_base():
    router = AdaptiveModelRouter(ladder=("or_qwen", "or_deepseek", "or_llama"))
    assert router.select("or_deepseek", escalation=0) == "or_deepseek"

def test_escalation_walks_ladder():
    router = AdaptiveModelRouter(ladder=("m1", "m2", "m3"))
    assert router.select("base", escalation=1) == "m1"
    assert router.select("base", escalation=2) == "m2"
    assert router.select("base", escalation=3) == "m3"

def test_escalation_clamps_to_last():
    router = AdaptiveModelRouter(ladder=("m1", "m2"))
    assert router.select("base", escalation=9) == "m2"

def test_empty_ladder_falls_back_to_base():
    router = AdaptiveModelRouter(ladder=())
    assert router.select("base", escalation=3) == "base"

def test_fallback_chain_dedupes():
    router = AdaptiveModelRouter(ladder=("base", "m2"))
    assert router.fallback_chain("base") == ["base", "m2"]

def test_default_ladder_comes_from_config():
    router = AdaptiveModelRouter()
    assert list(router.ladder) == list(cfg.ADAPTIVE_ESCALATION_LADDER)
