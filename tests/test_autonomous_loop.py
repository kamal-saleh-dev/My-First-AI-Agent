import json
import time

from autonomous_prompts import ObservationSummarizer
from autonomous_repetition import RepetitionDetector
from autonomous_loop import AutonomousExecutor, parse_action
from tool_registry import Tool, ToolResult, register_tool, unregister_tool


class FlakyTool(Tool):
    name = "test_flaky"
    description = "Fails once, then succeeds"
    schema = {"type": "object", "properties": {}}

    def __init__(self):
        self.calls = 0

    def execute(self, args: dict) -> str:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary failure")
        return json.dumps({"success": True, "message": "ok"})


class SleepTool(Tool):
    name = "test_sleep"
    description = "Sleeps for timeout tests"
    schema = {"type": "object", "properties": {"seconds": {"type": "number"}}}

    def execute(self, args: dict) -> str:
        time.sleep(float(args.get("seconds", 0.1)))
        return json.dumps({"success": True})


def _decisions(items):
    seq = iter(items)
    return lambda messages: next(seq)


def test_parse_action_recovers_fenced_json():
    action, error = parse_action('```json\n{"thought":"x","tool":"finish","args":{"answer":"done"}}\n```')
    assert error == ""
    assert action["tool"] == "finish"


def test_auto_command_routes_to_autonomous_executor():
    from model_router import detect_mode
    assert detect_mode("/auto inspect the project") == ("AUTO", "general")


def test_observation_summarizer_truncates_large_results():
    class Obs:
        step = 1
        tool = "read_file"
        args = {"path": "big.txt"}
        success = True
        error = ""
        result = ToolResult.ok(content="x" * 200)

    summary = ObservationSummarizer(max_result_chars=80).summarize(Obs())
    assert summary["summary"].endswith("...")
    assert len(summary["summary"]) <= 83


def test_repetition_detector_supports_semantic_fingerprints():
    detector = RepetitionDetector(
        repeat_limit=1,
        semantic_key_fn=lambda tool, args: f"{tool}:{args.get('path', '').lower()}",
    )
    first, _, _ = detector.observe("read_file", {"path": "A.py"})
    second, fingerprint, count = detector.observe("read_file", {"path": "a.py"})
    assert first is False
    assert second is True
    assert fingerprint.semantic_key == "read_file:a.py"
    assert count == 2


def test_malformed_json_recovery_then_finish():
    executor = AutonomousExecutor(
        decision_fn=_decisions([
            "not json",
            '{"thought":"done","tool":"finish","args":{"answer":"ok"}}',
        ]),
        max_retries=1,
    )
    state = executor.execute("finish after malformed json")
    assert state.status == "completed"
    assert state.final_answer == "ok"
    assert "malformed_json" in state.observations[0].error


def test_invalid_tool_handling_then_finish():
    executor = AutonomousExecutor(
        decision_fn=_decisions([
            '{"thought":"try missing","tool":"missing_tool","args":{}}',
            '{"thought":"done","tool":"finish","args":{"answer":"recovered"}}',
        ]),
        max_retries=1,
    )
    state = executor.execute("recover from invalid tool")
    assert state.status == "completed"
    assert "invalid_tool" in state.observations[0].error


def test_tool_retry_after_failure():
    tool = FlakyTool()
    try:
        register_tool(tool)
        executor = AutonomousExecutor(
            decision_fn=_decisions([
                '{"thought":"first","tool":"test_flaky","args":{}}',
                '{"thought":"retry","tool":"test_flaky","args":{}}',
                '{"thought":"done","tool":"finish","args":{"answer":"ok"}}',
            ]),
            max_retries=1,
        )
        state = executor.execute("retry flaky tool")
        assert state.status == "completed"
        assert tool.calls == 2
        assert state.observations[0].success is False
        assert state.observations[1].success is True
        assert isinstance(state.observations[1].result, ToolResult)
    finally:
        unregister_tool("test_flaky")


def test_repeated_loop_detection():
    tool = FlakyTool()
    try:
        register_tool(tool)
        executor = AutonomousExecutor(
            decision_fn=lambda messages: '{"thought":"loop","tool":"test_flaky","args":{}}',
            repeat_limit=1,
            max_steps=5,
        )
        state = executor.execute("detect repeated loop")
        assert state.status == "failed"
        assert "repeated action" in state.failure_reason
    finally:
        unregister_tool("test_flaky")


def test_tool_timeout_stops_after_retry_limit():
    try:
        register_tool(SleepTool())
        executor = AutonomousExecutor(
            decision_fn=_decisions([
                '{"thought":"sleep","tool":"test_sleep","args":{"seconds":0.05}}',
            ]),
            tool_timeout=0.01,
            max_retries=0,
        )
        state = executor.execute("timeout")
        assert state.status == "failed"
        assert "timed out" in state.failure_reason
    finally:
        unregister_tool("test_sleep")
