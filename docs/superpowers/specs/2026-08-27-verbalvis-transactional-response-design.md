# VerbalVis Transactional Response Design

## Goal

Make the existing single-user VerbalVis realtime session safe for genuine full-duplex analytical revision. A new user utterance must be classified before it supersedes a response; stale response output and tool effects must never enter the committed dashboard; and a tool batch may execute without blocking a later user revision.

## Current Gap

The current `RealtimeSession` increments `intent_epoch` and sends `response.cancel` on every `speech_started` event. It also ignores speech while `tool_running` and applies dashboard-changing tools to live global state before the client receives the final snapshot. This conflicts with the paper's distinction between acoustic overlap and semantic supersession.

## Scope and Compatibility

- Keep the single-user FastAPI/WebSocket/Qwen session model and the existing Olist tool names.
- Keep the existing browser message types; add optional fields and new status-only messages without breaking older clients.
- Do not import `dataops_agent`, add Redis, or change the visual encoding/data-query implementation in this change.
- The dashboard remains authoritative in the backend. A dashboard commit is the only operation that changes its public revision.

## Transaction Model

`ResponseTransaction` owns one model response and has `response_id`, `intent_epoch`, `base_revision`, `status`, `cancelled`, and its proposed tool calls. Valid statuses are `STREAMING`, `OVERLAP_PENDING`, `PROPOSING`, `EXECUTING_DRAFT`, `COMMITTED`, `SUPERSEDED`, `CANCELLED`, and `FAILED`.

`speech_started` creates an overlap candidate and asks the browser to duck or pause playback. It does not invalidate a response. The completed transcript is classified into `BACKCHANNEL`, `RECOGNITION_REPAIR`, `STOP_ONLY`, or `ANALYTICAL_REVISION`.

- `BACKCHANNEL` and `RECOGNITION_REPAIR` resume/retain the current response.
- `STOP_ONLY` cancels the response but does not change dashboard state or create a replacement plan.
- `ANALYTICAL_REVISION` increments the intent epoch, supersedes the prior transaction, invalidates its pending proposals, and permits a replacement response.

## Tool Contract

Each registered tool has a `ToolContract`: name, input schema, `mode`, dependencies, precondition, idempotency, cancellation support, and an effect description. Modes are `READ_ONLY`, `DRAFT_MUTATION`, and `PERSISTENT_WRITE`. Existing visualization tools are initially `DRAFT_MUTATION`; data lookup tools are `READ_ONLY`. The model proposes tools, but the runtime validates dependency order and owns commit.

Each proposed call carries the response id, intent epoch, base revision, call id, tool name, arguments, dependencies, and cancellation token. Unknown tools, invalid arguments, unmet dependencies, and obsolete transactions are rejected before execution.

## Draft and Conditional Commit

A dashboard-changing batch runs against a cloned `DashboardDraft` rooted at `base_revision`. The draft exposes a final snapshot but cannot mutate public state. The runtime commits the whole batch only when:

```text
transaction.intent_epoch == current intent epoch
AND transaction.base_revision == committed dashboard revision
AND transaction.status is EXECUTING_DRAFT
AND the transaction has not been cancelled
AND every required call succeeded
```

The dashboard store performs this compare-and-swap while holding its lock. If a check fails, the draft is discarded, its trace becomes `stale_discarded`, and its result is never rendered or returned as current context. Read-only work may finish after cancellation, but its stale result is similarly withheld.

## Required Invariants

1. A backchannel never increments the intent epoch or cancels a current response.
2. No tool whose transaction is superseded can change committed dashboard state.
3. A dashboard revision increases exactly once per successfully committed batch.
4. A batch never exposes a partial dashboard state.
5. Each tool proposal has exactly one terminal trace status: rejected, cancelled, failed, discarded, or committed.

## Runtime Integration

Create a focused `backend/runtime/` package:

- `interruption.py`: deterministic transcript classifier and overlap decision.
- `contracts.py`: immutable tool contract and proposal types.
- `dashboard_store.py`: snapshot, draft, and compare-and-swap commit.
- `transactions.py`: response lifecycle and admission decisions.

`backend/realtime.py` becomes the protocol adapter. It creates transactions, forwards client/provider messages, asks the interruption policy to decide after final transcript, invokes tools through the draft executor, and emits the existing dashboard snapshot only after a successful commit.

## Evaluation and Paper Alignment

The implementation records `response_id`, `intent_epoch`, `base_revision`, `decision`, `tool_call_id`, `draft_revision`, and final `commit_status`. The manuscript must replace the current response-id-only rule with the transaction state diagram and conditional commit predicate. It must not claim that backchannels are preserved until the tests and live interaction demonstrate it.

