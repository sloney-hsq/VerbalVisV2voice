# VerbalVis FD-Voice

VerbalVis FD-Voice is a voice-only conversational visual analytics prototype for
the Olist Brazilian E-Commerce dataset. It combines Qwen Omni-Realtime, a shared
Vega-Lite dashboard, structured analytical tools, compact conversation provenance,
and immediate speech interruption.

This repository implements the **FD-Voice** study condition. Text-CVA is maintained
as a separate condition. Results should be described as differences between the
complete FD-Voice and Text-CVA configurations, not as an isolated causal effect of
full-duplex speech.

## Final Architecture

The production path is deliberately small:

```text
Browser microphone
→ frontend/src/composables/useAudio.js
→ frontend/src/composables/useWebSocket.js
→ backend/main.py
→ backend/realtime.py
→ Qwen-Omni-Realtime

Qwen function call
→ backend/realtime.py
→ backend/tools.py
→ DuckDB
→ views_update / dashboard_state
→ Pinia dashboard store
→ Vega-Lite ChartSlot
```

There is one realtime implementation and one tool implementation:

```text
backend/realtime.py
backend/tools.py
```

The backend is intentionally **single-session** because dashboard state is held in
memory for one study participant. A second browser is rejected instead of sharing
filters, views, or undo history with the active participant.

## Realtime Boundary

The system uses the simple R-A interruption policy:

```text
Qwen Semantic VAD speech_started
→ stop all audio from the current assistant response
→ reject late audio from that response
→ send response.cancel when generation is still active
→ process the newest completed user utterance
```

The browser enforces a single-response playback invariant: audio from two assistant
responses can never remain scheduled together. A new response stops the old queue
before becoming current.

A local dashboard tool batch is a non-preemptive input-closed window:

```text
tool call selected
→ close the tool-selection response in the browser
→ block microphone forwarding in the browser
→ reject audio again in the backend
→ clear Qwen's partial input buffer
→ execute all tool calls sequentially
→ return every function_call_output
→ send one response.create
→ reopen microphone forwarding
```

Running tools are never cancelled or rolled back. The prototype does not implement
stale-result epochs, transactional cancellation, or multi-agent planning.

## Qwen Realtime Compliance

The implementation follows the current Qwen-Omni-Realtime WebSocket flow:

- `session.update` configures text+audio output, PCM formats, Semantic VAD,
  transcription, instructions, and tools;
- browser PCM is sent with `input_audio_buffer.append`;
- audio is received from `response.audio.delta`;
- assistant text is received from `response.audio_transcript.delta`;
- user text is received from
  `conversation.item.input_audio_transcription.delta/completed`;
- interruption sends `response.cancel`;
- tool results are returned with `conversation.item.create` using
  `function_call_output`;
- after all tool outputs, one `response.create` requests the final spoken answer;
- `response.done` closes each model response.

Tools and Qwen WebSearch are not enabled together.

## Browser Event Contract

### Backend → browser

```text
init
session_updated
session_ready
assistant_response_started
audio
transcript
response_done
speech_started
speech_stopped
assistant_playback_stop
tool_execution_started
tool_call
tool_result
views_update
dashboard_state
tool_execution_finished
runtime_state
error
```

### Browser → backend

```text
audio
playback_stopped
disconnect
```

`response_id` is the authority for assistant audio and transcript routing.
`call_id` is the authority for matching a TOOL timeline row with its result.
The backend is the authority for filters, views, highlights, and tool execution.

## Compact Transcript

The transcript is a flat chronological timeline:

```text
11:28:53  YOU   Compare week 48 with the actual category peaks
11:28:54  TOOL  Compare category metrics
11:29:01  AI    Week 48 is not a synchronized peak across all categories…
```

One assistant `response_id` owns one row; streaming deltas append to that row. YOU
and AI rows use at most two visible lines. An interrupted AI row keeps a small `×`.
TOOL rows use one line by default. Clicking a TOOL row expands only:

- the exact tool name;
- the JSON parameters.

Internal IDs, result payloads, durations, and contracts are not shown.

## Eleven Model-Facing Tools

### Scope

1. `update_analysis_scope`
   - replace, add, remove, or clear global filters.

### Data analysis

2. `aggregate_data`
   - return grouped metrics without creating a chart.
3. `compare_selected_groups`
   - compare explicitly selected states, categories, scores, weeks, or months.
4. `compare_category_metrics`
   - select one common Top-N category set, create coordinated views, and return
     compact evidence.

