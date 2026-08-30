# VerbalVis FD-Voice

## What it is

VerbalVis FD-Voice is a single-participant, full-duplex voice-driven visual
analytics research prototype for the Olist Brazilian E-Commerce dataset. One
browser conversation combines Qwen-Omni-Realtime, a shared Vega-Lite
dashboard, and structured analytical tools. It is intended for local research
and demonstration—not as a production service or deployment.

The prototype treats an interruption as an analytical decision only after the
user's final transcription is available. This preserves an answer while a
participant gives a short acknowledgement, while still allowing a later,
changed request to supersede it.

## Architecture

```text
Browser microphone + Vue/Pinia dashboard
                 | WebSocket
                 v
FastAPI (main.py) -> realtime coordinator -> Qwen-Omni-Realtime
                 |                           |
                 v                           v
       draft tool execution <--- function calls
                 |
                 v
      in-memory DuckDB + dashboard snapshot
                 |
                 v
       committed dashboard -> Vega-Lite browser views
```

One browser page owns one backend WebSocket and one Qwen Realtime session. The
microphone can start and stop within that session; dashboard state and undo
history are in memory, so a second browser session is rejected while one is
active.

Qwen configuration is read when the backend starts. Copy
`backend/.env.example` to `backend/.env`, set `DASHSCOPE_API_KEY`, and restart
Uvicorn after changing it. The supplied defaults are `QWEN_REGION=beijing`,
`QWEN_REALTIME_MODEL=qwen3.5-omni-plus-realtime`, and `QWEN_VOICE=Ethan`.
`QWEN_WORKSPACE_ID` is optional, and `QWEN_REALTIME_URL` is an optional complete
endpoint override. Endpoint selection prefers `QWEN_REALTIME_URL`, then
`QWEN_WORKSPACE_ID`, then the regional DashScope public endpoint; the runtime
also accepts `DASHSCOPE_WORKSPACE_ID` and `WORKSPACE_ID` as workspace aliases.
For provider setup and protocol details, consult the
[Qwen-Omni-Realtime documentation](https://help.aliyun.com/zh/model-studio/realtime)
rather than treating this README as an upstream event reference.

## Response transaction guarantee

Each provider response is associated with a response id, an intent epoch, and
a base dashboard revision. `speech_started` is an overlap observation only: it
does not itself cancel output or create a new intent. Interruption
classification happens after final transcription. A backchannel or recognition
repair keeps the current response eligible; a stop-only utterance cancels it;
an analytical revision supersedes it and advances the intent epoch.

Tool calls execute in a private dashboard draft. A batch can commit only when
its response transaction still matches the current epoch and dashboard
revision. Stale batches cannot update the dashboard, browser tool cards, or
model context. The legacy synchronous handlers are not CPU-preemptible: a
superseded handler may finish physically, but its result is discarded before it
becomes observable.

The authoritative states, WebSocket messages, and commit rules are in
[the runtime contract](docs/verbalvis-runtime-contract.md).

## Quick start

From a clean Windows development environment, make Python and Node.js
available on `PATH`, then open two PowerShell terminals from the repository
root. In the backend terminal, after copying `.env`, set a local
`DASHSCOPE_API_KEY` in that file before starting Uvicorn:

```powershell
cd backend
python -m pip install -r requirements-dev.txt
Copy-Item .env.example .env
```

Set the key in the copied `.env`, then start the backend:

```powershell
uvicorn main:app --host 127.0.0.1 --port 8000
```

In a second terminal:

```powershell
cd frontend
npm ci
npm run dev -- --port 5173
```

Open the local URL printed by Vite (normally `http://localhost:5173`). The
backend health endpoint at `http://127.0.0.1:8000/health` reports whether Qwen
is configured without exposing the key. With no key, the initial dashboard
remains available but the application reports a configuration error and keeps
microphone start disabled.

## Demo script

1. Ask for a state/category comparison.
2. During assistant playback, say: “yes, continue”. This is a backchannel and
   does not cancel the response.
3. Then say: “instead, show only 2017 orders”. This is an analytical revision
   and creates a new intent epoch.
4. Inspect the local transaction trace for the overlap resolution and final
   tool-batch commit status.

Use synthetic or scrubbed material when inspecting or sharing local traces;
see [PRIVACY.md](PRIVACY.md).

## Model-facing tools and metric semantics

The model can call these eleven tools:

| Tool | Current effect |
| --- | --- |
| `update_analysis_scope` | Replaces, adds, removes, or clears shared filters. |
| `aggregate_data` | Computes grouped metrics without creating a chart. |
| `compare_selected_groups` | Compares named states, categories, scores, or time values. |
| `compare_category_metrics` | Creates coordinated Top-N category comparison views; a state/date scope can be applied atomically. |
| `create_visual` | Adds a line, bar, or scatter visualization. |
| `update_visual` | Changes a visualization while retaining its view id. |
| `delete_visual` | Removes a visualization. |
| `highlight_visual` | Changes view or data-value highlighting. |
| `inspect_visual` | Reads an existing view without changing it. |
| `summarize_dashboard` | Returns the current dashboard state and compact statistics. |
| `undo_last_action` | Restores the previous completed dashboard-changing action. |

The metric vocabulary is `order_count`, `product_revenue`,
`low_score_ratio`, `delivery_days`, `late_ratio`, and `review_score`.
`order_count` is a distinct-order count. `product_revenue` is `SUM(price)` and
excludes freight. `low_score_ratio` is the share of reviewed distinct orders
with `review_score <= 2`; `delivery_days` and `review_score` are averages;
and `late_ratio` is the share of distinct orders with a known delivery status
that are late. For category service metrics, the grouping grain is one row per
`order_id + product_category`.

## Verification

For the local release checks, run the following from the repository root once
the script is available:

```powershell
scripts/verify_verbalvis_release.ps1
```

That verifier will be added by a later task; it is not present in this revision.
The manual browser checks are recorded in
[the release checklist](docs/verbalvis-release-checklist.md). Unit tests do
not represent provider/browser end-to-end checks or user-effect studies.

## Dataset and privacy

The application reads local Olist CSV files from `backend/data/olist/`; it does
not fetch or serve them. The dataset source/reuse boundary, expected files,
integrity command, and metric definitions are documented in
[docs/DATASET.md](docs/DATASET.md). Before sharing data, verify the source's
applicable reuse and redistribution terms.

[PRIVACY.md](PRIVACY.md) describes the local-log boundary and minimum
research-use protocol. Conversation text, tool arguments, dashboard state, and
transaction metadata may appear in local traces; do not commit or publish real
participant material.

## Standalone DataOps boundary

[dataops_agent/README.md](dataops_agent/README.md) documents a standalone
DataOps package. Its potential boundary with VerbalVis is described in
[docs/dataops-agent-verbalvis-integration.md](docs/dataops-agent-verbalvis-integration.md).
It is not wired into the VerbalVis realtime path.

## Limitations

- One active in-memory browser session is supported.
- Legacy synchronous handlers have no CPU-level cancellation.
- Provider/browser end-to-end checks and user-effect studies are not
  represented by unit tests.
- This repository makes no production or deployment claim.

## Contributing and security

Please read [CONTRIBUTING.md](CONTRIBUTING.md) before proposing a change and
[SECURITY.md](SECURITY.md) before reporting a vulnerability. The project is
released under the [MIT License](LICENSE). Never commit API keys, private data,
or unredacted participant traces.
