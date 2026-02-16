"""
MIT License
Copyright (c) 2026 socioy
See LICENSE file for full license text.

MCP (Model Context Protocol) package for AFK.

Exposes tools from a ``ToolRegistry`` as an MCP server using FastAPI
with JSON-RPC 2.0 wire format.

Quick start::

    from afk.tools import ToolRegistry, tool
    from afk.mcp import MCPServer

    registry = ToolRegistry()

    @tool(name="greet", description="Greet someone")
    def greet(name: str) -> str:
        return f"Hello, {name}!"

    registry.register(greet)

    server = MCPServer(registry)
    server.run()  # starts on http://0.0.0.0:8000
"""

from .server import MCPServer, MCPServerConfig

__all__ = [
    "MCPServer",
    "MCPServerConfig",
]
