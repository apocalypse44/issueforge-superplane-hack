import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from apply_patches import apply_file_changes


def test_create_new_file():
    with tempfile.TemporaryDirectory() as repo_dir:
        changes = [
            {
                "action": "create",
                "path": "src/components/NewWidget.tsx",
                "content": "export function NewWidget() { return <div>Hello</div>; }\n",
            }
        ]
        apply_file_changes(repo_dir, changes)
        created = os.path.join(repo_dir, "src", "components", "NewWidget.tsx")
        assert os.path.isfile(created)
        with open(created) as f:
            assert "NewWidget" in f.read()


def test_modify_existing_file():
    with tempfile.TemporaryDirectory() as repo_dir:
        fpath = os.path.join(repo_dir, "src", "app.ts")
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, "w") as f:
            f.write("const x = 1;\nconst y = 2;\n")

        changes = [
            {
                "action": "modify",
                "path": "src/app.ts",
                "content": "const x = 1;\nconst y = 2;\nconst z = 3;\n",
            }
        ]
        apply_file_changes(repo_dir, changes)
        with open(fpath) as f:
            content = f.read()
        assert "const z = 3" in content


def test_handles_nested_directories():
    with tempfile.TemporaryDirectory() as repo_dir:
        changes = [
            {
                "action": "create",
                "path": "src/deep/nested/dir/File.tsx",
                "content": "export default 'hi';\n",
            }
        ]
        apply_file_changes(repo_dir, changes)
        assert os.path.isfile(os.path.join(repo_dir, "src", "deep", "nested", "dir", "File.tsx"))
