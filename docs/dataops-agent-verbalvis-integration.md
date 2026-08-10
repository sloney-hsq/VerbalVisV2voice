# DataOps Agent and VerbalVis integration boundary

## Status

`dataops_agent` is a standalone package. It is **not wired into VerbalVis**:
this repository does not import it from `backend/main.py`, `backend/realtime.py`,
`backend/tools.py`, or `backend/response_coordinator.py`. The existing
in-process `ResponseCoordinator` remains the source of truth for current
realtime behavior.

## Future adapter contract

The future adapter belongs beside the existing response orchestration, not in
the DataOps package. It should retain the current coordinator checks and add
the `StateStore` as a second admission gate:

1. When `ResponseCoordinator.bind_response(response_id)` accepts a response,
   the adapter calls `StateStore.claim_response(session_id, response_id)` and
   retains the returned store epoch for that response.
2. When `ResponseCoordinator.admit_tool_calls(...)` returns an allowed call,
   the adapter calls `StateStore.admit_tool(session_id, response_id,
   store_epoch)`. It executes the call only when **both** checks allow it.
3. For a `ToolSpec` with `mutates=True`, the adapter calls
   `StateStore.claim_idempotency(f"{session_id}:{response_id}:{call_id}")`
   before execution. A duplicate key is returned as an explicit skipped output.
   Once execution begins, the adapter must not automatically retry it.
4. `ResponseCoordinator.begin_user_turn()` and `interrupt_current()` continue
   to reject stale or interrupted responses locally. The present `StateStore`
   has no explicit invalidation method, so it must not replace these checks.
   A future durable-state migration must first add and test an invalidation
   operation (or an equivalent atomic replacement) before relying on Redis for
   interruption semantics.

This boundary preserves today’s response IDs, epochs, tool arguments, and
Realtime output shape. It does not change the frontend protocol.

## Runtime ownership

```text
VerbalVis Realtime request
  -> backend/response_coordinator.py (current admission authority)
  -> future adapter (dual local + StateStore admission)
  -> existing VerbalVis tool handler

Standalone DataOps request
  -> dataops_agent.app
  -> DuckDB ingestion/audit/SQL + knowledge/runtime contracts
```

The two paths are intentionally separate until the future adapter is designed,
implemented, and verified against interruption and tool-output regression tests.

## DataOps verification and resume point

Run the standalone integration path without Redis or Elasticsearch:

```powershell
python -m pytest tests/dataops/test_integration.py -q
python -m pytest tests/dataops -q
python -m pytest tests -q
```

The integration test covers one valid record, one quarantined invalid record,
a DuckDB-backed terminal audit task, a `SELECT` metric, one filtered audit-rule
knowledge retrieval, and one JSONL trace whose Authorization and bearer token
are redacted.

Resume-ready DataOps work:

- deterministic DuckDB ingestion, quarantine, batch idempotency, and metrics;
- durable DuckDB audit progress plus local/Redis-capable task queues;
- allow-listed `SELECT`/`WITH` SQL only;
- in-memory and optional Elasticsearch knowledge retrieval;
- runtime ownership/idempotency contracts ready for, but not connected to,
  VerbalVis.
