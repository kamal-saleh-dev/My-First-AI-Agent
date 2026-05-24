# llm_client.py — LLM communication layer
# Extracted from agent.py — safe_chat, get_response, model aliases, lazy imports
# NOTE: lazy import helpers (_import_cv2 etc.) live HERE only — do not copy to other files

import os
import time
import ollama
from openai import OpenAI
from logger import safe_print
from errors import LLMError, ModelNotFoundError

# ── Default local model ─────────────────────────────────────────────────────────
# agent.py's _switch_model() acquires _model_lock before writing.
# Any module reading DEFAULT_MODEL should access llm_client.DEFAULT_MODEL directly.
from threading import RLock as _RLock
import config as _cfg
_model_lock = _RLock()
DEFAULT_MODEL = _cfg.DEFAULT_MODEL

# ── Cloud / OpenRouter setup ─────────────────────────────────────────────────
USE_OPENROUTER     = os.getenv("CLAUDE_CODE_USE_OPENROUTER") == "1"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")

cloud_client = None
if USE_OPENROUTER and OPENROUTER_API_KEY:
    cloud_client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY,
    )

# ── Model aliases (validated against OpenRouter's actual model IDs) ──────────
# "local" is a special reserved alias — always maps to the configured local model.
# Resolved lazily so it reflects runtime DEFAULT_MODEL changes.
_LOCAL_ALIAS = "local"

MODEL_ALIASES = {
    # ── Free models (no credits needed) ─────────────────────────────────────
    "or_free":     "openrouter/free",                          # auto-picks best available free model
    "or_deepseek": "deepseek/deepseek-r1-0528-qwen3-8b:free", # DeepSeek R1 0528 Qwen3 8B free
    "or_deepseek2":"deepseek/deepseek-chat-v3-0324:free",     # DeepSeek V3 free
    "or_llama":    "meta-llama/llama-3.3-70b-instruct:free",  # Llama 3.3 70B free
    "or_mistral":  "mistralai/mistral-small-3.1-24b-instruct:free",  # Mistral free
    "or_gemma":    "google/gemma-3-27b-it:free",              # Gemma 3 27B free
    "or_qwen":     "qwen/qwen3-coder:free",                   # Qwen3 Coder free

    # ── Paid models (تحتاج credits على OpenRouter) ────────────────────────
    "gpt54":  "openai/gpt-5.5",
    "gpt4":   "openai/gpt-4o",
    "claude":      "anthropic/claude-sonnet-4-6",
    "opus":        "anthropic/claude-opus-4-6",
    "codex":       "openai/gpt-4o",
    "kimi":        "moonshotai/kimi-k2.6",
}

# ── Lazy imports — SINGLE source of truth. Import from here, not from agent.py ─
def _import_cv2():
    """Lazy import cv2 — returns None if not installed instead of crashing."""
    try:
        import cv2 as _cv2
        return _cv2
    except ImportError:
        safe_print("⚠️ opencv-python not installed — image processing unavailable. Run: pip install opencv-python")
        return None


def _import_pil():
    """Lazy import PIL — returns (None, None) if not installed."""
    try:
        from PIL import ImageEnhance, ImageFilter
        return ImageEnhance, ImageFilter
    except ImportError:
        safe_print("⚠️ Pillow not installed — image enhancement unavailable. Run: pip install pillow")
        return None, None


def _import_pytesseract():
    """Lazy import pytesseract — returns None if not installed."""
    try:
        import pytesseract as _tess
        return _tess
    except ImportError:
        safe_print("⚠️ pytesseract not installed — OCR unavailable. Run: pip install pytesseract")
        return None


# ── Known OpenRouter model prefixes for validation ───────────────────────────
_KNOWN_PROVIDERS = {
    "anthropic/", "openai/", "qwen/", "z-ai/", "minimax/",
    "moonshotai/", "meta-llama/", "google/", "mistralai/",
    "cohere/", "01-ai/", "deepseek/", "nousresearch/",
    "openrouter/", "nvidia/", "microsoft/", "arcee-ai/",
}

def _validate_model(model_name: str, is_cloud: bool) -> bool:
    """
    Validate model name before sending to OpenRouter.
    Returns True if valid, prints a warning and returns False if suspicious.
    """
    if not is_cloud:
        return True  # Ollama models — no validation needed
    # Cloud model must have a provider/ prefix
    if not any(model_name.startswith(p) for p in _KNOWN_PROVIDERS):
        safe_print(
            f"⚠️ Model '{model_name}' doesn't look like a valid OpenRouter model ID "
            f"(expected format: 'provider/model-name'). Call may fail."
        )
        return False
    return True


# ── Core LLM call ─────────────────────────────────────────────────────────────
def safe_chat(model=None, messages=None, stream=False,
              retries=_cfg.LLM_RETRIES, timeout=_cfg.LLM_TIMEOUT,
              max_tokens: int = None):
    """
    Unified LLM call — handles Ollama (local) and OpenRouter (cloud).
    Always returns a response object or _FallbackResp on total failure.
    Never raises — caller always gets something back.
    """
    if model is None:
        model = DEFAULT_MODEL
    if messages is None:
        messages = []

    # Resolve "local" alias → always uses the current DEFAULT_MODEL (local ollama)
    if model == _LOCAL_ALIAS:
        model = DEFAULT_MODEL

    full_model_name = MODEL_ALIASES.get(model, model)

    # Validate model name on first call (attempt 0 only — avoid spam)
    _will_use_cloud = (USE_OPENROUTER and cloud_client is not None
                       and full_model_name != DEFAULT_MODEL
                       and full_model_name != "llava")
    _validate_model(full_model_name, _will_use_cloud)

    last_err = None

    for attempt in range(retries + 1):
        try:
            use_cloud = (
                USE_OPENROUTER
                and cloud_client is not None
                and full_model_name != DEFAULT_MODEL
                and full_model_name != "llava"
            )

            if use_cloud:
                response = cloud_client.chat.completions.create(
                    model=full_model_name,
                    messages=messages,
                    stream=stream,
                    **({"max_tokens": max_tokens} if max_tokens else {}),
                    extra_headers={
                        "HTTP-Referer": "https://localhost",
                        "X-Title": "Kamal Game Agent",
                    },
                )
                if stream:
                    def _stream_gen():
                        for chunk in response:
                            if chunk.choices and chunk.choices[0].delta.content:
                                yield {"message": {"content": chunk.choices[0].delta.content}}
                    return _stream_gen()
                else:
                    class _CloudMsg:
                        content = response.choices[0].message.content
                    class _CloudResp:
                        message = _CloudMsg()
                    return _CloudResp()

            else:
                return ollama.chat(model=full_model_name, messages=messages, stream=stream)

        except Exception as e:
            last_err = e
            err_type = type(e).__name__
            if attempt < retries:
                wait = 2 * (attempt + 1)
                safe_print(f"⚠️ safe_chat attempt {attempt + 1} failed ({err_type}): {e} — retrying in {wait}s...")
                time.sleep(wait)
            else:
                safe_print(f"❌ safe_chat failed after {retries + 1} attempts: {err_type}: {e}")

    class _FallbackMsg:
        content = f"[ERROR: Model unavailable after {retries + 1} attempts — {last_err}]"
    class _FallbackResp:
        message = _FallbackMsg()
    return _FallbackResp()


def get_response(r) -> str:
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
        safe_print(f"⚠ get_response error: {e}")
        return ""
