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

## Standalone DataOps Agent

`dataops_agent` is an isolated service package; it does not alter or replace
the current VerbalVis realtime implementation. Its architecture is:

```text
record ingestion -> DuckDB + quarantine -> durable audit task -> quality report
read-only SQL -> allow-listed DuckDB sandbox
knowledge lookup -> built-in local rule retriever or optional Elasticsearch adapter
trace event -> input-minimised JSONL
```

Every mutating endpoint requires a nonblank `Idempotency-Key` request header:
`POST /ingest`, `POST /ingestion`, `POST /ingest/csv`, and `POST /audit`.
Repeating the same key with the same request replays the prior result; changing
the request for that key returns HTTP `409`. In the default file-backed
configuration, request fingerprints and first responses persist across an API
restart; audit idempotency also prevents duplicate tasks.

For a local API-only demo, install the dependencies and start Uvicorn from the
repository root:

```powershell
python -m pip install -r requirements-dataops.txt
$env:DATAOPS_DATABASE_PATH = (Join-Path $PWD ".dataops/dataops.duckdb")
python -m uvicorn dataops_agent.app:app --reload
```

The Compose configuration provides an optional Elasticsearch mapping/bootstrap
demo. Docker was not run in the environment used for this update; local tests
verify the Compose configuration and fake-client Elasticsearch request shapes.

In a separate PowerShell terminal, call JSON and raw CSV ingestion, audit and
progress, read-only SQL, seeded knowledge retrieval, and trace inspection:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
$jsonHeaders = @{ "Idempotency-Key" = "demo-json-001" }
Invoke-RestMethod http://127.0.0.1:8000/ingest -Method Post -Headers $jsonHeaders -ContentType application/json -Body '{"batch_id":"demo-json","records":[{"record_id":"json-1","source":"demo","value":42}]}'
$csv = "record_id,source,value`r`ncsv-1,demo,84`r`n"
$csvHeaders = @{ "Idempotency-Key" = "demo-csv-001" }
Invoke-RestMethod "http://127.0.0.1:8000/ingest/csv?batch_id=demo-csv" -Method Post -Headers $csvHeaders -ContentType text/csv -Body $csv
$auditHeaders = @{ "Idempotency-Key" = "demo-audit-001" }
$task = Invoke-RestMethod http://127.0.0.1:8000/audit -Method Post -Headers $auditHeaders -ContentType application/json -Body '{"batch_id":"demo-csv"}'
Invoke-RestMethod "http://127.0.0.1:8000/tasks/$($task.task_id)/progress"
Invoke-RestMethod http://127.0.0.1:8000/sql -Method Post -ContentType application/json -Body '{"sql":"SELECT record_id, source FROM records"}'
$filter = [uri]::EscapeDataString('{"kind":"audit-rule"}')
Invoke-RestMethod "http://127.0.0.1:8000/knowledge?query=schema%20validity&filters=$filter&limit=1"
Get-Content .dataops/dataops-trace.jsonl -Tail 10
```

`POST /ingest/csv?batch_id=<id>` consumes a UTF-8 `text/csv` body directly;
no multipart package is needed. A native DuckDB database is consumed only by
the API process that owns it: the in-memory path uses FastAPI
`BackgroundTasks`; when Redis Streams is configured, an in-process lifecycle
worker drains and recovers its durable `pending_publish` outbox. This repository
does **not** present a separate multi-process worker topology for a native
DuckDB file.

Search requests never create or modify the knowledge index. For a separately
managed Elasticsearch instance, set `DATAOPS_ELASTICSEARCH_URL` and
`DATAOPS_ELASTICSEARCH_INDEX`, then run this once:

```powershell
python -m dataops_agent.knowledge.bootstrap
```

Without Elasticsearch, the API includes one built-in deterministic audit rule
so the quick-start `/knowledge` call returns a local lexical result. The seeded
Elasticsearch default exercises lexical retrieval and mapping bootstrap.
Elasticsearch hybrid KNN/vector retrieval additionally requires an embedder to
be injected into the application; it is not enabled solely by setting an
Elasticsearch URL.

An MCP server is available through standard input/output:

```powershell
python -m dataops_agent.mcp_server
```

It exposes five read-only tools for a compatible MCP host. It does not start an
LLM, hold a conversation, or automatically connect itself to a model provider.

Run the standalone verification with:

```powershell
python -m pytest tests/dataops/test_integration.py -q
python -m pytest tests/dataops -q
```

The integration test is end-to-end coverage of valid and quarantined ingestion,
terminal durable audit progress, an allow-listed SQL metric (with a default
1,000-row result cap), audit-rule retrieval, and an input-minimised JSONL
trace. It uses in-memory adapters and does not prove live Redis, Elasticsearch,
or Docker deployment. A request deadline remains a deployment-level safeguard
for expensive untrusted SQL.

Resume points:

- DataOps offers deterministic ingestion, quality checks, protected SQL,
  idempotent audit scheduling, and traceable runtime contracts.
- Redis Streams and Elasticsearch are optional integrations; their live-service
  operational claims require separate deployment evidence.
- VerbalVis remains on its existing in-memory response coordinator. The exact
  future dual-admission adapter boundary is documented in
  [`docs/dataops-agent-verbalvis-integration.md`](docs/dataops-agent-verbalvis-integration.md);
  it is not wired today.

