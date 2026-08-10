from concurrent.futures import ThreadPoolExecutor
import json
import multiprocessing
import os
import time
from pathlib import Path

import pytest

from dataops_agent.data.etl import load_records
from dataops_agent.data.repository import DuckDBRepository, execute_readonly_sql


def _load_file_batch_in_process(database, batch_id, ready, start, outcomes):
    ready.set()
    start.wait(timeout=10)
    try:
        repository = DuckDBRepository(database)
        summary = load_records(
            [{"record_id": "customer-process", "source": "crm"}],
            batch_id=batch_id,
            repository=repository,
        )
    except Exception as error:
        outcomes.put(("error", type(error).__name__, str(error)))
    else:
        outcomes.put(("ok", summary.loaded, summary.skipped))


def test_load_records_deduplicates_record_ids_within_a_batch():
    """A repeated record id must not create a second durable record."""
    repository = DuckDBRepository(":memory:")

    summary = load_records(
        [
            {"record_id": "customer-1", "source": "crm", "name": "Ada"},
            {"record_id": "customer-1", "source": "crm", "name": "Ada"},
        ],
        batch_id="batch-1",
        repository=repository,
    )

    assert summary.loaded == 1
    assert summary.duplicates == 1
    assert repository.count_rows("records") == 1


def test_load_records_quarantines_records_without_an_identifier():
    """Malformed input must be retained for audit instead of silently discarded."""
    repository = DuckDBRepository(":memory:")

    summary = load_records(
        [{"source": "crm", "name": "Missing identifier"}],
        batch_id="batch-malformed",
        repository=repository,
    )

    assert summary.quarantined == 1
    assert repository.count_rows("records") == 0
    assert repository.count_rows("quarantine_records") == 1
    assert repository.connection.execute(
        "SELECT reason FROM quarantine_records"
    ).fetchone() == ("record_id is required",)


def test_load_records_quarantines_a_non_object_record():
    """An unstructured input item must not abort the rest of a batch."""
    repository = DuckDBRepository(":memory:")

    summary = load_records(["not a record"], batch_id="batch-non-object", repository=repository)

    assert summary.quarantined == 1
    assert repository.connection.execute(
        "SELECT reason FROM quarantine_records"
    ).fetchone() == ("record must be an object",)


def test_load_records_skips_a_completed_batch_id():
    """Replaying an already completed batch must not reload its records."""
    repository = DuckDBRepository(":memory:")
    records = [{"record_id": "customer-2", "source": "crm", "name": "Grace"}]

    load_records(records, batch_id="batch-replay", repository=repository)
    replay = load_records(records, batch_id="batch-replay", repository=repository)

    assert replay.skipped is True
    assert replay.loaded == 0
    assert repository.count_rows("records") == 1
    assert repository.count_rows("load_batches") == 1


def test_load_records_rolls_back_every_write_when_the_iterator_fails():
    """A mid-batch producer failure must not leave a partially loaded batch."""
    repository = DuckDBRepository(":memory:")

    def records_that_fail_mid_batch():
        yield {"record_id": "customer-rollback", "source": "crm"}
        raise RuntimeError("upstream stream interrupted")

    with pytest.raises(RuntimeError, match="upstream stream interrupted"):
        load_records(
            records_that_fail_mid_batch(),
            batch_id="batch-rollback",
            repository=repository,
        )

    assert repository.count_rows("records") == 0
    assert repository.count_rows("quarantine_records") == 0
    assert repository.count_rows("load_batches") == 0


def test_load_records_retry_after_an_iterator_failure_matches_a_clean_load():
    """A failed batch id remains retryable as though its first attempt never ran."""
    repository = DuckDBRepository(":memory:")

    def records_that_fail_mid_batch():
        yield {"record_id": "customer-retry", "source": "crm"}
        raise RuntimeError("upstream stream interrupted")

    with pytest.raises(RuntimeError, match="upstream stream interrupted"):
        load_records(
            records_that_fail_mid_batch(),
            batch_id="batch-retry",
            repository=repository,
        )

    retry = load_records(
        [{"record_id": "customer-retry", "source": "crm"}],
        batch_id="batch-retry",
        repository=repository,
    )

    assert retry.received == 1
    assert retry.loaded == 1
    assert retry.duplicates == 0
    assert retry.quarantined == 0
    assert retry.skipped is False


