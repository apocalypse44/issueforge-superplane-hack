"""
Stages for SuperPlane runnerBash nodes. Reuses run_local.py logic.

Usage:
    python scripts/superplane_stages.py fetch <issue_url> <workdir>
    python scripts/superplane_stages.py validate <workdir> <spec_text_file>
    python scripts/superplane_stages.py verify <workdir> <changes_json_file> <spec_json_file>
    python scripts/superplane_stages.py deploy <workdir> <project_dir> <issue_number>
    python scripts/superplane_stages.py pr <workdir> <spec_json> <issue_info_json> <deploy_result_json> <attempts>
"""

import json
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from run_local import (  # noqa: E402
    load_env,
    fetch_issue,
    parse_and_validate,
    parse_llm_changes,
    materialize_project,
    run_build_checks,
    step_deploy,
    step_pr,
    parse_issue_url,
    github_api,
    _valid_github_token,
)


def cmd_fetch(issue_url, workdir):
    info = parse_issue_url(issue_url)
    if not info:
        load_env()
        token = os.environ.get("GITHUB_TOKEN")
        if not _valid_github_token(token):
            raise SystemExit(f"Invalid issue URL and no GitHub token: {issue_url}")
        parts = issue_url.rstrip("/").split("/")
        num = int(parts[-1])
        repo = "/".join(parts[-4:-2])
        data = github_api("GET", f"/repos/{repo}/issues/{num}", token)
        info = {"repo": repo, "number": num, "url": issue_url, "text": f"{data['title']}\n\n{data.get('body') or ''}", "title": data["title"]}
    else:
        info = fetch_issue(issue_url)
    os.makedirs(workdir, exist_ok=True)
    with open(os.path.join(workdir, "issue.json"), "w") as f:
        json.dump(info, f, indent=2)
    with open(os.path.join(workdir, "idea.txt"), "w") as f:
        f.write(info["text"])
    return {
        "issue_url": issue_url,
        "issue_number": info["number"],
        "issue_title": info["title"],
        "issue_text": info["text"],
        "idea_file": f"{workdir}/idea.txt",
    }


def cmd_validate(workdir, spec_text_file):
    with open(spec_text_file) as f:
        raw = f.read()
    spec, errors = parse_and_validate(raw)
    if errors:
        raise SystemExit("Spec validation failed: " + "; ".join(errors))
    path = os.path.join(workdir, "spec.json")
    with open(path, "w") as f:
        json.dump(spec, f, indent=2)
    return {"spec_file": path, "title": spec["title"]}


def cmd_verify(workdir, changes_file, spec_file):
    with open(changes_file) as f:
        changes = parse_llm_changes(f.read())
    project_dir = materialize_project(changes, workdir, fresh=True)
    passed, errors = run_build_checks(project_dir)
    result_path = os.path.join(workdir, "verify_result.json")
    with open(result_path, "w") as f:
        json.dump({"status": "pass" if passed else "fail", "attempts": 1, "errors": errors[-2000:]}, f)
    if not passed:
        raise SystemExit(f"Verify failed: {errors[-500:]}")
    return {"project_dir": project_dir, "verify_file": result_path, "attempts": 1}


def cmd_deploy(workdir, project_dir, issue_number):
    load_env()
    result = step_deploy(project_dir, int(issue_number), workdir)
    if not result:
        raise SystemExit("Deploy failed")
    return result


def cmd_pr(workdir, spec_file, issue_file, deploy_file, attempts):
    load_env()
    with open(spec_file) as f:
        spec = json.load(f)
    with open(issue_file) as f:
        issue_info = json.load(f)
    with open(deploy_file) as f:
        deploy_result = json.load(f)
    url = step_pr(spec, issue_info, deploy_result, int(attempts), workdir)
    return {"pr_url": url}


def main():
    load_env()
    stage = sys.argv[1]
    if stage == "fetch":
        print(json.dumps(cmd_fetch(sys.argv[2], sys.argv[3]), indent=2))
    elif stage == "validate":
        print(json.dumps(cmd_validate(sys.argv[2], sys.argv[3]), indent=2))
    elif stage == "verify":
        print(json.dumps(cmd_verify(sys.argv[2], sys.argv[3], sys.argv[4]), indent=2))
    elif stage == "deploy":
        print(json.dumps(cmd_deploy(sys.argv[2], sys.argv[3], sys.argv[4]), indent=2))
    elif stage == "pr":
        print(json.dumps(cmd_pr(sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]), indent=2))
    else:
        raise SystemExit(f"Unknown stage: {stage}")


if __name__ == "__main__":
    main()
