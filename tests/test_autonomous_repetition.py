import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from autonomous_repetition import ActionFingerprint, RepetitionDetector, normalize_args

def test_normalize_args_is_order_insensitive():
    a = {"path": "src/main.py", "mode": "r"}
    b = {"mode": "r", "path": "src/main.py"}
    left = json.dumps(normalize_args(a), sort_keys=True)
    right = json.dumps(normalize_args(b), sort_keys=True)
    assert left == right

def test_fingerprint_collapses_whitespace():
    detector = RepetitionDetector(repeat_limit=2)
    fp_a = detector.fingerprint("write_file", {"text": "hello   world"})
    fp_b = detector.fingerprint("write_file", {"text": "hello world"})
    assert fp_a.key == fp_b.key

def test_fingerprint_unifies_path_separators():
    detector = RepetitionDetector(repeat_limit=2)
    backslash = chr(92)
    windows_path = "src" + backslash + "app" + backslash + "main.py"
    posix_path = "src/app/main.py"
    fp_win = detector.fingerprint("read_file", {"path": windows_path})
    fp_posix = detector.fingerprint("read_file", {"path": posix_path})
    assert fp_win.key == fp_posix.key

def test_consecutive_repeats_trigger():
    detector = RepetitionDetector(repeat_limit=2)
    repeated = False
    for _ in range(5):
        repeated, fingerprint, count = detector.observe("scan_project", {"root": "."})
    assert repeated is True
    assert count > 2
    assert isinstance(fingerprint, ActionFingerprint)

def test_windowed_alternation_trigger():
    detector = RepetitionDetector(repeat_limit=2, window=8)
    flags = []
    for i in range(8):
        tool = "read_file" if i % 2 == 0 else "write_file"
        repeated, _fingerprint, _count = detector.observe(tool, {"path": "a"})
        flags.append(repeated)
    # No two consecutive actions are identical, so only the windowed check fires.
    assert any(flags)

def test_distinct_actions_do_not_trigger():
    detector = RepetitionDetector(repeat_limit=2, window=8)
    triggered = False
    for i in range(4):
        repeated, _fp, _count = detector.observe("read_file", {"path": f"file_{i}.py"})
        triggered = triggered or repeated
    assert triggered is False

def test_semantic_key_fn_overrides_fingerprint():
    detector = RepetitionDetector(repeat_limit=1, semantic_key_fn=lambda tool, args: "SAME")
    detector.observe("read_file", {"path": "a"})
    repeated, fingerprint, _count = detector.observe("write_file", {"path": "b"})
    assert fingerprint.key == "SAME"
    assert repeated is True
