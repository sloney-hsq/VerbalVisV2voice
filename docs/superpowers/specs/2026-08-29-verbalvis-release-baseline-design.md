# VerbalVis Release Baseline Design

**Status:** Approved scope; local implementation only. Do not push or create a GitHub release without an explicit later instruction.

## 1. Purpose

Make the existing VerbalVis FD-Voice research prototype reproducible, inspectable, and safe to present in a portfolio. The milestone packages the current runtime truth; it does not add a second agent architecture, change the single-session runtime, or claim production readiness.

The public-facing story is:

> A single-participant, full-duplex voice-driven visual analytics prototype for Olist data. It treats speech overlap as a signal rather than an automatic cancellation, and conditionally commits only tool results that still belong to the current response, intent, and dashboard revision.

## 2. Non-goals and invariants

- Do not change the existing Qwen Realtime protocol, response transaction semantics, tool behavior, visual encodings, or Olist data query logic.
- Do not wire `dataops_agent`, Redis, Elasticsearch, RAG, or MCP into VerbalVis. They remain independent packages/roadmap items.
- Do not represent the in-memory, single-active-session prototype as multi-tenant, distributed, high-concurrency, or production-ready.
- Do not submit/push/release anything remotely as part of this milestone.
- Do not commit secrets, raw audio, conversation logs, user traces, or new copies of third-party datasets.

## 3. Deliverables

### 3.1 Root README

Replace the current mixed/duplicated top-level presentation with a concise repository entry point:

1. Project positioning and a one-paragraph explanation of the response-transaction contribution.
2. A small ASCII architecture diagram and a direct link to the detailed runtime contract.
3. A clean Quick Start split into prerequisites, backend installation/configuration, frontend installation, and local launch.
4. A minimal two-minute demonstration script, including a backchannel and an analytical revision.
5. A precise list of guarantees and non-guarantees: semantic stale-result isolation is supported; CPU-level cancellation and multi-session recovery are not.
6. A clear link to standalone DataOps documentation without claiming it is attached to the realtime path.
7. Links to the dataset, privacy, contribution, security, license, and release verification documents.

Upstream Qwen event documentation must be cited by link rather than copied into the README. The README must not include invented metrics, latency claims, user-study conclusions, or deployment claims.

### 3.2 Reproducible development baseline

- Record tested Python and Node/npm version ranges in the README.
- Pin direct backend runtime dependencies in `backend/requirements.txt`; retain only dependencies actually needed by the backend.
- Use the existing frontend lockfile with `npm ci` in verification/CI.
- Add a local verification command that performs whitespace checks, backend tests, frontend tests, and frontend build in the documented directories. It must fail fast and return a non-zero process exit status for any failed step.
- Include a configuration-degradation check: missing Qwen configuration must produce the documented `configuration_error` behavior rather than a reconnect loop or a secret leak.

### 3.3 Automated checks

Add an independent `.github/workflows/verbalvis-ci.yml` workflow. It must:

- trigger on changes to the VerbalVis backend, frontend, shared documentation, or the workflow itself;
- run on supported Python versions and a pinned Node major version;
- install backend dependencies and run `pytest backend/tests -q`;
- run frontend `npm ci`, `npm test -- --run`, and `npm run build` from `frontend/`;
- avoid requiring a Qwen key, browser microphone, Redis, Elasticsearch, Docker, or a live third-party service.

This workflow is a local artifact in this milestone; it must not be presented as already executed remotely.

### 3.4 Dataset and privacy contracts

Add `docs/DATASET.md` with:

- the Olist source, version/acquisition instructions, contents, expected local location, and integrity-check procedure;
- a license/reuse verification boundary: do not copy uncertain third-party license text or promise redistribution rights that have not been verified;
- the preprocessing and metric semantics needed to reproduce the included tools;
- a distinction between source data, derived local artifacts, and the small/synthetic data suitable for examples.

Add `PRIVACY.md` with:

