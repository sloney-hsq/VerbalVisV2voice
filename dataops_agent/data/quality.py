"""Data-quality reporting."""

from .models import QualityReport
from .repository import DuckDBRepository


def run_quality_checks(repository: DuckDBRepository) -> QualityReport:
    """Aggregate quality metrics across completed ingestion batches."""
    received, loaded, duplicates = repository.connection.execute(
        """
        SELECT
            COALESCE(SUM(received), 0),
            COALESCE(SUM(loaded), 0),
            COALESCE(SUM(duplicates), 0)
        FROM load_batches
        WHERE status = 'completed'
        """
    ).fetchone()
    if received == 0:
        return QualityReport(schema_valid_rate=1.0, duplicate_rate=0.0)
    return QualityReport(
        schema_valid_rate=(loaded + duplicates) / received,
        duplicate_rate=duplicates / received,
    )
