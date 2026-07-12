# VerbalVis Coordinated Realtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make VerbalVis tool results, coordinated views, realtime interruption, browser state, and experiment logs agree with one authoritative current intent and dashboard revision.

**Architecture:** Keep the current FastAPI/DuckDB/Qwen/Vue stack. Add a pure response-epoch coordinator and explicit analytical view postconditions; keep running tool batches non-preemptive and publish full revisioned snapshots to a 2x2 comparison UI.

**Tech Stack:** Python 3, FastAPI, asyncio, DuckDB, Qwen Realtime WebSocket, Vue 3, Pinia, Vega-Lite 6, Node assertion scripts.

## Global Constraints

- Preserve all pre-existing uncommitted changes; do not reset, checkout, or rewrite unrelated files.
- Keep one browser, one backend session, one Qwen session, and one dashboard writer.
- Do not add running-tool cancellation, rollback, event sourcing, a database server, a queue service, or multi-agent product behavior.
- A started tool batch is sequential, fail-fast, non-preemptive, and not rolled back.
- Qwen tool follow-up remains `conversation.item.create(function_call_output)` for every call, then exactly one `response.create`.
- Low score is `review_score <= 2`; product revenue is `SUM(price)` without freight; category delivery metrics use one `order_id + product_category` row.
- Task A and Task B are general uses of `compare_category_metrics`, not hard-coded one-off endpoints.
- Backend state is authoritative; frontend only accepts full snapshots at nondecreasing revisions.
- Every production behavior change starts with a failing validation.

---

### Task 1: Verified analytical order and evidence

**Files:**
- Modify: `backend/tools.py`
- Modify: `backend/demo_validation.py`

**Interfaces:**
- Produces: `dashboard_revision: int` in `realtime_state()` and mutating tool payloads.
- Produces: `view["order_contract"]` with `field`, `mode`, `by`, `direction`, `values`, and `verified`.
- Produces: visual tool payload `postconditions` and comparison evidence `metric_ranks`.

- [ ] **Step 1: Add failing cross-metric and Task B order validations**

Add assertions equivalent to:

```python
created = tools.execute_tool("create_visual", {
    "chart_type": "bar", "x": "customer_state",
    "y": "low_score_ratio", "sort_by": "order_count",
    "sort_order": "desc", "title": "Low score by order volume",
})
view = view_by_id(created["payload"]["view_id"])
assert view["order_contract"]["values"][:3] == ["SP", "RJ", "MG"]
assert view["order_contract"]["verified"] is True
assert all("order_count" in row for row in view["data"])

expected = [row["product_category"] for row in task_b["payload"]["top_categories"]]
assert all(view(v)["order_contract"]["values"] == expected for v in task_b["payload"]["view_ids"])
assert all(set(row["metric_ranks"]) == set(task_b_metrics) for row in task_b["payload"]["evidence"])
```

- [ ] **Step 2: Run the backend validation and confirm RED**

Run: `cd backend; python demo_validation.py`

Expected: failure because `order_contract`, materialized `order_count`, or `metric_ranks` is missing.

- [ ] **Step 3: Materialize sort metrics and verify resolved order**

Change `_refresh_view` so a non-series view aggregates `y_field` plus a distinct
metric `sort_by`; reject a requested metric absent from every row. Store the
ordered unique X values in `order_contract`. Make `_rank_dimension` accept an
order and make Top-N series default an invalid/missing rank metric to `y_field`.

- [ ] **Step 4: Coordinate Task A/B metadata and evidence**

For category summaries use `rank_by` as every view's order basis, preserve the
comparison metadata on sort-only updates, set `focus_x=focus_week` for weekly
views, add focus rank/support, and compute independent descending metric ranks.

- [ ] **Step 5: Add monotonic dashboard revisions and payload postconditions**

Increment once after each successful dashboard-changing `execute_tool` call;
inject the new revision and order postconditions into the returned payload.

- [ ] **Step 6: Run the backend validation and confirm GREEN**

Run: `cd backend; python demo_validation.py`

