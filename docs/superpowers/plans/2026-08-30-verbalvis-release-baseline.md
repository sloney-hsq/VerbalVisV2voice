# VerbalVis Release Baseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make VerbalVis locally reproducible, verifiable, and portfolio-ready without changing its single-session realtime behavior or publishing it remotely.

**Architecture:** Keep the existing FastAPI/Qwen/DuckDB/Vue runtime untouched. Add focused release controls around it: pinned backend/test dependencies, an offline CI workflow, a fail-fast PowerShell verifier, and concise contracts for data and local research traces. The root README becomes the public project entry point and links to detailed runtime and standalone DataOps documents instead of duplicating them.

**Tech Stack:** Python 3.11/3.12, FastAPI, pytest, PowerShell 7+/Windows PowerShell-compatible scripts, Node 20, npm, Vue 3/Vite, GitHub Actions YAML, Markdown.

**Spec:** `docs/superpowers/specs/2026-08-29-verbalvis-release-baseline-design.md`

## Global Constraints

- Do not change Qwen Realtime, response-transaction, tool, visual encoding, Olist query, or single-active-session behavior.
- Do not import or wire `dataops_agent`, Redis, Elasticsearch, RAG, or MCP into VerbalVis.
- Do not add credentials, raw audio, conversation traces, user logs, or newly copied third-party datasets.
- Do not push, create a GitHub Release, or otherwise publish remotely.
- The deliverable may state only tested prototype capabilities; it must not claim multi-tenant, distributed, high-concurrency, production-ready, or user-study-validated behavior.
- Use exact path-scoped `git add` commands; never stage the whole worktree.

---

### Task 1: Pin VerbalVis backend and test dependencies

**Files:**
- Modify: `backend/requirements.txt`
- Create: `backend/requirements-dev.txt`
- Test: `backend/tests/test_release_baseline.py`

**Interfaces:**
- Consumes: the installed package versions that import the current `backend/main.py`, `backend/realtime.py`, and `backend/tests` suite.
- Produces: a runtime dependency file installable with `python -m pip install -r backend/requirements.txt` and a test dependency file installable with `python -m pip install -r backend/requirements-dev.txt`.

- [ ] **Step 1: Write the configuration-degradation test**

Create `backend/tests/test_release_baseline.py` with a backend path bootstrap and an async health assertion. The test must never call Qwen or read a real key.

```python
from __future__ import annotations

import asyncio
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

import main


def test_health_reports_safe_missing_qwen_configuration(monkeypatch) -> None:
    monkeypatch.setattr(main, "QWEN_API_KEY", "")

    payload = asyncio.run(main.health_check())

    assert payload["status"] == "ok"
    assert payload["qwen_configured"] is False
    assert "DASHSCOPE_API_KEY" in str(payload["qwen_configuration_error"])
```

- [ ] **Step 2: Run the new test before declaring the dependency contract complete**

Run: `C:\Users\admin\miniconda3\python.exe -m pytest backend/tests/test_release_baseline.py -q`

Expected: the test can import the backend without a live Qwen connection and passes only when the health payload reports safe missing-key behavior.

- [ ] **Step 3: Pin direct runtime packages and add a development requirements file**

Replace `backend/requirements.txt` with the tested direct runtime versions:

```text
fastapi==0.136.3
uvicorn[standard]==0.49.0
websockets==15.0.1
duckdb==1.5.3
python-dotenv==1.1.0
websocket-client==1.9.0
```

Create `backend/requirements-dev.txt`:

```text
-r requirements.txt
pytest==9.1.1
```

- [ ] **Step 4: Verify the dependency files and all backend tests**

Run:

```powershell
& 'C:\Users\admin\miniconda3\python.exe' -m pip install -r backend/requirements-dev.txt
& 'C:\Users\admin\miniconda3\python.exe' -m pytest backend/tests -q
```

Expected: no dependency resolver error; all backend tests, including `test_release_baseline.py`, pass without a Qwen key.

- [ ] **Step 5: Commit the dependency baseline locally**