def test_load_records_concurrently_claims_one_completed_batch(tmp_path):
    """Independent requests for one batch yield one load and skipped replays."""
    database = str(tmp_path / "concurrent-load.duckdb")
    repositories = [DuckDBRepository(database) for _ in range(4)]

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [
            executor.submit(
                load_records,
                [{"record_id": "customer-concurrent", "source": "crm"}],
                batch_id="batch-concurrent",
                repository=repository,
            )
            for repository in repositories
        ]
        summaries = [future.result() for future in futures]

    assert sum(summary.loaded for summary in summaries) == 1
    assert sum(summary.skipped for summary in summaries) == 3
    assert repositories[0].count_rows("records") == 1
    assert repositories[0].count_rows("load_batches") == 1


def test_load_records_coordinates_a_batch_across_processes(tmp_path):
    """One process loads a file-backed batch while the other returns a skipped replay."""
    context = multiprocessing.get_context("spawn")
    database = str(tmp_path / "cross-process-load.duckdb")
    batch_id = "batch-cross-process"
    start = context.Event()
    outcomes = context.Queue()
    ready = [context.Event(), context.Event()]
    processes = [
        context.Process(
            target=_load_file_batch_in_process,
            args=(database, batch_id, ready_event, start, outcomes),
        )
        for ready_event in ready
    ]

    for process in processes:
        process.start()
    try:
        assert all(event.wait(timeout=10) for event in ready)
        start.set()
        results = [outcomes.get(timeout=15) for _ in processes]
    finally:
        for process in processes:
            process.join(timeout=15)
            if process.is_alive():
                process.terminate()
                process.join()

    assert [result for result in results if result[0] == "error"] == []
    assert sorted((result[1], result[2]) for result in results) == [(0, True), (1, False)]
    repository = DuckDBRepository(database)
    assert repository.count_rows("records") == 1
    assert repository.count_rows("load_batches") == 1


def test_load_records_releases_a_parent_file_connection_before_child_ingestion(tmp_path):
    """Parent-side ingestion releases a direct file connection before worker processes load."""
    context = multiprocessing.get_context("spawn")
    database = str(tmp_path / "parent-connection-load.duckdb")
    parent_repository = DuckDBRepository(database)
    assert parent_repository.connection.execute("SELECT 1").fetchone() == (1,)
    load_records([], batch_id="batch-parent-release", repository=parent_repository)

    batch_id = "batch-after-parent-release"
    start = context.Event()
    outcomes = context.Queue()
    ready = [context.Event(), context.Event()]
    processes = [
        context.Process(
            target=_load_file_batch_in_process,
            args=(database, batch_id, ready_event, start, outcomes),
        )
        for ready_event in ready
    ]

    for process in processes:
        process.start()
    try:
        assert all(event.wait(timeout=10) for event in ready)
        start.set()
        results = [outcomes.get(timeout=15) for _ in processes]
    finally:
        for process in processes:
            process.join(timeout=15)
            if process.is_alive():
                process.terminate()
                process.join()

    assert [result for result in results if result[0] == "error"] == []
    assert sorted((result[1], result[2]) for result in results) == [(0, True), (1, False)]
    assert parent_repository.count_rows("records") == 1


def test_load_records_reclaims_an_expired_incomplete_file_lock(tmp_path):
    """A crash between lock-file creation and owner metadata write remains retryable."""
    database = str(tmp_path / "stale-file-lock.duckdb")
    database_path = Path(database)
    lock_path = database_path.with_suffix(database_path.suffix + ".dataops.lock")
    lock_path.write_text("incomplete owner metadata", encoding="utf-8")
    expired_at = time.time() - 61
    os.utime(lock_path, (expired_at, expired_at))
    repository = DuckDBRepository(database)

    summary = load_records(
        [{"record_id": "customer-stale-lock", "source": "crm"}],
        batch_id="batch-stale-lock",
        repository=repository,
    )

    assert summary.loaded == 1
    assert lock_path.exists() is False


def test_load_records_safely_quarantines_non_json_values():
    """Opaque malformed values remain auditable instead of breaking batch accounting."""
    repository = DuckDBRepository(":memory:")
    opaque_value = object()

    summary = load_records(
        [
            b"raw-bytes-record",
            {"source": "crm", "nested": {"bytes": b"\x00\xff", "opaque": opaque_value}},
        ],
        batch_id="batch-non-json",
        repository=repository,
    )

    assert summary.quarantined == 2
    assert repository.count_rows("quarantine_records") == 2
    raw_records = repository.connection.execute(
        "SELECT raw_record FROM quarantine_records ORDER BY reason"
    ).fetchall()
    assert [json.loads(raw_record) for (raw_record,) in raw_records]
    assert repository.connection.execute(
        "SELECT quarantined FROM load_batches WHERE batch_id = 'batch-non-json'"
    ).fetchone() == (2,)


