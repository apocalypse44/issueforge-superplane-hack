"""
IssueForge pipeline runner.

Usage (use the project venv — do not use system python):
    Windows PowerShell:  .\run.ps1 --issue https://github.com/superplanehq/superplane/issues/5368
    Git Bash:            ./run.sh --issue https://github.com/superplanehq/superplane/issues/5368
    Direct:              venv\\Scripts\\python run_local.py --issue ...

    python run_local.py "markdown files should render mermaid diagrams in view mode"
    python run_local.py --issue https://github.com/superplanehq/superplane/issues/5368 --full
    python run_local.py --all-eval

Requires: Node.js/npm, git. LLM: Groq (GROQ_API_KEY) or Ollama (LLM_PROVIDER=ollama).
For --issue: GITHUB_TOKEN (uses GitHub API if gh CLI is not installed).
For --full: GITHUB_TOKEN, OUTPUT_REPO. Optional: RENDER_API_KEY, RENDER_SERVICE_ID.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

try:
    from groq import Groq
except ImportError:
    Groq = None

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "scripts")
PROMPTS_DIR = os.path.join(os.path.dirname(__file__), "prompts")

sys.path.insert(0, SCRIPTS_DIR)
from validate_spec import parse_and_validate
from apply_patches import apply_file_changes, parse_llm_changes

EVAL_ISSUES = [
    "https://github.com/superplanehq/superplane/issues/5368",
    "https://github.com/superplanehq/superplane/issues/5366",
    "https://github.com/superplanehq/superplane/issues/5164",
    "https://github.com/superplanehq/superplane/issues/5704",
    "https://github.com/superplanehq/superplane/issues/5705",
]


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


def call_ollama(system_prompt, user_message, max_tokens=8000, model=None):
    base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/")
    model = model or os.environ.get("OLLAMA_MODEL", "qwen2.5-coder:7b")
    payload = json.dumps({
        "model": model,
        "stream": False,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "options": {"num_predict": max_tokens},
    }).encode()
    req = urllib.request.Request(
        f"{base}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=600) as resp:
            data = json.loads(resp.read())
        return data["message"]["content"]
    except urllib.error.URLError as e:
        print(f"ERROR: Ollama not reachable at {base} — install from https://ollama.com and run: ollama pull {model}")
        sys.exit(1)


def call_groq(system_prompt, user_message, max_tokens=8000, model=None):
    if Groq is None:
        print("ERROR: groq not installed. Run: pip install groq  (or set LLM_PROVIDER=ollama)")
        sys.exit(1)
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("ERROR: GROQ_API_KEY not set. Add it to issueforge/.env or use LLM_PROVIDER=ollama")
        sys.exit(1)
    client = Groq(api_key=api_key)
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


def call_llm(system_prompt, user_message, max_tokens=8000, model=None):
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    if provider == "ollama":
        return call_ollama(system_prompt, user_message, max_tokens, model)
    return call_groq(system_prompt, user_message, max_tokens, model)


def parse_issue_url(issue_url):
    match = re.search(r"github\.com/([^/]+/[^/]+)/issues/(\d+)", issue_url)
    if not match:
        return None
    return {"repo": match.group(1), "number": int(match.group(2)), "url": issue_url}


def github_api(method, path, token=None, data=None):
    url = f"https://api.github.com{path}"
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token and token not in ("ghp_...", "ghp_"):
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")
        raise RuntimeError(f"GitHub API {method} {path} failed ({e.code}): {detail}") from e


def _valid_github_token(token):
    return bool(token) and not token.startswith("ghp_...") and token != "ghp_"


def fetch_issue(issue_url):
    info = parse_issue_url(issue_url)
    if not info:
        print(f"ERROR: Could not parse issue URL: {issue_url}")
        sys.exit(1)

    load_env()
    token = os.environ.get("GITHUB_TOKEN")
    gh = shutil.which("gh")

    if gh and _valid_github_token(token):
        result = subprocess.run(
            [gh, "issue", "view", str(info["number"]), "--repo", info["repo"], "--json", "title,body"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            data = json.loads(result.stdout)
            text = f"{data['title']}\n\n{data['body']}"
            return {**info, "text": text, "title": data["title"]}
        print(f"gh failed ({result.stderr.strip()}), trying GitHub API...")

    try:
        data = github_api(
            "GET",
            f"/repos/{info['repo']}/issues/{info['number']}",
            token if _valid_github_token(token) else None,
        )
    except RuntimeError as e:
        print(f"ERROR: Could not fetch issue: {e}")
        sys.exit(1)

    text = f"{data['title']}\n\n{data.get('body') or ''}"
    return {**info, "text": text, "title": data["title"]}


def run_cmd(cmd, cwd, check=True):
    use_shell = os.name == "nt"
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, shell=use_shell)
    if check and result.returncode != 0:
        raise RuntimeError((result.stderr + "\n" + result.stdout).strip())
    return result


def step_spec(idea):
    print("\n" + "=" * 60)
    print("STAGE 1: Spec Agent")
    print("=" * 60)

    with open(os.path.join(PROMPTS_DIR, "spec_agent.md")) as f:
        system_prompt = f.read()

    raw = call_llm(system_prompt, idea, max_tokens=3000)
    spec, errors = parse_and_validate(raw)
    if errors:
        print("SPEC VALIDATION FAILED:")
        for e in errors:
            print(f"  - {e}")
        print(f"\nRaw LLM output:\n{raw[:500]}")
        return None

    print(f"Title: {spec['title']}")
    print(f"Summary: {spec['summary']}")
    print(f"Acceptance criteria: {len(spec.get('acceptance_criteria', []))}")
    print("SPEC: PASSED")
    return spec


def step_code(spec):
    print("\n" + "=" * 60)
    print("STAGE 2: Code Agent")
    print("=" * 60)

    with open(os.path.join(PROMPTS_DIR, "code_agent.md")) as f:
        system_prompt = f.read()

    raw = call_llm(system_prompt, f"## Specification\n\n{json.dumps(spec, indent=2)}", max_tokens=8000)

    try:
        changes = parse_llm_changes(raw)
    except ValueError as e:
        print(f"CODE PARSE FAILED: {e}")
        print(f"\nRaw LLM output:\n{raw[:500]}")
        return None

    print(f"Generated {len(changes)} files")
    if not any(c.get("path") == "package.json" for c in changes):
        print("WARNING: No package.json in output")
    print("CODE: PASSED")
    return changes


def ensure_vite_scaffold(project_dir):
    """Minimal Vite scaffold if the code agent omitted required files."""
    pkg_path = os.path.join(project_dir, "package.json")
    if not os.path.isfile(pkg_path):
        pkg = {
            "name": "issueforge-poc",
            "private": True,
            "version": "0.0.0",
            "type": "module",
            "scripts": {"dev": "vite", "build": "vite build", "preview": "vite preview"},
            "dependencies": {"react": "^18.3.1", "react-dom": "^18.3.1"},
            "devDependencies": {"@vitejs/plugin-react": "^4.3.1", "vite": "^5.4.0", "typescript": "^5.5.0"},
        }
        with open(pkg_path, "w") as f:
            json.dump(pkg, f, indent=2)

    index_html = os.path.join(project_dir, "index.html")
    if not os.path.isfile(index_html):
        with open(index_html, "w") as f:
            f.write(
                '<!DOCTYPE html><html><head><meta charset="UTF-8"/>'
                '<meta name="viewport" content="width=device-width,initial-scale=1"/>'
                '<title>IssueForge PoC</title></head><body><div id="root"></div>'
                '<script type="module" src="/src/main.tsx"></script></body></html>\n'
            )

    vite_config = os.path.join(project_dir, "vite.config.ts")
    if not os.path.isfile(vite_config):
        with open(vite_config, "w") as f:
            f.write(
                "import { defineConfig } from 'vite';\n"
                "import react from '@vitejs/plugin-react';\n"
                "export default defineConfig({ plugins: [react()] });\n"
            )

    src_dir = os.path.join(project_dir, "src")
    os.makedirs(src_dir, exist_ok=True)
    main_tsx = os.path.join(src_dir, "main.tsx")
    if not os.path.isfile(main_tsx):
        with open(main_tsx, "w") as f:
            f.write(
                "import React from 'react';\n"
                "import ReactDOM from 'react-dom/client';\n"
                "import App from './App';\n"
                "ReactDOM.createRoot(document.getElementById('root')!).render(<App />);\n"
            )

    app_tsx = os.path.join(src_dir, "App.tsx")
    if not os.path.isfile(app_tsx):
        with open(app_tsx, "w") as f:
            f.write("export default function App() { return <div>IssueForge PoC</div>; }\n")

    tsconfig = os.path.join(project_dir, "tsconfig.json")
    if not os.path.isfile(tsconfig):
        with open(tsconfig, "w") as f:
            json.dump({
                "compilerOptions": {
                    "target": "ES2020", "useDefineForClassFields": True,
                    "lib": ["ES2020", "DOM", "DOM.Iterable"], "module": "ESNext",
                    "skipLibCheck": True, "moduleResolution": "bundler",
                    "isolatedModules": True, "jsx": "react-jsx", "strict": True,
                    "noEmit": True,
                },
                "include": ["src"],
            }, f, indent=2)


def merge_file_changes(base, updates):
    by_path = {c["path"]: c for c in base}
    for c in updates:
        by_path[c["path"]] = {**c, "action": "modify" if c["path"] in by_path else c.get("action", "create")}
    return list(by_path.values())


def _src_uses_package(project_dir, package_name):
    src = os.path.join(project_dir, "src")
    if not os.path.isdir(src):
        return False
    needles = (
        f"from '{package_name}'",
        f'from "{package_name}"',
        f"require('{package_name}')",
    )
    for root, _, files in os.walk(src):
        for fname in files:
            if not fname.endswith((".tsx", ".ts", ".jsx", ".js")):
                continue
            with open(os.path.join(root, fname), encoding="utf-8") as f:
                content = f.read()
            if any(n in content for n in needles):
                return True
    return False


def sanitize_package_json(project_dir):
    """Fix common LLM-hallucinated npm package names."""
    pkg_path = os.path.join(project_dir, "package.json")
    if not os.path.isfile(pkg_path):
        return False

    with open(pkg_path, encoding="utf-8") as f:
        pkg = json.load(f)

    modified = False
    deps = pkg.get("dependencies", {})
    dev = pkg.setdefault("devDependencies", {})

    for bad, good in (("mermaid-react", "mermaid"), ("mermaidjs", "mermaid")):
        if bad in deps:
            del deps[bad]
            deps.setdefault(good, "^11.4.1")
            modified = True

    dev_only = ("vite", "@vitejs/plugin-react", "typescript")
    for name in list(deps.keys()):
        if name in dev_only or name.startswith("@types/"):
            dev.setdefault(name, deps.pop(name))
            modified = True

    # Pin known-good versions (LLM often hallucinates version numbers)
    known_good = {
        "vite": "^5.4.11",
        "@vitejs/plugin-react": "^4.3.4",
        "typescript": "^5.6.3",
        "react": "^18.3.1",
        "react-dom": "^18.3.1",
        "mermaid": "^11.4.1",
        "react-markdown": "^9.0.1",
        "remark-gfm": "^4.0.0",
        "react-diff-viewer-continued": "^4.2.2",
    }
    for section in (deps, dev):
        for name, version in list(section.items()):
            if name in known_good and not version.replace("^", "").replace("~", "")[0].isdigit():
                section[name] = known_good[name]
                modified = True
            # plugin-react has no 3.x line — LLM confuses it with vite's version
            if name == "@vitejs/plugin-react" and version.startswith("^3"):
                section[name] = known_good[name]
                modified = True
            # LLM hallucinates 3.13.x for react-diff-viewer-continued (latest is 4.x)
            if name == "react-diff-viewer-continued":
                section[name] = known_good[name]
                modified = True

    for dep_name in list(deps.keys()):
        if dep_name in ("react", "react-dom"):
            continue
        if not _src_uses_package(project_dir, dep_name):
            del deps[dep_name]
            modified = True
            print(f"  removed unused dep: {dep_name}")

    # Always pin compatible Vite stack (LLM mixes vite 5 with plugin-react 2.x)
    if "vite" in dev or "@vitejs/plugin-react" in dev or "vite" in deps:
        dev["vite"] = known_good["vite"]
        dev["@vitejs/plugin-react"] = known_good["@vitejs/plugin-react"]
        dev["typescript"] = known_good["typescript"]
        dev.setdefault("@types/react", "^18.3.12")
        dev.setdefault("@types/react-dom", "^18.3.1")
        modified = True

    if modified:
        pkg["dependencies"] = deps
        with open(pkg_path, "w", encoding="utf-8") as f:
            json.dump(pkg, f, indent=2)
        print("  sanitized package.json (fixed hallucinated deps)")

    return modified


def sanitize_sources(project_dir):
    """Fix hallucinated import paths in generated source files."""
    src = os.path.join(project_dir, "src")
    if not os.path.isdir(src):
        return
    for root, _, files in os.walk(src):
        for fname in files:
            if not fname.endswith((".tsx", ".ts", ".jsx", ".js")):
                continue
            path = os.path.join(root, fname)
            with open(path, encoding="utf-8") as f:
                text = f.read()
            if "mermaid-react" not in text:
                continue
            text = text.replace("mermaid-react", "mermaid")
            with open(path, "w", encoding="utf-8") as f:
                f.write(text)
            rel = os.path.relpath(path, project_dir)
            print(f"  sanitized imports in {rel}")


def materialize_project(changes, workdir, fresh=True):
    project_dir = os.path.join(workdir, "project")
    if fresh:
        if os.path.isdir(project_dir):
            shutil.rmtree(project_dir)
        os.makedirs(project_dir, exist_ok=True)

    results = apply_file_changes(project_dir, changes)
    for r in results:
        print(f"  {r}")

    if not fresh and any(c.get("path") == "package.json" for c in changes):
        nm = os.path.join(project_dir, "node_modules")
        if os.path.isdir(nm):
            shutil.rmtree(nm, ignore_errors=True)

    ensure_vite_scaffold(project_dir)
    sanitize_package_json(project_dir)
    sanitize_sources(project_dir)
    write_poc_gitignore(project_dir)
    return project_dir


def run_build_checks(project_dir):
    print("Running npm install...")
    install = run_cmd("npm install", project_dir, check=False)
    if install.returncode != 0:
        print("  retrying with --legacy-peer-deps...")
        install = run_cmd("npm install --legacy-peer-deps", project_dir, check=False)
    if install.returncode != 0:
        return False, install.stderr + "\n" + install.stdout

    print("Running npm run build...")
    build = run_cmd("npm run build", project_dir, check=False)
    if build.returncode != 0:
        return False, build.stderr + "\n" + build.stdout

    return True, ""


def step_verify(changes, workdir, fresh=True):
    print("\n" + "=" * 60)
    print("STAGE 3: Verifier")
    print("=" * 60)

    project_dir = materialize_project(changes, workdir, fresh=fresh)
    ok, errors = run_build_checks(project_dir)
    if ok:
        print("VERIFY: PASSED")
    else:
        print("VERIFY: FAILED")
        print(errors[-2000:])
    return ok, project_dir, errors


def step_fix(spec, changes, error_output):
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
{error_output[-8000:]}

Fix the errors and return the corrected file changes as a JSON array."""

    raw = call_llm(system_prompt, user_msg, max_tokens=8000)
    try:
        fixed = parse_llm_changes(raw)
        print(f"Fix agent returned {len(fixed)} file changes")
        return fixed
    except ValueError as e:
        print(f"FIX PARSE FAILED: {e}")
        return None


