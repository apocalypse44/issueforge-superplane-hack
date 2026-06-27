from __future__ import annotations

import json
import os


def apply_file_changes(repo_dir: str, changes: list[dict]) -> list[str]:
    applied = []
    for change in changes:
        action = change.get("action", "create")
        rel_path = change["path"]
        content = change["content"]
        full_path = os.path.join(repo_dir, rel_path)

        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)

        applied.append(f"{action}: {rel_path}")

    return applied


def parse_llm_changes(text: str) -> list[dict]:
    try:
        start = text.find("[")
        if start != -1:
            obj, _ = json.JSONDecoder().raw_decode(text[start:])
            if isinstance(obj, list):
                return obj
        start = text.find("{")
        end = text.rfind("}") + 1
        if start == -1 or end == 0:
            raise ValueError("No JSON found in LLM output")
        obj = json.loads(text[start:end])
        if "changes" in obj:
            return obj["changes"]
        return [obj]
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse LLM change output: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 3:
        print("Usage: apply_patches.py <repo_dir> <changes.json>")
        sys.exit(1)

    repo_dir = sys.argv[1]
    with open(sys.argv[2]) as f:
        text = f.read()

    changes = parse_llm_changes(text)
    results = apply_file_changes(repo_dir, changes)
    for r in results:
        print(r)