- what the runtime may write locally (conversation text, tool arguments, dashboard state, event timestamps);
- default log locations and the fact that they are excluded from version control;
- instructions not to commit/upload real participant traces;
- a minimum research-use protocol: consent, access restriction, retention/deletion decision, and anonymisation review;
- a clear statement that this document is operational guidance, not legal/compliance certification.

### 3.5 Release verification document

Add a VerbalVis-specific checklist (or extend a clearly named section) covering clean install, tests/build, no-key degradation, secret/trace scan, dataset acknowledgment, and a manual websocket smoke test. It must distinguish local verification from remote GitHub Actions execution.

## 4. File-level change plan

| File | Change | Compatibility rule |
| --- | --- | --- |
| `README.md` | Rewrite as focused VerbalVis project entry point. | Keep real configuration keys and working commands; link rather than duplicate detailed contracts. |
| `backend/requirements.txt` | Pin direct runtime dependencies. | Do not introduce DataOps-only packages. |
| `.github/workflows/verbalvis-ci.yml` | Add offline CI for backend and frontend. | No credentials or external services. |
| `scripts/verify_verbalvis_release.ps1` | Add fail-fast local verification. | Read-only except normal build/test caches; no git/network publish action. |
| `docs/DATASET.md` | Add data provenance and reproducibility contract. | No unsupported redistribution claim. |
| `PRIVACY.md` | Add trace handling and research-use guidance. | No claim of certified compliance. |
| `docs/verbalvis-release-checklist.md` | Add local release checklist/manual smoke test. | Explicitly retain single-session and no-live-provider test limits. |

## 5. Data and control flow

The milestone preserves the existing runtime flow:

```text
Browser audio/text
  -> FastAPI WebSocket adapter
  -> Qwen Realtime conversation / function call
  -> ResponseTransactionManager + DashboardDraft
  -> schema-grounded Olist tools + DuckDB
  -> conditional DashboardStore commit
  -> authoritative dashboard snapshot + JSONL trace
```

Only the surrounding reproducibility, documentation, and verification controls change. The `dataops_agent` path remains separate:

```text
Standalone DataOps API / ETL / quality / optional adapters
  != VerbalVis realtime adapter
```

## 6. Error handling and safety requirements

- The local verifier must report the failing command and return its exit status.
- CI must surface test/build failures directly; it must not hide them behind `continue-on-error`.
- Documentation commands must use environment variables or `.env` placeholders, never example secrets.
- Configuration-error behavior must remain safe: no API key echoing and no repeated reconnection requirement.
- Dataset and trace documentation must name uncertainties instead of filling them with assumptions.

## 7. Acceptance criteria

1. A first-time contributor can follow the README to install the backend and frontend, configure a local Qwen key, and start the prototype without guessing the missing dependency step.
2. The local verification script succeeds only if `git diff --check`, backend tests, frontend tests, and frontend build all succeed.
3. The CI workflow encodes the same offline checks and does not require an API key or live provider.
4. The README, dataset document, privacy document, and release checklist contain no claim that DataOps is integrated, that VerbalVis is distributed/production-ready, or that user performance has been validated.
5. All existing runtime transaction tests remain green; no runtime behavior is intentionally changed.
6. All changes remain local until the user explicitly requests a commit/push/release action.

## 8. Verification strategy

Before declaring the milestone ready, run:

```powershell
./scripts/verify_verbalvis_release.ps1
```

Then separately inspect the working tree and intended diff. The manual smoke checklist will verify one configuration-error path and one local session lifecycle path. A live Qwen/browser microphone test is documented as manual evidence, not replaced by fake-socket unit tests.

## 9. Scope review

The specification contains no unresolved placeholders. The work is intentionally limited to the VerbalVis release baseline and does not require a DataOps integration or a runtime redesign. The main dependency is accurate current documentation; implementation must inspect actual commands, dependency versions, log paths, and configuration keys before writing them.
