"""Public-contract integration coverage for the standalone DataOps Agent."""

from __future__ import annotations

import json

from dataops_agent.data import DuckDBRepository, execute_readonly_sql, load_records
from dataops_agent.knowledge import HybridRetriever, KnowledgeChunk
from dataops_agent.runtime import JsonlTracer
from dataops_agent.tasks import AuditTask, AuditWorker, DuckDBTaskStore, InMemoryTaskQueue, TaskStatus


def test_in_memory_dataops_flow_ingests_audits_queries_retrieves_and_traces(tmp_path) -> None:
    repository = DuckDBRepository(":memory:")
    load_summary = load_records(
        [
            {"record_id": "demo-1", "source": "demo", "amount": 42},
            {"source": "demo", "amount": "invalid"},
        ],
        batch_id="integration-batch",
        repository=repository,
    )
    assert (load_summary.loaded, load_summary.quarantined) == (1, 1)

    store = DuckDBTaskStore(repository)
    queue = InMemoryTaskQueue(store)
    worker = AuditWorker(queue=queue, store=store, repository=repository)
    task_id = queue.enqueue(AuditTask(batch_id="integration-batch"))
    assert worker.run_once() is True
    progress = store.progress(task_id)
    assert progress.status is TaskStatus.COMPLETED
    assert progress.result == {"schema_valid_rate": 0.5, "duplicate_rate": 0.0}

    metric = execute_readonly_sql(
        repository, "SELECT COUNT(*) AS retained_records FROM records"
    )
    assert metric == [{"retained_records": 1}]

    retriever = HybridRetriever(
        [
            KnowledgeChunk(
                id="audit-schema-rule",
                content="Audit rule: report schema validity for every completed ingestion batch.",
                metadata={"kind": "audit-rule"},
            )
        ]
    )
    chunks = retriever.search("schema validity audit rule", filters={"kind": "audit-rule"}, limit=1)
    assert [chunk.id for chunk in chunks] == ["audit-schema-rule"]

    trace_path = tmp_path / "traces" / "integration.jsonl"
    JsonlTracer(trace_path).emit(
        {
            "event": "audit.completed",
            "task_id": task_id,
            "authorization": "Bearer should-not-appear",
            "message": "worker saw Bearer should-not-appear",
            "quality": progress.result,
        }
    )
    trace_event = json.loads(trace_path.read_text(encoding="utf-8"))
    assert trace_event["authorization"] == "[REDACTED]"
    assert trace_event["message"] == "worker saw Bearer [REDACTED]"
    assert "should-not-appear" not in trace_path.read_text(encoding="utf-8")
