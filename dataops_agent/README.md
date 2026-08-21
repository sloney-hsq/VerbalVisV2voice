# DataOps Agent

The standalone, interview-oriented agent ingests deterministic records into
DuckDB, records durable audit progress and results, serves allow-listed
read-only SQL, and searches a replaceable knowledge retriever. Redis Streams
and Elasticsearch are optional adapters. It does not change the VerbalVis
single-session experiment.

Every state-changing call requires a nonblank `Idempotency-Key` header:
`POST /ingest`, `POST /ingestion`, `POST /ingest/csv`, and `POST /audit`.
The same key and same request replay the stored response; reusing the key with
a changed request returns HTTP `409`. In the default file-backed configuration,
the request fingerprint and first response are durable across an API restart;
audit idempotency also prevents duplicate audit tasks after a client retry.

## Two-minute demo

From the repository root, install the dependencies and launch the standalone
API:

```powershell
python -m pip install -r requirements-dataops.txt
$env:DATAOPS_DATABASE_PATH = (Join-Path $PWD ".dataops/dataops.duckdb")
python -m uvicorn dataops_agent.app:app --reload
```

`docker-compose.dataops.yml` provides an optional local Elasticsearch
mapping/bootstrap demo. Docker was not run in the environment used for this
update; local tests cover the Compose definition and fake-client Elasticsearch
request shapes.

In a second PowerShell terminal, exercise JSON and raw CSV ingestion, audit
progress, read-only SQL, seeded knowledge retrieval, and the resulting trace:

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

`POST /ingest/csv` takes `batch_id` as a required query parameter and the CSV
document as a UTF-8 `text/csv` request body. It does not require multipart form
support. `POST /ingestion` is the JSON ingestion alias and follows the same
idempotency contract. A native DuckDB database is consumed only by the API
process that owns it: the in-memory path uses FastAPI `BackgroundTasks`; when
Redis Streams is configured, an in-process lifecycle worker drains and
recovers its durable `pending_publish` outbox. This repository does **not**
present a separate multi-process worker topology for a native DuckDB file.

For an already-running Elasticsearch instance, bootstrap explicitly once
instead of mutating the index during a search:

```powershell
$env:DATAOPS_ELASTICSEARCH_URL = "http://127.0.0.1:9200"
$env:DATAOPS_ELASTICSEARCH_INDEX = "dataops-knowledge"
python -m dataops_agent.knowledge.bootstrap
```

Without Elasticsearch, the API includes one built-in deterministic audit rule
so the quick-start `/knowledge` call returns a local lexical result. The seeded
Elasticsearch default demonstrates lexical retrieval and index mapping bootstrap.
Elasticsearch hybrid KNN/vector retrieval requires an embedder injected into
the application; setting an Elasticsearch URL alone does not create embeddings
or enable semantic retrieval.

## MCP

```powershell
python -m dataops_agent.mcp_server
```

The server exposes five read-only tools over stdio to a compatible MCP host. It
does not run an LLM, retain a conversation, or automatically attach itself to a
model provider.

## Architecture and verification

```text
ingestion -> DuckDB records/quarantine -> durable idempotent audit -> quality report
SQL endpoint -> existing allow-listed read-only executor
knowledge endpoint -> in-memory HybridRetriever (or configured Elasticsearch)
runtime event -> JsonlTracer with minimised input shape and credential redaction
```

Run the whole DataOps test scope with:

```powershell
python -m pytest tests/dataops -q
```

`tests/dataops/test_integration.py` is the end-to-end contract: it uses an
in-memory DuckDB repository, queues a durable audit to a terminal state,
executes a read-only metric, retrieves an audit-rule chunk, and reads a safe
minimised trace. SQL results are capped at 1,000 rows by default; request-level
deadlines remain an application/deployment responsibility. It requires no live
Redis or Elasticsearch. Add
`python -m compileall -q dataops_agent` and `git diff --check` before release.

## Resume point

- Data: deterministic ingestion, quarantine, batch idempotency, quality
  metrics, and allow-listed SQL are available.
- Agent: durable task progress, in-process runtime coordination, optional Redis
  transport, retrieval, MCP read tools, and safe tracing are available.
- VerbalVis: remains unchanged. The future dual-admission adapter boundary is
  documented in [`docs/dataops-agent-verbalvis-integration.md`](../docs/dataops-agent-verbalvis-integration.md).
