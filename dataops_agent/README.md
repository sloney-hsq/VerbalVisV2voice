# DataOps Agent

The standalone agent ingests deterministic records into DuckDB, records durable
audit progress and results in DuckDB, serves allow-listed read-only SQL, and
searches a replaceable knowledge retriever. Redis Streams and Elasticsearch are
optional adapters.

## Two-minute local demo

From the repository root, install the service dependencies, choose a local
DuckDB file, and launch the API:

```powershell
python -m pip install -r requirements-dataops.txt
$env:DATAOPS_DATABASE_PATH = (Join-Path $PWD ".dataops/dataops.duckdb")
python -m uvicorn dataops_agent.app:app --reload
```

In a second terminal, ingest a sample record, request an audit, and run a
read-only query. The API schedules one background worker pass for each audit
request, so the following progress request returns a terminal state unless the
process is interrupted:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
Invoke-RestMethod http://127.0.0.1:8000/ingest -Method Post -ContentType application/json -Body '{"batch_id":"demo-1","records":[{"record_id":"demo-1","source":"demo","value":42}]}'
$task = Invoke-RestMethod http://127.0.0.1:8000/audit -Method Post -ContentType application/json -Body '{"batch_id":"demo-1"}'
Invoke-RestMethod "http://127.0.0.1:8000/tasks/$($task.task_id)/progress"
Invoke-RestMethod http://127.0.0.1:8000/sql -Method Post -ContentType application/json -Body '{"sql":"SELECT record_id, source FROM records"}'
```

For the Compose demo, run `docker compose -f docker-compose.dataops.yml up`.
It provisions Redis and Elasticsearch only on the internal Compose network;
the API remains available at `http://127.0.0.1:8000`. The Redis queue creates a
consumer group lazily, reclaims idle pending messages before reading fresh
work, and ACKs terminal tasks. A reclaimed task that had already started is
marked failed rather than retried. Unit tests use in-memory or injected fake
adapters; they do not require either external service.

## Architecture and verification

```text
ingestion -> DuckDB records/quarantine -> durable audit task -> quality report
SQL endpoint -> existing allow-listed read-only executor
knowledge endpoint -> in-memory HybridRetriever (or configured Elasticsearch)
runtime event -> JsonlTracer with credential redaction
```

Run the whole DataOps test scope with:

```powershell
python -m pytest tests/dataops -q
```

`tests/dataops/test_integration.py` is the end-to-end contract: it uses an
in-memory DuckDB repository, queues a durable audit to a terminal state,
executes a read-only metric, retrieves an audit-rule chunk, and reads a safe
redacted trace. It requires no live Redis or Elasticsearch.

Measured on 2026-08-10: the integration file has 1 test; the DataOps suite
has 77 tests; the repository Python suite has 79 tests; and the existing
frontend suite has 5 tests.

## Resume point

- Data: deterministic ingestion, quarantine, batch idempotency, quality
  metrics, and allow-listed SQL are available.
- Agent: durable task progress, local/Redis queue adapters, retrieval, and
  safe tracing are available.
- VerbalVis: remains unchanged. The future dual-admission adapter boundary is
  documented in [`docs/dataops-agent-verbalvis-integration.md`](../docs/dataops-agent-verbalvis-integration.md).
