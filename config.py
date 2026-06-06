# config.py — Single source of truth for all tunable values
# To change any behaviour: edit here only, never hunt through source files.

import os

# ══════════════════════════════════════════════════════════════════════════════
# LLM / MODEL
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_MODEL        = "qwen2.5-coder:7b"
LLM_RETRIES          = 2          # number of retry attempts on failure
LLM_TIMEOUT          = 120        # seconds per LLM call
INTENT_ROUTER_RETRIES = 1         # fewer retries for fast intent classification

# ── Context window limits (characters, not tokens — 1 token ≈ 4 chars) ───────
CTX_CLOUD   = 150_000   # large-context models
CTX_MID     = 32_000    # local 14b+ models
CTX_SMALL   = 8_000     # default local 7b model

# ══════════════════════════════════════════════════════════════════════════════
# GENERATION
# ══════════════════════════════════════════════════════════════════════════════

MAX_SCRIPTS_PER_PROJECT = 8       # cap on generated files per request
COMPILE_FIX_ATTEMPTS    = 3       # Unity C# compile-fix loop max retries
PYTHON_SANDBOX_TIMEOUT  = 5       # seconds for sandbox test run
PYTHON_RUN_TIMEOUT      = 15      # seconds for normal project run
PLACEHOLDER_REGEN       = True    # regenerate scripts that still contain placeholders

# Autonomous think/act/observe loop
AUTONOMOUS_MAX_STEPS     = 12
AUTONOMOUS_MAX_RETRIES   = 2
AUTONOMOUS_TOOL_TIMEOUT  = 30
AUTONOMOUS_REPEAT_LIMIT  = 3

# Multi-agent model preferences use aliases from llm_client.MODEL_ALIASES.
MULTI_AGENT_MODEL_DEEPSEEK   = "local_reason"    # Planner, Debugger
MULTI_AGENT_MODEL_QWEN_CODER = "local_coder"     # Coding, Testing
MULTI_AGENT_MODEL_LLAMA      = "local_general"   # Reviewer, Context

# ══════════════════════════════════════════════════════════════════════════════
# ADAPTIVE AUTONOMY  (Phase 3 — redesigned per architecture audit)
# ══════════════════════════════════════════════════════════════════════════════
# A single, lightweight reflect -> decide -> adapt control loop layered on top
# of the existing multi-agent system. Used ONLY by adaptive_runtime.py; /auto
# and /multi are unaffected. The audit merged the original Phase 3 (reflection),
# Phase 6 (repair) and Phase 8 (routing) ideas into this one thin layer and
# rescoped Phase 4 memory to "integrate the store we already have".
ADAPTIVE_MAX_STEP_RETRIES      = 2      # per-agent failed attempts before debug/stop
ADAPTIVE_MAX_ESCALATIONS       = 2      # model escalations per agent before plain retry
ADAPTIVE_MAX_DEBUG_DELEGATIONS = 1      # DebuggerAgent hand-offs per failing step
ADAPTIVE_STUCK_THRESHOLD       = 4      # identical (agent+error) failures => stuck => stop

# Memory integration (wires the existing memory_store RAG into the agent loop).
ADAPTIVE_MEMORY_ENABLED      = True     # recall + record around each agent step
ADAPTIVE_MEMORY_TOP_K        = 3        # past experiences injected per step
ADAPTIVE_MEMORY_ONLY_SUCCESS = False    # restrict recall to past successes only

# Model escalation ladder — aliases resolved via llm_client.MODEL_ALIASES.
# Ordered weaker -> stronger. All LOCAL aliases (no cloud).
ADAPTIVE_ESCALATION_LADDER   = ("local_coder", "local_reason", "local_general")

# ══════════════════════════════════════════════════════════════════════════════
# CONTEXT / HISTORY
# ══════════════════════════════════════════════════════════════════════════════

HISTORY_MAX_TOKENS      = 3000    # trim chat history above this token budget
HISTORY_MIN_KEEP        = 4       # always keep last N messages
HISTORY_MAX_SESSIONS    = 30      # max stored sessions in chat_sessions.json
FILE_CONTEXT_READ_CHARS = 1500    # max chars read from each attached text file

# ══════════════════════════════════════════════════════════════════════════════
# PLANNING CACHE
# ══════════════════════════════════════════════════════════════════════════════

PLAN_CACHE_MAX          = 300     # max entries in planning_cache.json
PLAN_CACHE_EVICT        = 50      # entries to evict when limit is reached

# ══════════════════════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════════════════════

LOG_FILE                = "agent_log.jsonl"
LOG_FLUSH_EVERY         = 20      # write to disk every N log entries
LOG_MAX_FILE_MB         = 5       # rotate log file above this size
LOG_KEEP_ROTATED        = 10      # number of rotated log files to keep
LOG_MIN_LEVEL           = "INFO"  # DEBUG | INFO | WARN | ERROR

# ══════════════════════════════════════════════════════════════════════════════
# PROCESS REGISTRY
# ══════════════════════════════════════════════════════════════════════════════

PROC_TERMINATE_TIMEOUT  = 3.0     # seconds to wait before force-killing

