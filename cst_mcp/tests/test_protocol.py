import pytest

pytest.importorskip("mcp", reason="install the mcp extra to run protocol tests")

from mcp import types

from cst_mcp import register_tool
from cst_mcp.server import SERVER_NAME, _tool_definitions, build_server


def test_server_registers_mcp_request_handlers():
    server = build_server()
    assert SERVER_NAME == "cst-automation-mcp"
    assert types.ListToolsRequest in server.request_handlers
    assert types.CallToolRequest in server.request_handlers


def test_tool_definitions_publish_json_schemas_and_read_only_annotations():
    tools = _tool_definitions()
    by_name = {tool.name: tool for tool in tools}
    assert "run_simulation" in by_name
    assert by_name["run_simulation"].inputSchema["type"] == "object"
    assert by_name["run_simulation"].annotations.readOnlyHint is False
    assert by_name["get_results"].annotations.readOnlyHint is True


def test_explicit_domain_extension_appears_in_protocol_tool_list():
    register_tool("protocol_extension",
                  {"name": "protocol_extension", "description": "domain extension",
                   "inputSchema": {"type": "object"},
                   "annotations": {"readOnlyHint": True}},
                  lambda _arguments: {"ok": True})
    assert "protocol_extension" in {tool.name for tool in _tool_definitions()}
