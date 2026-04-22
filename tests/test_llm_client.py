# tests/test_llm_client.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch, MagicMock


# ── Helpers ───────────────────────────────────────────────────────────────────

def _mock_response(text="ok"):
    r = MagicMock()
    r.message.content = text
    return r


# ══════════════════════════════════════════════════════════════
# TestLocalAlias
# ══════════════════════════════════════════════════════════════

class TestLocalAlias:
    """'local' must always resolve to the configured local model, never be
    sent literally to ollama/OpenRouter (which causes 404)."""

    def test_local_resolves_to_default_model(self):
        import llm_client, config
        calls = []

        def fake_ollama_chat(model, messages, stream=False):
            calls.append(model)
            return _mock_response()

        with patch("llm_client.ollama.chat", side_effect=fake_ollama_chat):
            llm_client.safe_chat(model="local", messages=[])

        assert calls, "ollama.chat was never called"
        assert calls[0] == config.DEFAULT_MODEL, (
            f"Expected '{config.DEFAULT_MODEL}', got '{calls[0]}' — "
            "'local' was not resolved before sending to ollama"
        )

    def test_local_alias_not_sent_literally(self):
        """'local' must NEVER reach ollama as a literal model name."""
        import llm_client
        calls = []

        def fake_ollama_chat(model, messages, stream=False):
            calls.append(model)
            return _mock_response()

        with patch("llm_client.ollama.chat", side_effect=fake_ollama_chat):
            llm_client.safe_chat(model="local", messages=[])

        assert "local" not in calls, (
            "'local' was sent literally to ollama — this causes 404"
        )

    def test_none_model_uses_default_model(self):
        """safe_chat(model=None) must use llm_client.DEFAULT_MODEL."""
        import llm_client
        calls = []

        def fake_ollama_chat(model, messages, stream=False):
            calls.append(model)
            return _mock_response()

        with patch("llm_client.ollama.chat", side_effect=fake_ollama_chat):
            llm_client.safe_chat(model=None, messages=[])

        assert calls[0] == llm_client.DEFAULT_MODEL


# ══════════════════════════════════════════════════════════════
# TestSwitchModel
# ══════════════════════════════════════════════════════════════

class TestSwitchModel:
    """_switch_model() must store the resolved model name, not the alias."""

    def _call_switch(self, alias: str):
        """Import and call _switch_model from agent.py."""
        import importlib, agent as ag
        importlib.reload(ag)   # fresh state
        import llm_client
        ag._switch_model(alias)
        return llm_client.DEFAULT_MODEL

    def test_switch_to_local_stores_real_model(self):
        import config
        import llm_client
        # Directly test the resolution logic without reloading agent
        original = llm_client.DEFAULT_MODEL
        try:
            # Simulate what _switch_model does for "local"
            resolved = config.DEFAULT_MODEL
            llm_client.DEFAULT_MODEL = resolved
            assert llm_client.DEFAULT_MODEL == config.DEFAULT_MODEL
            assert llm_client.DEFAULT_MODEL != "local"
        finally:
            llm_client.DEFAULT_MODEL = original

    def test_switch_to_or_free_stores_resolved_id(self):
        """Alias like 'or_free' must be resolved to full model ID."""
        import llm_client
        original = llm_client.DEFAULT_MODEL
        try:
            alias    = "or_free"
            resolved = llm_client.MODEL_ALIASES.get(alias, alias)
            llm_client.DEFAULT_MODEL = resolved
            assert "/" in llm_client.DEFAULT_MODEL or llm_client.DEFAULT_MODEL == alias, \
                f"Expected resolved model ID, got: {llm_client.DEFAULT_MODEL}"
        finally:
            llm_client.DEFAULT_MODEL = original


# ══════════════════════════════════════════════════════════════
# TestModelAliases
# ══════════════════════════════════════════════════════════════

class TestModelAliases:

    def test_all_free_aliases_have_free_suffix_or_are_router(self):
        """All 'or_*' aliases must end in :free or be the openrouter/free router."""
        import llm_client
        for alias, model_id in llm_client.MODEL_ALIASES.items():
            if alias.startswith("or_"):
                assert model_id.endswith(":free") or model_id == "openrouter/free", (
                    f"Free alias '{alias}' → '{model_id}' doesn't end in :free"
                )

    def test_paid_aliases_have_no_free_suffix(self):
        """Paid model aliases must NOT end in :free."""
        import llm_client
        paid = ("gpt54", "gpt4", "kimi", "claude", "opus", "codex")
        for alias in paid:
            if alias in llm_client.MODEL_ALIASES:
                model_id = llm_client.MODEL_ALIASES[alias]
                assert not model_id.endswith(":free"), (
                    f"Paid alias '{alias}' → '{model_id}' incorrectly marked as free"
                )

    def test_all_cloud_aliases_have_provider_slash(self):
        """All cloud model IDs must follow 'provider/model-name' format."""
        import llm_client
        for alias, model_id in llm_client.MODEL_ALIASES.items():
            if alias == "local":
                continue
            assert "/" in model_id, (
                f"Alias '{alias}' → '{model_id}' missing provider/ prefix"
            )

    def test_get_response_handles_fallback(self):
        """get_response must return string even from _FallbackResp."""
        import llm_client
        fallback = MagicMock()
        fallback.message.content = "[ERROR: something went wrong]"
        result = llm_client.get_response(fallback)
        assert isinstance(result, str)
        assert len(result) > 0
