"""
memory_store.py — RAG Memory System for the AI Agent
=====================================================
Stores every task + result so the agent can learn from past experience.

Storage: JSON file (zero dependencies).
Retrieval: Token-overlap similarity (no FAISS/Chroma needed).
Upgrade path: ChromaDB (see _chroma_search below — just install & uncomment).

Usage:
    from memory_store import memory

    # Save a result
    memory.add(task="add /weather command", success=True,
               solution="added _tool_weather to tool_registry.py",
               feedback="worked on first try")

    # Retrieve similar past experiences
    hits = memory.search("add /date command", top_k=3)
    for h in hits:
        print(h["task"], h["score"])

    # Inject as context string into a prompt
    context = memory.format_context("add /clock command")
"""

import json
import os
import re
import time
from typing import Optional

# ── Config ────────────────────────────────────────────────────────────────────
_MEMORY_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "memory_store.json")
_MIN_SCORE   = 0.12    # minimum similarity to include in results
# No entry limit — everything is stored. Each entry is ~200 bytes compressed.
# 10,000 entries ≈ 2 MB — negligible.


# ── Similarity ────────────────────────────────────────────────────────────────

def _tokenize(text: str) -> set[str]:
    """Lowercase word tokens, strip punctuation."""
    return set(re.findall(r"[a-z0-9_/]+", text.lower()))


def _similarity(a: str, b: str) -> float:
    """
    Jaccard-style token overlap score [0.0 – 1.0].
    Fast, deterministic, zero dependencies.
    """
    ta, tb = _tokenize(a), _tokenize(b)
    if not ta or not tb:
        return 0.0
    intersection = len(ta & tb)
    union        = len(ta | tb)
    return intersection / union if union else 0.0


# ══════════════════════════════════════════════════════════════════════════════
# MemoryStore class
# ══════════════════════════════════════════════════════════════════════════════

