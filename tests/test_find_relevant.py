import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from find_relevant_files import find_relevant_files


def test_finds_files_by_keyword():
    with tempfile.TemporaryDirectory() as repo_dir:
        os.makedirs(os.path.join(repo_dir, "src", "components"), exist_ok=True)
        with open(os.path.join(repo_dir, "src", "components", "FileViewer.tsx"), "w") as f:
            f.write("export function FileViewer() { return <div>markdown</div>; }\n")
        with open(os.path.join(repo_dir, "src", "components", "Sidebar.tsx"), "w") as f:
            f.write("export function Sidebar() { return <div>nav</div>; }\n")

        issue_text = "markdown files should render properly in view mode"
        results = find_relevant_files(repo_dir, issue_text)

        paths = [r["path"] for r in results]
        assert any("FileViewer" in p for p in paths), f"Expected FileViewer in results, got {paths}"


def test_returns_path_and_snippet():
    with tempfile.TemporaryDirectory() as repo_dir:
        os.makedirs(os.path.join(repo_dir, "src"), exist_ok=True)
        content = "function render() { /* markdown logic */ }\n"
        with open(os.path.join(repo_dir, "src", "render.ts"), "w") as f:
            f.write(content)

        results = find_relevant_files(repo_dir, "markdown render")
        assert len(results) >= 1
        assert "path" in results[0]
        assert "snippet" in results[0]
        assert len(results[0]["snippet"]) > 0


def test_limits_results():
    with tempfile.TemporaryDirectory() as repo_dir:
        os.makedirs(os.path.join(repo_dir, "src"), exist_ok=True)
        for i in range(20):
            with open(os.path.join(repo_dir, "src", f"file{i}.ts"), "w") as f:
                f.write(f"// markdown related code {i}\n")

        results = find_relevant_files(repo_dir, "markdown", max_files=5)
        assert len(results) <= 5
