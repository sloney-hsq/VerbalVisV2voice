# VerbalVis FD-Voice

VerbalVis is a full-duplex voice-driven conversational visual analytics prototype
for the Olist Brazilian E-Commerce dataset. The FD-Voice condition combines one
Qwen-Omni-Realtime conversation, a shared Vega-Lite dashboard, structured tools,
and immediate speech interruption.

# VerbalVis-FD-Voice

**资料，[help.aliyun.com/zh/model-studio/client-events](https://help.aliyun.com/zh/model-studio/client-events)要求详细查看，[help.aliyun.com/zh/model-studio/realtime?spm=a2ty_o06.30285417.0.0.71d2c921CJ5d6U#d6f3ba031di77](https://help.aliyun.com/zh/model-studio/realtime?spm=a2ty_o06.30285417.0.0.71d2c921CJ5d6U#d6f3ba031di77)。**

[help.aliyun.com/zh/model-studio/omni-realtime-python-sdk](https://help.aliyun.com/zh/model-studio/omni-realtime-python-sdk)

[help.aliyun.com/zh/model-studio/omni-realtime-interaction-process](https://help.aliyun.com/zh/model-studio/omni-realtime-interaction-process)

# 客户端事件

**更新时间：2026-06-16 23:00:39**

**复制 MD 格式**[产品详情](https://www.aliyun.com/product/bailian)

[我的收藏](https://help.aliyun.com/my_favorites.html)

Qwen-Omni-Realtime API的客户端事件参考。

> 另请参见： [实时（Qwen-Omni-Realtime）](https://help.aliyun.com/zh/model-studio/realtime) 。

## **session.update**

建立 WebSocket 连接后，发送此事件更新会话的默认配置。服务端收到 `session.update` 事件后校验参数，若参数不合法则返回错误，若参数合法则应用更改并返回完整配置。

[help.aliyun.com/zh/model-studio/server-events](https://help.aliyun.com/zh/model-studio/server-events)

**Qwen-Omni-Realtime
更新时间：2026-06-12 15:05:06**

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

Qwen-Omni-Realtime WebSocket access requires an API Key. When no business-space
ID or complete endpoint is set, VerbalVis uses the DashScope public regional
endpoint for the selected region.

Create the local configuration file:

```bat
cd /d F:\VerbalVis2\backend
copy .env.example .env
```

Edit `backend/.env`:

```env
DASHSCOPE_API_KEY=sk-your-api-key
QWEN_REGION=beijing
QWEN_REALTIME_MODEL=qwen3.5-omni-plus-realtime
QWEN_VOICE=Ethan
```

For Singapore:

```env
QWEN_REGION=singapore
```

A business-space ID may be supplied to use its regional endpoint:

```env
QWEN_WORKSPACE_ID=your-bailian-workspace-id
```

A complete endpoint may also be supplied:

```env
QWEN_REALTIME_URL=wss://your-workspace-id.cn-beijing.maas.aliyuncs.com/api-ws/v1/realtime
```

`QWEN_REALTIME_URL` takes priority, followed by `QWEN_WORKSPACE_ID`, followed
by the public DashScope endpoint. The code also accepts
`DASHSCOPE_WORKSPACE_ID` or `WORKSPACE_ID` as aliases, but
`QWEN_WORKSPACE_ID` is the recommended name.

After changing `.env`, restart Uvicorn. Environment variables are read when the
backend process starts.

### Configuration-error behavior

When the API Key is missing:

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
If one tool fails validation or execution, later calls from that same model
response receive explicit skipped outputs and do not run. This fail-fast rule is
separate from user interruption: a tool that has already begun still completes.

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

For the experiment's state-and-date comparisons, `compare_category_metrics`
accepts `customer_state`, `start_date`, and `end_date` together. The backend
applies that scope, selects the Top-N categories, and creates all coordinated
views as one dashboard action. Generic filters also normalize common equality
aliases and omitted scalar/range operators before validation.

Supported chart types:

```text
line
bar
scatter
```

`create_visual` and `update_visual` accept `normalize=true` for 100% stacked
bar charts with a series. Rating-share charts use the fixed domain
`null, 1, 2, 3, 4, 5`, a shared gray-to-green palette, and ascending stack
order. Dashboard cards use a `540 × 360 px` desktop size.

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