# ══════════════════════════════════════════════════════════════════════════════
# FILE PATHS
# ══════════════════════════════════════════════════════════════════════════════

BASE_DIR        = os.path.dirname(os.path.abspath(__file__))
MEMORY_FILE     = os.path.join(BASE_DIR, "agent_memory.txt")
CONTEXT_FILE    = os.path.join(BASE_DIR, "project_context.json")
HISTORY_FILE    = os.path.join(BASE_DIR, "chat_sessions.json")
METRICS_FILE    = os.path.join(BASE_DIR, "agent_metrics.json")
PLAN_CACHE_FILE = os.path.join(BASE_DIR, "planning_cache.json")

# ══════════════════════════════════════════════════════════════════════════════
# OVERRIDE FROM ENVIRONMENT (optional)
# Set env vars to override without editing this file:
#   AGENT_DEFAULT_MODEL=llama3:8b
#   AGENT_LLM_RETRIES=3
# ══════════════════════════════════════════════════════════════════════════════

def _env(key: str, default, cast=str):
    val = os.getenv(f"AGENT_{key.upper()}")
    return cast(val) if val is not None else default

def _env_bool(key: str, default: bool) -> bool:
    val = os.getenv(f"AGENT_{key.upper()}")
    if val is None:
        return default
    return val.strip().lower() not in ("0", "false", "no", "off", "")

def _env_list(key: str, default: list) -> list:
    val = os.getenv(f"AGENT_{key.upper()}")
    if val is None:
        return default
    return [s.strip() for s in val.split(",") if s.strip()]

DEFAULT_MODEL        = _env("DEFAULT_MODEL",        DEFAULT_MODEL)
LLM_RETRIES          = _env("LLM_RETRIES",          LLM_RETRIES,          int)
LLM_TIMEOUT          = _env("LLM_TIMEOUT",          LLM_TIMEOUT,          int)
COMPILE_FIX_ATTEMPTS = _env("COMPILE_FIX_ATTEMPTS", COMPILE_FIX_ATTEMPTS, int)
LOG_MIN_LEVEL        = _env("LOG_MIN_LEVEL",        LOG_MIN_LEVEL)
AUTONOMOUS_MAX_STEPS    = _env("AUTONOMOUS_MAX_STEPS",    AUTONOMOUS_MAX_STEPS,    int)
AUTONOMOUS_MAX_RETRIES  = _env("AUTONOMOUS_MAX_RETRIES",  AUTONOMOUS_MAX_RETRIES,  int)
AUTONOMOUS_TOOL_TIMEOUT = _env("AUTONOMOUS_TOOL_TIMEOUT", AUTONOMOUS_TOOL_TIMEOUT, int)
AUTONOMOUS_REPEAT_LIMIT = _env("AUTONOMOUS_REPEAT_LIMIT", AUTONOMOUS_REPEAT_LIMIT, int)
MULTI_AGENT_MODEL_DEEPSEEK   = _env("MULTI_AGENT_MODEL_DEEPSEEK",   MULTI_AGENT_MODEL_DEEPSEEK)
MULTI_AGENT_MODEL_QWEN_CODER = _env("MULTI_AGENT_MODEL_QWEN_CODER", MULTI_AGENT_MODEL_QWEN_CODER)
MULTI_AGENT_MODEL_LLAMA      = _env("MULTI_AGENT_MODEL_LLAMA",      MULTI_AGENT_MODEL_LLAMA)
ADAPTIVE_MAX_STEP_RETRIES      = _env("ADAPTIVE_MAX_STEP_RETRIES",      ADAPTIVE_MAX_STEP_RETRIES,      int)
ADAPTIVE_MAX_ESCALATIONS       = _env("ADAPTIVE_MAX_ESCALATIONS",       ADAPTIVE_MAX_ESCALATIONS,       int)
ADAPTIVE_MAX_DEBUG_DELEGATIONS = _env("ADAPTIVE_MAX_DEBUG_DELEGATIONS", ADAPTIVE_MAX_DEBUG_DELEGATIONS, int)
ADAPTIVE_STUCK_THRESHOLD       = _env("ADAPTIVE_STUCK_THRESHOLD",       ADAPTIVE_STUCK_THRESHOLD,       int)
ADAPTIVE_MEMORY_TOP_K          = _env("ADAPTIVE_MEMORY_TOP_K",          ADAPTIVE_MEMORY_TOP_K,          int)
ADAPTIVE_MEMORY_ENABLED        = _env_bool("ADAPTIVE_MEMORY_ENABLED",      ADAPTIVE_MEMORY_ENABLED)
ADAPTIVE_MEMORY_ONLY_SUCCESS   = _env_bool("ADAPTIVE_MEMORY_ONLY_SUCCESS", ADAPTIVE_MEMORY_ONLY_SUCCESS)

# ── Testing / Debug ──────────────────────────────────────────────────────────
# Set AGENT_SCRIPT_DELAY=5 to slow generation for manual checkpoint testing
SCRIPT_DELAY: int = _env("SCRIPT_DELAY", 0, int)
