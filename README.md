# VerbalVis-FD-Voice

VerbalVis-FD-Voice is a full-duplex, voice-only visual analytics prototype for
the Olist dashboard. It supports continuous microphone input, Qwen semantic VAD,
live user transcription, assistant speech and text output, dashboard tools,
barge-in during assistant playback, and experiment logs.

Text-CVA, Voice/Text switching, text input, `/ws/text`, and `/ws/qwen` are not
part of this project.

## Runtime

- Model: `qwen3.5-omni-plus-realtime`
- Voice: `Ethan`
- Input audio: 16 kHz PCM16
- Output audio: 24 kHz PCM16
- Turn detection: `semantic_vad`
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`
- WebSocket: `ws://localhost:8000/ws`

## Environment

```env
DASHSCOPE_API_KEY=你的API_KEY
QWEN_REGION=beijing
```

`QWEN_API_KEY` is also supported as a compatible fallback.

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

Open:

```text
http://localhost:5173
```

## Interaction Boundary

Only Qwen `input_audio_buffer.speech_started` stops an old assistant response.
Browser RMS activity does not pause assistant audio, stop playback, or send
`response.cancel`.

When `speech_started` arrives while a Qwen response is active, the backend marks
that response interrupted, asks the frontend to stop playback, clears the
streaming assistant transcript, and sends `response.cancel`. If generation has
already completed and only buffered browser audio remains, the backend stops
frontend playback without sending `response.cancel`.

## Non-preemptive Tool Boundary

Dashboard tool execution is intentionally non-preemptive. Once a tool batch has
started, it is allowed to finish normally. The project does not implement:

- stale-tool invalidation;
- rollback or transactions;
- intent epochs;
- tool-thread cancellation.

While a tool batch is running:

- the frontend stops forwarding new microphone chunks;
- the backend independently ignores any audio chunks that still arrive;
- all calls use the completed user transcript captured for that batch;
- calls are executed sequentially in the order returned by Qwen;
- the browser receives `tool_execution_started`, `tool_execution_finished`,
  `runtime_state`, and `dashboard_state` events;
- microphone streaming resumes after the post-tool Qwen response is requested.

There is no artificial four-call cap. The prompt discourages meaningless repeated
calls but allows the model to use all operations needed to complete an analysis.
A tool that has already entered `execute_tool()` is allowed to finish and update
the dashboard.

## Tool Design

The original general-purpose tools remain available for free exploration:

- `filter_data`: add or replace one global filter;
- `remove_filter`: remove filters for one field;
- `set_low_score_threshold`: redefine low-score orders;
- `append_visual`: create one custom chart;
- `delete_visual`: remove one view;
- `highlight_visual`: direct visual attention;
- `inspect_visual`: read authoritative chart data.

Two high-level tools complement these primitives:

### `set_analysis_scope`

Applies several global filters in one operation. It is useful when a request
contains a state and a date range. For both study tasks, the date range is:

```json
{
  "field": "order_date",
  "operator": "between",
  "value": ["2017-10-01", "2018-05-31"]
}
```

### `compare_category_metrics`

Selects one common Top-N product-category set within the current global scope and
creates coordinated comparison views for that same set.

- `mode="weekly_trends"`: one weekly multi-series line chart per metric;
- `mode="category_summary"`: one category bar chart per metric;
- `rank_by="revenue"`: select the shared category set by revenue;
- `focus_week="2017-W48"`: compare the proposed week with each metric peak.

The tool also returns compact evidence:

- Task A: per category and metric, peak week/value, focus-week value, and top weeks;
- Task B: one metric row per revenue Top-15 category.

The high-level tool does not replace free exploration. The realtime model may use
primitive tools before or after it, add other views, change scope, inspect a chart,
or follow a different analytical path.

## Demo Coverage

### Task A: SP peak-period operations

Recommended reliable path:

1. `set_analysis_scope` with `customer_state=SP` and the study date range;
2. `compare_category_metrics` with:
   - `mode="weekly_trends"`;
   - `top_n=5`;
   - `rank_by="revenue"`;
   - metrics `order_count`, `low_score_ratio`, `delivery_days`, `late_ratio`;
   - `focus_week="2017-W48"`.

This produces four weekly multi-series line charts using the same revenue Top-5
categories and returns evidence for deciding whether week 48 is a synchronized
order/risk peak.

### Task B: RJ delivery-resource allocation

Recommended reliable path:

1. `set_analysis_scope` with `customer_state=RJ` and the study date range;
2. `compare_category_metrics` with:
   - `mode="category_summary"`;
   - `top_n=15`;
   - `rank_by="revenue"`;
   - metrics `low_score_ratio`, `delivery_days`, `revenue`, `order_count`.

This produces four category bar charts using the same revenue Top-15 set and
returns a compact evidence table that includes `office_furniture` when the study
data premise holds.

## Dashboard State Feedback

The frontend includes a shared runtime panel showing:

- current phase: ready, listening, processing, speaking, reading, or updating;
- active tool names;
- global filter count;
- view count;
- current low-score definition;
- filtered row count when available;
- tool failures and the temporary input gate during tool execution.

This state feedback is informational. It does not add direct-manipulation controls
that would change the voice-only study condition.

## Logs

The original multi-file logs are preserved. Non-preemptive tool batches also
write `tool_execution.jsonl`, including batch duration, success/failure counts,
ignored audio chunks, and whether the post-tool response was requested.

Frontend playback completion is reported with `playback_stopped`, including
`reason=natural_end` for normal completion.

## Validation

Compile the backend:

```bat
cd /d F:\VerbalVis2\backend
python -m compileall .
```

Validate Task A and Task B directly against the bundled Olist data without
calling Qwen:

```bat
cd /d F:\VerbalVis2\backend
python demo_validation.py
```

The script checks:

- SP/RJ study scopes contain data;
- Task A creates four weekly multi-series line charts for one common Top-5 set;
- Task A returns peak and `2017-W48` evidence for all four metrics;
- Task B creates four bar charts for one common revenue Top-15 set;
- Task B returns all four requested metrics and verifies whether
  `office_furniture` is present in that Top-15 set.

Build the frontend:

```bat
cd /d F:\VerbalVis2\frontend
npm run build
```
