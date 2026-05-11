# tests/test_model_advisor.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch, MagicMock
from model_advisor import (
    assess_quality, escalate,
    _ladder_index, _models_above,
    ESCALATION_LADDER, _ESCALATE_THRESHOLD,
)


# ── helpers ───────────────────────────────────────────────────────────────────

def _mock_llm(code: str):
    """Return a mock safe_chat response that contains code."""
    r = MagicMock()
    r.message.content = code
    return r

# Good Unity code — passes all checks
GOOD_UNITY = """```csharp
using UnityEngine;
using System.Collections;

public class PlayerController : MonoBehaviour
{
    private Rigidbody2D rb;
    private float speed = 5f;
    private float jumpForce = 10f;
    private bool isGrounded = false;

    void Start()
    {
        rb = GetComponent<Rigidbody2D>();
    }

    void Update()
    {
        float h = Input.GetAxis("Horizontal");
        rb.velocity = new Vector2(h * speed, rb.velocity.y);
        if (Input.GetKeyDown(KeyCode.Space) && isGrounded)
        {
            rb.AddForce(Vector2.up * jumpForce, ForceMode2D.Impulse);
        }
    }

    void OnCollisionEnter2D(Collision2D col)
    {
        if (col.gameObject.CompareTag("Ground"))
            isGrounded = true;
    }

    void OnCollisionExit2D(Collision2D col)
    {
        if (col.gameObject.CompareTag("Ground"))
            isGrounded = false;
    }
}
```"""

# Bad code — placeholder + too short
BAD_PLACEHOLDER = """```csharp
using UnityEngine;
public class Player : MonoBehaviour
{
    void Start() { }  // TODO: implement
    void Update() { } // add logic here
}
```"""

# No code block at all
NO_BLOCK = "Here is my answer: the player should move with WASD keys."

# Too short
TOO_SHORT = """```csharp
using UnityEngine;
public class Tiny : MonoBehaviour { }
```"""


# ══════════════════════════════════════════════════════════════
# TestAssessQuality
# ══════════════════════════════════════════════════════════════

class TestAssessQuality:

    def test_good_code_scores_high(self):
        score, issues = assess_quality(GOOD_UNITY, "unity")
        assert score >= 70, f"Good code scored too low: {score} — issues: {issues}"

    def test_good_code_has_no_issues(self):
        _, issues = assess_quality(GOOD_UNITY, "unity")
        # Good code may have compile issues if dotnet isn't available — that's OK
        non_compile = [i for i in issues if "compile" not in i]
        assert len(non_compile) == 0, f"Unexpected issues in good code: {non_compile}"

    def test_no_code_block_scores_low(self):
        score, issues = assess_quality(NO_BLOCK, "unity")
        assert score < (100 - _ESCALATE_THRESHOLD), \
            f"No-block code should trigger escalation, got score={score}"
        assert any("no_code_block" in i for i in issues)

    def test_placeholder_scores_low(self):
        score, issues = assess_quality(BAD_PLACEHOLDER, "unity")
        assert score < (100 - _ESCALATE_THRESHOLD), \
            f"Placeholder code should trigger escalation, got score={score}"
        assert any("placeholder" in i for i in issues)

    def test_too_short_scores_low(self):
        score, issues = assess_quality(TOO_SHORT, "unity")
        assert score < (100 - _ESCALATE_THRESHOLD), \
            f"Short code should trigger escalation, got score={score}"
        assert any("too_short" in i for i in issues)

    def test_score_is_0_to_100(self):
        for code in [GOOD_UNITY, BAD_PLACEHOLDER, NO_BLOCK, TOO_SHORT]:
            score, _ = assess_quality(code, "unity")
            assert 0 <= score <= 100, f"Score out of range: {score}"

    def test_non_unity_engine_skips_compile(self):
        # Python engine should not trigger Unity compile check
        py_code = "```python\ndef main():\n    print('hello')\n    x = 1\n    return x\n```"
        score, issues = assess_quality(py_code, "python")
        assert not any("compile" in i for i in issues)


# ══════════════════════════════════════════════════════════════
# TestLadder
# ══════════════════════════════════════════════════════════════

