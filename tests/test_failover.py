# tests/test_failover.py — v1.1 Local → Cloud Failover
#
# Verifies the opt-in, infrastructure-failure-only, free-cloud-only failover
# behavior added to llm_client.safe_chat(). Covers:
#   • OFF by default (no failover unless explicitly enabled)
#   • Infra failure with failover ON escalates to a FREE cloud model
#   • The failover ladder never touches a paid model
#   • Non-infra errors never trigger failover
#   • allow_failover=False suppresses failover even when enabled
#   • Failover is a safe no-op when OpenRouter is not configured

import pytest

import llm_client


# ── Fake OpenRouter cloud client ──────────────────────────────────────────

class _FakeCloudMsg:
    def __init__(self, content):
        self.content = content


class _FakeChoice:
    def __init__(self, content):
        self.message = _FakeCloudMsg(content)


class _FakeCompletion:
    def __init__(self, content):
        self.choices = [_FakeChoice(content)]


class _FakeCompletions:
    def __init__(self, content="CLOUD_OK", fail=False):
        self._content = content
        self._fail = fail
        self.calls = []            # records every model id requested

    def create(self, model=None, messages=None, stream=False, **kwargs):
        self.calls.append(model)
        if self._fail:
            raise RuntimeError(f"cloud model {model} unavailable")
        return _FakeCompletion(self._content)


class _FakeChat:
    def __init__(self, completions):
        self.completions = completions


class _FakeCloudClient:
    def __init__(self, content="CLOUD_OK", fail=False):
        self.chat = _FakeChat(_FakeCompletions(content=content, fail=fail))

    @property
    def calls(self):
        return self.chat.completions.calls


# ── Helpers ─────────────────────────────────────────────────────────

def _force_local_infra_failure(monkeypatch, exc=None):
    """Make the local Ollama backend raise an infrastructure-style error."""
    if exc is None:
        exc = ConnectionError("connection refused")

    def _boom(*args, **kwargs):
        raise exc

    monkeypatch.setattr(llm_client.ollama, "chat", _boom)


def _enable_cloud(monkeypatch, client):
    """Pretend OpenRouter is configured and reachable."""
    monkeypatch.setattr(llm_client, "USE_OPENROUTER", True)
    monkeypatch.setattr(llm_client, "cloud_client", client)


def _set_failover(monkeypatch, enabled, ladder=None):
    monkeypatch.setattr(llm_client._cfg, "LOCAL_CLOUD_FAILOVER", enabled)
    if ladder is not None:
        monkeypatch.setattr(llm_client._cfg, "FAILOVER_FREE_LADDER", ladder)


# ── Tests ──────────────────────────────────────────────────────────

def test_failover_off_by_default(monkeypatch):
    """With LOCAL_CLOUD_FAILOVER disabled, a local infra failure must NOT
    escalate to the cloud — the fallback response is returned instead."""
    client = _FakeCloudClient()
    _enable_cloud(monkeypatch, client)
    _set_failover(monkeypatch, enabled=False)
    _force_local_infra_failure(monkeypatch)

    r = llm_client.safe_chat(model="local", messages=[], retries=0)

    assert client.calls == []                       # cloud never touched
    assert "[ERROR" in llm_client.get_response(r)    # fallback response


def test_failover_on_infra_error_uses_free_cloud(monkeypatch):
    """Local infra failure + failover ON → response comes from a FREE cloud model."""
    client = _FakeCloudClient(content="CLOUD_OK")
    _enable_cloud(monkeypatch, client)
    _set_failover(monkeypatch, enabled=True)
    _force_local_infra_failure(monkeypatch)

    r = llm_client.safe_chat(model="local", messages=[], retries=0)

    assert llm_client.get_response(r) == "CLOUD_OK"
    assert len(client.calls) == 1
    assert llm_client._is_free_cloud_model(client.calls[0])


def test_failover_ladder_is_free_only(monkeypatch):
    """Even if paid aliases are injected into the ladder, failover must skip them
    and only ever request free models."""
    client = _FakeCloudClient(fail=True)   # all cloud attempts fail → full ladder walk
    _enable_cloud(monkeypatch, client)
    _set_failover(monkeypatch, enabled=True,
                  ladder=["or_qwen", "claude", "or_llama", "kimi", "or_free"])
    _force_local_infra_failure(monkeypatch)

    r = llm_client.safe_chat(model="local", messages=[], retries=0)

    # No paid model id was ever requested
    paid = {
        llm_client.MODEL_ALIASES["claude"],
        llm_client.MODEL_ALIASES["kimi"],
    }
    assert paid.isdisjoint(set(client.calls))
    # Every requested model was a free model
    assert client.calls                                   # at least one free attempt
    assert all(llm_client._is_free_cloud_model(m) for m in client.calls)
    # Falls back to an error response since every free model failed
    assert "[ERROR" in llm_client.get_response(r)


def test_non_infra_error_does_not_failover(monkeypatch):
    """A non-infrastructure error (e.g. a value error) must NOT trigger failover."""
    client = _FakeCloudClient()
    _enable_cloud(monkeypatch, client)
    _set_failover(monkeypatch, enabled=True)
    _force_local_infra_failure(monkeypatch, exc=ValueError("bad prompt formatting"))

    r = llm_client.safe_chat(model="local", messages=[], retries=0)

    assert client.calls == []
    assert "[ERROR" in llm_client.get_response(r)


def test_allow_failover_false_suppresses(monkeypatch):
    """allow_failover=False suppresses failover even when globally enabled
    (this is how self_mod keeps ownership of its own escalation ladder)."""
    client = _FakeCloudClient()
    _enable_cloud(monkeypatch, client)
    _set_failover(monkeypatch, enabled=True)
    _force_local_infra_failure(monkeypatch)

    r = llm_client.safe_chat(model="local", messages=[], retries=0,
                             allow_failover=False)

    assert client.calls == []
    assert "[ERROR" in llm_client.get_response(r)


def test_failover_requires_openrouter(monkeypatch):
    """With OpenRouter not configured, failover is a safe no-op."""
    monkeypatch.setattr(llm_client, "USE_OPENROUTER", False)
    monkeypatch.setattr(llm_client, "cloud_client", None)
    _set_failover(monkeypatch, enabled=True)
    _force_local_infra_failure(monkeypatch)

    r = llm_client.safe_chat(model="local", messages=[], retries=0)

    assert "[ERROR" in llm_client.get_response(r)
