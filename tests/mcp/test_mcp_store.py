from __future__ import annotations

import asyncio
import types

from afk.mcp import MCPStore
from afk.tools import ToolRegistry


def run_async(coro):
    return asyncio.run(coro)


def test_mcp_store_materializes_remote_tools_and_executes_call():
    store = MCPStore()
    seen_methods: list[str] = []

    async def fake_jsonrpc(self, server, *, method: str, params: dict):
        _ = self
        _ = server
        seen_methods.append(method)
        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": "add",
                        "description": "Add two integers",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "a": {"type": "integer"},
                                "b": {"type": "integer"},
                            },
                            "required": ["a", "b"],
                        },
                    }
                ]
            }
        if method == "tools/call":
            assert params["name"] == "add"
            assert params["arguments"] == {"a": 1, "b": 2}
            return {
                "content": [{"type": "text", "text": "3"}],
                "isError": False,
            }
        raise AssertionError(f"Unexpected method: {method}")

    store._jsonrpc = types.MethodType(fake_jsonrpc, store)

    tools = run_async(store.tools_from_servers(["calc=https://fake.example/mcp"]))
    assert [tool.spec.name for tool in tools] == ["calc__add"]

    registry = ToolRegistry()
    registry.register_many(tools)
    result = run_async(registry.call("calc__add", {"a": 1, "b": 2}))

    assert result.success is True
    assert result.output == "3"
    assert seen_methods.count("tools/list") == 1
    assert seen_methods.count("tools/call") == 1


def test_mcp_store_list_tools_uses_cache_until_refresh():
    store = MCPStore()
    tool_list_calls = 0

    async def fake_jsonrpc(self, server, *, method: str, params: dict):
        _ = self
        _ = server
        _ = params
        nonlocal tool_list_calls
        if method == "tools/list":
            tool_list_calls += 1
            return {"tools": [{"name": "echo", "inputSchema": {"type": "object"}}]}
        raise AssertionError(f"Unexpected method: {method}")

    store._jsonrpc = types.MethodType(fake_jsonrpc, store)

    ref = "svc=https://fake.example/mcp"
    first = run_async(store.list_tools(ref))
    second = run_async(store.list_tools(ref))
    refreshed = run_async(store.list_tools(ref, refresh=True))

    assert [tool.name for tool in first] == ["echo"]
    assert [tool.name for tool in second] == ["echo"]
    assert [tool.name for tool in refreshed] == ["echo"]
    assert tool_list_calls == 2


def test_mcp_remote_tool_error_surfaces_as_failed_tool_result():
    store = MCPStore()

    async def fake_jsonrpc(self, server, *, method: str, params: dict):
        _ = self
        _ = server
        _ = params
        if method == "tools/list":
            return {
                "tools": [
                    {
                        "name": "explode",
                        "description": "Always fails",
                        "inputSchema": {"type": "object"},
                    }
                ]
            }
        if method == "tools/call":
            return {
                "content": [{"type": "text", "text": "remote boom"}],
                "isError": True,
            }
        raise AssertionError(f"Unexpected method: {method}")

    store._jsonrpc = types.MethodType(fake_jsonrpc, store)

    tools = run_async(store.tools_from_servers(["svc=https://fake.example/mcp"]))
    registry = ToolRegistry()
    registry.register_many(tools)

    result = run_async(registry.call("svc__explode", {}))

    assert result.success is False
    assert result.error_message is not None
    assert "remote boom" in result.error_message
