"""MCP integration for the general CST automation service."""

__version__ = "0.1.0"

from cst_mcp.tools import dispatch, register_tool, tool_names

__all__ = ["__version__", "dispatch", "register_tool", "tool_names"]
