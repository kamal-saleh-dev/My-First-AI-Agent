# plugins/__init__.py — Auto-discover and register all domain plugins
# Add a new plugin: create plugins/my_plugin.py and import it here.

from plugins.base_plugin import register_plugin, get_plugin, all_plugins, get_keywords

# ── Built-in domain plugins ───────────────────────────────────────────────────
# Each module calls register_plugin() at import time.

from plugins import unity_plugin    # noqa: F401
from plugins import unreal_plugin   # noqa: F401
from plugins import web_plugin      # noqa: F401
from plugins import python_plugin   # noqa: F401

__all__ = ["register_plugin", "get_plugin", "all_plugins", "get_keywords"]