```powershell
git add -- backend/requirements.txt backend/requirements-dev.txt backend/tests/test_release_baseline.py
git commit -m "build: pin VerbalVis development dependencies"
```

### Task 2: Add dataset, privacy, and release-verification contracts

**Files:**
- Create: `docs/DATASET.md`
- Create: `PRIVACY.md`
- Create: `docs/verbalvis-release-checklist.md`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `backend/db.py` dataset filenames, `backend/realtime.py` log root, `backend/tools.py` tool trace behavior, `backend/.env.example`, and the response-transaction contract.
- Produces: human-readable, source-linked release boundaries and explicit local-only log protection used by the README and manual release process.

- [ ] **Step 1: Derive the documented data and trace facts from the implementation**

Record these implementation facts before writing prose:

```powershell
rg -n "DATA_DIR|olist_.*dataset\.csv" backend/db.py
rg -n "LOG_ROOT|events\.jsonl|conversation\.jsonl" backend/realtime.py backend/tools.py
Get-Content backend/.env.example
```

Expected: the documents name only files and log artifacts the code actually creates.

- [ ] **Step 2: Create `docs/DATASET.md`**

Include all of the following headings and statements:

```markdown
# Dataset contract
## Scope and local location
## Source and reuse boundary
## Expected source files
## Integrity procedure
## Tool metric semantics
```

The document must name `backend/data/olist/` as the expected local path, list the CSV names from `backend/db.py`, link to the canonical Olist/Kaggle source without copying an unverified licence, tell contributors to verify reuse/redistribution terms before publishing data, and include the exact PowerShell integrity command:

```powershell
Get-FileHash backend/data/olist/*.csv -Algorithm SHA256
```

It must define low score as `review_score <= 2`, product revenue as `SUM(price)` excluding freight, and category service metrics as one row per `order_id + product_category`.

- [ ] **Step 3: Create `PRIVACY.md` and protect generated logs**

`PRIVACY.md` must state that local runs can write conversation text, tool arguments, dashboard state, response/transaction metadata, and timestamps under `backend/logs/`; that these logs are already ignored; and that contributors must not commit real participant traces. Add these narrowly scoped patterns to `.gitignore` if absent:

```text
backend/logs/
backend/*.raw
```

The document must require consent, access restriction, retention/deletion decisions, and anonymisation review before research use, while explicitly stating that it is not legal or compliance certification.

- [ ] **Step 4: Create `docs/verbalvis-release-checklist.md`**

The checklist must cover: clean backend/frontend installation, `.env` setup without copying a key into source, `scripts/verify_verbalvis_release.ps1`, no-key `/health` behavior, a single-session WebSocket smoke test, a backchannel smoke test, an analytical-revision smoke test, trace review, dataset acknowledgement, and a final secret/log scan. It must distinguish local checks from a future remote CI run and state that no live Qwen/microphone test is performed by unit tests.

- [ ] **Step 5: Check documentation contracts and commit locally**

Run:

```powershell
rg -n "standalone|not wired|single-participant|not legal" README.md docs/DATASET.md PRIVACY.md docs/verbalvis-release-checklist.md
git diff --check -- docs/DATASET.md PRIVACY.md docs/verbalvis-release-checklist.md .gitignore
```

Expected: no unsupported integration or deployment claim, and no whitespace errors.

```powershell
git add -- docs/DATASET.md PRIVACY.md docs/verbalvis-release-checklist.md .gitignore
git commit -m "docs: add VerbalVis release contracts"
```

### Task 3: Rewrite the root README as a VerbalVis entry point

**Files:**
- Modify: `README.md`
- Test: `docs/verbalvis-release-checklist.md`

**Interfaces:**
- Consumes: `backend/.env.example`, `backend/requirements-dev.txt`, `frontend/package.json`, `docs/verbalvis-runtime-contract.md`, `docs/DATASET.md`, `PRIVACY.md`, and standalone `dataops_agent/README.md`.
- Produces: the single copy-pasteable start path and accurate public narrative for VerbalVis.

- [ ] **Step 1: Preserve real setup commands and configuration names**

Verify the values to be documented:

```powershell
Get-Content backend/.env.example
Get-Content frontend/package.json -Raw
rg -n "@app.get\(\"/health\"|qwen_configuration_error|_active_session_id" backend/main.py
```

Expected: README commands use `DASHSCOPE_API_KEY`, `QWEN_REGION`, `uvicorn main:app`, `npm ci`, and `npm run dev -- --port 5173` exactly as implemented.

- [ ] **Step 2: Replace the README with the focused structure**

Write these top-level sections in this order:

```markdown
# VerbalVis FD-Voice
## What it is
## Architecture
## Response transaction guarantee
## Quick start
## Demo script
## Model-facing tools and metric semantics
## Verification
## Dataset and privacy
## Standalone DataOps boundary
## Limitations
## Contributing and security
```

The Quick Start must include:

```powershell
cd backend
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
uvicorn main:app --host 127.0.0.1 --port 8000
```

and, in a second terminal:

```powershell
cd frontend
npm ci
npm run dev -- --port 5173
```

Replace copied Qwen event reference content with official links. Explain that `speech_started` marks overlap only, final transcription determines the interruption decision, stale tool bundles do not update browser/dashboard/model context, and legacy handlers are not CPU-preemptible. Link to `docs/verbalvis-runtime-contract.md` for the protocol details.

- [ ] **Step 3: Add the demonstration and boundary language**

Document exactly this manual flow: ask for a state/category comparison; say “yes, continue” during playback; say “instead, show only 2017 orders”; inspect the corresponding transaction trace. State that the first does not cancel the response while the second creates a new intent epoch. Keep the DataOps section to a short pointer to `dataops_agent/README.md` and `docs/dataops-agent-verbalvis-integration.md`; say it is standalone and not wired into the realtime path.

- [ ] **Step 4: Validate the README contract**

Run:

```powershell
rg -n "^# |^## |DASHSCOPE_API_KEY|npm ci|requirements-dev.txt|response transaction|single-participant" README.md
rg -n "Qwen-Omni-Realtime API的客户端事件参考|复制 MD 格式|更新时间" README.md
git diff --check -- README.md
```

Expected: required sections/configuration strings are present; copied Qwen reference fragments are absent; no whitespace errors.

- [ ] **Step 5: Commit the README rewrite locally**

```powershell
git add -- README.md
git commit -m "docs: prepare VerbalVis portfolio README"
```

### Task 4: Add offline CI and a fail-fast local verifier

**Files:**
- Create: `.github/workflows/verbalvis-ci.yml`
- Create: `scripts/verify_verbalvis_release.ps1`
- Test: `scripts/verify_verbalvis_release.ps1`

**Interfaces:**
- Consumes: `backend/requirements-dev.txt`, `backend/tests`, `frontend/package-lock.json`, `frontend/package.json`, `docs/verbalvis-release-checklist.md`.
- Produces: one credentials-free remote CI definition and one local PowerShell command that returns non-zero as soon as a required release check fails.

- [ ] **Step 1: Write the local verifier with explicit failure propagation**

Create `scripts/verify_verbalvis_release.ps1` using this control structure:

```powershell
[CmdletBinding()]
param(
    [string]$PythonExecutable = "python",
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot

function Invoke-ReleaseStep {
    param([string]$Name, [scriptblock]$Command)
    Write-Host "==> $Name" -ForegroundColor Cyan
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Name failed with exit code $LASTEXITCODE."
    }
}
```

The script must run `git diff --check` and `git diff --cached --check`; when `-InstallDependencies` is supplied, install `backend/requirements-dev.txt` and run `npm ci`; then run `pytest backend/tests -q`, `npm test -- --run`, and `npm run build` in the correct directories. It must print a final local-only notice and never call `git push`, `gh`, Docker, Qwen, or any network deployment command.

- [ ] **Step 2: Run a negative failure-propagation check**

Create a temporary untracked file containing trailing whitespace, execute the verifier, and confirm it exits non-zero before removing the file:

