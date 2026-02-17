#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REQUIRED_CONCEPT_HEADERS = {
    "When To Read",
    "Required Features",
    "Failure Modes",
    "Examples",
    "Next Step",
}

SAFE_ICONS = {
    "rocket",
    "file-code",
    "play-circle",
    "shield",
    "database",
    "lock",
    "book",
    "folder",
    "code",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run AFK docs structure checks.")
    parser.add_argument("--docs-root", default="docs", help="Docs root directory")
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail when concept section headers are missing",
    )
    return parser.parse_args()


def check_nav_pages(docs_root: Path) -> list[str]:
    issues: list[str] = []
    cfg_path = docs_root / "docs.json"
    if not cfg_path.exists():
        return [f"missing docs config: {cfg_path}"]
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    pages = []
    for group in cfg.get("navigation", {}).get("groups", []):
        pages.extend(group.get("pages", []))
    for page in pages:
        p = docs_root / f"{page}.mdx"
        if not p.exists():
            issues.append(f"navigation page missing: {p}")
    return issues


def check_icons(docs_root: Path) -> list[str]:
    issues: list[str] = []
    icon_re = re.compile(r'icon="([^"]+)"')
    for path in docs_root.rglob("*.mdx"):
        text = path.read_text(encoding="utf-8")
        for icon in icon_re.findall(text):
            if icon not in SAFE_ICONS:
                issues.append(f"unsupported icon '{icon}' in {path}")
    return issues


def check_concept_sections(docs_root: Path) -> list[str]:
    issues: list[str] = []
    concept_dir = docs_root / "library"
    for path in sorted(concept_dir.glob("*.mdx")):
        if path.name in {
            "overview.mdx",
            "developer-guide.mdx",
            "api-reference.mdx",
            "full-module-reference.mdx",
            "public-imports-and-function-improvement.mdx",
            "tested-behaviors.mdx",
            "agentic-levels.mdx",
            "building-with-ai.mdx",
        }:
            continue
        text = path.read_text(encoding="utf-8")
        headers = set(re.findall(r"^##\s+(.+)$", text, flags=re.M))
        missing = sorted(REQUIRED_CONCEPT_HEADERS - headers)
        if missing:
            issues.append(f"{path}: missing sections: {', '.join(missing)}")
    return issues


def main() -> int:
    args = parse_args()
    docs_root = Path(args.docs_root).resolve()
    issues = []
    issues.extend(check_nav_pages(docs_root))
    issues.extend(check_icons(docs_root))
    section_issues = check_concept_sections(docs_root)
    if args.strict:
        issues.extend(section_issues)
    elif section_issues:
        print("[warn] Concept section issues (run with --strict to fail):")
        for issue in section_issues:
            print(f"- {issue}")

    if issues:
        print("Docs quality checks failed:")
        for issue in issues:
            print(f"- {issue}")
        return 1
    print("Docs quality checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
