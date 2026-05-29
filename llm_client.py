# llm_client.py — LLM communication layer
# safe_chat, get_response, model aliases, lazy imports, auto free-model fallback
# NOTE: lazy import helpers (_import_cv2 etc.) live HERE only — do not copy to other files

import os
import time
import ollama
from openai import OpenAI
from logger import safe_print
from errors import LLMError, ModelNotFoundError

# Default local model
from threading import RLock as _RLock
import config as _cfg
_model_lock = _RLock()
DEFAULT_MODEL = _cfg.DEFAULT_MODEL

# Cloud / OpenRouter setup
USE_OPENROUTER     = os.getenv("CLAUDE_CODE_USE_OPENROUTER") == "1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

cloud_client = None
if USE_OPENROUTER and OPENROUTER_API_KEY:
    cloud_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

# Model aliases — refreshed against OpenRouter's live free list
_LOCAL_ALIAS = "local"

MODEL_ALIASES = {
    # Free models (no credits needed)
    "or_free":     "qwen/qwen3-coder:free",
    "or_qwen":     "qwen/qwen3-coder:free",
    "or_gptoss":   "openai/gpt-oss-120b:free",
    "or_gptoss20": "openai/gpt-oss-20b:free",
    "or_glm":      "z-ai/glm-4.5-air:free",
    "or_llama":    "meta-llama/llama-3.3-70b-instruct:free",
    "or_deepseek": "deepseek/deepseek-chat-v3-0324:free",

    # Paid models (need credits on OpenRouter)
    "gpt54":  "openai/gpt-5.5",
    "gpt4":   "openai/gpt-4o",
    "claude": "anthropic/claude-sonnet-4-6",
    "opus":   "anthropic/claude-opus-4-6",
    "kimi":   "moonshotai/kimi-k2.6",
}

# Ordered fallback chain of FREE cloud models. When a model is rate-limited (429)
# or has no available endpoints (404), safe_chat() automatically tries the next.
FREE_FALLBACK_CHAIN = [
    "qwen/qwen3-coder:free",
    "openai/gpt-oss-120b:free",
    "z-ai/glm-4.5-air:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-chat-v3-0324:free",
    "openai/gpt-oss-20b:free",
]


# Lazy imports — SINGLE source of truth. Import from here, not from agent.py
def _import_cv2():
    """Lazy import cv2 — returns None if not installed instead of crashing."""
    try:
        import cv2 as _cv2
        return _cv2
    except ImportError:
        safe_print("opencv-python not installed — image processing unavailable. Run: pip install opencv-python")
        return None


def _import_pil():
    """Lazy import PIL — returns (None, None) if not installed."""
    try:
        from PIL import ImageEnhance, ImageFilter
        return ImageEnhance, ImageFilter
    except ImportError:
        safe_print("Pillow not installed — image enhancement unavailable. Run: pip install pillow")
        return None, None


def _import_pytesseract():
    """Lazy import pytesseract — returns None if not installed."""
    try:
        import pytesseract as _tess
        return _tess
    except ImportError:
        safe_print("pytesseract not installed — OCR unavailable. Run: pip install pytesseract")
        return None


# Known OpenRouter model prefixes
_KNOWN_PROVIDERS = {
    "anthropic/", "openai/", "qwen/", "z-ai/", "minimax/",
    "moonshotai/", "meta-llama/", "google/", "mistralai/",
    "cohere/", "01-ai/", "deepseek/", "nousresearch/",
    "openrouter/", "nvidia/", "microsoft/", "arcee-ai/",
    "liquid/", "venice/", "poolside/",
}


def _is_cloud_model(model_name):
    """
    A model is a cloud (OpenRouter) model if it carries a 'provider/' prefix.
    Local Ollama models (e.g. 'qwen2.5-coder:7b', 'llava') have no provider prefix.
    Do NOT compare against DEFAULT_MODEL — _switch_model() overwrites it with the
    active (possibly cloud) model.
    """
    return any(model_name.startswith(p) for p in _KNOWN_PROVIDERS)


# Cloud fallback helpers
def _build_kwargs(max_tokens):
    return {"max_tokens": max_tokens} if max_tokens else {}


def _wrap_cloud_response(response, stream):
    if stream:
        def _stream_gen():
            for chunk in response:
                if chunk.choices and chunk.choices[0].delta.content:
                    yield {"message": {"content": chunk.choices[0].delta.content}}
        return _stream_gen()
    class _CloudMsg:
        content = response.choices[0].message.content
    class _CloudResp:
        message = _CloudMsg()
    return _CloudResp()


