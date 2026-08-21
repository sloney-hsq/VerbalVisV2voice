"""Public-contract integration coverage for the standalone DataOps Agent."""

from __future__ import annotations

import json
from pathlib import Path

import yaml
from packaging.requirements import Requirement

from dataops_agent.data import DuckDBRepository, execute_readonly_sql, load_records
from dataops_agent.knowledge import HybridRetriever, KnowledgeChunk
from dataops_agent.runtime import JsonlTracer
from dataops_agent.tasks import AuditTask, AuditWorker, DuckDBTaskStore, InMemoryTaskQueue, TaskStatus


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


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


def test_compose_demo_waits_for_elasticsearch_then_bootstraps_before_api_start() -> None:
    config = yaml.safe_load(
        (REPOSITORY_ROOT / "docker-compose.dataops.yml").read_text(encoding="utf-8")
    )
    api = config["services"]["dataops-agent"]
    elasticsearch = config["services"]["elasticsearch"]

    assert api["environment"] == {
        "DATAOPS_DATABASE_PATH": "/app/.dataops/dataops.duckdb",
        "DATAOPS_ELASTICSEARCH_URL": "http://elasticsearch:9200",
        "DATAOPS_ELASTICSEARCH_INDEX": "dataops-knowledge",
        "DATAOPS_ELASTICSEARCH_EMBEDDING_DIMENSIONS": "384",
        "DATAOPS_TRACE_PATH": "/app/.dataops/dataops-trace.jsonl",
    }
    command = api["command"]
    assert command.index("python -m dataops_agent.knowledge.bootstrap") < command.index(
        "uvicorn dataops_agent.app:app"
    )
    assert api["depends_on"]["elasticsearch"]["condition"] == "service_healthy"
    assert elasticsearch["image"] == (
        "docker.elastic.co/elasticsearch/elasticsearch:8.15.3"
    )
    assert any("_cluster/health" in item for item in elasticsearch["healthcheck"]["test"])


def test_dataops_requirements_pin_client_to_compose_elasticsearch_major() -> None:
    requirements = {
        requirement.name: requirement
        for requirement in (
            Requirement(line)
            for line in (REPOSITORY_ROOT / "requirements-dataops.txt")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        )
    }

    assert requirements["elasticsearch"].specifier.contains("8.15.3")
    assert not requirements["elasticsearch"].specifier.contains("9.0.0")
    assert requirements["pyyaml"].specifier.contains("6.0.3")