def test_load_records_safely_quarantines_a_self_referential_record():
    """A circular malformed record is represented for audit instead of crashing JSON encoding."""
    repository = DuckDBRepository(":memory:")
    record = {"source": "crm"}
    record["self"] = record

    summary = load_records([record], batch_id="batch-circular", repository=repository)

    assert summary.quarantined == 1
    raw_record = repository.connection.execute(
        "SELECT raw_record FROM quarantine_records"
    ).fetchone()[0]
    assert json.loads(raw_record)["self"] == {"type": "circular_reference"}


def test_execute_readonly_sql_returns_records_as_dictionaries():
    """A permitted SELECT must return column-addressable result rows."""
    repository = DuckDBRepository(":memory:")
    load_records(
        [{"record_id": "customer-4", "source": "crm", "name": "Lin"}],
        batch_id="batch-sql",
        repository=repository,
    )

    rows = execute_readonly_sql(
        repository, "SELECT record_id, source FROM records ORDER BY record_id"
    )

    assert rows == [{"record_id": "customer-4", "source": "crm"}]


def test_execute_readonly_sql_allows_a_with_query_over_records():
    """A CTE keeps SQL read-only while supporting ordinary analytical queries."""
    repository = DuckDBRepository(":memory:")
    load_records(
        [{"record_id": "customer-5", "source": "crm"}],
        batch_id="batch-with",
        repository=repository,
    )

    rows = execute_readonly_sql(
        repository,
        "WITH crm_records AS (SELECT record_id FROM records) SELECT record_id FROM crm_records",
    )

    assert rows == [{"record_id": "customer-5"}]


def test_execute_readonly_sql_rejects_mutating_statements():
    """The SQL interface must not execute writes even when DuckDB accepts them."""
    repository = DuckDBRepository(":memory:")

    with pytest.raises(ValueError, match="Only SELECT or WITH statements are allowed"):
        execute_readonly_sql(repository, "DELETE FROM records")


def test_execute_readonly_sql_rejects_a_non_allow_listed_table():
    """Catalog tables must not be exposed through the constrained SQL boundary."""
    repository = DuckDBRepository(":memory:")

    with pytest.raises(ValueError, match="allow-listed"):
        execute_readonly_sql(repository, "SELECT table_name FROM information_schema.tables")


def test_execute_readonly_sql_rejects_a_quoted_non_allow_listed_table():
    """Quoting an identifier must not bypass the table allow-list."""
    repository = DuckDBRepository(":memory:")

    with pytest.raises(ValueError, match="allow-listed"):
        execute_readonly_sql(repository, 'SELECT table_name FROM "information_schema"."tables"')


def test_execute_readonly_sql_rejects_a_second_non_allow_listed_table():
    """Every source in a comma join must pass the table allow-list."""
    repository = DuckDBRepository(":memory:")

    with pytest.raises(ValueError, match="allow-listed"):
        execute_readonly_sql(
            repository,
            "SELECT records.record_id FROM records, information_schema.tables",
        )


def test_execute_readonly_sql_rejects_a_file_backed_relation():
    """DuckDB relation literals must not escape the table allow-list."""
    repository = DuckDBRepository(":memory:")

    with pytest.raises(ValueError, match="allow-listed"):
        execute_readonly_sql(repository, "SELECT * FROM 'outside.parquet'")


def test_execute_readonly_sql_rejects_a_catalog_pivot_relation():
    """PIVOT must not bypass relation allow-listing inside a FROM subquery."""
    repository = DuckDBRepository(":memory:")

    with pytest.raises(ValueError, match="allow-listed"):
        execute_readonly_sql(
            repository,
            "SELECT * FROM (PIVOT information_schema.tables ON table_schema USING count(*))",
        )


def test_execute_readonly_sql_rejects_a_pivot_table_function():
    """PIVOT cannot be used to reach a file-backed table function."""
    repository = DuckDBRepository(":memory:")

    with pytest.raises(ValueError, match="allow-listed"):
        execute_readonly_sql(
            repository,
            "SELECT * FROM (PIVOT read_csv_auto('not-permitted.csv') ON column0 USING count(*))",
        )


def test_execute_readonly_sql_does_not_normalise_a_different_quoted_identifier():
    """Removing spaces from a quoted name must not grant records-table access."""
    repository = DuckDBRepository(":memory:")
    repository.connection.execute('CREATE TABLE "rec ords" (record_id VARCHAR)')

    with pytest.raises(ValueError, match="allow-listed"):
        execute_readonly_sql(repository, 'SELECT record_id FROM "rec ords"')


