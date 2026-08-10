# DataOps Agent Runtime Design

## Goal

Build a locally runnable, testable DataOps Agent that makes deterministic data
quality operations available as structured tools. It must demonstrate the
separation between SQL facts, retrieval knowledge, and runtime state without
altering the experimental single-session behavior of VerbalVis.

## Scope and delivery order

1. **DataOps MVP:** idempotent CSV/JSON ingestion into DuckDB, incremental
   loading, bad-record quarantine, quality metrics, SQL analysis, background
   audit task contracts, progress, and structured execution traces.
2. **Knowledge and runtime:** tool registry, pluggable state store, Redis
   adapters, context budgeting, Hybrid RAG primitives (BM25/vector RRF and a
   reranker interface), and MCP-ready tool descriptions.
3. **VerbalVis reuse:** export the Runtime contracts so a later adapter can
   use them. No change to VerbalVis's single-participant WebSocket semantics
   is in this delivery.

## Architecture

`dataops_agent` is a sibling Python package with five bounded modules:

- `data`: deterministic ETL, DuckDB tables, data-quality rules, and SQL facts.
- `runtime`: tool metadata, state-store contracts, Redis/in-memory state,
  context budgets, and JSONL trace events.
- `knowledge`: documentation chunks, metadata-aware hybrid retrieval, RRF, and
  a reranker protocol. Direct identifiers remain deterministic lookups.
- `tasks`: durable task state and Redis Stream queue adapters.
- `app`: FastAPI endpoints and the router that selects SQL, knowledge, task,
  or deterministic lookup paths.

The application owns durable audit outputs in DuckDB. Redis holds ephemeral
session/task state, idempotency keys, Streams messages, and caches; it is not
the only source of audit truth. External Redis and Elasticsearch are optional
at test time through protocol-based adapters and required only for the
containerized demonstration stack.

## Routing rules

- Explicit record IDs, project IDs, or document paths use deterministic lookup.
- Counts, filters, metrics, and version diffs use SQL tools.
- Definitions, audit rules, and historical cases use Hybrid RAG.
- Batch audits create a task and enqueue work through Redis Streams.
- Multi-step requests create an explicit plan whose actions are routed using
  the preceding rules.

## Non-negotiable behavior

- Mutating operations require an idempotency key and are never automatically
  retried after their handler begins.
- A task has `queued`, `running`, `completed`, or `failed` status, counters,
  and an error summary.
- Every tool event records trace ID, session ID, call ID, tool name, status,
  elapsed milliseconds, retry count, and safe result metadata.
- Context uses exact current state directly; RAG must never retrieve current
  dashboard or task state.
- All new logic is test-first and must run without a live Redis or
  Elasticsearch service.

## Acceptance evidence

- Unit tests cover ETL idempotency, quarantine, quality metrics, state
  ownership, trace emission, RRF ordering, and router selection.
- A local FastAPI demo accepts a sample dataset, runs a quality audit, exposes
  task progress, queries a metric through SQL, and retrieves an audit rule.
- README documents the architecture, startup commands, and a two-minute demo.
