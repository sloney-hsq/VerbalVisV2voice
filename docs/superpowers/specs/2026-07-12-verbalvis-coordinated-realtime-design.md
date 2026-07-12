# VerbalVis Coordinated Realtime Redesign

## Objective

Build a functional, inspectable research prototype whose implementation supports
its paper claims: users may interrupt an unfinished assistant response, stale
response output must not resume, only eligible completed responses may submit
tools, an admitted tool batch runs non-preemptively, and the final explanation
must use the committed dashboard state and verified analytical evidence.

This design targets full-paper-quality engineering and reproducibility, but it
does not claim that engineering alone satisfies IEEE VIS acceptance criteria.

## Research claim and boundary

VerbalVis studies response-scoped coordination in a speech-first visual
analytics system. Its implemented policy is:

1. A new user speech start supersedes the unfinished assistant response.
2. Audio and transcript events from superseded responses are discarded.
3. Tool calls are admitted only from the current, completed response and current
   intent epoch.
4. Once admitted, a tool batch is sequential, fail-fast, non-preemptive, and is
   not rolled back.
5. After the batch, one authoritative dashboard revision and all tool outputs
   are returned to Qwen before exactly one `response.create`.

The prototype does not promise cancellation or rollback of running tools,
multi-user concurrency, deterministic reproduction of the proprietary model,
or perfect rejection of backchannels such as “嗯”.

## Alternatives considered

### Prompt-only repair

Rejected. Prompt rules cannot materialize a missing cross-metric sort field,
verify a rendered category order, reject stale provider events, or make a
blocked Qwen reader consume events concurrently.

### Event sourcing, cancellable tools, and rollback

Rejected. These capabilities are unnecessary for the research claim and would
make the prototype harder to understand and evaluate.

### Thin coordinator plus verified declarative state

Selected. Keep FastAPI, DuckDB, Qwen Realtime, Vue, Pinia, and Vega-Lite. Add a
small response-epoch coordinator, a monotonic dashboard revision, explicit view
postconditions, and first-class comparison groups.

## Target architecture

### Realtime adapter

`backend/realtime.py` remains the only Qwen and browser WebSocket adapter. It
must not contain analytical semantics. It owns network I/O, continuous provider
event consumption, one background tool batch, and protocol logging.

`backend/response_coordinator.py` is a pure state machine. It owns:

- monotonic `intent_epoch`;
- response-to-epoch bindings;
- current, interrupted, and executed response/call identities;
- pending complete function arguments keyed by `(response_id, call_id)`;
- eligibility decisions with stable rejection reasons;
- the expected post-tool response epoch.

The Qwen reader must never await the duration of a tool batch. It schedules one
background batch task and continues consuming provider events. Events arriving
while the input window is closed are consumed, rejected, and logged immediately.

### Dashboard and tool state

`backend/tools.py` remains the single dashboard writer in this single-user
prototype. A monotonic `dashboard_revision` increments once for each successful
dashboard-changing tool. Undo creates a new revision; revisions never decrease.

Tool success means both execution and semantic postconditions succeeded. Each
visual mutation returns a compact postcondition object:

```json
{
  "order_verified": true,
  "resolved_order": ["SP", "RJ", "MG"],
  "sort_by": "order_count",
  "sort_order": "desc",
  "dashboard_revision": 7
}
```

If the requested sort field cannot be materialized or the resolved order fails
verification, the tool returns `success=false`; metadata alone is never treated
as proof.

### View contract

Every discrete bar view carries an `order_contract`:

```json
{
  "field": "product_category",
  "mode": "metric",
  "by": "product_revenue",
  "direction": "desc",
  "values": ["watches_gifts", "bed_bath_table"],
  "verified": true
}
```

When `sort_by` is a metric other than the visible Y metric, the backend includes
that metric in the grouped query before sorting. A Top-N series chart separates
series ranking from temporal X-axis order internally; a missing or invalid
series rank metric defaults to the visible Y metric.

`inspect_visual` and dashboard metadata expose the order contract, comparison
identity, scope, Top-N basis, focus value, and revision so the model can inspect
rather than guess.

### Comparison group

`compare_category_metrics` creates one `ComparisonGroup` with:

- one `comparison_id`;
- one scope and one ranked category cohort;
- one explicit `category_order` shared by all views;
- four view IDs and a `2x2` layout hint;
- one stable series color domain;
- an optional persistent focus X value.

Task A uses SP, 2017-10-01 through 2018-05-31, product-revenue Top 5,
`order_count`, `low_score_ratio`, `delivery_days`, and `late_ratio`. All four
views are weekly multi-series lines. `2017-W48` is a persistent reference line,
not a temporary highlight that dims the rest of the chart. Evidence includes
peak week, focus value, focus rank among observed weeks, and order support.

Task B uses RJ and the same dates, product-revenue Top 15, and the four requested
metrics. Every horizontal bar chart uses the exact product-revenue order. The
evidence includes the rank of every category for every metric so the assistant
cannot reuse the revenue rank as an order-count rank.

