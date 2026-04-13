# plugins/base_plugin.py — Abstract base for all domain plugins
# Every engine/framework plugin implements this interface.
# generation_engine.py calls plugins via the registry — no if/elif chains needed.

from abc import ABC, abstractmethod
from typing import Optional


class DomainPlugin(ABC):
    """
    Abstract base class for a generation domain (Unity, Unreal, React, etc.).

    Subclass this to add support for a new engine or framework without
    touching generation_engine.py or model_router.py.

    Minimal example:
        class MyFrameworkPlugin(DomainPlugin):
            name = "myframework"
            keywords = ["myframework", "mfw"]
            file_extension = ".mf"
            language_label = "MyFramework"
            launchable = False

            def system_prompt(self) -> str:
                return "You are a senior MyFramework developer..."

            def get_file_ext(self, script_name: str, role: str) -> str:
                return ".mf"
    """

    # ── Required class attributes ─────────────────────────────────────────────
    name:           str  = ""          # unique key, e.g. "unity"
    keywords:       list = []          # matched against user input
    language_label: str  = ""          # shown in prompts, e.g. "Unity C#"
    file_extension: str  = ".txt"      # default output extension
    launchable:     bool = False       # can this project be auto-launched?

    # ── Abstract interface ────────────────────────────────────────────────────

    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for LLM code generation."""

    @abstractmethod
    def get_file_ext(self, script_name: str, role: str) -> str:
        """Return the correct file extension for a generated script."""

    # ── Optional overrides ────────────────────────────────────────────────────

    def get_template(self, script_name: str, role: str) -> Optional[str]:
        """Return a skeleton template string, or None to go straight to LLM."""
        return None

    def validate(self, code: str) -> tuple[bool, str]:
        """
        Validate generated code.
        Returns (is_valid, code_or_error_message).
        """
        return True, code

    def post_process(self, code: str) -> str:
        """Apply engine-specific cleanup to generated code."""
        return code

    def planning_prompt(self, task: str) -> Optional[str]:
        """
        Return a custom planning prompt for this domain, or None to use
        the default game-architect prompt.
        """
        return None

    def post_generate(self, project_folder: str, project_name: str):
        """
        Called after all scripts are saved.
        Use for post-processing (e.g. creating .csproj, npm install, etc.).
        """

    def launch(self, project_folder: str):
        """Launch the generated project (open browser, start server, etc.)."""


# ── Plugin registry ───────────────────────────────────────────────────────────

_REGISTRY: dict[str, DomainPlugin] = {}


def register_plugin(plugin: DomainPlugin):
    """Register a plugin instance. Called at module import time."""
    _REGISTRY[plugin.name] = plugin


def get_plugin(name: str) -> Optional[DomainPlugin]:
    """Return the plugin for the given domain key, or None."""
    return _REGISTRY.get(name)


def all_plugins() -> dict[str, DomainPlugin]:
    """Return all registered plugins."""
    return dict(_REGISTRY)


def get_keywords() -> dict[str, list]:
    """Return {domain_name: [keywords]} for all registered plugins."""
    return {name: p.keywords for name, p in _REGISTRY.items()}
