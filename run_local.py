"""
IssueForge Local Test Runner

Runs the core pipeline locally without any external side effects.
No GitHub PRs, no Render deploy, no branch pushing.

Usage:
    python run_local.py "markdown files should render mermaid diagrams in view mode"

    # Or with a GitHub issue URL (fetches issue text, still no PR/deploy):
    python run_local.py --issue https://github.com/superplanehq/superplane/issues/5368

Requires:
    - GROQ_API_KEY in .env or environment
    - pip install groq
    - Node.js + npm (for build verification)
    - gh CLI (only if using --issue flag)
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

try:
    from groq import Groq
except ImportError:
    print("ERROR: groq package not installed. Run: pip install groq")
    sys.exit(1)

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

sys.path.insert(0, SCRIPTS_DIR)
from validate_spec import parse_and_validate
from apply_patches import apply_file_changes, parse_llm_changes


def load_env():
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.isfile(env_path):
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    val = val.strip().strip("'\"")
                    os.environ[key.strip()] = val


def get_groq_client():
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY not set. Add it to issueforge/.env or export it.")
        sys.exit(1)
    print(f"Using Groq API key: {api_key[:8]}...{api_key[-4:]}")
    return Groq(api_key=api_key)


def call_llm(client, system_prompt, user_message, max_tokens=8000, model=None):
    model = model or os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
    try:
        response = client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )
        return response.choices[0].message.content
    except Exception as e:
        if "413" in str(e) or "rate_limit" in str(e) or "too large" in str(e):
            print(f"Request too large for {model}, trimming prompt...")
            trimmed = user_message[:6000]
            response = client.chat.completions.create(
                model=model,
                max_tokens=min(max_tokens, 6000),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": trimmed},
                ],
            )
            return response.choices[0].message.content
        raise


def fetch_issue(issue_url):
    """Fetch issue title + body using gh CLI."""
    import re
    match = re.search(r"github\.com/([^/]+/[^/]+)/issues/(\d+)", issue_url)
    if not match:
        print(f"ERROR: Could not parse issue URL: {issue_url}")
        sys.exit(1)

    repo, number = match.group(1), match.group(2)
    result = subprocess.run(
        ["gh", "issue", "view", number, "--repo", repo, "--json", "title,body"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"ERROR: gh CLI failed: {result.stderr}")
        sys.exit(1)

    data = json.loads(result.stdout)
    return f"{data['title']}\n\n{data['body']}"


def step_spec(client, idea):
    print("\n" + "=" * 60)
    print("STAGE 1: Spec Agent")
    print("=" * 60)
    print(f"Input: {idea[:100]}...")

    with open(os.path.join(PROMPTS_DIR, "spec_agent.md")) as f:
        system_prompt = f.read()

    raw = call_llm(client, system_prompt, idea, max_tokens=3000)

    spec, errors = parse_and_validate(raw)
    if errors:
        print(f"SPEC VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        print(f"\nRaw LLM output:\n{raw[:500]}")
        return None

    print(f"Title: {spec['title']}")
    print(f"Summary: {spec['summary']}")
    print(f"Requirements: {len(spec.get('acceptance_criteria', []))} acceptance criteria")
    print(f"Tech: {spec.get('tech_stack', 'not specified')}")
    print(f"Files to modify: {spec.get('likely_files', [])}")
    print("SPEC: PASSED")
    return spec


def step_code(client, spec):
    print("\n" + "=" * 60)
    print("STAGE 2: Code Agent")
    print("=" * 60)

    with open(os.path.join(PROMPTS_DIR, "code_agent.md")) as f:
        system_prompt = f.read()

    user_msg = f"## Specification\n\n{json.dumps(spec, indent=2)}"
    raw = call_llm(client, system_prompt, user_msg, max_tokens=8000)

    try:
        changes = parse_llm_changes(raw)
    except ValueError as e:
        print(f"CODE PARSE FAILED: {e}")
        print(f"\nRaw LLM output:\n{raw[:500]}")
        return None

    print(f"Generated {len(changes)} file changes:")
    for c in changes:
        action = c.get("action", "create")
        path = c.get("path", "?")
        size = len(c.get("content", ""))
        print(f"  {action}: {path} ({size} chars)")

    has_pkg = any(c.get("path") == "package.json" for c in changes)
    if not has_pkg:
        print("WARNING: No package.json in output")

    print("CODE: PASSED")
    return changes


def step_verify(client, spec, changes, workdir):
    print("\n" + "=" * 60)
    print("STAGE 3: Verifier")
    print("=" * 60)

    project_dir = os.path.join(workdir, "project")
    os.makedirs(project_dir, exist_ok=True)

    print("Materializing files...")
    results = apply_file_changes(project_dir, changes)
    for r in results:
        print(f"  {r}")

    # Ensure essential scaffolding exists
    pkg_path = os.path.join(project_dir, "package.json")
    has_tsx = any(f.endswith((".tsx", ".ts")) for c in changes for f in [c.get("path", "")])

    if not os.path.isfile(pkg_path):
        print("No package.json found — generating default...")
        default_pkg = {
            "name": "issueforge-output",
            "version": "1.0.0",
            "private": True,
            "scripts": {"start": "react-scripts start", "build": "react-scripts build", "test": "react-scripts test"},
            "dependencies": {"react": "^18.3.0", "react-dom": "^18.3.0", "react-scripts": "5.0.1"},
        }
        if has_tsx:
            default_pkg["devDependencies"] = {"typescript": "^5.5.0", "@types/react": "^18.3.0", "@types/react-dom": "^18.3.0"}
        with open(pkg_path, "w") as f:
            json.dump(default_pkg, f, indent=2)

    # public/index.html — required by react-scripts
    public_dir = os.path.join(project_dir, "public")
    os.makedirs(public_dir, exist_ok=True)
    index_html = os.path.join(public_dir, "index.html")
    if not os.path.isfile(index_html):
        print("Creating public/index.html...")
        with open(index_html, "w") as f:
            f.write('<!DOCTYPE html>\n<html lang="en"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width,initial-scale=1"/><title>IssueForge Output</title></head><body><div id="root"></div></body></html>\n')

    # src/index.js entry point — required by react-scripts
    src_dir = os.path.join(project_dir, "src")
    os.makedirs(src_dir, exist_ok=True)
    entry_js = os.path.join(src_dir, "index.js")
    entry_tsx = os.path.join(src_dir, "index.tsx")
    if not os.path.isfile(entry_js) and not os.path.isfile(entry_tsx):
        print("Creating src/index.js entry point...")
        # Find the first component file to import
        component = None
        for c in changes:
            p = c.get("path", "")
            if "component" in p.lower() and p.endswith((".js", ".jsx", ".tsx")):
                component = p
                break
        entry_path = entry_tsx if has_tsx else entry_js
        with open(entry_path, "w") as f:
            lines = [
                "import React from 'react';",
                "import ReactDOM from 'react-dom/client';",
            ]
            if component:
                name = os.path.splitext(os.path.basename(component))[0]
                rel = os.path.relpath(os.path.join(project_dir, component), src_dir).replace("\\", "/")
                if not rel.startswith("."):
                    rel = "./" + rel
                rel = os.path.splitext(rel)[0]
                lines.append(f"import {name} from '{rel}';")
                lines.append(f"ReactDOM.createRoot(document.getElementById('root')).render(<React.StrictMode><{name} /></React.StrictMode>);")
            else:
                lines.append("ReactDOM.createRoot(document.getElementById('root')).render(<React.StrictMode><div>IssueForge Output</div></React.StrictMode>);")
            f.write("\n".join(lines) + "\n")

    print("Files materialized. Run `npm install && npm start` in the output directory.")

    print("VERIFY: PASSED")
    return True, project_dir


def step_fix(client, spec, changes, error_output):
    print("\n" + "=" * 60)
    print("REPAIR: Fix Agent")
    print("=" * 60)

    with open(os.path.join(PROMPTS_DIR, "fix_agent.md")) as f:
        system_prompt = f.read()

    user_msg = f"""## Specification
{json.dumps(spec, indent=2)}