class TestLadder:

    def test_ladder_has_at_least_four_levels(self):
        assert len(ESCALATION_LADDER) >= 4

    def test_local_is_bottom(self):
        assert _ladder_index("local") == 0

    def test_claude_is_top(self):
        assert _ladder_index("claude") == len(ESCALATION_LADDER) - 1

    def test_models_above_local_returns_all_others(self):
        above = _models_above("local")
        assert len(above) == len(ESCALATION_LADDER) - 1

    def test_models_above_claude_returns_empty(self):
        assert _models_above("claude") == []

    def test_models_above_or_free_excludes_local(self):
        above = _models_above("or_free")
        assert "local" not in above
        assert len(above) == len(ESCALATION_LADDER) - 2

    def test_unknown_model_treated_as_local(self):
        # Unknown model → index 0 (local), so all others are "above"
        above = _models_above("some_unknown_model")
        assert len(above) == len(ESCALATION_LADDER) - 1


# ══════════════════════════════════════════════════════════════
# TestEscalate
# ══════════════════════════════════════════════════════════════

class TestEscalate:

    def _eng_cfg(self):
        return {
            "system": "You are a Unity developer.",
            "lang":   "Unity C#",
            "block":  "csharp",
            "skip_template": False,
        }

    def test_returns_original_if_no_candidates(self):
        """Top model has no models above it — should return original code."""
        best, model = escalate(
            task="make a shooter",
            script_name="Player",
            script_role="player",
            engine="unity",
            current_model="claude",      # already at top
            current_code=BAD_PLACEHOLDER,
            eng_cfg=self._eng_cfg(),
            script_pairs=[("Player","player")],
            generated_context={},
            model_name="claude",
        )
        assert best  == BAD_PLACEHOLDER
        assert model == "claude"

    def test_escalates_when_openrouter_not_configured(self):
        """
        With USE_OPENROUTER=False, cloud models are skipped.
        Starting from 'local', all candidates are cloud → returns original.
        """
        import llm_client
        original_use = getattr(llm_client, "USE_OPENROUTER", False)
        llm_client.USE_OPENROUTER = False
        try:
            best, model = escalate(
                task="make a shooter",
                script_name="Player",
                script_role="player",
                engine="unity",
                current_model="local",
                current_code=BAD_PLACEHOLDER,
                eng_cfg=self._eng_cfg(),
                script_pairs=[("Player","player")],
                generated_context={},
                model_name="local",
            )
            # All candidates are cloud (have "/" in alias resolution)
            # → skipped → returns original
            assert best == BAD_PLACEHOLDER
        finally:
            llm_client.USE_OPENROUTER = original_use

    def test_escalates_and_returns_better_code(self):
        """
        Mock OpenRouter available: first escalation candidate returns good code.
        Result should be the good code, not the original bad code.
        """
        import llm_client
        original_use    = getattr(llm_client, "USE_OPENROUTER", False)
        original_client = getattr(llm_client, "cloud_client",   None)

        llm_client.USE_OPENROUTER = True
        llm_client.cloud_client   = MagicMock()   # pretend cloud is configured

        with patch("model_advisor.safe_print"), \
             patch("model_advisor._regenerate", return_value=GOOD_UNITY):
            best, used_model = escalate(
                task="make a shooter",
                script_name="Player",
                script_role="player",
                engine="unity",
                current_model="local",
                current_code=BAD_PLACEHOLDER,
                eng_cfg=self._eng_cfg(),
                script_pairs=[("Player","player")],
                generated_context={},
                model_name="local",
            )

        llm_client.USE_OPENROUTER = original_use
        llm_client.cloud_client   = original_client

        assert best != BAD_PLACEHOLDER, "Should have returned better code"
        assert used_model != "local",   "Should have escalated to a higher model"

    def test_returns_best_when_all_fail(self):
        """
        Even if every escalation attempt returns bad code,
        we still get back the best code seen (original or escalated).
        """
        import llm_client
        original_use    = getattr(llm_client, "USE_OPENROUTER", False)
        original_client = getattr(llm_client, "cloud_client",   None)

        llm_client.USE_OPENROUTER = True
        llm_client.cloud_client   = MagicMock()

        # All attempts return the same bad code
        with patch("model_advisor.safe_print"), \
             patch("model_advisor._regenerate", return_value=BAD_PLACEHOLDER):
            best, _ = escalate(
                task="make a shooter",
                script_name="Player",
                script_role="player",
                engine="unity",
                current_model="local",
                current_code=BAD_PLACEHOLDER,
                eng_cfg=self._eng_cfg(),
                script_pairs=[("Player","player")],
                generated_context={},
                model_name="local",
            )

        llm_client.USE_OPENROUTER = original_use
        llm_client.cloud_client   = original_client

        # Should return something (not crash), even if still bad
        assert isinstance(best, str) and len(best) > 0