POC_GITIGNORE = """node_modules/
dist/
build/
.env
.env.local
.env.*.local
*.log
npm-debug.log*
.DS_Store
coverage/
.vite/
.cache/
"""


def write_poc_gitignore(project_dir):
    path = os.path.join(project_dir, ".gitignore")
    with open(path, "w", encoding="utf-8") as f:
        f.write(POC_GITIGNORE)


def get_default_branch(repo_slug, token):
    try:
        repo = github_api("GET", f"/repos/{repo_slug}", token)
        return repo.get("default_branch", "main")
    except RuntimeError:
        return "main"


def trigger_render_deploy():
    api_key = os.environ.get("RENDER_API_KEY", "")
    service_id = os.environ.get("RENDER_SERVICE_ID", "")
    if not api_key or not service_id:
        print("Render credentials not set — skipping deploy trigger")
        return ""

    req = urllib.request.Request(
        f"https://api.render.com/v1/services/{service_id}/deploys",
        data=b'{"clearCache": "do_not_clear"}',
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        deploy = json.loads(resp.read())

    deploy_id = deploy.get("id", "")
    print(f"Render deploy triggered: {deploy_id}")

    for i in range(18):
        time.sleep(10)
        status_req = urllib.request.Request(
            f"https://api.render.com/v1/services/{service_id}/deploys/{deploy_id}",
            headers={"Authorization": f"Bearer {api_key}"},
        )
        with urllib.request.urlopen(status_req, timeout=30) as resp:
            status = json.loads(resp.read()).get("status", "pending")
        print(f"  Render status: {status} ({i + 1}/18)")
        if status == "live":
            break
        if status in ("build_failed", "deactivated", "update_failed"):
            break

    svc_req = urllib.request.Request(
        f"https://api.render.com/v1/services/{service_id}",
        headers={"Authorization": f"Bearer {api_key}"},
    )
    with urllib.request.urlopen(svc_req, timeout=30) as resp:
        svc = json.loads(resp.read())
    return svc.get("serviceDetails", {}).get("url") or svc.get("url", "")


def ensure_repo_gitignore(repo_dir):
    """Keep PoC build artifacts out of the output repo root."""
    path = os.path.join(repo_dir, ".gitignore")
    marker = "pocs/**/node_modules/"
    extra = f"{marker}\npocs/**/dist/\n"
    if os.path.isfile(path):
        with open(path, encoding="utf-8") as f:
            content = f.read()
        if marker not in content:
            with open(path, "a", encoding="utf-8") as f:
                f.write("\n" + extra)
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(extra)


def copy_poc_tree(src, dest):
    """Copy built PoC into repo, excluding build artifacts."""
    ignore = shutil.ignore_patterns("node_modules", "dist", "build", ".git", ".vite", ".cache")
    if os.path.isdir(dest):
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=ignore)