### Browser state

The backend remains authoritative. `init`, `views_update`, and
`dashboard_state` carry a revision. Pinia ignores revisions older than the most
recent committed revision. It does not re-sort analytical data.

`Dashboard.vue` groups views with the same `comparison_id` in a dedicated 2x2
section. `ChartSlot.vue` shows concise badges for shared order and focus week.
`specFactory.js` uses the explicit `order_contract.values` array for the
discrete Vega-Lite scale and uses the shared comparison category domain for
line colors and legend order.

After Vega rendering, the browser sends a small `view_render_result` event with
view ID, revision, and success/error. This is logged for evaluation but does not
delay the voice response or change tool semantics.

## Realtime sequence and invariants

```text
speech_started
→ intent_epoch += 1
→ invalidate current response
→ stop browser playback
→ response.cancel when a response is generating

response.function_call_arguments.done
→ register complete arguments only; do not execute

response.done(status=completed)
→ require current response and current epoch
→ reconcile completed output items with pending calls
→ validate tool names, JSON objects, IDs, and duplicate calls
→ schedule one background non-preemptive batch

batch
→ close input window and clear provider input audio
→ execute sequentially with fail-fast dependency handling
→ return every function_call_output
→ publish one final revision snapshot
→ send one response.create

post-tool response.created
→ bind to the same epoch
→ reopen input window
```

Required invariants:

- At most one assistant `response_id` may produce browser audio.
- Older epochs cannot update audio, transcript, tool, or dashboard state.
- A `call_id` executes at most once.
- Tool selection uses complete arguments and a completed current response.
- The Qwen reader remains live while tools execute.
- A dashboard revision is monotonic and frontend snapshots never move backward.
- A successful sort result includes a verified explicit order.

## Prompt policy

The stable system prompt contains role, metric semantics, tool-selection rules,
ambiguity recovery, evidence requirements, and response brevity. Fast-changing
dashboard metadata is injected separately.

For “make view 5 follow view 3,” the model must inspect view 3 before updating
view 5. It may claim completion only when the returned postcondition says the
order is verified. For Task B it must give one explicit support/non-support
decision and one replacement category when it does not support the proposal.

## Failure handling

- Invalid pending tool plan: reject before execution, log the reason, return a
  failed function output, and request a concise corrected response.
- Tool failure inside an admitted batch: keep completed earlier actions, skip
  dependent later calls, publish the actual final revision, and state the
  partial failure. No rollback is claimed.
- Stale provider event: discard and log `stale_epoch`, `interrupted_response`,
  or `duplicate_call`.
- Vega render failure: preserve the authoritative backend state, show a chart
  error, and log `view_render_result(success=false)`.
- Revision gap: frontend accepts the newest full snapshot and records the gap;
  no optimistic patch merging is used.

## Evaluation and reproducibility

Events must include UTC and monotonic timestamps, sequence number, condition,
task, epoch, utterance/response/item/call/batch IDs, response status, eligibility
decision, dashboard base/result revision, tool arguments/results/errors,
postconditions, render result, audio stop cursor, cancel and first-audio latency,
model/VAD configuration, prompt/schema version, and git commit.

Release or archive the Olist data reference and checksums, preprocessing and
metric definitions, schemas and prompts, Task A/B scripts and rubrics, condition
configuration, anonymized event traces or replay fixtures, analysis code,
environment lock files, and a demo video. Human-participant reporting must state
ethics oversight or exemption and informed consent status. Audio recording needs
explicit consent and a retention policy.

## Acceptance criteria

1. Cross-metric sort reproduces `SP, RJ, MG, ...` for a low-score state chart
   ordered by order count, and the order is deterministic across repeated calls.
2. All Task B views compile to the same explicit revenue-ranked Y domain.
3. Task A produces four weekly multi-series views with a visible W48 reference
   and a common Top-5 color domain.
4. Task B evidence reports independent revenue, order, low-score, and delivery
   ranks for `office_furniture` and every comparison category.
5. A superseded response cannot execute a registered pending call.
6. The Qwen reader consumes speech/control events while a tool task runs.
7. Frontend rejects stale revisions and logs every chart render outcome.
8. Existing build, highlight, session, normalized-chart, Task A, and Task B
   validations continue to pass.

## Official references

- Qwen client events: https://help.aliyun.com/zh/model-studio/client-events
- Qwen server events: https://help.aliyun.com/zh/model-studio/server-events
- Qwen Realtime: https://help.aliyun.com/zh/model-studio/realtime
- Qwen interaction flow: https://help.aliyun.com/zh/model-studio/omni-realtime-interaction-process
- IEEE VIS 2026 paper guidelines: https://ieeevis.org/year/2026/info/call-participation/paper-submission-guidelines/
- IEEE VIS 2026 open practices: https://ieeevis.org/year/2026/info/open-practices/open-practices/
