# VerbalVis release checklist

Use this checklist for a local release review of the standalone prototype. It
is not a remote-CI gate and is not wired to deployment, DataOps, or an
automated release service.

## Installation and configuration

- [ ] Start from clean backend and frontend installations; install their
  declared dependencies without relying on untracked local state.
- [ ] Create a secret-safe backend `.env` from `backend/.env.example`; provide
  required Qwen credentials only locally and keep secrets out of commits.
- [ ] When the release-verification script is present, run
  `scripts/verify_verbalvis_release.ps1` from the repository root and retain
  its local output only where it contains no secrets or participant material.

## Runtime checks

- [ ] Confirm the no-key `/health` behaviour is the documented availability
  check and does not expose credentials.
- [ ] Exercise one browser session and confirm the WebSocket workflow is
  single-session / single-participant in scope.
- [ ] Confirm a spoken backchannel does not cancel the active response.
- [ ] Confirm an analytical-revision utterance supersedes the active response
  without publishing stale dashboard state.
- [ ] Review any local trace needed for the test, then remove it under the
  retention decision in `PRIVACY.md`.

## Data and final release boundary

- [ ] Acknowledge `docs/DATASET.md`, including the source/reuse boundary,
  local-file integrity procedure, and metric semantics.
- [ ] Perform a final scan for committed secrets, `backend/logs/` traces, and
  raw capture files before packaging or sharing.

## Automation boundary

These are local checks. Future remote CI may repeat suitable static and test
checks, but it is outside this release baseline. Unit tests do not run a live
Qwen or microphone test; the WebSocket and audio checks above therefore need
explicit local review with controlled credentials and no real participant data.