def step_deploy(project_dir, issue_number, workdir):
    print("\n" + "=" * 60)
    print("STAGE 4: Deploy")
    print("=" * 60)

    token = os.environ.get("GITHUB_TOKEN")
    repo_slug = os.environ.get("OUTPUT_REPO")
    if not _valid_github_token(token) or not repo_slug:
        print("ERROR: Set a real GITHUB_TOKEN and OUTPUT_REPO in .env for --full")
        return None

    branch = f"issueforge/{issue_number}"
    poc_path = f"pocs/{issue_number}"
    remote_url = f"https://x-access-token:{token}@github.com/{repo_slug}.git"
    base_branch = get_default_branch(repo_slug, token)

    repo_dir = os.path.join(workdir, "output_repo")
    if os.path.isdir(repo_dir):
        shutil.rmtree(repo_dir)

    print(f"Cloning {repo_slug} ({base_branch})...")
    clone = run_cmd(
        f'git clone --depth=1 --branch {base_branch} "{remote_url}" output_repo',
        workdir,
        check=False,
    )
    if clone.returncode != 0:
        print(f"Clone failed: {clone.stderr}")
        return None

    run_cmd(f"git checkout -B {branch}", repo_dir, check=False)
    run_cmd('git config user.email "issueforge@bot.local"', repo_dir, check=False)
    run_cmd('git config user.name "IssueForge"', repo_dir, check=False)
    ensure_repo_gitignore(repo_dir)

    poc_dest = os.path.join(repo_dir, poc_path)
    print(f"Copying PoC to {poc_path}/")
    copy_poc_tree(project_dir, poc_dest)
    write_poc_gitignore(poc_dest)

    run_cmd("git add -A", repo_dir)
    commit = run_cmd(
        f'git commit -m "feat: add PoC for issue #{issue_number}"',
        repo_dir,
        check=False,
    )
    if commit.returncode != 0 and "nothing to commit" not in (commit.stdout + commit.stderr).lower():
        print(f"Commit failed: {commit.stderr}")
        return None

    run_cmd(f"git push -u origin {branch}", repo_dir)

    preview_url = trigger_render_deploy()
    result = {
        "branch": branch,
        "preview_url": preview_url,
        "repo": repo_slug,
        "poc_path": poc_path,
        "base_branch": base_branch,
    }
    with open(os.path.join(workdir, "deploy_result.json"), "w") as f:
        json.dump(result, f, indent=2)

    print(f"Branch pushed: {branch} (from {base_branch})")
    print(f"PoC path: {poc_path}/")
    if preview_url:
        print(f"Preview: {preview_url}")
    print("DEPLOY: PASSED")
    return result


