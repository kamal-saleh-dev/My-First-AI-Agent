"""Prompt construction and observation summarization for the autonomous loop."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass

from tool_registry import ToolResult


SYSTEM_PROMPT_TEMPLATE = """You are {agent_name}, an autonomous engineering executor.
Agent-specific operating context:
{agent_context}

Think briefly, choose exactly one tool, and respond with one JSON object only.
Use this schema:
{{"thought":"Inspect compile errors","tool":"read_file","args":{{"path":"PlayerController.cs"}}}}
When the task is complete, use tool "finish" with args {{"answer":"..."}}.
Available tools:
{tools_json}
"""


class ObservationSummarizer:
    """Small, deterministic summaries to keep future prompts compact."""

    def __init__(self, max_result_chars: int = 1200, max_history: int = 8):
        self.max_result_chars = max_result_chars
        self.max_history = max_history

    def summarize(self, observation) -> dict:
        result = getattr(observation, "result", None)
        result_dict = _result_to_dict(result)
        compact_result = _truncate_json(result_dict, self.max_result_chars)
        return {
            "step": getattr(observation, "step", 0),
            "tool": getattr(observation, "tool", ""),
            "args": getattr(observation, "args", {}),
            "success": getattr(observation, "success", False),
            "error": getattr(observation, "error", ""),
            "summary": compact_result,
        }

    def summarize_many(self, observations: list) -> list[dict]:
        return [self.summarize(obs) for obs in observations[-self.max_history:]]


def build_system_prompt(
    tools: list[dict],
    agent_name: str = "AutonomousExecutor",
    agent_context: str = "Use the available tools to complete the task.",
) -> str:
    tools_json = json.dumps(tools, ensure_ascii=False)
    return SYSTEM_PROMPT_TEMPLATE.format(
        agent_name=agent_name,
        agent_context=agent_context,
        tools_json=tools_json,
    )


def build_user_prompt(task: str, step: int, observation_summaries: list[dict]) -> str:
    payload = {
        "task": task,
        "step": step,
        "observations": observation_summaries,
    }
    return json.dumps(payload, ensure_ascii=False)


def _result_to_dict(result) -> dict:
    if isinstance(result, ToolResult):
        return result.to_dict()
    if isinstance(result, dict):
        return result
    if is_dataclass(result):
        return asdict(result)
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                return parsed
        except Exception:
            pass
        return {"success": True, "data": {"output": result}, "error": ""}
    return {"success": True, "data": {"value": result}, "error": ""}


def _truncate_json(value: dict, max_chars: int) -> str:
    text = json.dumps(value, ensure_ascii=False, default=str)
    if max_chars and len(text) > max_chars:
        return text[:max_chars] + "..."
    return text
