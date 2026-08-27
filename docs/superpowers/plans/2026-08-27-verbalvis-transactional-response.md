# VerbalVis Transactional Response Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace eager response cancellation and live-state tool effects with a testable transactional response runtime for VerbalVis.

**Architecture:** A small backend runtime package owns interruption classification, response transactions, tool contracts, and draft/CAS dashboard commits. `RealtimeSession` remains the Qwen/WebSocket adapter. The browser receives overlap and terminal-state feedback but continues to apply only committed dashboard snapshots.

**Tech Stack:** Python 3.12, asyncio, FastAPI/WebSocket backend, Vue 3/Pinia frontend, Node test runner, pytest.

**Spec:** `docs/superpowers/specs/2026-08-27-verbalvis-transactional-response-design.md`

## Global Constraints

- Preserve existing Olist tool names and the public WebSocket messages used by the browser.
- Do not add Redis, a new LLM dependency, or persistent multi-session storage.
- Every production behaviour begins with a focused failing pytest or Node test.
- Tool batches may update the browser only through a successful conditional dashboard commit.

---

### Task 1: Interruption policy and response transaction lifecycle

**Files:**
- Create: `backend/runtime/interruption.py`
- Create: `backend/runtime/transactions.py`
- Create: `backend/runtime/__init__.py`
- Create: `backend/tests/test_transaction_runtime.py`

**Interfaces:**
- Produces `classify_completed_utterance(text) -> InterruptionDecision`.
- Produces `ResponseTransactionManager.begin_response(response_id, base_revision)`, `mark_overlap(response_id)`, `resolve_overlap(text)`, `supersede_current()`, and `can_admit(response_id)`.

- [ ] Write a failing test proving `"yes, continue"` returns `BACKCHANNEL` and does not increment the epoch.
- [ ] Run `python -m pytest backend/tests/test_transaction_runtime.py -q` and confirm failure because the runtime package is absent.
- [ ] Implement the smallest enum-based interruption classifier and transaction manager required by the test.
- [ ] Re-run the focused test and confirm pass.
- [ ] Add failing tests for `STOP_ONLY`, an analytical revision, and rejection of a superseded response; implement and re-run.

### Task 2: Tool contracts, dashboard draft, and conditional commit

**Files:**
- Create: `backend/runtime/contracts.py`
- Create: `backend/runtime/dashboard_store.py`
- Modify: `backend/tool_contracts.py`
- Create: `backend/tests/test_dashboard_transactions.py`

**Interfaces:**
- Produces `ToolMode`, `ToolContract`, and `ToolProposal`.
- Produces `DashboardStore.snapshot()`, `begin_draft(transaction)`, and `commit(draft, transaction) -> CommitResult`.

- [ ] Write a failing test that a draft can be changed without altering the committed snapshot.
- [ ] Run the focused pytest node and confirm failure because `DashboardStore` is absent.
- [ ] Implement immutable snapshot copying and draft mutation.
- [ ] Write a failing test that a stale epoch or mismatched base revision rejects commit without incrementing the revision.
- [ ] Implement lock-protected compare-and-swap commit, then run both tests.
- [ ] Add contracts for every existing Olist tool using its existing `changes_dashboard` metadata; run all runtime tests.

### Task 3: Realtime adapter and draft tool execution

**Files:**
- Modify: `backend/realtime.py`
- Modify: `backend/tools.py`
- Modify: `backend/response_coordinator.py`
- Create: `backend/tests/test_realtime_transactions.py`

**Interfaces:**
- `RealtimeSession._speech_started` creates overlap feedback only.
- `RealtimeSession._user_transcript_completed` resolves the overlap and supersedes only for a semantic revision.
- `RealtimeSession._execute_tool_batch` executes against a draft and emits `dashboard_commit` only after `DashboardStore.commit` succeeds.

- [ ] Write a failing async test that a speech-start event does not send `response.cancel`.
- [ ] Implement overlap feedback and remove eager epoch advancement.
- [ ] Write a failing test that a revision while a draft batch is running yields `stale_discarded` instead of `dashboard_commit`.
- [ ] Implement transaction cancellation propagation and conditional commit.
- [ ] Write a failing test that a valid batch emits exactly one committed snapshot; implement and run the realtime test file.

### Task 4: Browser feedback and trace visibility

**Files:**
- Modify: `frontend/src/composables/useWebSocket.js`
- Modify: `frontend/src/stores/runtime.js`
- Modify: `frontend/src/stores/dashboard.js`
- Create: `frontend/tests/transactionRuntime.test.js`

**Interfaces:**
- Consumes `response_overlap`, `response_resumed`, `response_superseded`, and `tool_execution_finished.commit_status`.
- Produces `runtime.overlapPending`, `runtime.responseStatus`, and transcript terminal labels.

- [ ] Write a failing Node test for overlap-pending state and response-resumed state.
- [ ] Implement additive message handling without changing legacy message behaviour.
- [ ] Write a failing test that only `commit_status: "committed"` applies a dashboard snapshot.
- [ ] Implement the guard and run all frontend tests.

### Task 5: Contracts, traces, documentation, and verification

**Files:**
- Modify: `backend/tool_contracts.py`
- Modify: `README.md`
- Modify: `tex02/main.tex` only after code behaviour and tests agree
- Modify: `F:\VerbalVis2 - 副本 (4)7月15\\tex02/main.tex` only after code behaviour and tests agree

**Interfaces:**
- Documents the response transaction predicate, tool contract fields, known cancellation boundary, and test commands.

- [ ] Add a failing test that every allowed tool has a mode, idempotency flag, and cancellation flag.
- [ ] Implement missing metadata and run contract tests.
- [ ] Update README with the actual transaction lifecycle and no unsupported claims.
- [ ] Update both manuscript copies only after tests prove the stated behaviour.
- [ ] Run `python -m pytest tests backend/tests -q`, `npm test -- --run`, build the frontend, and `git diff --check`.

## Self-Review

- The five tasks cover interruption semantics, state isolation, conditional commit, realtime integration, client visibility, contracts, tests, documentation, and manuscript alignment.
- All named types are introduced before later tasks consume them.
- The plan has no placeholder implementation steps; test commands and behavioural expectations are explicit.

