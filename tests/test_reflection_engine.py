"""Unit tests for the reflection engine (no agents, no network)."""

from reflection_engine import (
    CONTINUE,
    DELEGATE_DEBUG,
    RETRY,
    STOP,
    SWITCH_MODEL,
    ReflectionEngine,
)

def _ok():
    return {"status": "completed"}

def _fail(error="boom"):
    return {"status": "failed", "error": error}

def test_success_continues_and_scores_progress():
    eng = ReflectionEngine(total_steps=2)
    r = eng.reflect(1, "PlannerAgent", _ok())
    assert r.decision == CONTINUE
    assert r.success is True
    assert r.progress == 0.5

def test_first_failure_escalates_model():
    eng = ReflectionEngine(total_steps=1, max_retries=2, max_escalations=2)
    r = eng.reflect(1, "CodingAgent", _fail("err-a"))
    assert r.decision == SWITCH_MODEL
    assert r.attempts == 1

def test_escalate_then_debug_then_stop():
    eng = ReflectionEngine(
        total_steps=1,
        max_retries=2,
        max_escalations=2,
        max_debug_delegations=1,
        stuck_threshold=10,
        can_debug=True,
    )
    decisions = [eng.reflect(1, "TestingAgent", _fail(f"e{i}")).decision for i in range(4)]
    assert decisions == [SWITCH_MODEL, SWITCH_MODEL, DELEGATE_DEBUG, STOP]

def test_stuck_detection_stops():
    eng = ReflectionEngine(total_steps=1, stuck_threshold=3, max_retries=9, max_escalations=9)
    eng.reflect(1, "CodingAgent", _fail("same"))
    eng.reflect(1, "CodingAgent", _fail("same"))
    r = eng.reflect(1, "CodingAgent", _fail("same"))
    assert r.stuck is True
    assert r.decision == STOP

def test_retry_when_escalations_exhausted():
    eng = ReflectionEngine(
        total_steps=1, max_retries=2, max_escalations=0, can_debug=False, stuck_threshold=10
    )
    assert eng.reflect(1, "CodingAgent", _fail("a")).decision == RETRY
    assert eng.reflect(1, "CodingAgent", _fail("b")).decision == RETRY
    # third failure exceeds retries and debug is disabled -> stop
    assert eng.reflect(1, "CodingAgent", _fail("c")).decision == STOP

def test_debugger_agent_never_self_delegates():
    eng = ReflectionEngine(
        total_steps=1, max_retries=0, max_escalations=0, can_debug=True, stuck_threshold=10
    )
    r = eng.reflect(1, "DebuggerAgent", _fail("z"))
    assert r.decision == STOP

def test_accepts_objectlike_results():
    eng = ReflectionEngine(total_steps=1)

    class R:
        status = "completed"
        error = ""

    assert eng.reflect(1, "X", R()).success is True

def test_summary_reports_counts():
    eng = ReflectionEngine(total_steps=2)
    eng.reflect(1, "PlannerAgent", _ok())
    eng.reflect(2, "CodingAgent", _fail("x"))
    summary = eng.summary()
    assert summary["completed"] == 1
    assert summary["total_steps"] == 2
    assert isinstance(summary["decisions"], list)