### Visualization

5. `create_visual`
   - create one line, bar, or scatter view.
6. `update_visual`
   - change an existing view while preserving its `view_id`.
7. `delete_visual`
   - remove one view.

### Attention and evidence

8. `highlight_visual`
   - focus views and highlight a week, category, or their intersection.
9. `inspect_visual`
   - read one view, optionally restricted to a series, X values, and Top-K rows.
10. `summarize_dashboard`
    - return current filters, views, encodings, statistics, and highlights.

### Recovery

11. `undo_last_action`
    - restore the state before the most recent completed dashboard-changing action.

Schemas and implementations have one source of truth: `backend/tools.py`.

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

Dimensions and series include month, week, date, state, product category, and
review score.

## Fixed Metric Semantics

Low-score orders are fixed as:

```text
review_score <= 2
```

Product-category revenue is:

```sql
SUM(price)
```

Freight is excluded. Category delivery and service metrics deduplicate to one row
per `order_id + product_category`, so multiple same-category items in one order do
not receive extra weight.

## Study Task Coverage

### Task A: SP weekly operational risk

Reliable path:

1. `update_analysis_scope` with SP and 2017-10-01 through 2018-05-31;
2. `compare_category_metrics` with:
   - `mode="weekly_trends"`;
   - `top_n=5`;
   - `rank_by="product_revenue"`;
   - `metrics=["order_count", "low_score_ratio", "delivery_days", "late_ratio"]`;
   - `focus_week="2017-W48"`.

The four multi-series line charts use exactly the same Top-5 categories. Evidence
contains each category's focus-week value, peak week/value, and top weeks.

### Task B: RJ delivery-resource allocation

Reliable path:

1. `update_analysis_scope` with RJ and the same date range;
2. `compare_category_metrics` with:
   - `mode="category_summary"`;
   - `top_n=15`;
   - `rank_by="product_revenue"`;
   - `metrics=["low_score_ratio", "delivery_days", "product_revenue", "order_count"]`.

The result contains four bar charts and one evidence row per category for evaluating
`office_furniture` and alternatives.

These paths are recommendations, not hard-coded conversations. The model can use
all eleven tools for free exploration, revision, comparison, evidence inspection,
and recovery.

## Main Files

```text
frontend/src/composables/useAudio.js
  16 kHz PCM capture, single-response 24 kHz playback, interruption cursor

frontend/src/composables/useWebSocket.js
  browser protocol, response filtering, transcript and dashboard routing

frontend/src/components/Dashboard.vue
  compact top bar, chart grid, flat transcript timeline

frontend/src/stores/dashboard.js
  views, highlights, and timeline state

frontend/src/stores/runtime.js
  connection, listening, processing, speaking, and tool-running phases

frontend/src/specFactory.js
  line/bar/scatter Vega-Lite specifications

frontend/src/highlightSpec.js
  in-chart value and intersection highlighting

backend/main.py
  FastAPI entry point and single-session guard

backend/realtime.py
  Qwen session, Semantic VAD, R-A interruption, tool boundary, logs

backend/tools.py
  dashboard state, metric queries, eleven tools, undo

backend/demo_validation.py
  offline validation for all tools and both study tasks
```

## Qwen Connection

A current Bailian workspace endpoint is required:

```env
DASHSCOPE_API_KEY=your_api_key
QWEN_WORKSPACE_ID=your_workspace_id
QWEN_REGION=beijing
QWEN_VOICE=Ethan
```

For a custom gateway or complete WebSocket endpoint:

```env
QWEN_REALTIME_URL=wss://your-host/api-ws/v1/realtime
```

`QWEN_REALTIME_URL` has priority over `QWEN_WORKSPACE_ID`. The backend does not fall
back to the retired generic DashScope realtime host.

## Validation

Backend validation does not call Qwen:

```bat
cd /d F:\VerbalVis2\backend
python -m compileall .
python demo_validation.py
```

Frontend validation:

```bat
cd /d F:\VerbalVis2\frontend
npm install
npm run validate:highlight
npm run build
```

GitHub Actions runs backend compilation and tool/task validation, highlight
validation, and the frontend production build for pushes to `fd-voice`.

## Start

```bat
cd /d F:\VerbalVis2\backend
uvicorn main:app --reload --port 8000
```

```bat
cd /d F:\VerbalVis2\frontend
npm install
npm run dev -- --port 5173
```

Open `http://localhost:5173` and press **Start mic**. Space toggles the microphone
when focus is not inside an input element.
