import json

from tool_registry import (
    BACKGROUND_TOOLS,
    TOOL_REGISTRY,
    Tool,
    ToolResult,
    TOOL_CATEGORIES,
    get_tool,
    list_tools,
    register_tool,
    unregister_tool,
)


class EchoTool(Tool):
    name = "test_echo"
    description = "Echo test tool"
    schema = {"type": "object", "properties": {"value": {"type": "string"}}}

    def execute(self, args: dict) -> str:
        return json.dumps({"success": True, "value": args.get("value", "")})


def test_register_get_and_list_structured_tool():
    tool = EchoTool()
    try:
        register_tool(tool)
        assert get_tool("test_echo", structured=True) is tool
        assert get_tool("test_echo") is tool
        names = [item["name"] for item in list_tools()]
        assert "test_echo" in names
    finally:
        unregister_tool("test_echo")


def test_tool_result_structured_and_legacy_serialization():
    result = ToolResult.ok(path="a.py", chars=10)
    assert result.to_dict() == {
        "success": True,
        "data": {"path": "a.py", "chars": 10},
        "error": "",
    }
    legacy = json.loads(result.to_json(legacy=True))
    assert legacy == {"success": True, "path": "a.py", "chars": 10}


def test_structured_tool_metadata_includes_categories_and_tags():
    assert "memory" in TOOL_CATEGORIES
    tools = {item["name"]: item for item in list_tools()}
    assert "filesystem" in tools["read_file"]["categories"]
    assert "testing" in tools["run_tests"]["categories"]
    assert "analysis" in tools["analyze_errors"]["categories"]
    assert "read" in tools["read_file"]["tags"]


def test_auto_command_is_registered_for_background_execution():
    assert "AUTO" in TOOL_REGISTRY
    assert "AUTO" in BACKGROUND_TOOLS


def test_default_file_tools_execute(tmp_path):
    root = str(tmp_path)

    write = get_tool("write_file", structured=True)
    read = get_tool("read_file", structured=True)
    edit = get_tool("edit_file", structured=True)
    search = get_tool("search_files", structured=True)
    scan = get_tool("scan_project", structured=True)
    analyze = get_tool("analyze_errors", structured=True)

    written = json.loads(write.execute({
        "root": root,
        "path": "notes/example.txt",
        "content": "hello\nold value\n",
    }))
    assert written["success"] is True
    structured_written = write.execute_structured({
        "root": root,
        "path": "notes/structured.txt",
        "content": "hello",
    })
    assert isinstance(structured_written, ToolResult)
    assert structured_written.data["path"] == "notes/structured.txt"

    edited = json.loads(edit.execute({
        "root": root,
        "path": "notes/example.txt",
        "old_text": "old value",
        "new_text": "new value",
    }))
    assert edited["replacements"] == 1

    content = json.loads(read.execute({"root": root, "path": "notes/example.txt"}))
    assert "new value" in content["content"]

    matches = json.loads(search.execute({
        "root": root,
        "query": "new value",
        "path": "notes",
    }))
    assert matches["matches"][0]["path"] == "notes/example.txt"

    project = json.loads(scan.execute({"root": root}))
    assert any(f["path"] == "notes/example.txt" for f in project["files"])

    errors = json.loads(analyze.execute({"text": "FAILED test_x\nAssertionError: boom"}))
    assert errors["success"] is True
    assert errors["category"] == "test_failure"


def test_run_tests_reports_subprocess_failure(monkeypatch, tmp_path):
    def fake_run_process(cmd, cwd=None, timeout=120, input_data=None):
        return {"success": False, "stdout": "", "stderr": "failed", "returncode": 1}

    monkeypatch.setattr("tool_registry.run_process", fake_run_process)
    tool = get_tool("run_tests", structured=True)
    result = json.loads(tool.execute({
        "root": str(tmp_path),
        "command": ["pytest", "tests"],
    }))
    assert result["success"] is False
    assert result["result"]["returncode"] == 1
