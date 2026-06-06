# llm_client.py — LLM communication layer
# Extracted from agent.py — safe_chat, get_response, model aliases, lazy imports
# NOTE: lazy import helpers (_import_cv2 etc.) live HERE only — do not copy to other files

import time
import ollama
from logger import safe_print
from errors import LLMError, ModelNotFoundError

# ── Default local model ──────────────────────────────────────────────────────────
# agent.py's _switch_model() acquires _model_lock before writing.
# Any module reading DEFAULT_MODEL should access llm_client.DEFAULT_MODEL directly.
from threading import RLock as _RLock
import config as _cfg
_model_lock = _RLock()
DEFAULT_MODEL = _cfg.DEFAULT_MODEL

# ── Model aliases — local Ollama models only (free, offline) ─────────────────
# "local" is a special reserved alias — always maps to the configured local model.
# Resolved lazily so it reflects runtime DEFAULT_MODEL changes.
_LOCAL_ALIAS = "local"

MODEL_ALIASES = {
    "local_coder":   "qwen2.5-coder:7b",   # coding / generation (default)
    "local_reason":  "deepseek-r1:8b",      # reasoning / analysis / debugging
    "local_general": "qwen3.5:9b",          # general chat (Arabic) + vision
    "local_fast":    "qwen3.5:4b",          # quick / short tasks
    "local_vision":  "qwen3.5:9b",          # images (multimodal — same as general)
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


# ── Core LLM call — local Ollama only ──────────────────────────────────────
def safe_chat(model=None, messages=None, stream=False,
              retries=_cfg.LLM_RETRIES, timeout=_cfg.LLM_TIMEOUT,
              max_tokens: int = None, allow_failover: bool = True):
    """
    Unified LLM call — local Ollama only.
    Always returns a response object or _FallbackResp on total failure.
    Never raises — caller always gets something back.
    (timeout / max_tokens / allow_failover kept for backward compatibility —
     currently unused now that cloud failover has been removed — keeps callers
     like self_mod.py that pass allow_failover=False working.)
    """
    if model is None:
        model = DEFAULT_MODEL
    if messages is None:
        messages = []

    # Resolve "local" alias → always uses the current DEFAULT_MODEL (local ollama)
    if model == _LOCAL_ALIAS:
        model = DEFAULT_MODEL

    full_model_name = MODEL_ALIASES.get(model, model)

    last_err = None

    for attempt in range(retries + 1):
        try:
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
