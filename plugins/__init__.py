# plugins/__init__.py — Auto-discover and register all domain plugins
# Add a new plugin: create plugins/my_plugin.py and import it here.

from .base_plugin import register_plugin, get_plugin, all_plugins, get_keywords

# ── Built-in domain plugins ───────────────────────────────────────────────────
# Each module calls register_plugin() at import time.

from . import unity_plugin    # noqa: F401
from . import unreal_plugin   # noqa: F401
from . import web_plugin      # noqa: F401
from . import python_plugin   # noqa: F401

__all__ = ["register_plugin", "get_plugin", "all_plugins", "get_keywords"]