def step_pr(spec, issue_info, deploy_result, verify_attempts, workdir):
    print("\n" + "=" * 60)
    print("STAGE 5: PR")
    print("=" * 60)

    token = os.environ.get("GITHUB_TOKEN")
    repo_slug = os.environ.get("OUTPUT_REPO")
    if not _valid_github_token(token) or not repo_slug:
        print("ERROR: Set a real GITHUB_TOKEN and OUTPUT_REPO in .env for PR creation")
        return None

    issue_number = issue_info["number"]
    source = issue_info.get("url", f"superplanehq/superplane#{issue_number}")
    branch = deploy_result["branch"]
    preview_url = deploy_result.get("preview_url", "")
    poc_path = deploy_result.get("poc_path", "")

    ac_lines = "\n".join(
        f"- {ac['id']}: {ac['description']}" for ac in spec.get("acceptance_criteria", [])
    )
    impl_lines = "\n".join(f"- {step}" for step in spec.get("implementation_plan", []))
    preview_section = f"\n### Preview\n[{preview_url}]({preview_url})\n" if preview_url else ""
    poc_section = f"\n### PoC location\n`{poc_path}/` — run `npm install && npm run build` from that directory.\n" if poc_path else ""

    body = f"""## IssueForge — Automated PoC

Implements [{source}]({source})
{poc_section}
### Summary
{spec.get('summary', '')}

### Acceptance Criteria
{ac_lines}

### Implementation
{impl_lines}
{preview_section}
### Verification
- Build: **pass**
- Repair attempts: {verify_attempts}

---
*Generated by IssueForge*"""

    title = f"[IssueForge] {spec.get('title', f'PoC #{issue_number}')}"
    base_branch = deploy_result.get("base_branch") or get_default_branch(repo_slug, token)
    print(f"PR base branch: {base_branch}")

    pr_url = ""
    gh = shutil.which("gh")
    if gh:
        os.environ["GH_TOKEN"] = token
        result = subprocess.run(
            [gh, "pr", "create", "--repo", repo_slug, "--head", branch, "--base", base_branch, "--title", title, "--body", body],
            capture_output=True,
            text=True,
        )
        pr_url = result.stdout.strip() if result.returncode == 0 else ""

    if not pr_url:
        try:
            pr = github_api(
                "POST",
                f"/repos/{repo_slug}/pulls",
                token,
                {"title": title, "body": body, "head": branch, "base": base_branch},
            )
            pr_url = pr.get("html_url", "")
        except RuntimeError as e:
            if "already exists" in str(e).lower() or "422" in str(e):
                pulls = github_api(
                    "GET",
                    f"/repos/{repo_slug}/pulls?head={repo_slug.split('/')[0]}:{branch}&state=open",
                    token,
                )
                if pulls:
                    pr_url = pulls[0].get("html_url", "")
            if not pr_url:
                print(f"PR creation failed: {e}")
                pr_url = "unknown"

    print(f"PR: {pr_url}")
    with open(os.path.join(workdir, "pr_result.json"), "w") as f:
        json.dump({"pr_url": pr_url, "issue_number": issue_number}, f, indent=2)
    return pr_url