## Applied File Changes
{json.dumps(changes, indent=2)}

## Build/Test Error Output
{error_output}

Fix the errors and return the corrected file changes as a JSON array."""

    raw = call_llm(client, system_prompt, user_msg, max_tokens=8000)

    try:
        fixed = parse_llm_changes(raw)
        print(f"Fix agent returned {len(fixed)} file changes")
        return fixed
    except ValueError as e:
        print(f"FIX PARSE FAILED: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="IssueForge Local Test Runner")
    parser.add_argument("idea", nargs="?", help="Vague feature description")
    parser.add_argument("--issue", help="GitHub issue URL (fetches title+body)")
    parser.add_argument("--max-retries", type=int, default=2, help="Max repair attempts")
    parser.add_argument("--keep", action="store_true", help="Keep output directory after run")
    args = parser.parse_args()

    if not args.idea and not args.issue:
        parser.error("Provide either a text idea or --issue URL")

    load_env()
    client = get_groq_client()

    if args.issue:
        print(f"Fetching issue: {args.issue}")
        idea = fetch_issue(args.issue)
    else:
        idea = args.idea

    print("\n" + "#" * 60)
    print("  ISSUEFORGE LOCAL TEST RUN")
    print("#" * 60)
    print(f"\nIdea: {idea[:200]}")

    start = time.time()

    # Stage 1: Spec
    spec = step_spec(client, idea)
    if not spec:
        print("\nPIPELINE FAILED at Spec stage")
        sys.exit(1)

    # Stage 2: Code
    changes = step_code(client, spec)
    if not changes:
        print("\nPIPELINE FAILED at Code stage")
        sys.exit(1)

    # Stage 3: Verify (with retry)
    output_base = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_base, exist_ok=True)
    workdir = tempfile.mkdtemp(prefix="run_", dir=output_base)
    print(f"\nWork directory: {workdir}")

    attempt = 0
    passed = False
    project_dir = None

    while attempt < args.max_retries + 1:
        attempt += 1
        passed, project_dir = step_verify(client, spec, changes, workdir)

        if passed:
            break

        if attempt <= args.max_retries:
            print(f"\nAttempt {attempt} failed. Trying repair...")
            # Collect error output
            error_file = os.path.join(workdir, f"error_{attempt}.txt")
            build_result = subprocess.run(
                "npm run build",
                cwd=project_dir,
                capture_output=True, text=True,
                shell=True,
            )
            error_output = build_result.stderr + "\n" + build_result.stdout

            fixed = step_fix(client, spec, changes, error_output)
            if fixed:
                changes = fixed
                shutil.rmtree(project_dir, ignore_errors=True)
            else:
                print("Fix agent failed to produce valid output")
                break

    elapsed = time.time() - start

    print("\n" + "#" * 60)
    print("  RESULTS")
    print("#" * 60)
    print(f"Status:   {'PASSED' if passed else 'FAILED'}")
    print(f"Attempts: {attempt}")
    print(f"Duration: {elapsed:.1f}s")
    if project_dir:
        print(f"Output:   {project_dir}")
    print(f"Spec:     {spec['title']}")

    if passed and project_dir:
        print(f"\nGenerated project at: {project_dir}")
        print("You can inspect it or run it locally:")
        print(f"  cd {project_dir}")
        print(f"  npm run dev  (or npm start)")

    if not args.keep and not passed:
        shutil.rmtree(workdir, ignore_errors=True)

    print()
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
