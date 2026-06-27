# IssueForge on SuperPlane — Setup Guide

Wire IssueForge into your Cloud SuperPlane org for the hackathon demo.

**Docs:** [SuperPlane Apps](https://docs.superplane.com/concepts/superplane-apps/) · [Canvas](https://docs.superplane.com/concepts/canvas/) · [Runners](https://docs.superplane.com/concepts/runners/) · [Claude component](https://docs.superplane.com/components/claude/) · [Files](https://docs.superplane.com/concepts/files/)

---

## Architecture

```text
Webhook → Fetch Issue (runner) → Spec Agent (Claude) → Validate Spec (runner)
       → Code Agent (Claude) → Verify Build (runner) → Deploy (runner) → Create PR (runner)
```

- **Claude nodes** — spec + code (cloud LLM, no Groq rate limits)
- **Runner nodes** — fetch, validate, npm build, git push, PR
- **Same scripts** as local `run_local.py` via `scripts/superplane_stages.py`

---

## Step 1 — Create the app

1. Go to [app.superplane.com](https://app.superplane.com)
2. Create app **IssueForge**
3. Complete the hackathon team form (org + app access)

---

## Step 2 — Upload app Files

Your SuperPlane app has a **Files** git repo ([docs](https://docs.superplane.com/concepts/files/)). Upload this repo content:

| Path | Purpose |
|------|---------|
| `prompts/*.md` | Claude system prompts |
| `runners/sp_*.sh` | SuperPlane runner scripts |
| `scripts/superplane_stages.py` | Shared pipeline logic |
| `scripts/validate_spec.py`, `apply_patches.py` | Helpers |
| `superplane-app/canvas.yaml` | Workflow graph |
| `superplane-app/console.yaml` | Dashboard |

**Option A — Git:** Connect `apocalypse44/issueforge-superplane-hack` as the app Files remote.

**Option B — UI:** Files tab → paste/upload each file.

---

## Step 3 — Secrets

App → **Secrets** (organization or app scope):

| Secret | Required |
|--------|----------|
| `GITHUB_TOKEN` | Yes — classic PAT with `repo` scope |
| `RENDER_API_KEY` | For preview deploy |
| `RENDER_SERVICE_ID` | Render service ID |

**Claude:** Add Claude integration in SuperPlane (API key from [platform.claude.com](https://platform.claude.com)) — used by Text Prompt nodes, not stored in IssueForge secrets.

Remove `GROQ_API_KEY` — not needed on SuperPlane.

---

## Step 3b — Connect external app via Webhook (your question)

**Direction:** Your app (or `curl`) → **POST** → SuperPlane webhook → canvas runs.

This is already how IssueForge is designed. No separate "connect app to canvas" integration — you use the **Webhook trigger** node.

### In the Canvas UI (Build mode)

1. **Edit** canvas → **+ Components** → add **Webhook** trigger
2. Name it **Issue Webhook** (must match runner scripts)
3. Set **authentication**:
   - **`none`** — fine for hackathon testing (anyone with URL can fire)
   - **`bearer`** — production: `Authorization: Bearer <token>` (store token in SuperPlane secrets)
   - **`signature`** — HMAC-SHA256 in `X-Signature-256` (recommended for prod)
4. **Publish** the canvas
5. Open the **Issue Webhook** node → copy the **webhook URL** from the node panel

### Connect the edge

Drag from **Issue Webhook** output channel **`default`** → **Fetch Issue** runner node.

Our `canvas.yaml` already has:
```yaml
edges:
  - sourceId: webhook-issue-input
    targetId: fetch-issue
    channel: default
```

### What downstream nodes receive

SuperPlane wraps your POST as (expression syntax):

| Field | Expression |
|-------|------------|
| Issue URL from body | `{{ root().data.body.issue_url }}` |
| Custom header | `{{ root().data.headers["X-Custom"][0] }}` |

Runner scripts read the same data from `$SUPERPLANE_PAYLOAD_FILE` via `runners/sp_common.sh`.

### Test with curl (auth: none)

```bash
curl -X POST "https://YOUR_WEBHOOK_URL_FROM_NODE_PANEL" \
  -H "Content-Type: application/json" \
  -d '{"issue_url":"https://github.com/superplanehq/superplane/issues/5368"}'
```

### Test with bearer auth

If webhook node uses `authentication: bearer`:

```bash
curl -X POST "https://YOUR_WEBHOOK_URL" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_WEBHOOK_TOKEN" \
  -d '{"issue_url":"https://github.com/superplanehq/superplane/issues/5368"}'
```

### Repo linking (Files)

Your scripts (`runners/sp_*.sh`, `prompts/`) live in the app's **Files** git repo — not a separate "connection". Upload or sync `apocalypse44/issueforge-superplane-hack` to the app Files tab so runners can execute them.

---

## Step 4 — Build the Canvas (UI recommended)

Open **Canvas** → Edit mode. Add nodes in this order and connect **Passed/default** channels:

### 1. Webhook trigger (`webhook`)
- Name: **Issue Webhook**
- Copy the webhook URL after publish
- Test payload:
  ```json
  {"issue_url": "https://github.com/superplanehq/superplane/issues/5368"}
  ```

### 2. Run Bash (`runnerBash`) — **Fetch Issue**
- Docker image: `python:3.12-slim`
- Setup: `apt-get install -y jq curl git && pip install groq`
- Script: `bash runners/sp_fetch_issue.sh`
- Env: `GITHUB_TOKEN` → secret

### 3. Claude Text Prompt (`claude.textPrompt`) — **Spec Agent**
- Model: `claude-sonnet-4-20250514` (or latest Sonnet)
- **System message:** paste contents of `prompts/spec_agent.md`
- **Prompt:** expression referencing fetch output, e.g. issue title + body from upstream payload
- Attach `prompts/spec_agent.md` via **Files** field if available

### 4. Run Bash — **Validate Spec**
- Script: `bash runners/sp_validate_spec.sh`

### 5. Claude Text Prompt — **Code Agent**
- **System message:** `prompts/code_agent.md`
- **Prompt:** include validated spec JSON from previous step

### 6. Run Bash — **Verify Build**
- Docker image: `node:22-bookworm`
- Setup: install `python3`, `pip`, `jq`
- Script: `bash runners/sp_verify.sh`
- Timeout: 3600s

### 7. Run Bash — **Deploy**
- Script: `bash runners/sp_deploy.sh`
- Env: `GITHUB_TOKEN`, `OUTPUT_REPO=apocalypse44/issueforge-superplane-hack`, `RENDER_*`

### 8. Run Bash — **Create PR**
- Script: `bash runners/sp_create_pr.sh`
- Env: `GITHUB_TOKEN`, `OUTPUT_REPO`

**Reference YAML:** `superplane-app/canvas.yaml` (import via Files or CLI `superplane apps canvas update -f ...`). Adjust `metadata.id` and field names to match your instance.

---

## Step 5 — Console dashboard

Import `superplane-app/console.yaml` or add panels in the Console UI showing:
- Run status per stage
- PR URL + Render preview link from last run

---

## Step 6 — Test the 5 eval issues

POST to webhook (or trigger manually):

```json
{"issue_url": "https://github.com/superplanehq/superplane/issues/5368"}
{"issue_url": "https://github.com/superplanehq/superplane/issues/5366"}
{"issue_url": "https://github.com/superplanehq/superplane/issues/5164"}
{"issue_url": "https://github.com/superplanehq/superplane/issues/5704"}
{"issue_url": "https://github.com/superplanehq/superplane/issues/5705"}
```

---

## Step 7 — Render preview

In Render dashboard for `issueforge-superplane-hack`:
- **Root Directory:** `pocs/5368` (per issue branch) or configure PR previews
- **Build:** `npm install && npm run build`
- **Publish:** `dist`

---

## Demo script (3 min)

1. Show IssueForge canvas + console
2. Trigger issue #5368 on webhook
3. Watch Spec → Code → Verify → Deploy → PR complete
4. Open PR on GitHub (PoC under `pocs/5368/`)
5. Open Render preview link from PR body

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| Runner can't find scripts | Ensure Files repo contains `runners/` and `scripts/`; set `APP_ROOT` to repo root in setup |
| Claude returns markdown fences | Validate Spec node will fail — tighten prompt "JSON only" |
| PR fails base branch | Deploy clones `master` — already fixed in `run_local.py` |
| `node_modules` in PR | `.gitignore` written before commit in deploy stage |
| Groq rate limit | You're on SuperPlane Claude — don't use Groq in cloud |

---

## Local vs SuperPlane

| | Local `run_local.py` | SuperPlane |
|--|---------------------|------------|
| Purpose | Dev/testing | Hackathon demo |
| LLM | Groq / Ollama | Claude Text Prompt |
| Orchestration | Python script | Canvas + Runners |
| When to use | Debug prompts | Judge demo |
