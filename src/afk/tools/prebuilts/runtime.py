"""
MIT License
Copyright (c) 2026 arpan404
See LICENSE file for full license text.

General runtime-safe filesystem tools.
"""

from __future__ import annotations


from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from afk.tools.core import Tool
from afk.tools.core.decorator import tool
from afk.tools.prebuilts.errors import FileAccessError


class _ListDirectoryArgs(BaseModel):
    path: str = "."
    max_entries: int = Field(default=200, ge=1, le=5000)


class _ReadFileArgs(BaseModel):
    path: str = Field(min_length=1)
    max_chars: int = Field(default=20_000, ge=1, le=500_000)


def build_runtime_tools(*, root_dir: Path) -> list[Tool[Any, Any]]:
    root = root_dir.resolve()

    @tool(
        args_model=_ListDirectoryArgs,
        name="list_directory",
        description="List the contents of a directory. Returns a list of entries with their name, path, and type (file or directory).",
    )
    async def list_directory(args: _ListDirectoryArgs) -> dict[str, Any]:
        target = (root / args.path).resolve()
        _ensure_inside(target, root)
        if not target.exists() or not target.is_dir():
            raise FileAccessError(f"Directory not found: {args.path}")

        entries = []
        for row in sorted(target.iterdir()):
            entries.append(
                {
                    "name": row.name,
                    "path": str(row),
                    "is_dir": row.is_dir(),
                    "is_file": row.is_file(),
                }
            )
            if len(entries) >= args.max_entries:
                break
        return {"root": str(root), "path": str(target), "entries": entries}

    @tool(
        args_model=_ReadFileArgs,
        name="read_file",
        description="Read the contents of a file.",
    )
    async def read_file(args: _ReadFileArgs) -> dict[str, Any]:
        target = (root / args.path).resolve()
        _ensure_inside(target, root)
        if not target.exists() or not target.is_file():
            raise FileAccessError(f"File not found: {args.path}")
        text = target.read_text(encoding="utf-8")
        truncated = len(text) > args.max_chars
        if truncated:
            text = text[: args.max_chars]
        return {
            "root": str(root),
            "path": str(target),
            "content": text,
            "truncated": truncated,
        }

    return [list_directory, read_file]


def _ensure_inside(path: Path, root: Path) -> None:
    """
    Ensures that the given path is inside the root directory.
    Raises FileAccessError if the path escapes the root.
    """
    try:
        path.relative_to(root)
    except ValueError as e:
        raise FileAccessError(f"Path '{path}' escapes root '{root}'") from e
