# errors.py — Project-specific exception hierarchy
# Replace bare `except Exception` with these for precise error handling.
#
# Usage:
#   from errors import GenerationError, PlanningError, ValidationError
#   raise GenerationError("Script save failed", engine="unity", script="PlayerController")


class AgentError(Exception):
    """Base class for all agent errors. Carry structured context."""

    def __init__(self, message: str, **context):
        super().__init__(message)
        self.context = context      # arbitrary key/value pairs for logging

    def __str__(self):
        base = super().__str__()
        if self.context:
            ctx = ", ".join(f"{k}={v!r}" for k, v in self.context.items())
            return f"{base} [{ctx}]"
        return base


# ── LLM / network ─────────────────────────────────────────────────────────────

class LLMError(AgentError):
    """Raised when the LLM call fails after all retries."""

class ModelNotFoundError(LLMError):
    """Raised when a model alias or name is not recognised by the backend."""

class StreamError(LLMError):
    """Raised when streaming output from the LLM breaks mid-response."""


# ── Planning ──────────────────────────────────────────────────────────────────

class PlanningError(AgentError):
    """Raised when the planner cannot produce a valid script plan."""

class CacheError(PlanningError):
    """Raised when the planning cache cannot be read or written."""


# ── Generation ────────────────────────────────────────────────────────────────

class GenerationError(AgentError):
    """Raised when code generation fails for a script."""

class TemplateError(GenerationError):
    """Raised when a template cannot be loaded or rendered."""

class CompileError(GenerationError):
    """Raised when generated code fails to compile after max fix attempts."""


# ── Validation ────────────────────────────────────────────────────────────────

class ValidationError(AgentError):
    """Raised when generated code fails syntax or structural validation."""

class UnsafeCodeError(ValidationError):
    """Raised when generated code is rejected for safety reasons."""


# ── File handling ─────────────────────────────────────────────────────────────

class FileHandlerError(AgentError):
    """Raised when a file attachment cannot be processed."""

class UnsupportedFileTypeError(FileHandlerError):
    """Raised when a file type has no handler."""

class OCRError(FileHandlerError):
    """Raised when OCR extraction fails."""


# ── Session / persistence ─────────────────────────────────────────────────────

class SessionError(AgentError):
    """Raised when session save or load fails."""

class ContextError(AgentError):
    """Raised when project context cannot be read or written."""


# ── Self-modification ─────────────────────────────────────────────────────────

class SelfModError(AgentError):
    """Raised when self-modification is blocked or fails."""

class ProtectedFileError(SelfModError):
    """Raised when self-mod targets a protected core module."""


# ── Startup ───────────────────────────────────────────────────────────────────

class DependencyMissingError(AgentError):
    """Raised at startup when a required dependency is not installed."""