def run_pipeline(idea, issue_info, full_deploy, max_retries, keep):
    load_env()
    provider = os.environ.get("LLM_PROVIDER", "groq").lower()
    print(f"LLM provider: {provider}")

    print("\n" + "#" * 60)
    print("  ISSUEFORGE")
    print("#" * 60)
    print(f"\nInput: {idea[:200]}...")

    start = time.time()
    spec = step_spec(idea)
    if not spec:
        return False

    if issue_info:
        spec["issue_number"] = issue_info["number"]

    changes = step_code(spec)
    if not changes:
        return False

    output_base = os.path.join(os.path.dirname(__file__), "output")
    os.makedirs(output_base, exist_ok=True)
    workdir = tempfile.mkdtemp(prefix="run_", dir=output_base)

    with open(os.path.join(workdir, "spec.json"), "w") as f:
        json.dump(spec, f, indent=2)

    passed = False
    project_dir = None
    attempt = 0
    fix_delta = None

    while attempt <= max_retries:
        attempt += 1
        is_fresh = attempt == 1
        passed, project_dir, errors = step_verify(
            changes if is_fresh else fix_delta,
            workdir,
            fresh=is_fresh,
        )
        if passed:
            break
        if attempt > max_retries:
            break
        fix_delta = step_fix(spec, changes, errors)
        if not fix_delta:
            break
        changes = merge_file_changes(changes, fix_delta)

    with open(os.path.join(workdir, "verify_result.json"), "w") as f:
        json.dump({"status": "pass" if passed else "fail", "attempts": attempt}, f)

    pr_url = None
    if passed and full_deploy and issue_info:
        deploy_result = step_deploy(project_dir, issue_info["number"], workdir)
        if deploy_result:
            pr_url = step_pr(spec, issue_info, deploy_result, attempt, workdir)

    elapsed = time.time() - start
    print("\n" + "#" * 60)
    print("  RESULTS")
    print("#" * 60)
    print(f"Status:   {'PASSED' if passed else 'FAILED'}")
    print(f"Attempts: {attempt}")
    print(f"Duration: {elapsed:.1f}s")
    if project_dir:
        print(f"Output:   {project_dir}")
    if pr_url:
        print(f"PR:       {pr_url}")

    if not keep and not passed:
        shutil.rmtree(workdir, ignore_errors=True)

    return passed


