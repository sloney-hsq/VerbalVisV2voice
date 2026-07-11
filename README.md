# VerbalVis FD-Voice

VerbalVis is a full-duplex voice-driven conversational visual analytics prototype
for the Olist Brazilian E-Commerce dataset. The FD-Voice condition combines one
Qwen-Omni-Realtime conversation, a shared Vega-Lite dashboard, structured tools,
and immediate speech interruption.

## Session lifecycle

One browser page lifecycle owns one analysis conversation:

```text
open or refresh page
→ create one browser WebSocket
→ create one backend session
→ connect and configure one Qwen Realtime session
→ initialize the dashboard and conversation context
```

The microphone is only an input switch inside that existing session:

```text
Start mic
→ begin 16 kHz PCM capture
→ send audio to the existing Qwen session

Stop mic
→ stop PCM transmission
→ keep the WebSocket, Qwen session, conversation history, and dashboard state

Start mic again
→ resume audio transmission to the same Qwen session
```

A new Qwen session is created only when the page is refreshed, the WebSocket is
closed, or the backend/model connection fails. Clicking Start mic repeatedly does
not create additional model sessions.

The backend is intentionally single-participant because dashboard state and undo
history are held in memory. A second browser is rejected while one page session is
active.

## Qwen Realtime configuration

Current Qwen-Omni-Realtime WebSocket access requires both an API Key and a Bailian
business-space ID for the selected region.

Create the local configuration file:

```bat
cd /d F:\VerbalVis2\backend
copy .env.example .env
```

Edit `backend/.env`:

```env
DASHSCOPE_API_KEY=sk-your-api-key
QWEN_WORKSPACE_ID=your-bailian-workspace-id
QWEN_REGION=beijing
QWEN_REALTIME_MODEL=qwen3.5-omni-plus-realtime
QWEN_VOICE=Ethan
```

For Singapore:

```env
QWEN_REGION=singapore
```

A complete endpoint may be supplied instead of `QWEN_WORKSPACE_ID`:

```env
QWEN_REALTIME_URL=wss://your-workspace-id.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime
```

`QWEN_REALTIME_URL` takes priority. The code also accepts
`DASHSCOPE_WORKSPACE_ID` or `WORKSPACE_ID` as aliases, but
`QWEN_WORKSPACE_ID` is the recommended name.

After changing `.env`, restart Uvicorn. Environment variables are read when the
backend process starts.

### Configuration-error behavior

When credentials or the workspace ID are missing:

- the page still receives the initial dashboard;
- the backend sends one `configuration_error` event;
- the UI shows `Qwen configuration required`;
- Start mic remains disabled;
- the WebSocket stays open so the page does not enter a reconnect loop;
- the backend no longer raises the repeated `QWEN_WORKSPACE_ID ... required`
  session traceback.

Use the health endpoint to inspect configuration without opening a conversation:

```text
http://127.0.0.1:8000/health
```

Relevant fields:

```json
{
  "qwen_configured": true,
  "qwen_configuration_error": null
}
```

## Runtime architecture

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
→ Pinia
→ Vega-Lite dashboard
```

There is one Realtime implementation and one tool implementation:

```text
backend/realtime.py
backend/tools.py
```

## Voice interruption

The system uses the simple R-A policy:

```text
Qwen Semantic VAD speech_started
→ stop the current Assistant audio queue
→ reject late audio from that response
→ send response.cancel while generation is active
→ process the newest completed user utterance
```

The browser enforces that audio from at most one Assistant `response_id` may be
scheduled at a time.

A tool batch that has already started is non-preemptive:

```text
tool call selected
→ block microphone forwarding
→ clear Qwen partial input audio
→ execute tool calls sequentially
→ return all function_call_output items
→ inject the latest dashboard state
→ request one final spoken response
```

Running tools are not cancelled or rolled back.

## Model-facing tools

```text
update_analysis_scope
aggregate_data
compare_selected_groups
compare_category_metrics
create_visual
update_visual
delete_visual
highlight_visual
inspect_visual
summarize_dashboard
undo_last_action
```

Supported chart types:

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

Fixed semantics:

- low score: `review_score <= 2`;
- product revenue: `SUM(price)`, excluding freight;
- category service metrics: one row per `order_id + product_category`.

## Start

Backend:

```bat
cd /d F:\VerbalVis2\backend
uvicorn main:app --host 127.0.0.1 --port 8000
```

Frontend:

```bat
cd /d F:\VerbalVis2\frontend
npm install
npm run dev -- --port 5173
```

Open `http://localhost:5173`. Wait until the top status becomes `Ready`, then
press **Start mic**. Start/Stop mic may be toggled repeatedly within the same
conversation session.

## Validation

Backend:

```bat
cd /d F:\VerbalVis2\backend
python -m compileall .
python demo_validation.py
```

Frontend:

```bat
cd /d F:\VerbalVis2\frontend
npm install
npm run validate:highlight
npm run validate:layout
npm run validate:session
npm run build
```

The session validation guards the central contract: page load creates the Qwen
session once; microphone toggles only control PCM transmission.
