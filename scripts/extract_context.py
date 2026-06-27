from __future__ import annotations

import json
import os


MAX_CONTEXT_CHARS = 80_000


def extract_context(
    repo_dir: str,
    relevant_files: list[dict],
    max_chars: int = MAX_CONTEXT_CHARS,
) -> str:
    sections = []
    total = 0

    for entry in relevant_files:
        fpath = os.path.join(repo_dir, entry["path"])
        if not os.path.isfile(fpath):
            continue
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read()
        except OSError:
            continue

        header = f"### File: {entry['path']}\n```\n"
        footer = "\n```\n\n"
        chunk = header + content + footer

        if total + len(chunk) > max_chars:
            remaining = max_chars - total - len(header) - len(footer)
            if remaining > 200:
                chunk = header + content[:remaining] + "\n... (truncated)" + footer
            else:
                break

        sections.append(chunk)
        total += len(chunk)

    return "".join(sections)


def build_agent_context(
    repo_dir: str,
    issue: dict,
    relevant_files: list[dict],
) -> str:
    parts = []

    parts.append(f"## Issue #{issue.get('number', '?')}: {issue.get('title', '')}\n")
    parts.append(f"{issue.get('body', '')}\n\n")

    parts.append("## Repository Info\n")
    pkg_path = os.path.join(repo_dir, "package.json")
    if os.path.isfile(pkg_path):
        with open(pkg_path, "r") as f:
            pkg = json.load(f)
        parts.append(f"- Name: {pkg.get('name', '?')}\n")
        deps = list(pkg.get("dependencies", {}).keys())[:20]
        parts.append(f"- Key deps: {', '.join(deps)}\n")
    parts.append("\n")

    parts.append("## Relevant Source Files\n\n")
    parts.append(extract_context(repo_dir, relevant_files))

    return "".join(parts)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 4:
        print("Usage: extract_context.py <repo_dir> <issue.json> <relevant_files.json>")
        sys.exit(1)

    repo_dir = sys.argv[1]
    with open(sys.argv[2]) as f:
        issue = json.load(f)
    with open(sys.argv[3]) as f:
        relevant = json.load(f)

    print(build_agent_context(repo_dir, issue, relevant))