def _retry_after_seconds(e, default):
    """Read the provider-suggested retry delay from a 429 error body (capped at 30s)."""
    try:
        body = getattr(e, "body", None) or {}
        meta = (body.get("error", {}) or {}).get("metadata", {}) or {}
        ra = meta.get("retry_after_seconds")
        if ra:
            return min(float(ra), 30.0)
    except Exception:
        pass
    return default


def _is_switchable_error(e):
    """429 (rate-limited) or 404 (no endpoints) -> worth trying another free model."""
    if type(e).__name__ in ("RateLimitError", "NotFoundError"):
        return True
    return getattr(e, "status_code", None) in (404, 429)


def _make_fallback(err):
    class _FallbackMsg:
        content = "[ERROR: Model unavailable — " + str(err) + "]"
    class _FallbackResp:
        message = _FallbackMsg()
    return _FallbackResp()


def _cloud_chat(primary_model, messages, stream, retries, max_tokens):
    # Try the requested model first, then the rest of the free chain.
    candidates = [primary_model]
    for m in FREE_FALLBACK_CHAIN:
        if m not in candidates:
            candidates.append(m)

    last_err = None
    for idx, cand in enumerate(candidates):
        for attempt in range(retries + 1):
            try:
                response = cloud_client.chat.completions.create(
                    model=cand,
                    messages=messages,
                    stream=stream,
                    **_build_kwargs(max_tokens),
                    extra_headers={
                        "HTTP-Referer": "https://localhost",
                        "X-Title": "Kamal Game Agent",
                    },
                )
                if idx > 0:
                    safe_print("↪️ Switched to free model: " + cand)
                return _wrap_cloud_response(response, stream)
            except Exception as e:
                last_err = e
                err_type = type(e).__name__
                if _is_switchable_error(e):
                    if attempt < retries:
                        wait = _retry_after_seconds(e, 2 * (attempt + 1))
                        safe_print("⚠️ " + cand + " busy (" + err_type + ") — retrying in " + str(round(wait)) + "s...")
                        time.sleep(wait)
                        continue
                    safe_print("⚠️ " + cand + " unavailable (" + err_type + ") — trying next free model...")
                    break  # move to next candidate
                # Non-switchable (e.g. 401 auth, 402 credits, bad request) — stop here.
                safe_print("❌ Cloud call failed (" + err_type + "): " + str(e))
                return _make_fallback(e)
    safe_print("❌ All free models unavailable after fallback. Last error: " + str(last_err))
    return _make_fallback(last_err)


def _local_chat(model_name, messages, stream, retries):
    last_err = None
    for attempt in range(retries + 1):
        try:
            return ollama.chat(model=model_name, messages=messages, stream=stream)
        except Exception as e:
            last_err = e
            err_type = type(e).__name__
            if attempt < retries:
                wait = 2 * (attempt + 1)
                safe_print("⚠️ safe_chat attempt " + str(attempt + 1) + " failed (" + err_type + "): " + str(e) + " — retrying in " + str(wait) + "s...")
                time.sleep(wait)
            else:
                safe_print("❌ safe_chat failed after " + str(retries + 1) + " attempts: " + err_type + ": " + str(e))
    return _make_fallback(last_err)


# Core LLM call
def safe_chat(model=None, messages=None, stream=False,
              retries=_cfg.LLM_RETRIES, timeout=_cfg.LLM_TIMEOUT,
              max_tokens=None):
    """
    Unified LLM call — handles Ollama (local) and OpenRouter (cloud).
    On cloud calls, automatically falls back through FREE_FALLBACK_CHAIN when a
    model is rate-limited (429) or unavailable (404).
    Never raises — caller always gets a response object or _FallbackResp.
    """
    if model is None:
        model = DEFAULT_MODEL
    if messages is None:
        messages = []

    if model == _LOCAL_ALIAS:
        model = DEFAULT_MODEL

    full_model_name = MODEL_ALIASES.get(model, model)

    use_cloud = (
        USE_OPENROUTER
        and cloud_client is not None
        and _is_cloud_model(full_model_name)
    )

    if use_cloud:
        return _cloud_chat(full_model_name, messages, stream, retries, max_tokens)
    return _local_chat(full_model_name, messages, stream, retries)


def get_response(r):
    """
    Unified response extractor for safe_chat() results.
    Handles: ollama dict, attribute-style objects, _FallbackResp.
    Always returns str — never raises KeyError / AttributeError.
    """
    try:
        if isinstance(r, dict):
            return r.get("message", {}).get("content", "") or ""
        msg = getattr(r, "message", None)
        if msg is not None:
            return getattr(msg, "content", "") or ""
        return str(r)
    except Exception as e:
        safe_print("get_response error: " + str(e))
        return ""
