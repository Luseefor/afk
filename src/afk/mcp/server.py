"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

MCP (Model Context Protocol) server built on FastAPI.

Exposes tools from a ``ToolRegistry`` as MCP-compatible endpoints,
following the JSON-RPC 2.0 wire format specified by the MCP standard.

Supports:
- ``initialize`` — server capability handshake
- ``tools/list`` — discover available tools
- ``tools/call`` — execute a tool
- SSE transport for streaming JSON-RPC responses
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, Iterable

try:
    from fastapi import Request as FastAPIRequest
    from fastapi.responses import Response as FastAPIResponse
except Exception:  # pragma: no cover
    FastAPIRequest = Any  # type: ignore[assignment]
    FastAPIResponse = Any  # type: ignore[assignment]

from ..tools import ToolRegistry, ToolContext

logger = logging.getLogger("afk.mcp")

MCP_PROTOCOL_VERSION = "2026-02-20"


# ---------------------------------------------------------------------------
# MCP server configuration
# ---------------------------------------------------------------------------


@dataclass
class MCPServerConfig:
    """
    Configuration for the MCP server.

    Attributes:
        name: Server name advertised during ``initialize``.
        version: Server version string.
        host: Bind host for the FastAPI server.
        port: Bind port for the FastAPI server.
        instructions: Optional instructions describing the server's purpose.
        cors_origins: List of allowed CORS origins.
        mcp_path: JSON-RPC endpoint path.
        sse_path: SSE endpoint path.
        health_path: Health endpoint path.
        enable_sse: Whether to expose SSE endpoint.
        enable_health: Whether to expose health endpoint.
        allow_batch_requests: Whether JSON-RPC batch requests are accepted.
    """

    name: str = "afk-mcp-server"
    version: str = "1.0.0"
    host: str = "0.0.0.0"
    port: int = 8000
    instructions: str | None = None
    cors_origins: list[str] = field(default_factory=lambda: ["*"])
    mcp_path: str = "/mcp"
    sse_path: str = "/mcp/sse"
    health_path: str = "/health"
    enable_sse: bool = True
    enable_health: bool = True
    allow_batch_requests: bool = True


# ---------------------------------------------------------------------------
# JSON-RPC helpers
# ---------------------------------------------------------------------------


