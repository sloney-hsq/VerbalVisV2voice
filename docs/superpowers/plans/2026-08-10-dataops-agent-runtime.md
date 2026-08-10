# DataOps Agent Runtime Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a testable FastAPI DataOps Agent that routes deterministic data work to DuckDB, knowledge work to Hybrid RAG, and runtime state/task coordination to Redis-capable adapters.

**Architecture:** A new `dataops_agent` package isolates data, runtime, knowledge, task, and API concerns. The first delivery uses in-memory fakes in tests and optional external Redis/Elasticsearch adapters in the demo stack. VerbalVis remains untouched except for future imports of the standalone runtime contracts.

**Tech Stack:** Python 3.11+, FastAPI, DuckDB, redis-py, Elasticsearch client, pytest, Docker Compose.

## Global Constraints

- Create all new application code under `dataops_agent/`; do not modify VerbalVis realtime behavior.
- Keep durable audit data in DuckDB and treat Redis as runtime state, queue, cache, and idempotency storage.
- Test first; every newly exported behavior must have a focused pytest test.
- No live Redis or Elasticsearch is required for unit tests.
- SQL must be constrained to read-only `SELECT`/`WITH` queries over allow-listed tables.
- Mutating tools require idempotency and cannot be automatically retried after execution begins.

---

### Task 1: Deterministic ETL and Data Quality

**Files:**
- Create: `dataops_agent/data/{__init__.py,models.py,etl.py,repository.py,quality.py}`
- Create: `tests/dataops/test_etl.py`, `tests/dataops/test_quality.py`

**Interfaces:**
- Produces `load_records(records, *, batch_id, repository) -> LoadSummary`.
- Produces `run_quality_checks(repository) -> QualityReport`.
- Produces `execute_readonly_sql(repository, sql) -> list[dict[str, object]]`.

- [ ] Write failing tests for duplicate-safe loading, malformed-record quarantine, a second identical batch, and `schema_valid_rate`/`duplicate_rate`.
- [ ] Run `python -m pytest tests/dataops/test_etl.py tests/dataops/test_quality.py -q` and verify failure because the package does not exist.
- [ ] Implement a DuckDB repository with `records`, `quarantine_records`, and `load_batches` tables; record a completed batch and skip a repeated batch ID.
- [ ] Implement validation, quarantine reason recording, quality metrics, and an allow-listed read-only SQL executor.
- [ ] Re-run the focused tests and commit the task.

### Task 2: Runtime State, Tool Registry, Context, and Trace

**Files:**
- Create: `dataops_agent/runtime/{__init__.py,tools.py,state.py,context.py,tracing.py}`
- Create: `tests/dataops/test_runtime.py`

**Interfaces:**
- Produces `ToolSpec`, `ToolRegistry`, `InMemoryStateStore`, `RedisStateStore`, `ContextManager`, and `JsonlTracer`.
- `StateStore.claim_response(session_id, response_id) -> int` returns a monotonically increasing epoch.
- `StateStore.admit_tool(session_id, response_id, epoch) -> bool` denies stale execution.

- [ ] Write failing tests for registered-tool lookup, response ownership rejection, context budgeting, idempotency keys, and one JSONL trace event.
- [ ] Run `python -m pytest tests/dataops/test_runtime.py -q` and verify the expected missing-package failure.
- [ ] Implement protocol-first stores, a dependency-injected Redis adapter, registry validation, context compaction, and safe trace serialization.
- [ ] Re-run the focused tests and commit the task.

### Task 3: Knowledge Layer and Hybrid Retrieval

**Files:**
- Create: `dataops_agent/knowledge/{__init__.py,models.py,chunking.py,retrieval.py,elastic.py}`
- Create: `tests/dataops/test_knowledge.py`

**Interfaces:**
- Produces `KnowledgeChunk`, `rrf_fuse(rankings, *, k=60) -> list[str]`, and `HybridRetriever.search(query, *, filters, limit) -> list[KnowledgeChunk]`.
- Produces `Reranker.rank(query, chunks) -> list[KnowledgeChunk]`.

- [ ] Write failing tests for structure-aware chunks, metadata filtering, exact-ID priority, deterministic RRF fusion, and reranking a candidate set.
- [ ] Run `python -m pytest tests/dataops/test_knowledge.py -q` and verify failure because the package does not exist.
- [ ] Implement pure-Python retriever contracts and fakes for tests; implement an Elasticsearch adapter that issues BM25/vector retrieval only when configured.
- [ ] Re-run focused tests and commit the task.

### Task 4: Task Queue, Router, and FastAPI Integration

**Files:**
- Create: `dataops_agent/{__init__.py,app.py,router.py,settings.py}`
- Create: `dataops_agent/tasks/{__init__.py,models.py,queue.py,worker.py}`
- Create: `tests/dataops/test_app.py`, `tests/dataops/test_tasks.py`
- Create: `requirements-dataops.txt`, `docker-compose.dataops.yml`, `dataops_agent/README.md`

**Interfaces:**
- `route_request(text) -> Route` returns `lookup`, `sql`, `knowledge`, `audit`, or `plan`.
- `TaskQueue.enqueue(AuditTask) -> str` and `TaskStore.progress(task_id) -> TaskProgress`.
- FastAPI exposes health, ingestion, audit, task-progress, SQL, and knowledge endpoints.

- [ ] Write failing tests for route selection, task transitions, queued audit progress, and FastAPI endpoint responses with fake adapters.
- [ ] Run `python -m pytest tests/dataops/test_app.py tests/dataops/test_tasks.py -q` and verify the expected missing-module failure.
- [ ] Implement queue/state protocols, Redis Stream consumer-group adapter, in-memory worker path, the router, and FastAPI composition root.
- [ ] Add optional Redis/Elasticsearch services to Compose and document a two-minute demo using the sample dataset.
- [ ] Run all Python tests, then commit the task.

### Task 5: VerbalVis Compatibility Boundary and End-to-End Verification

**Files:**
- Create: `docs/dataops-agent-verbalvis-integration.md`
- Modify: `README.md`
- Test: `tests/dataops/test_integration.py`

**Interfaces:**
- Documents a future adapter from `backend/response_coordinator.py` to `dataops_agent.runtime.StateStore` without replacing current memory state.

- [ ] Write a failing integration test for ingest -> audit -> SQL -> knowledge -> trace using only in-memory adapters.
- [ ] Run the integration test and verify the failure is caused by a missing integration path.
- [ ] Implement only the DataOps composition required to satisfy the test; do not modify `backend/realtime.py`, `backend/tools.py`, or `backend/main.py`.
- [ ] Document the migration boundary, demo commands, architecture, metrics, and resume-ready accomplishments.
- [ ] Run `python -m pytest tests/dataops -q`, `python -m pytest tests -q`, and `npm test` from `frontend/`; commit the task.
