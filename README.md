# VerbalVis FD-Voice

VerbalVis FD-Voice is a voice-only conversational visual analytics prototype for
exploring the Olist Brazilian E-Commerce dataset. The system combines Qwen
Omni-Realtime, a shared Vega-Lite dashboard, structured analytical tools, compact
conversation provenance, and immediate speech interruption.

This repository implements the FD-Voice condition. Text-CVA remains a separate
experimental condition. Study results should be described as differences between
the complete FD-Voice and Text-CVA configurations, not as an isolated causal effect
of full-duplex speech.

## Final Runtime Boundary

The system uses the simple R-A interruption policy:

```text
Qwen Semantic VAD speech_started
→ stop all audio from the current assistant response
→ reject late audio from that response
→ send response.cancel
→ process the newest user utterance
```

The browser enforces a single-response playback invariant: audio belonging to two
assistant responses can never remain scheduled together. A new response stops the
old playback queue before becoming current.

A local dashboard tool batch is non-preemptive. Once execution starts, microphone
audio is blocked until the complete batch has finished and its follow-up response
has been requested. The prototype intentionally does not implement tool rollback,
stale-result epochs, transactional cancellation, or multi-agent planning.

## Compact Transcript

The transcript is a flat chronological timeline:

```text
11:28:53  YOU   Compare week 48 with the actual category peaks
11:28:54  TOOL  Compare category metrics
11:29:01  AI    Week 48 is not a synchronized peak across all categories…
```

One assistant `response_id` owns one row; streaming deltas append to that row.
YOU and AI rows use at most two visible lines to minimize height. An interrupted AI
row keeps a small `×` marker. TOOL rows use one line by default. Clicking a TOOL row
expands only:

- the exact tool name;
- the JSON parameters.

Internal call IDs, response IDs, result payloads, durations, and contracts are not
shown in the transcript.

## Eleven Model-Facing Tools

### Scope

1. `update_analysis_scope`
   - `replace`, `add`, `remove`, or `clear` global filters.

### Data analysis

2. `aggregate_data`
   - returns grouped metrics without creating a chart.
3. `compare_selected_groups`
   - compares explicitly selected states, categories, scores, weeks, or months.
4. `compare_category_metrics`
   - selects one common Top-N product-category set, creates coordinated views, and
     returns compact evidence.

### Visualization

5. `create_visual`
   - creates one line, bar, or scatter view.
6. `update_visual`
   - changes an existing view while preserving its `view_id`.
7. `delete_visual`
   - removes one view.

### Attention and evidence

8. `highlight_visual`
   - focuses views and can highlight a week, category, or their intersection inside
     a Vega-Lite chart.
9. `inspect_visual`
   - reads one view and can focus on a series, selected x values, and a Top-K subset.
10. `summarize_dashboard`
    - returns current filters, views, encodings, statistics, and highlights.

### Recovery

11. `undo_last_action`
    - restores the state before the most recent completed dashboard-changing action.

The tool implementation and schemas have one source of truth: `backend/tools.py`.
Older files such as `demo_tools.py`, `realtime_nonpreemptive.py`, and
`tool_runtime_patch.py` are now tiny import-safe compatibility modules and contain
no separate runtime logic.

## Supported Visual and Metric Vocabulary

Charts:

```text
line
bar
scatter
```

Core metrics:

```text
order_count
product_revenue
low_score_ratio
delivery_days
late_ratio
review_score
```

Dimensions and series include month, week, date, customer state, product category,
and review score.

## Fixed Metric Semantics

Low-score orders are fixed as:

```text
review_score <= 2
```

Product-category revenue is:

```sql
SUM(price)
```

Freight is excluded. Category delivery and service metrics first deduplicate to one
row per `order_id + product_category`, so multiple items of the same category in one
order do not receive extra weight.

## Study Task Coverage

### Task A: SP weekly operational risk

Reliable tool path:

1. `update_analysis_scope` with SP and 2017-10-01 through 2018-05-31;
2. `compare_category_metrics` with:
   - `mode="weekly_trends"`;
   - `top_n=5`;
   - `rank_by="product_revenue"`;
   - `metrics=["order_count", "low_score_ratio", "delivery_days", "late_ratio"]`;
   - `focus_week="2017-W48"`.

The result contains four multi-series weekly line charts using exactly the same
product-revenue Top-5 categories. Evidence contains each category's focus-week
value, peak week/value, and top weeks for each metric.

### Task B: RJ delivery-resource allocation

Reliable tool path:

1. `update_analysis_scope` with RJ and the same date range;
2. `compare_category_metrics` with:
   - `mode="category_summary"`;
   - `top_n=15`;
   - `rank_by="product_revenue"`;
   - `metrics=["low_score_ratio", "delivery_days", "product_revenue", "order_count"]`.

The result contains four bar charts and one compact evidence row per category for
evaluating `office_furniture` and alternatives.

These paths are recommendations, not hard-coded conversations. The model can use
all eleven tools for free exploration, revision, comparison, evidence inspection,
and recovery.

## Main Files

```text
frontend/src/composables/useAudio.js
  PCM microphone capture, single-response PCM playback, interruption, cursor

frontend/src/composables/useWebSocket.js
  one WebSocket protocol, response filtering, transcript and dashboard routing

frontend/src/components/Dashboard.vue
  compact top bar, chart grid, and flat transcript timeline

frontend/src/stores/dashboard.js
  views, highlights, and transcript timeline state

frontend/src/specFactory.js
  line/bar/scatter Vega-Lite specifications

frontend/src/highlightSpec.js
  in-chart value and intersection highlighting

backend/tools.py
  dashboard state, metric queries, eleven schemas, eleven implementations, undo

backend/realtime.py
  Qwen session, Semantic VAD, immediate interruption, sequential tool batches, logs

backend/demo_validation.py
  offline validation for all tools and both study tasks
```

## Validation

Backend validation does not call Qwen:

```bat
cd /d F:\VerbalVis2\backend
python -m compileall .
python demo_validation.py
```

It validates the exact eleven-tool surface, all general tools, undo, Task A, Task B,
`SUM(price)` revenue, order-category delivery grain, coordinated view refresh, and
`office_furniture` membership in the stated RJ Top-15 premise.

Frontend validation:

```bat
cd /d F:\VerbalVis2\frontend
npm install
npm run validate:highlight
npm run build
```

GitHub Actions runs backend compilation and validation, highlight validation, and
the frontend production build for pushes to `fd-voice` and pull requests.

## Qwen Connection

Current deployments should provide a Bailian workspace ID. The backend builds the
regional WebSocket URL automatically:

```env
DASHSCOPE_API_KEY=your_api_key
QWEN_WORKSPACE_ID=your_workspace_id
QWEN_REGION=beijing
QWEN_VOICE=Ethan
```

For a custom gateway or an already complete WebSocket endpoint, set:

```env
QWEN_REALTIME_URL=wss://your-host/api-ws/v1/realtime
```

`QWEN_REALTIME_URL` has priority over `QWEN_WORKSPACE_ID`. Existing installations
without either variable fall back to the earlier DashScope realtime host and emit a
warning; new installations should use a workspace ID or explicit URL.

## Start

Start the backend:

```bat
cd /d F:\VerbalVis2\backend
uvicorn main:app --reload --port 8000
```

Start the frontend:

```bat
cd /d F:\VerbalVis2\frontend
npm install
npm run dev -- --port 5173
```

Open `http://localhost:5173` and press **Start mic**. Space also toggles the
microphone when focus is not inside an input element.
