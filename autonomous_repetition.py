"""Repeated-action detection for the autonomous loop.

The detector uses deterministic, non-semantic action fingerprints. Arguments are
normalized (key ordering, whitespace, path separators) so trivially different but
equivalent actions collapse to the same fingerprint. In addition to consecutive
repeats, a small sliding window catches short alternating loops (A, B, A, B, ...).

No embeddings or semantic similarity are used. The optional `semantic_key_fn`
hook is preserved for a future phase but defaults to off.
"""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass
from typing import Callable, Optional

# Defined as a constant to avoid embedding a literal path-separator backslash.
_BACKSLASH = chr(92)

# Default number of recent actions inspected for windowed repetition.
DEFAULT_REPETITION_WINDOW = 12

def normalize_args(args):
    """Return a deterministically normalized copy of tool arguments.

    Normalization is purely structural/textual:
    - nested dicts/lists are normalized recursively
    - string values are stripped and internal whitespace runs are collapsed
    - path-like separators are unified to "/"

    Dict key ordering is handled later by json.dumps(sort_keys=True). This is
    intentionally NOT semantic: it does not interpret meaning, embed, or compare
    similarity. It only canonicalizes equivalent literal inputs.
    """
    if isinstance(args, dict):
        return {str(key): normalize_args(value) for key, value in args.items()}
    if isinstance(args, (list, tuple)):
        return [normalize_args(item) for item in args]
    if isinstance(args, str):
        collapsed = " ".join(args.strip().split())
        return collapsed.replace(_BACKSLASH, "/")
    return args

@dataclass(frozen=True)
class ActionFingerprint:
    tool: str
    args_signature: str
    semantic_key: str = ""

    @property
    def key(self) -> str:
        return self.semantic_key or f"{self.tool}:{self.args_signature}"

class RepetitionDetector:
    def __init__(
        self,
        repeat_limit: int,
        semantic_key_fn: Optional[Callable[[str, dict], str]] = None,
        window: int = DEFAULT_REPETITION_WINDOW,
    ):
        self.repeat_limit = repeat_limit
        self.semantic_key_fn = semantic_key_fn
        self.window = max(int(window), 1)
        self.last_fingerprint: ActionFingerprint | None = None
        self.repeated_count = 0
        self.recent_keys: deque[str] = deque(maxlen=self.window)

    def fingerprint(self, tool: str, args: dict) -> ActionFingerprint:
        normalized = normalize_args(args)
        try:
            args_signature = json.dumps(normalized, sort_keys=True, ensure_ascii=False, default=str)
        except TypeError:
            args_signature = str(normalized)
        semantic_key = self.semantic_key_fn(tool, args) if self.semantic_key_fn else ""
        return ActionFingerprint(tool=tool, args_signature=args_signature, semantic_key=semantic_key)

    def observe(self, tool: str, args: dict) -> tuple[bool, ActionFingerprint, int]:
        fingerprint = self.fingerprint(tool, args)

        # Consecutive repeats (original behavior).
        if self.last_fingerprint and fingerprint.key == self.last_fingerprint.key:
            self.repeated_count += 1
        else:
            self.last_fingerprint = fingerprint
            self.repeated_count = 1

        # Windowed repeats catch short alternating loops without semantics.
        self.recent_keys.append(fingerprint.key)
        windowed_count = sum(1 for key in self.recent_keys if key == fingerprint.key)

        effective_count = max(self.repeated_count, windowed_count)
        repeated = self.repeated_count > self.repeat_limit or windowed_count > self.repeat_limit
        return repeated, fingerprint, effective_count