Expected: `VerbalVis validation: PASS`, including deterministic cross-metric and shared Task B order assertions.

### Task 2: Response epoch and nonblocking tool worker

**Files:**
- Create: `backend/response_coordinator.py`
- Create: `backend/coordination_validation.py`
- Modify: `backend/realtime.py`

**Interfaces:**
- Produces: `PendingToolCall(response_id, call_id, item_id, output_index, name, arguments_raw, intent_epoch, origin_user_transcript)`.
- Produces: `ResponseCoordinator.begin_user_turn()`, `bind_response()`, `register_tool_call()`, `eligible_calls()`, `mark_executed()`, and `bind_followup()`.

- [ ] **Step 1: Write failing pure coordinator tests**

Cover stale response rejection, current completed response admission, duplicate
call rejection, unknown tool rejection, same-epoch post-tool response binding,
and no epoch increment when the input window is closed.

- [ ] **Step 2: Run coordinator validation and confirm RED**

Run: `cd backend; python coordination_validation.py`

Expected: import failure because `response_coordinator.py` does not exist.

- [ ] **Step 3: Implement the pure coordinator**

Use only dataclasses and Python collections. Return stable eligibility reason
codes: `current`, `stale_epoch`, `interrupted_response`, `response_not_completed`,
`unknown_tool`, `invalid_arguments`, and `duplicate_call`.

- [ ] **Step 4: Integrate official function argument completion**

Handle `response.function_call_arguments.done` in `_qwen_to_client`, register the
complete arguments, and reconcile them with completed `response.done.output`.
Never execute from a delta or from the done-arguments event alone.

- [ ] **Step 5: Move tool execution off the Qwen reader**

In `_response_done`, schedule one stored `asyncio.Task` instead of awaiting the
batch. Keep the provider reader active. Treat `tool_running` or
`awaiting_followup` as a closed backend input window. Await and cancel/close the
stored task during session shutdown without cancelling a normal admitted batch.

- [ ] **Step 6: Coalesce the authoritative browser snapshot**

Send tool progress per call but send one final `views_update` and
`dashboard_state` after the batch, both carrying the final revision. Include
epoch, base revision, and final revision in Qwen function outputs and logs.

- [ ] **Step 7: Run coordinator and existing session validations**

Run: `cd backend; python coordination_validation.py`

Run: `cd frontend; npm run validate:session`

Expected: both pass and the source validation confirms `_response_done` schedules rather than awaits the tool batch.

### Task 3: Revisioned 2x2 coordinated frontend

**Files:**
- Create: `frontend/src/components/ComparisonGroup.vue`
- Create: `frontend/scripts/validate-coordinated-comparison.mjs`
- Modify: `frontend/src/specFactory.js`
- Modify: `frontend/src/components/ChartSlot.vue`
- Modify: `frontend/src/components/Dashboard.vue`
- Modify: `frontend/src/stores/dashboard.js`
- Modify: `frontend/src/stores/runtime.js`
- Modify: `frontend/src/composables/useWebSocket.js`
- Modify: `frontend/package.json`

**Interfaces:**
- Consumes: backend `order_contract`, `comparison_id`, `comparison_config`, `comparison_categories`, `focus_x`, and `revision`.
- Produces: `view_render_result {view_id, revision, success, error}` browser event.

- [ ] **Step 1: Write the failing Vega and revision validation**

Create four Task B fixtures with one common explicit category order and assert
that all compiled Y scale domains equal it. Create a Task A fixture and assert a
persistent rule uses `2017-W48`. Assert the store source contains a stale-revision gate.

- [ ] **Step 2: Run validation and confirm RED**

Run: `cd frontend; node scripts/validate-coordinated-comparison.mjs`

Expected: failure because the explicit order, focus layer, or comparison group support is missing.

- [ ] **Step 3: Make Vega consume backend order and focus contracts**

Prefer `order_contract.values` as the discrete sort array. Preserve field-sort
fallback for independent views. Add a non-dimming reference-rule layer for
`focus_x`; keep temporary highlight behavior separate.

- [ ] **Step 4: Add comparison grouping and concise evidence badges**