```powershell
$probe = Join-Path $PWD '.tmp/release-whitespace-probe.txt'
New-Item -ItemType Directory -Force (Split-Path -Parent $probe) | Out-Null
[IO.File]::WriteAllText($probe, "bad  `n")
git add --intent-to-add -- $probe
git diff --check -- $probe
if ($LASTEXITCODE -eq 0) { throw 'Git whitespace check accepted the staged probe.' }
git reset -- $probe
Remove-Item -LiteralPath $probe
```

Expected: the verifier fails at the whitespace step. Remove only the explicit probe file after observing the failure.

- [ ] **Step 3: Add the VerbalVis CI workflow**

Create `.github/workflows/verbalvis-ci.yml` with `contents: read`, Python matrix `3.11`/`3.12`, Node `20`, `push`/`pull_request`/`workflow_dispatch` triggers, and path filters for `backend/**`, `frontend/**`, `docs/**`, `README.md`, `PRIVACY.md`, `.github/workflows/verbalvis-ci.yml`, and `scripts/verify_verbalvis_release.ps1`.

The Python job must run:

```yaml
- run: python -m pip install -r backend/requirements-dev.txt
- run: python -m pytest backend/tests -q
```

The frontend job must run:

```yaml
- run: npm ci
  working-directory: frontend
- run: npm test -- --run
  working-directory: frontend
- run: npm run build
  working-directory: frontend
```

No job may read a Qwen secret or require a live service.

- [ ] **Step 4: Run the positive local verifier and inspect the CI workflow**

Run:

```powershell
& ./scripts/verify_verbalvis_release.ps1 -PythonExecutable 'C:\Users\admin\miniconda3\python.exe'
rg -n "requirements-dev.txt|pytest backend/tests|npm ci|npm test -- --run|npm run build|DASHSCOPE_API_KEY" .github/workflows/verbalvis-ci.yml scripts/verify_verbalvis_release.ps1
git diff --check -- .github/workflows/verbalvis-ci.yml scripts/verify_verbalvis_release.ps1
```

Expected: all local checks pass; the workflow has the required commands and no credential reference.

- [ ] **Step 5: Commit CI and local verification locally**

```powershell
git add -- .github/workflows/verbalvis-ci.yml scripts/verify_verbalvis_release.ps1
git commit -m "ci: verify VerbalVis release baseline"
```

### Task 5: Final local release-baseline verification

**Files:**
- Verify: `README.md`
- Verify: `backend/requirements.txt`
- Verify: `backend/requirements-dev.txt`
- Verify: `backend/tests/test_release_baseline.py`
- Verify: `docs/DATASET.md`
- Verify: `PRIVACY.md`
- Verify: `docs/verbalvis-release-checklist.md`
- Verify: `.github/workflows/verbalvis-ci.yml`
- Verify: `scripts/verify_verbalvis_release.ps1`

**Interfaces:**
- Consumes: all preceding deliverables.
- Produces: local evidence that the release baseline is internally consistent; it does not create remote execution evidence.

- [ ] **Step 1: Run the full local release verifier**

Run:

```powershell
& ./scripts/verify_verbalvis_release.ps1 -PythonExecutable 'C:\Users\admin\miniconda3\python.exe'
```

Expected: whitespace checks, backend tests, frontend tests, and frontend build all finish successfully.

- [ ] **Step 2: Verify no runtime coupling was introduced**

Run:

```powershell
rg -n "dataops_agent" backend frontend
rg -n "redis|elasticsearch|mcp" backend frontend
git diff 599088e..HEAD -- backend/realtime.py backend/tools.py backend/main.py
```

Expected: no new DataOps/Redis/Elasticsearch/MCP import or runtime modification; only the explicitly added health test may touch backend tests.

- [ ] **Step 3: Verify local-only delivery state**

Run:

```powershell
git status --short
git log --oneline -8
git branch -vv
```

Expected: all intended changes are committed locally; do not run `git push` or create a GitHub Release.

- [ ] **Step 4: Commit only if Task 5 added an intentional tracked artifact**

If Task 5 added a tracked artifact, stage only that exact path and create a local commit. Otherwise leave the verified, clean worktree unchanged.
