"""Specialized autonomous engineering agents."""

from __future__ import annotations

import config as _cfg

from .base_agent import BaseAgent, tools


class PlannerAgent(BaseAgent):
    name = "PlannerAgent"
    role = "planning"
    preferred_model = _cfg.MULTI_AGENT_MODEL_DEEPSEEK
    allowed_tools = tools("search_files", "scan_project", "analyze_errors")
    restricted_tools = tools("write_file", "edit_file")
    system_prompt = (
        "Decompose engineering tasks, inspect project shape, identify dependencies, "
        "and produce prioritized execution plans. Do not modify files."
    )


class CodingAgent(BaseAgent):
    name = "CodingAgent"
    role = "coding"
    preferred_model = _cfg.MULTI_AGENT_MODEL_QWEN_CODER
    allowed_tools = tools("read_file", "write_file", "edit_file", "search_files")
    system_prompt = (
        "Generate and apply focused code changes using repository patterns and local context."
    )


class ReviewerAgent(BaseAgent):
    name = "ReviewerAgent"
    role = "review"
    preferred_model = _cfg.MULTI_AGENT_MODEL_LLAMA
    allowed_tools = tools("read_file", "search_files", "analyze_errors")
    restricted_tools = tools("write_file", "edit_file")
    system_prompt = (
        "Review architecture, behavior, consistency, and quality risks. Report findings clearly. "
        "Do not modify files."
    )


class TestingAgent(BaseAgent):
    name = "TestingAgent"
    role = "testing"
    preferred_model = _cfg.MULTI_AGENT_MODEL_QWEN_CODER
    allowed_tools = tools("compile_project", "run_tests", "analyze_errors")
    system_prompt = (
        "Compile projects, run tests, validate outputs, and summarize failures with reproduction context."
    )


class DebuggerAgent(BaseAgent):
    name = "DebuggerAgent"
    role = "debugging"
    preferred_model = _cfg.MULTI_AGENT_MODEL_DEEPSEEK
    allowed_tools = tools("read_file", "edit_file", "compile_project", "run_tests", "analyze_errors")
    system_prompt = (
        "Analyze compile, test, and runtime failures, then apply narrow repairs and revalidate."
    )


class ContextAgent(BaseAgent):
    name = "ContextAgent"
    role = "context"
    preferred_model = _cfg.MULTI_AGENT_MODEL_LLAMA
    allowed_tools = tools("read_file", "search_files", "scan_project")
    system_prompt = (
        "Summarize project state, manage context windows, and retrieve relevant files for other agents."
    )


DEFAULT_AGENT_CLASSES = (
    PlannerAgent,
    CodingAgent,
    ReviewerAgent,
    TestingAgent,
    DebuggerAgent,
    ContextAgent,
)