class MemoryStore:
    """
    Persistent task-memory with similarity search.

    Each entry:
        {
          "id":        "mem_1714500000",
          "timestamp": 1714500000,
          "task":      "add /weather command",
          "solution":  "added _tool_weather() to tool_registry.py",
          "success":   true,
          "feedback":  "worked on first try",
          "files":     ["tool_registry.py"],
          "tags":      ["command", "tool", "weather"]
        }
    """

    def __init__(self, path: str = _MEMORY_FILE):
        self._path    = path
        self._entries: list[dict] = []
        self._dirty   = False
        self._load()

    # ── Persistence ───────────────────────────────────────────────────────────

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, encoding="utf-8") as f:
                    self._entries = json.load(f)
            except Exception:
                self._entries = []

    def _save(self):
        """Atomic write — prevents corruption if process crashes mid-write."""
        tmp = self._path + ".tmp"
        try:
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, separators=(",", ":"))
            os.replace(tmp, self._path)   # atomic on all platforms
            self._dirty = False
        except Exception as e:
            import logging
            logging.warning(f"memory_store: save failed — {e}")
            try:
                os.remove(tmp)
            except Exception:
                pass

    # ── Write ─────────────────────────────────────────────────────────────────

    def add(self,
            task:     str,
            success:  bool,
            solution: str  = "",
            feedback: str  = "",
            files:    list[str] | None = None,
            tags:     list[str] | None = None) -> dict:
        """
        Add a new memory entry. Stored in compact form to save space.
        ~150–200 bytes per entry — 10,000 entries ≈ 1.5 MB.
        """
        ts    = int(time.time())
        # Compact entry — only store what's useful for retrieval
        entry = {
            "t":  ts,                            # timestamp (short key)
            "q":  task.strip()[:200],            # task (capped at 200 chars)
            "s":  int(success),                  # 1 = success, 0 = fail
            "r":  solution.strip()[:150],        # result/solution summary
            "f":  feedback.strip()[:100],        # feedback (optional)
            "fi": [os.path.basename(x) for x in (files or [])][:4],
        }
        # Remove empty fields to save space
        entry = {k: v for k, v in entry.items() if v or v == 0}

        self._entries.append(entry)
        self._save()
        return entry

    def update_feedback(self, task: str, feedback: str, success: Optional[bool] = None):
        """Update the feedback on the most recent matching entry."""
        for entry in reversed(self._entries):
            if _similarity(entry.get("q", ""), task) > 0.5:
                entry["f"] = feedback[:100]
                if success is not None:
                    entry["s"] = int(success)
                self._save()
                return

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 3,
               only_successful: bool = False) -> list[dict]:
        """
        Return top_k most similar past memories to the query.
        Each result has an extra "score" key [0.0 – 1.0].
        """
        scored = []
        for entry in self._entries:
            if only_successful and not entry.get("s", 1):
                continue
            score = _similarity(query, entry.get("q", ""))
            if score >= _MIN_SCORE:
                scored.append({**entry, "score": round(score, 3)})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def format_context(self, query: str, top_k: int = 3) -> str:
        """
        Return a formatted string to inject into an LLM prompt.
        Shows the actual code pattern so the LLM reuses it.
        Empty string if no relevant memories exist.
        """
        hits = self.search(query, top_k=top_k)
        if not hits:
            return ""

        lines = ["RELEVANT PAST EXPERIENCE — reuse these patterns:"]
        for h in hits:
            icon   = "✅" if h.get("s", 1) else "❌"
            result = "success" if h.get("s", 1) else "failed"
            sol    = h.get("r", "")
            lines.append(f"\n  {icon} [{result}] Similar task: {h.get('q','')}")
            if sol:
                lines.append(f"     Pattern used:")
                for part in sol.split(" | "):
                    lines.append(f"       {part.strip()}")
            if h.get("f"):
                lines.append(f"     Note: {h['f']}")
        lines.append(
            "\nApply the same pattern above to implement the current task."
        )
        return "\n".join(lines)

    # ── Stats & Management ────────────────────────────────────────────────────

    def stats(self) -> dict:
        total    = len(self._entries)
        success  = sum(1 for e in self._entries if e.get("s", 1))
        failures = total - success
        # Estimate file size
        try:
            size_kb = os.path.getsize(self._path) // 1024
            size_str = f"{size_kb} KB"
        except Exception:
            size_str = "?"
        return {
            "total":    total,
            "success":  success,
            "failures": failures,
            "rate":     f"{(success/total*100):.0f}%" if total else "n/a",
            "file_size": size_str,
        }

    def print_recent(self, n: int = 15):
        """Print the n most recent memories."""
        recent = self._entries[-n:][::-1]
        if not recent:
            print("🧠 Memory is empty — memories build up as you use the agent.")
            return
        s = self.stats()
        print(f"\n🧠 Memory — {s['total']} entries  |  {s['file_size']}  |  "
              f"success rate: {s['rate']}\n")
        for e in recent:
            icon = "✅" if e.get("s", 1) else "❌"
            ts   = time.strftime("%Y-%m-%d %H:%M", time.localtime(e.get("t", 0)))
            print(f"  {icon} [{ts}] {e.get('q', '')}")
            if e.get("r"):
                preview = e["r"][:80] + ("…" if len(e["r"]) > 80 else "")
                print(f"         → {preview}")
        print()

    def print_search(self, query: str, top_k: int = 5):
        """Print search results for a query."""
        hits = self.search(query, top_k=top_k)
        if not hits:
            print(f"🔍 No relevant memories found for: '{query}'")
            return
        print(f"\n🔍 Top {len(hits)} memories matching '{query}':\n")
        for h in hits:
            icon = "✅" if h.get("s", 1) else "❌"
            print(f"  {icon} [score={h['score']}] {h.get('q','')}")
            if h.get("r"):
                print(f"         → {h['r'][:100]}")
        print()

    def clear(self):
        """Delete all memories (irreversible)."""
        self._entries = []
        self._save()
        print("🧹 Memory cleared.")

    def export(self, path: str):
        """Export memory to a readable JSON file (pretty-printed for humans)."""
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self._entries, f, ensure_ascii=False, indent=2)
        s = self.stats()
        print(f"📤 Memory exported → {path}  ({s['total']} entries, {s['file_size']})")

    def __len__(self):
        return len(self._entries)


# ── Auto-tag helper ───────────────────────────────────────────────────────────

def _auto_tags(task: str) -> list[str]:
    """Extract meaningful tags from a task string."""
    KNOWN_TAGS = {
        "command", "tool", "weather", "date", "time", "search",
        "game", "web", "api", "database", "sql", "react", "unity",
        "unreal", "file", "auth", "login", "chat", "model", "voice",
        "image", "pdf", "email", "gui", "plugin", "memory", "install",
    }
    tokens = _tokenize(task)
    return sorted(tokens & KNOWN_TAGS)


# ── ChromaDB upgrade path (optional) ─────────────────────────────────────────
# When you want semantic search instead of token overlap:
#
#   pip install chromadb
#
# Then replace MemoryStore.search() with:
#
#   def search(self, query, top_k=3, only_successful=False):
#       import chromadb
#       client     = chromadb.PersistentClient(path="./chroma_memory")
#       collection = client.get_or_create_collection("agent_memory")
#       results    = collection.query(query_texts=[query], n_results=top_k)
#       ...
#
# And in add(), call collection.add() with the entry text as document.


# ── Singleton instance (import this everywhere) ───────────────────────────────
memory = MemoryStore()
