"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

Provider-facing tool export utilities.

This module converts AFK tool/tool-spec objects into provider-compatible
function tool definitions used by OpenAI-compatible transports (OpenAI,
LiteLLM, etc.).
"""

from __future__ import annotations


from typing import Any, Iterable


def normalize_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    """
    Ensure schema is at least an object schema with properties.
    """
    if not isinstance(schema, dict):
        return {"type": "object", "properties": {}}

    out = dict(schema)
    out.setdefault("type", "object")
    out.setdefault("properties", {})
    return out


def toolspec_to_openai_tool(spec: Any) -> dict[str, Any]:
    """
    Convert a tool spec-like object into an OpenAI-compatible function tool.

    Required attributes on `spec`:
      - name: str
      - description: str
      - parameters_schema: dict
    """
    return {
        "type": "function",
        "function": {
            "name": spec.name,
            "description": spec.description,
            "parameters": normalize_json_schema(spec.parameters_schema),
        },
    }


def tool_to_openai_tool(tool: Any) -> dict[str, Any]:
    """Convert a tool-like object with `.spec` into a function tool."""
    return toolspec_to_openai_tool(tool.spec)


def to_openai_tools(tools: Iterable[Any]) -> list[dict[str, Any]]:
    """Convert tool-like objects into OpenAI-compatible function tools."""
    return [tool_to_openai_tool(tool) for tool in tools]


def to_openai_tools_from_specs(specs: Iterable[Any]) -> list[dict[str, Any]]:
    """Convert tool-spec-like objects into OpenAI-compatible function tools."""
    return [toolspec_to_openai_tool(spec) for spec in specs]


def export_tools_for_provider(
    tools: Iterable[Any],
    *,
    format: str = "openai",
) -> list[dict[str, Any]]:
    """
    Generic export entrypoint for OpenAI-compatible function tool payloads.

    Supported formats:
      - "openai" (default)
      - "litellm" (same schema)
      - "function"
      - "openai_function"
    """
    fmt = format.lower().strip()
    if fmt in ("openai", "litellm", "function", "openai_function"):
        return to_openai_tools(tools)
    raise ValueError(f"Unknown export format: {format}")
