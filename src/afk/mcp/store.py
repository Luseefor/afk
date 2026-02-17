"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

External MCP server registry/store and AFK tool materialization helpers.
"""

from __future__ import annotations

import asyncio
import json
import re
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable

from pydantic import BaseModel, ConfigDict

from ..tools import Tool, ToolContext, ToolSpec


@dataclass(frozen=True, slots=True)
class MCPServerRef:
    """
    External MCP server reference.

    Attributes:
        name: Stable local alias for the external MCP server.
        url: JSON-RPC endpoint URL (for example: http://localhost:8000/mcp).
        headers: Optional HTTP headers sent with each request.
        timeout_s: HTTP timeout in seconds for `tools/list` and `tools/call`.
        prefix_tools: Whether generated AFK tool names should be prefixed.
        tool_name_prefix: Optional explicit prefix override.
    """

    name: str
    url: str
    headers: dict[str, str] = field(default_factory=dict)
    timeout_s: float = 20.0
    prefix_tools: bool = True
    tool_name_prefix: str | None = None


@dataclass(frozen=True, slots=True)
class MCPRemoteTool:
    """Normalized remote MCP tool descriptor."""

    server_name: str
    name: str
    qualified_name: str
    description: str
    input_schema: dict[str, Any]


class MCPStoreError(RuntimeError):
    """Base MCP store error."""


class MCPServerResolutionError(MCPStoreError):
    """Raised when an MCP server reference cannot be resolved."""


class MCPRemoteProtocolError(MCPStoreError):
    """Raised when remote MCP response shape is invalid."""


class MCPRemoteCallError(MCPStoreError):
    """Raised when remote MCP server returns a call error."""


class _MCPArgs(BaseModel):
    """Permissive args model used for dynamic remote MCP tools."""

    model_config = ConfigDict(extra="allow")


class MCPStore:
    """
    Process-wide registry for external MCP servers.

    The store resolves server references, caches remote tool metadata and can
    materialize those tools as AFK `Tool` instances so existing runtime
    orchestration (policy/sandbox/replay/fail-safe) continues to apply.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._servers: dict[str, MCPServerRef] = {}
        self._tool_cache: dict[str, list[MCPRemoteTool]] = {}

    def register_server(self, ref: MCPServerRef) -> None:
        with self._lock:
            existing = self._servers.get(ref.name)
            self._servers[ref.name] = ref
            if existing is None or existing != ref:
                self._tool_cache.pop(ref.name, None)

    def unregister_server(self, name: str) -> None:
        with self._lock:
            self._servers.pop(name, None)
            self._tool_cache.pop(name, None)

    def clear(self) -> None:
        with self._lock:
            self._servers.clear()
            self._tool_cache.clear()

    def resolve_server(self, ref: str | dict[str, Any] | MCPServerRef) -> MCPServerRef:
        """Resolve a server reference from string/dict/dataclass form."""
        if isinstance(ref, MCPServerRef):
            self.register_server(ref)
            return ref

        if isinstance(ref, str):
            parsed = ref.strip()
            if not parsed:
                raise MCPServerResolutionError("MCP server reference cannot be empty")

            if "=" in parsed:
                name, url = parsed.split("=", 1)
                resolved = MCPServerRef(name=name.strip(), url=url.strip())
            else:
                if not parsed.startswith(("http://", "https://")):
                    raise MCPServerResolutionError(
                        "String MCP server refs must be 'name=url' or an http(s) URL"
                    )
                url_parts = urllib.parse.urlparse(parsed)
                base = url_parts.netloc or "mcp_server"
                derived_name = _sanitize_name(base.replace(":", "_"))
                resolved = MCPServerRef(name=derived_name, url=parsed)
            self.register_server(resolved)
            return resolved

        if isinstance(ref, dict):
            url = ref.get("url")
            if not isinstance(url, str) or not url.strip():
                raise MCPServerResolutionError("MCP server dict ref requires non-empty 'url'")
            name_raw = ref.get("name")
            if isinstance(name_raw, str) and name_raw.strip():
                name = name_raw.strip()
            else:
                netloc = urllib.parse.urlparse(url).netloc or "mcp_server"
                name = _sanitize_name(netloc.replace(":", "_"))
            headers = ref.get("headers") or {}
            if not isinstance(headers, dict):
                raise MCPServerResolutionError("MCP server 'headers' must be a dict")
            timeout_s = ref.get("timeout_s", 20.0)
            if not isinstance(timeout_s, (int, float)) or timeout_s <= 0:
                raise MCPServerResolutionError("MCP server 'timeout_s' must be > 0")
            prefix_tools = bool(ref.get("prefix_tools", True))
            tool_name_prefix = ref.get("tool_name_prefix")
            if tool_name_prefix is not None and not isinstance(tool_name_prefix, str):
                raise MCPServerResolutionError(
                    "MCP server 'tool_name_prefix' must be a string when set"
                )
            resolved = MCPServerRef(
                name=name,
                url=url.strip(),
                headers={str(k): str(v) for k, v in headers.items()},
                timeout_s=float(timeout_s),
                prefix_tools=prefix_tools,
                tool_name_prefix=tool_name_prefix.strip()
                if isinstance(tool_name_prefix, str) and tool_name_prefix.strip()
                else None,
            )
            self.register_server(resolved)
            return resolved

        raise MCPServerResolutionError(
            f"Unsupported MCP server reference type: {type(ref).__name__}"
        )

    async def list_tools(
        self,
        ref: str | dict[str, Any] | MCPServerRef,
        *,
        refresh: bool = False,
    ) -> list[MCPRemoteTool]:
        """List remote MCP tools for one server, using cache by default."""
        server = self.resolve_server(ref)
        with self._lock:
            if not refresh and server.name in self._tool_cache:
                return list(self._tool_cache[server.name])

        response = await self._jsonrpc(server, method="tools/list", params={})
        tools = response.get("tools")
        if not isinstance(tools, list):
            raise MCPRemoteProtocolError(
                f"Invalid tools/list response from '{server.name}': missing tools list"
            )

        normalized: list[MCPRemoteTool] = []
        for row in tools:
            if not isinstance(row, dict):
                continue
            name = row.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            description = row.get("description")
            schema = row.get("inputSchema")
            normalized.append(
                MCPRemoteTool(
                    server_name=server.name,
                    name=name,
                    qualified_name=self._qualified_tool_name(server, name),
                    description=(description if isinstance(description, str) else name),
                    input_schema=(schema if isinstance(schema, dict) else {"type": "object"}),
                )
            )

        with self._lock:
            self._tool_cache[server.name] = list(normalized)
        return normalized

    async def call_tool(
        self,
        ref: str | dict[str, Any] | MCPServerRef,
        *,
        tool_name: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Call one remote MCP tool and return raw MCP result payload."""
        server = self.resolve_server(ref)
        response = await self._jsonrpc(
            server,
            method="tools/call",
            params={"name": tool_name, "arguments": arguments},
        )
        if not isinstance(response, dict):
            raise MCPRemoteProtocolError(
                f"Invalid tools/call response from '{server.name}' for '{tool_name}'"
            )

        if bool(response.get("isError")):
            message = _extract_mcp_text(response.get("content")) or "Remote MCP tool error"
            raise MCPRemoteCallError(f"{server.name}:{tool_name}: {message}")

        return response

    async def tools_from_servers(
        self,
        refs: Iterable[str | dict[str, Any] | MCPServerRef],
    ) -> list[Tool[Any, Any]]:
        """
        Materialize AFK tools from one or more external MCP servers.
        """
        tools: list[Tool[Any, Any]] = []
        for ref in refs:
            server = self.resolve_server(ref)
            remote_tools = await self.list_tools(server)
            for remote in remote_tools:
                invoke = self._make_remote_tool_fn(server=server, remote=remote)

                spec = ToolSpec(
                    name=remote.qualified_name,
                    description=remote.description,
                    parameters_schema=normalize_json_schema(remote.input_schema),
                )
                tools.append(
                    Tool(
                        spec=spec,
                        fn=invoke,
                        args_model=_MCPArgs,
                    )
                )
        return tools

    def _make_remote_tool_fn(
        self,
        *,
        server: MCPServerRef,
        remote: MCPRemoteTool,
    ):
        async def _invoke(args: _MCPArgs, ctx: ToolContext) -> Any:
            _ = ctx
            raw = args.model_dump(mode="python")
            result = await self.call_tool(
                server,
                tool_name=remote.name,
                arguments=raw,
            )
            text = _extract_mcp_text(result.get("content"))
            if text is not None:
                return text
            return result

        return _invoke

    async def _jsonrpc(
        self,
        server: MCPServerRef,
        *,
        method: str,
        params: dict[str, Any],
    ) -> dict[str, Any]:
        request_body = {
            "jsonrpc": "2.0",
            "id": uuid.uuid4().hex,
            "method": method,
            "params": params,
        }
        payload = json.dumps(request_body).encode("utf-8")
        response_bytes = await asyncio.to_thread(
            self._http_post,
            server,
            payload,
        )
        try:
            decoded = json.loads(response_bytes.decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            raise MCPRemoteProtocolError(
                f"Invalid JSON response from MCP server '{server.name}'"
            ) from e

        if not isinstance(decoded, dict):
            raise MCPRemoteProtocolError(
                f"Invalid JSON-RPC envelope from MCP server '{server.name}'"
            )

        err = decoded.get("error")
        if isinstance(err, dict):
            message = err.get("message") if isinstance(err.get("message"), str) else ""
            raise MCPRemoteCallError(
                f"MCP server '{server.name}' method '{method}' failed: {message or err}"
            )

        result = decoded.get("result")
        if not isinstance(result, dict):
            raise MCPRemoteProtocolError(
                f"Missing JSON-RPC result object from MCP server '{server.name}'"
            )
        return result

    def _http_post(self, server: MCPServerRef, payload: bytes) -> bytes:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            **server.headers,
        }
        req = urllib.request.Request(
            server.url,
            data=payload,
            method="POST",
            headers=headers,
        )
        try:
            with urllib.request.urlopen(req, timeout=server.timeout_s) as resp:  # noqa: S310
                return resp.read()
        except urllib.error.HTTPError as e:
            body = ""
            try:
                body = e.read().decode("utf-8", errors="replace")
            except Exception:  # noqa: BLE001
                body = ""
            raise MCPRemoteCallError(
                f"HTTP {e.code} calling MCP server '{server.name}': {body or e.reason}"
            ) from e
        except urllib.error.URLError as e:
            raise MCPRemoteCallError(
                f"Network error calling MCP server '{server.name}': {e.reason}"
            ) from e

    def _qualified_tool_name(self, server: MCPServerRef, tool_name: str) -> str:
        if not server.prefix_tools:
            return tool_name
        prefix = server.tool_name_prefix or server.name
        safe_prefix = _sanitize_name(prefix)
        safe_tool = _sanitize_name(tool_name)
        return f"{safe_prefix}__{safe_tool}"


def _sanitize_name(value: str) -> str:
    out = re.sub(r"[^a-zA-Z0-9_]+", "_", value)
    out = out.strip("_")
    return out or "mcp"


def _extract_mcp_text(content: Any) -> str | None:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return None
    chunks: list[str] = []
    for row in content:
        if not isinstance(row, dict):
            continue
        text = row.get("text")
        if isinstance(text, str):
            chunks.append(text)
    if not chunks:
        return None
    return "\n".join(chunks)


def normalize_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """Ensure a safe object schema shape for model-facing tool definitions."""
    if not isinstance(schema, dict):
        return {
            "type": "object",
            "properties": {},
            "required": [],
            "additionalProperties": False,
        }

    out = dict(schema)

    # Tool parameter schemas should always be object-shaped.
    out["type"] = "object"

    properties_raw = out.get("properties")
    if not isinstance(properties_raw, dict):
        properties: dict[str, Any] = {}
    else:
        properties = {
            str(key): (value if isinstance(value, dict) else {})
            for key, value in properties_raw.items()
        }
    out["properties"] = properties

    required_raw = out.get("required")
    if isinstance(required_raw, list):
        required = [
            str(name)
            for name in required_raw
            if isinstance(name, str) and name in properties
        ]
    else:
        required = []
    out["required"] = required

    additional_properties = out.get("additionalProperties")
    if not isinstance(additional_properties, (bool, dict)):
        out["additionalProperties"] = False

    return out


_MCP_STORE: MCPStore | None = None
_MCP_STORE_LOCK = threading.Lock()


def get_mcp_store() -> MCPStore:
    """Return process-wide MCP store singleton."""
    global _MCP_STORE
    if _MCP_STORE is not None:
        return _MCP_STORE
    with _MCP_STORE_LOCK:
        if _MCP_STORE is None:
            _MCP_STORE = MCPStore()
    return _MCP_STORE


def reset_mcp_store() -> None:
    """Reset MCP store singleton (for tests)."""
    global _MCP_STORE
    with _MCP_STORE_LOCK:
        _MCP_STORE = None
