"""Public result models for data ingestion."""

from dataclasses import dataclass


@dataclass(frozen=True)
class LoadSummary:
    batch_id: str
    received: int
    loaded: int
    duplicates: int
    quarantined: int
    skipped: bool = False


@dataclass(frozen=True)
class QualityReport:
    schema_valid_rate: float
    duplicate_rate: float
