from dataops_agent.data.etl import load_records
from dataops_agent.data.quality import run_quality_checks
from dataops_agent.data.repository import DuckDBRepository


def test_quality_checks_report_schema_valid_and_duplicate_rates():
    """The report must distinguish invalid inputs from valid duplicates."""
    repository = DuckDBRepository(":memory:")
    load_records(
        [
            {"record_id": "customer-3", "source": "crm"},
            {"record_id": "customer-3", "source": "crm"},
            {"source": "crm"},
        ],
        batch_id="batch-quality",
        repository=repository,
    )

    report = run_quality_checks(repository)

    assert report.schema_valid_rate == 2 / 3
    assert report.duplicate_rate == 1 / 3
