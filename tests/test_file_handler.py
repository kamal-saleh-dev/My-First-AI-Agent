# tests/test_file_handler.py
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from unittest.mock import patch, MagicMock


# ── Bootstrap inject_globals so file_handler is usable without agent ─────────
@pytest.fixture(autouse=True)
def inject_fh():
    import file_handler as fh
    mock_r = MagicMock()
    mock_r.message.content = "default"
    fh.inject_globals(
        safe_chat=lambda **kw: mock_r,
        get_response=lambda r: getattr(r.message, "content", "default"),
        log=MagicMock(),
        _state=MagicMock(),
        project_context=[],
        safe_print=print,
        save_project_context=lambda: None,
    )


# ── detect_file_type ──────────────────────────────────────────────────────────

class TestDetectFileType:
    def setup_method(self):
        from file_handler import detect_file_type
        self.detect = detect_file_type

    def test_python_is_code(self):
        assert self.detect("script.py") == "code"

    def test_csharp_is_code(self):
        assert self.detect("Player.cs") == "code"

    def test_png_is_image(self):
        assert self.detect("screenshot.png") == "image"

    def test_mp4_is_video(self):
        assert self.detect("demo.mp4") == "video"

    def test_pdf_detected(self):
        assert self.detect("invoice.pdf") == "pdf"

    def test_docx_detected(self):
        assert self.detect("report.docx") == "word"

    def test_xlsx_detected(self):
        assert self.detect("data.xlsx") == "excel"

    def test_pptx_detected(self):
        assert self.detect("slides.pptx") == "ppt"

    def test_unknown_defaults_to_text(self):
        assert self.detect("notes.txt") == "text"


# ── detect_intent ─────────────────────────────────────────────────────────────

class TestDetectIntent:
    def setup_method(self):
        from file_handler import detect_intent
        self.detect = detect_intent

    def test_compare_arabic(self):
        assert self.detect("قارن الملفين") == "compare"

    def test_compare_english(self):
        assert self.detect("compare these files") == "compare"

    def test_summarize(self):
        assert self.detect("summarize this document") == "summarize"

    def test_detect_issues(self):
        assert self.detect("find bugs in this code") == "detect_issues"

    def test_default_for_coding(self):
        assert self.detect("make a game") == "default"

    def test_default_for_greeting(self):
        assert self.detect("hello how are you") == "default"


# ── get_token_limit ───────────────────────────────────────────────────────────

class TestGetTokenLimit:
    def setup_method(self):
        from file_handler import get_token_limit
        self.limit = get_token_limit

    def test_claude_gets_large_context(self):
        assert self.limit("claude") > 100_000

    def test_14b_gets_medium_context(self):
        assert self.limit("deepseek-14b") > 10_000

    def test_default_small(self):
        assert self.limit("qwen2.5-coder:7b") == 8_000

    def test_none_returns_small(self):
        assert self.limit(None) == 8_000
