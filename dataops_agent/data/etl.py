"""Idempotent record loading."""

from collections.abc import Iterable

from .models import LoadSummary
from .repository import DuckDBRepository


def load_records(
    records: Iterable[object], *, batch_id: str, repository: DuckDBRepository
) -> LoadSummary:
    """Load unique records and persist a completed batch marker."""
    if repository.is_file_backed:
        repository.close()
    with repository.batch_lock(batch_id):
        close_after_load = repository.is_file_backed
        try:
            with repository.transaction():
                if not repository.claim_batch(batch_id):
                    return LoadSummary(batch_id, 0, 0, 0, 0, skipped=True)

                received = loaded = duplicates = quarantined = 0
                for record in records:
                    received += 1
                    if not isinstance(record, dict):
                        quarantined += 1
                        repository.quarantine_record(batch_id, record, "record must be an object")
                        continue
                    record_id = record.get("record_id")
                    if not isinstance(record_id, str) or not record_id.strip():
                        quarantined += 1
                        repository.quarantine_record(batch_id, record, "record_id is required")
                        continue
                    source = record.get("source", "unknown")
                    if repository.insert_record(record_id, str(source), record, batch_id):
                        loaded += 1
                    else:
                        duplicates += 1

                repository.record_batch(batch_id, received, loaded, duplicates, quarantined)
                return LoadSummary(batch_id, received, loaded, duplicates, quarantined)
        finally:
            if close_after_load:
                repository.close()
