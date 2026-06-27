from __future__ import annotations

import os
import re
from pathlib import Path


SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", "coverage",
    "__pycache__", ".turbo", ".cache", "vendor",
}
CODE_EXTENSIONS = {
    ".ts", ".tsx", ".js", ".jsx", ".py", ".go", ".rs",
    ".css", ".scss", ".html", ".yaml", ".yml", ".json",
    ".md", ".mdx",
}
MAX_FILE_SIZE = 50_000


def find_relevant_files(
    repo_dir: str,
    issue_text: str,
    max_files: int = 15,
) -> list[dict]:
    keywords = _extract_keywords(issue_text)
    scored: list[tuple[float, str, str]] = []

    for root, dirs, files in os.walk(repo_dir):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for fname in files:
            ext = Path(fname).suffix
            if ext not in CODE_EXTENSIONS:
                continue
            fpath = os.path.join(root, fname)
            if os.path.getsize(fpath) > MAX_FILE_SIZE:
                continue
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except (OSError, UnicodeDecodeError):
                continue

            score = _score_file(fpath, content, keywords)
            if score > 0:
                rel_path = os.path.relpath(fpath, repo_dir)
                snippet = _extract_snippet(content, keywords)
                scored.append((score, rel_path, snippet))

    scored.sort(key=lambda x: x[0], reverse=True)
    return [
        {"path": path, "snippet": snippet, "score": score}
        for score, path, snippet in scored[:max_files]
    ]


def _extract_keywords(text: str) -> list[str]:
    stop_words = {
        "the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
        "or", "is", "are", "was", "were", "be", "been", "not", "no",
        "with", "from", "by", "as", "it", "that", "this", "should",
        "can", "will", "do", "does", "have", "has", "had", "but",
        "if", "when", "where", "how", "what", "which", "we", "they",
        "i", "you", "he", "she", "my", "your", "our", "their",
        "mode", "view", "file", "files", "properly", "render",
    }
    words = re.findall(r"[a-zA-Z][a-zA-Z0-9]*", text.lower())
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    camel = re.findall(r"[A-Z][a-z]+", text)
    keywords.extend([c.lower() for c in camel])
    return list(set(keywords))


def _score_file(path: str, content: str, keywords: list[str]) -> float:
    score = 0.0
    path_lower = path.lower()
    content_lower = content.lower()

    for kw in keywords:
        if kw in path_lower:
            score += 3.0
        count = content_lower.count(kw)
        if count > 0:
            score += min(count * 0.5, 5.0)

    if "test" in path_lower or "__test__" in path_lower or ".test." in path_lower:
        score *= 0.5
    if "component" in path_lower:
        score *= 1.2

    return score


def _extract_snippet(content: str, keywords: list[str], max_lines: int = 30) -> str:
    lines = content.split("\n")
    if len(lines) <= max_lines:
        return content

    best_start = 0
    best_score = 0
    for i in range(len(lines) - max_lines):
        window = "\n".join(lines[i : i + max_lines]).lower()
        score = sum(window.count(kw) for kw in keywords)
        if score > best_score:
            best_score = score
            best_start = i

    return "\n".join(lines[best_start : best_start + max_lines])


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 3:
        print("Usage: find_relevant_files.py <repo_dir> <issue_text> [max_files]")
        sys.exit(1)

    repo_dir = sys.argv[1]
    issue_text = sys.argv[2]
    max_files = int(sys.argv[3]) if len(sys.argv) > 3 else 15

    results = find_relevant_files(repo_dir, issue_text, max_files)
    print(json.dumps(results, indent=2))