def _jsonrpc_response(id: Any, result: Any) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 success response."""
    return {"jsonrpc": "2.0", "id": id, "result": result}


def _jsonrpc_error(
    id: Any, code: int, message: str, data: Any = None
) -> dict[str, Any]:
    """Build a JSON-RPC 2.0 error response."""
    error: dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return {"jsonrpc": "2.0", "id": id, "error": error}


# Standard JSON-RPC error codes
PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------


class MCPServer:
    """
    MCP server that exposes ``ToolRegistry`` tools via FastAPI.

    Implements the Model Context Protocol over HTTP with JSON-RPC 2.0
    message format. Tools are automatically discovered from the registry.

    Usage::

        from afk.tools import ToolRegistry, tool
        from afk.mcp import MCPServer

        registry = ToolRegistry()

        @tool(name="greet", description="Greet someone")
        def greet(name: str) -> str:
            return f"Hello, {name}!"

        registry.register(greet)

        server = MCPServer(registry)
        server.run()  # starts FastAPI on port 8000

    Endpoints:
        ``POST /mcp`` — JSON-RPC 2.0 endpoint for ``initialize``, ``tools/list``, ``tools/call``
        ``GET /mcp/sse`` — SSE transport (Server-Sent Events)
        ``GET /health`` — Health check

    Args:
        registry: ``ToolRegistry`` containing tools to expose.
        config: Server configuration.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        *,
        config: MCPServerConfig | None = None,
        app: Any | None = None,
    ) -> None:
        self._registry = registry
        self._config = config or MCPServerConfig()
        self._app = app or self._create_app()
        if app is not None:
            self.mount(app)

    @classmethod
    def from_tools(
        cls,
        tools: Iterable[Any],
        *,
        config: MCPServerConfig | None = None,
        app: Any | None = None,
    ) -> "MCPServer":
        """
        Build an MCP server from an iterable of AFK tools.

        This is a DX-focused convenience for simple setups where callers have
        tools but not an explicit ``ToolRegistry`` instance.
        """
        registry = ToolRegistry()
        registry.register_many(tools)
        return cls(registry, config=config, app=app)

    @property
    def app(self):
        """
        The FastAPI application instance.

        Use this to mount the MCP server into an existing app or for testing::

            from fastapi.testclient import TestClient
            client = TestClient(server.app)
        """
        return self._app

    @property
    def config(self) -> MCPServerConfig:
        """Server configuration."""
        return self._config

    def _create_router(self):
        """Build an APIRouter containing MCP routes."""
        try:
            from fastapi import APIRouter
            from fastapi.responses import JSONResponse, StreamingResponse
        except ImportError:
            raise ImportError(
                "FastAPI is required for MCPServer. "
                "Install it with: pip install fastapi uvicorn"
            )

        router = APIRouter()

        if self._config.enable_health:

            @router.get(self._config.health_path)
            async def health():
                return {
                    "status": "ok",
                    "server": self._config.name,
                    "version": self._config.version,
                    "tools_count": len(self._registry.names()),
                }

        @router.post(self._config.mcp_path)
        async def mcp_endpoint(request: FastAPIRequest):
            """Main JSON-RPC 2.0 endpoint for MCP."""
            try:
                body = await request.json()
            except Exception:
                return JSONResponse(
                    _jsonrpc_error(None, PARSE_ERROR, "Parse error"),
                    status_code=200,
                )

            if isinstance(body, list):
                if not self._config.allow_batch_requests:
                    return JSONResponse(
                        _jsonrpc_error(None, INVALID_REQUEST, "Batch requests disabled"),
                        status_code=200,
                    )
                responses = []
                for item in body:
                    resp = await self._handle_jsonrpc(item)
                    if resp is not None:
                        responses.append(resp)
                return JSONResponse(responses, status_code=200)

            result = await self._handle_jsonrpc(body)
            if result is None:
                return FastAPIResponse(status_code=204)
            return JSONResponse(result, status_code=200)

        if self._config.enable_sse:

            @router.get(self._config.sse_path)
            async def sse_endpoint(request: FastAPIRequest):
                """SSE transport for MCP — sends JSON-RPC messages as events."""
                _ = request
                import asyncio

                session_id = uuid.uuid4().hex

                async def event_stream():
                    endpoint_data = json.dumps(
                        {
                            "endpoint": self._config.mcp_path,
                            "sessionId": session_id,
                        }
                    )
                    yield f"event: endpoint\ndata: {endpoint_data}\n\n"

                    try:
                        while True:
                            await asyncio.sleep(30)
                            yield ": heartbeat\n\n"
                    except asyncio.CancelledError:
                        pass

                return StreamingResponse(
                    event_stream(),
                    media_type="text/event-stream",
                    headers={
                        "Cache-Control": "no-cache",
                        "Connection": "keep-alive",
                        "X-Accel-Buffering": "no",
                    },
                )

        return router

    def _create_app(self):
        """Build the FastAPI application with MCP routes."""
        try:
            from fastapi import FastAPI
            from fastapi.middleware.cors import CORSMiddleware
        except ImportError:
            raise ImportError(
                "FastAPI is required for MCPServer. "
                "Install it with: pip install fastapi uvicorn"
            )

        app = FastAPI(
            title=self._config.name,
            version=self._config.version,
            description="AFK MCP Server — Model Context Protocol",
        )

        app.add_middleware(
            CORSMiddleware,
            allow_origins=self._config.cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        app.include_router(self._create_router())
        return app

    def mount(self, app: Any) -> Any:
        """
        Mount MCP routes into an existing FastAPI app.

        Returns the provided app for fluent usage.
        """
        app.include_router(self._create_router())
        return app

    async def _handle_jsonrpc(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """
        Route a JSON-RPC 2.0 message to the appropriate handler.
        """
        if not isinstance(message, dict):
            return _jsonrpc_error(None, INVALID_REQUEST, "Invalid Request")

        jsonrpc = message.get("jsonrpc")
        if jsonrpc != "2.0":
            return _jsonrpc_error(
                message.get("id"), INVALID_REQUEST, "Invalid JSON-RPC version"
            )

        method = message.get("method")
        params = message.get("params", {})
        msg_id = message.get("id")

        if not method:
            return _jsonrpc_error(msg_id, INVALID_REQUEST, "Missing method")

        is_notification = msg_id is None

        try:
            if method == "initialize":
                result = self._handle_initialize(params)
            elif method == "tools/list":
                result = self._handle_tools_list(params)
            elif method == "tools/call":
                result = await self._handle_tools_call(params)
            elif method == "ping":
                result = {}
            elif method == "notifications/initialized":
                if is_notification:
                    return None
                return _jsonrpc_response(msg_id, {})
            else:
                return _jsonrpc_error(
                    msg_id, METHOD_NOT_FOUND, f"Method not found: {method}"
                )

            if is_notification:
                return None
            return _jsonrpc_response(msg_id, result)

        except Exception as exc:
            logger.exception("Error handling MCP method %s", method)
            return _jsonrpc_error(msg_id, INTERNAL_ERROR, str(exc))

    def _handle_initialize(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ``initialize`` — return server capabilities."""
        return {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {
                "tools": {
                    "listChanged": False,
                },
            },
            "serverInfo": {
                "name": self._config.name,
                "version": self._config.version,
            },
            **(
                {"instructions": self._config.instructions}
                if self._config.instructions
                else {}
            ),
        }

    def _handle_tools_list(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ``tools/list`` — return registered tools as MCP tool schemas."""
        tools = []
        for tool_obj in self._registry.list():
            spec = tool_obj.spec
            tools.append(
                {
                    "name": spec.name,
                    "description": spec.description,
                    "inputSchema": {
                        "type": "object",
                        **(spec.parameters_schema or {}),
                    },
                }
            )
        return {"tools": tools}

    async def _handle_tools_call(self, params: dict[str, Any]) -> dict[str, Any]:
        """Handle ``tools/call`` — execute a tool and return result."""
        tool_name = params.get("name")
        if not tool_name:
            raise ValueError("Missing 'name' in tools/call params")

        arguments = params.get("arguments", {})
        if not isinstance(arguments, dict):
            raise ValueError("'arguments' must be an object")

        # Create tool context with MCP metadata
        ctx = ToolContext(
            request_id=uuid.uuid4().hex,
            metadata={"source": "mcp", "tool_name": tool_name},
        )

        # Execute via registry (includes concurrency, timeout, middleware)
        result = await self._registry.call(
            tool_name,
            arguments,
            ctx=ctx,
        )

        # Build MCP content response
        content: list[dict[str, Any]] = []

        if result.success:
            output = result.output
            if isinstance(output, str):
                content.append({"type": "text", "text": output})
            elif output is not None:
                content.append(
                    {
                        "type": "text",
                        "text": json.dumps(output, default=str),
                    }
                )
            else:
                content.append({"type": "text", "text": ""})
        else:
            content.append(
                {
                    "type": "text",
                    "text": result.error_message or "Tool execution failed",
                }
            )

        return {
            "content": content,
            "isError": not result.success,
        }

    def run(self, **kwargs: Any) -> None:
        """
        Start the MCP server using uvicorn.

        Args:
            **kwargs: Additional arguments passed to ``uvicorn.run()``.
        """
        try:
            import uvicorn
        except ImportError:
            raise ImportError(
                "uvicorn is required to run MCPServer. "
                "Install it with: pip install uvicorn"
            )

        uvicorn.run(
            self._app,
            host=kwargs.pop("host", self._config.host),
            port=kwargs.pop("port", self._config.port),
            **kwargs,
        )


def create_mcp_server(
    *,
    registry: ToolRegistry | None = None,
    tools: Iterable[Any] | None = None,
    config: MCPServerConfig | None = None,
    app: Any | None = None,
) -> MCPServer:
    """
    DX-first constructor for MCP servers.

    Callers can pass either an existing registry or a list of tools.
    """
    if registry is not None and tools is not None:
        raise ValueError("Pass either 'registry' or 'tools', not both")
    if registry is not None:
        return MCPServer(registry, config=config, app=app)
    return MCPServer.from_tools(tools or [], config=config, app=app)
