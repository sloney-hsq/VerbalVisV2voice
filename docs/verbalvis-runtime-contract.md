# VerbalVis response-transaction contract

This document is the implementation contract for the FD-Voice runtime. It
describes what the current prototype guarantees, the boundaries it deliberately
does not claim, and the public messages consumed by the browser. It applies to
the single-session in-memory VerbalVis adapter; it is not a Redis or
multi-process coordination protocol.

## 1. Core invariants

Every provider response is bound to the immutable tuple:

```text
(response_id, intent_epoch, base_revision)
```

- `response_id` identifies one Qwen Realtime response.
- `intent_epoch` increases only after a completed utterance is classified as
  `ANALYTICAL_REVISION`, or when the provider creates a genuine replacement
  response while another response is current.
- `base_revision` is the dashboard revision from which the response's tool
  batch begins.

The response lifecycle is:

```text
STREAMING
  └─ speech_started → OVERLAP_PENDING
       ├─ BACKCHANNEL / RECOGNITION_REPAIR → prior state
       ├─ STOP_ONLY                         → CANCELLED
       └─ ANALYTICAL_REVISION               → SUPERSEDED, epoch + 1

STREAMING → EXECUTING_DRAFT → COMMITTED | FAILED | SUPERSEDED
```

No state from `CANCELLED`, `SUPERSEDED`, or `FAILED` is admitted to the
dashboard or model context.

## 2. Interruption policy

`input_audio_buffer.speech_started` produces an overlap observation. It **must
not** send `response.cancel`, clear the Qwen audio buffer, clear the current
response id, or increment an epoch.

The deterministic baseline classifier runs only after a final transcription:

| Final utterance category | Decision | Effect |
| --- | --- | --- |
| `yes`, `yes, continue`, `okay`, `go on` | `BACKCHANNEL` | Keep assistant response and playback eligible. |
| `sorry, I mean…`, `correction…` | `RECOGNITION_REPAIR` | Keep the response eligible; a provider may later supply a corrected final turn. |
| `stop`, `cancel`, `never mind` | `STOP_ONLY` | Cancel the owned response without treating it as a new analytical intent. |
| Any other completed request | `ANALYTICAL_REVISION` | Supersede the response, increment epoch, cancel provider output, and retain committed dashboard state. |

The lexical classifier is deliberately conservative and injectable. A future
semantic classifier may improve recall, but it must preserve the same four
decision values and must never cancel at speech onset.

## 3. Tool contracts

`backend/tool_contracts.py` binds each allowed Olist tool to the schema already
registered with Qwen—schemas are not copied into a second registry. The
materialized immutable `ToolContract` contains:

```text
name, input_schema, mode, dependencies, precondition,
idempotent, cancellable, effect_detail
```

`mode` is `READ_ONLY` or `DRAFT_MUTATION`. All current legacy handlers declare
`cancellable: false`: a handler may finish in its Python worker even after its
transaction becomes stale. That is the explicit cancellation boundary. The
runtime protects externally observable correctness by dropping stale results;
it does not promise CPU-level preemption.

## 4. Draft execution and conditional commit

`backend/tools.py` owns the existing synchronous globals. A complete dashboard
snapshot includes filters, views, highlights, history, id allocator, and
revision. `execute_tool_in_snapshot(name, arguments, snapshot)` performs:

1. Acquire the re-entrant dashboard-state lock.
2. Copy committed globals and install the private draft.
3. Run the unchanged handler with per-tool revision increments disabled.
4. Capture the next draft and restore the committed globals in `finally`.

`DashboardStore.commit(draft, transaction)` is the only mutation publication
path. It succeeds iff:

```text
transaction.intent_epoch == current_intent_epoch
AND transaction.base_revision == committed_revision
AND draft.base_revision == transaction.base_revision
AND transaction.status == EXECUTING_DRAFT
AND transaction.cancelled == false
```

For a successful mutation bundle, the store increments the revision exactly
once, atomically installs the full snapshot, and causes one `dashboard_commit`.
Read-only bundles use the identical freshness predicate without manufacturing a
new dashboard revision.

On `stale_discarded`, the runtime emits trace metadata and a terminal batch
message, but does **not** send a tool result, a dashboard snapshot, or
`function_call_output` to Qwen. This prevents a late result from contaminating
replanning context.

## 5. WebSocket protocol additions

Existing message types remain compatible. The following additive payloads are
consumed by `frontend/src/composables/useWebSocket.js`.

| Type | Required fields | Browser effect |
| --- | --- | --- |
| `response_overlap` | `response_id`, `utterance_id`, `intent_epoch`, `status: "overlap_pending"` | Show pending overlap feedback; do not stop audio. |
| `response_resumed` | `response_id`, `intent_epoch`, `decision` | Clear overlap feedback and continue the current response. |
| `response_superseded` | `response_id`, `intent_epoch`, `reason: "analytical_revision"` | Stop only the named stale response. |
| `response_cancelled` | `response_id`, `intent_epoch`, `reason: "stop_only"` | Stop only the named response without implying a new analytical goal. |
| `tool_execution_finished` | `commit_status`, optionally `discard_reason` | Record committed, stale-discarded, or failed batch outcome. |
| `dashboard_commit` | `commit_status: "committed"`, `views`, `state`, `dashboard_revision` | Apply the authoritative snapshot. |

For migration, the browser accepts a legacy `dashboard_commit` that omits
`commit_status`. Any explicit status other than `committed` is ignored for
dashboard mutation.

## 6. Trace contract

`events.jsonl` records response id, intent epoch, base revision, tool metadata,
and the final commit status. Important event names are:

```text
response_overlap
response_overlap_resolved
tool_batch_started
tool_result_staged
tool_batch_stale_discarded
tool_batch_finished
```

`tool_batch_finished` includes `commit_status` and `discard_reason`; this lets a
research trace distinguish a physically completed legacy handler from a result
that became semantically obsolete.

## 7. Verification

From the repository root:

```powershell
& 'C:\Users\admin\miniconda3\python.exe' -m pytest backend/tests -q
cd frontend
npm test -- --run
npm run build
```

The focused realtime tests prove that speech onset does not cancel, a
backchannel resumes, a revision during an in-flight draft yields
`stale_discarded` without a dashboard commit, the legacy snapshot bridge
restores committed globals, and a valid multi-tool mutation batch commits once
and orders all Qwen function outputs before `response.create`.