def test_execute_readonly_sql_allows_quoted_keyword_cte_and_column_aliases():
    """Quoted CTE and column aliases that are SQL keywords remain valid SQL."""
    repository = DuckDBRepository(":memory:")
    load_records(
        [{"record_id": "customer-cte", "source": "crm"}],
        batch_id="batch-quoted-cte",
        repository=repository,
    )

    rows = execute_readonly_sql(
        repository,
        'WITH "order" AS (SELECT record_id AS "select" FROM records) '
        'SELECT "select" FROM "order"',
    )

    assert rows == [{"select": "customer-cte"}]


def test_execute_readonly_sql_allows_quoted_keyword_cte_column_aliases():
    """CTE column lists remain valid when aliases are quoted SQL keywords."""
    repository = DuckDBRepository(":memory:")
    load_records(
        [{"record_id": "customer-cte-list", "source": "crm"}],
        batch_id="batch-quoted-cte-list",
        repository=repository,
    )

    rows = execute_readonly_sql(
        repository,
        'WITH "order" ("select") AS (SELECT record_id FROM records) '
        'SELECT "select" FROM "order"',
    )

    assert rows == [{"select": "customer-cte-list"}]


def test_execute_readonly_sql_allows_quoted_pivot_cte_and_column_aliases():
    """A quoted PIVOT identifier is an alias, not the denied PIVOT operator."""
    repository = DuckDBRepository(":memory:")
    load_records(
        [{"record_id": "customer-pivot-alias", "source": "crm"}],
        batch_id="batch-pivot-alias",
        repository=repository,
    )

    rows = execute_readonly_sql(
        repository,
        'WITH "PIVOT" ("PIVOT") AS (SELECT record_id FROM records) '
        'SELECT "PIVOT" FROM "PIVOT"',
    )

    assert rows == [{"PIVOT": "customer-pivot-alias"}]


def test_execute_readonly_sql_allows_quoted_mutating_keyword_aliases():
    """Quoted mutation keywords are aliases and do not make a SELECT mutable."""
    repository = DuckDBRepository(":memory:")
    load_records(
        [{"record_id": "customer-delete-alias", "source": "crm"}],
        batch_id="batch-delete-alias",
        repository=repository,
    )

    rows = execute_readonly_sql(
        repository,
        'WITH "DELETE" ("UPDATE") AS (SELECT record_id FROM records) '
        'SELECT "UPDATE" FROM "DELETE"',
    )

    assert rows == [{"UPDATE": "customer-delete-alias"}]


def test_execute_readonly_sql_rejects_an_unpivot_catalog_relation():
    """UNPIVOT is a relation operator and cannot expose catalog tables."""
    repository = DuckDBRepository(":memory:")

    with pytest.raises(ValueError, match="allow-listed"):
        execute_readonly_sql(
            repository,
            "SELECT * FROM (UNPIVOT information_schema.tables "
            "ON table_name INTO NAME column_name VALUE column_value)",
        )


def test_execute_readonly_sql_rejects_a_table_catalog_relation():
    """TABLE cannot bypass source allow-listing for catalog relations."""
    repository = DuckDBRepository(":memory:")

    with pytest.raises(ValueError, match="allow-listed"):
        execute_readonly_sql(repository, "SELECT * FROM (TABLE information_schema.tables)")


def test_execute_readonly_sql_rejects_a_table_function_relation():
    """TABLE cannot be used to invoke an external-file table function."""
    repository = DuckDBRepository(":memory:")

    with pytest.raises(ValueError, match="allow-listed"):
        execute_readonly_sql(
            repository,
            "SELECT * FROM (TABLE read_csv_auto('not-permitted.csv'))",
        )


def test_execute_readonly_sql_allows_semicolons_in_quoted_aliases():
    """A semicolon inside a quoted alias is not a second SQL statement."""
    repository = DuckDBRepository(":memory:")
    load_records(
        [{"record_id": "customer-semicolon", "source": "crm"}],
        batch_id="batch-semicolon",
        repository=repository,
    )

    rows = execute_readonly_sql(repository, 'SELECT record_id AS "semi;colon" FROM records')

    assert rows == [{"semi;colon": "customer-semicolon"}]


def test_execute_readonly_sql_allows_materialized_ctes():
    """A materialized CTE remains an allow-listed read-only query."""
    repository = DuckDBRepository(":memory:")
    load_records(
        [{"record_id": "customer-materialized", "source": "crm"}],
        batch_id="batch-materialized",
        repository=repository,
    )

    rows = execute_readonly_sql(
        repository,
        "WITH cte AS MATERIALIZED (SELECT record_id FROM records) SELECT record_id FROM cte",
    )

    assert rows == [{"record_id": "customer-materialized"}]