Group consecutive views by `comparison_id`; render a header and an internal 2x2
grid. Show `Shared order: Product revenue ↓` and `Focus: 2017-W48` without exposing internal tool names.

- [ ] **Step 5: Gate snapshots by revision and report render outcome**

Ignore a views/dashboard event only when its revision is older than the current
revision. Emit `view_render_result` after `vegaEmbed` succeeds or fails and route
it through the browser WebSocket.

- [ ] **Step 6: Run frontend validations and build**

Run: `cd frontend; npm run validate:coordinated`

Run: `cd frontend; npm run validate:highlight`

Run: `cd frontend; npm run validate:normalized`

Run: `cd frontend; npm run validate:layout`

Run: `cd frontend; npm run validate:session`

Run: `cd frontend; npm run build`

Expected: every command exits 0.

### Task 4: Grounded prompt, protocol logs, and reproducibility handoff

**Files:**
- Modify: `backend/prompts.py`
- Modify: `backend/realtime.py`
- Modify: `backend/tool_contracts.py`
- Modify: `README.md`
- Modify: `frontend/scripts/validate-session-control.mjs`

**Interfaces:**
- Consumes: coordinator epoch/reason, dashboard revision, tool postconditions, and render-result events.
- Produces: linked experiment events and concise model instructions.

- [ ] **Step 1: Add failing source/log contract assertions**

Require prompt text to inspect a referenced source view before matching order and
to claim sort completion only with `order_verified=true`. Require runtime source
to log epoch, eligibility reason, base/final revision, and render results.

- [ ] **Step 2: Run validations and confirm RED**

Run: `cd frontend; npm run validate:session`

Expected: failure on at least one new protocol/log assertion.

- [ ] **Step 3: Tighten prompt and user-facing summaries**

Keep stable rules in the system prompt, inject compact revisioned dashboard
metadata, require a single explicit Task B recommendation, and prohibit rank
claims not present in `metric_ranks`.

- [ ] **Step 4: Add linked product events without logging secrets**

Every coordination/tool event includes monotonic sequence, epoch, response/call
or batch IDs, eligibility reason, revision, and timing. Log render success/error,
not SVG or API credentials. Keep raw provider events distinguishable by event type.

- [ ] **Step 5: Document exact claims, boundaries, task semantics, and commands**

Describe response-level interruption, non-preemptive tools, revision semantics,
Task A/B visual contracts, required human-subjects ethics reporting, and the
reproducibility asset checklist.

- [ ] **Step 6: Run the complete local verification**

Run: `cd backend; python -m compileall .`

Run: `cd backend; python demo_validation.py`

Run: `cd backend; python coordination_validation.py`

Run all frontend validation commands from Task 3 and `npm run build`.

Expected: all commands exit 0 with no assertion failures.

### Task 5: End-to-end browser verification and final review

**Files:**
- Review only; modify covering files only when verification exposes a defect.

**Interfaces:**
- Consumes: built backend and frontend behavior from Tasks 1-4.
- Produces: verified Task A, Task B, and interruption evidence.

- [ ] **Step 1: Start backend and frontend locally**

Run Uvicorn on `127.0.0.1:8000` and Vite on `127.0.0.1:5173` using hidden background processes.

- [ ] **Step 2: Verify Task A and Task B visually**

Task A must render one 2x2 group with four shared-color weekly line charts and a
W48 rule. Task B must render one 2x2 group whose four Y axes have the identical
revenue order and whose `office_furniture` ranks match backend evidence.

- [ ] **Step 3: Verify stale-state and render logging**

Confirm older revisions are ignored, render results appear in the session log,
and a failed Vega render does not become a spoken success claim.

- [ ] **Step 4: Review the full diff against the design**

Check no unrelated user change was overwritten, no secret entered logs, tool
batches remain non-preemptive and non-rollback, and all success statements have
postcondition evidence.

- [ ] **Step 5: Stop local processes and report evidence**

Stop only the processes started for this verification. Report exact commands,
pass/fail counts, remaining online-Qwen limitation, and modified files.