def main():
    parser = argparse.ArgumentParser(description="IssueForge pipeline")
    parser.add_argument("idea", nargs="?", help="Vague feature description")
    parser.add_argument("--issue", help="GitHub issue URL")
    parser.add_argument("--full", action="store_true", help="Push branch, deploy Render, create PR")
    parser.add_argument("--all-eval", action="store_true", help="Run all 5 hackathon evaluation issues")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--keep", action="store_true")
    args = parser.parse_args()

    if args.full and not args.issue and not args.all_eval:
        parser.error("--full requires --issue or --all-eval")

    if args.all_eval:
        results = []
        for url in EVAL_ISSUES:
            print(f"\n\n{'#' * 60}\n  EVAL: {url}\n{'#' * 60}")
            info = fetch_issue(url)
            ok = run_pipeline(info["text"], info, args.full, args.max_retries, args.keep)
            results.append((url, ok))
        print("\n\nEVAL SUMMARY")
        for url, ok in results:
            print(f"  {'PASS' if ok else 'FAIL'}  {url}")
        sys.exit(0 if all(r[1] for r in results) else 1)

    if not args.idea and not args.issue:
        parser.error("Provide an idea, --issue URL, or --all-eval")

    issue_info = None
    if args.issue:
        issue_info = fetch_issue(args.issue)
        idea = issue_info["text"]
    else:
        idea = args.idea

    ok = run_pipeline(idea, issue_info, args.full, args.max_retries, args.keep)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
