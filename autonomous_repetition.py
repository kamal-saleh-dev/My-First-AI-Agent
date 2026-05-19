"""Repeated-action detection for the autonomous loop.

The current detector uses exact action fingerprints. The interface leaves room
for semantic fingerprints later without changing AutonomousExecutor.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Callable, Optional


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
    ):
        self.repeat_limit = repeat_limit
        self.semantic_key_fn = semantic_key_fn
        self.last_fingerprint: ActionFingerprint | None = None
        self.repeated_count = 0

    def fingerprint(self, tool: str, args: dict) -> ActionFingerprint:
        try:
            args_signature = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
        except TypeError:
            args_signature = str(args)
        semantic_key = self.semantic_key_fn(tool, args) if self.semantic_key_fn else ""
        return ActionFingerprint(tool=tool, args_signature=args_signature, semantic_key=semantic_key)

    def observe(self, tool: str, args: dict) -> tuple[bool, ActionFingerprint, int]:
        fingerprint = self.fingerprint(tool, args)
        if self.last_fingerprint and fingerprint.key == self.last_fingerprint.key:
            self.repeated_count += 1
        else:
            self.last_fingerprint = fingerprint
            self.repeated_count = 1
        return self.repeated_count > self.repeat_limit, fingerprint, self.repeated_count
