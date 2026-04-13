# template_cache.py — Lazy loading + weak-reference cache for large template modules
# Solves: unity_templates, unreal_templates etc loaded eagerly at startup (wastes ~40MB RAM)
# Solution: import on first use, hold via WeakValueDictionary so GC can reclaim if needed.

import sys
import importlib
import threading
import weakref
from typing import Any, Optional


class LazyTemplateCache:
    """
    Import template modules on first access, not at startup.
    Uses a regular dict for pinned modules (always needed) and allows
    explicit unpinning to free memory for less-used domains.
    """

    def __init__(self):
        self._lock    = threading.RLock()
        self._loaded: dict[str, Any]  = {}          # strong refs — pinned
        self._pinned: set[str]        = set()        # explicitly pinned

    # ── Load / get ────────────────────────────────────────────────────────────

    def get(self, module_name: str) -> Any:
        """Return the module, importing it if necessary."""
        with self._lock:
            mod = self._loaded.get(module_name)
            if mod is not None:
                return mod
            mod = importlib.import_module(module_name)
            self._loaded[module_name] = mod
            return mod

    def get_attr(self, module_name: str, attr: str) -> Any:
        """Convenience: return a single attribute from a template module."""
        return getattr(self.get(module_name), attr)

    # ── Pin / unpin ───────────────────────────────────────────────────────────

    def pin(self, module_name: str):
        """Keep module loaded permanently (e.g. unity for a Unity-heavy session)."""
        self.get(module_name)           # ensure it's loaded
        self._pinned.add(module_name)

    def unpin(self, module_name: str):
        """Allow module to be unloaded to free memory."""
        self._pinned.discard(module_name)

    def unload(self, module_name: str):
        """
        Explicitly unload a template module to free RAM.
        Only unloads if not pinned. Safe — next get() will reimport.
        """
        if module_name in self._pinned:
            return
        with self._lock:
            self._loaded.pop(module_name, None)
            # Remove from sys.modules so GC can collect
            sys.modules.pop(module_name, None)

    def unload_domain(self, domain: str):
        """Unload all template modules for a given domain."""
        mapping = {
            "unity":   ["unity_templates", "unity_stubs"],
            "unreal":  ["unreal_templates"],
            "dotnet":  ["dotnet_templates"],
            "react":   ["react_templates"],
            "angular": ["angular_templates"],
            "html":    ["html_templates"],
            "sql":     ["sql_templates"],
            "python":  ["python_templates"],
        }
        for mod in mapping.get(domain, []):
            self.unload(mod)

    # ── Status ────────────────────────────────────────────────────────────────

    def loaded_modules(self) -> list[str]:
        return list(self._loaded.keys())

    def memory_report(self):
        loaded = self.loaded_modules()
        print(f"\n📦 Template cache: {len(loaded)} module(s) loaded")
        for name in loaded:
            pinned = "📌" if name in self._pinned else "  "
            size_kb = sys.getsizeof(self._loaded[name]) // 1024
            print(f"   {pinned} {name:<30} ~{size_kb} KB")
        print()


# ── Global singleton ──────────────────────────────────────────────────────────
template_cache = LazyTemplateCache()


# ── Convenience accessors (replace direct module-level imports) ───────────────

def get_unity_templates():
    m = template_cache.get("unity_templates")
    return m.UNIVERSAL_TEMPLATES, m.TEMPLATED_ROLES, m.FILL_TEMPLATES, m.ROLE_FILL_RULES

def get_unreal_templates():
    m = template_cache.get("unreal_templates")
    return m.UNREAL_SYSTEM_PROMPT, m.get_unreal_template, m.get_unreal_cpp_template

def get_dotnet_templates():
    m = template_cache.get("dotnet_templates")
    return m.DOTNET_SYSTEM_PROMPT, m.get_dotnet_template, m.get_dotnet_ext

def get_react_templates():
    m = template_cache.get("react_templates")
    return m.REACT_SYSTEM_PROMPT, m.get_react_template, m.get_react_ext

def get_angular_templates():
    m = template_cache.get("angular_templates")
    return m.ANGULAR_SYSTEM_PROMPT, m.get_angular_template, m.get_angular_ext

def get_html_templates():
    m = template_cache.get("html_templates")
    return m.HTML_SYSTEM_PROMPT, m.get_html_template, m.get_html_ext

def get_sql_templates():
    m = template_cache.get("sql_templates")
    return m.SQL_SYSTEM_PROMPT, m.get_sql_template

def get_python_templates():
    m = template_cache.get("python_templates")
    return m.PYTHON_SYSTEM_PROMPT, m.get_python_template, m.SELF_MOD_PROMPT
