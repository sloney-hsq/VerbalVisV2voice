"""Environment-backed configuration for optional external adapters."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Settings:
    database_path: str = ":memory:"
    redis_url: str | None = None
    elasticsearch_url: str | None = None
    elasticsearch_index: str = "dataops-knowledge"
    redis_stream: str = "dataops:audit"
    redis_group: str = "dataops-workers"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_path=os.getenv("DATAOPS_DATABASE_PATH", ":memory:"),
            redis_url=os.getenv("DATAOPS_REDIS_URL") or None,
            elasticsearch_url=os.getenv("DATAOPS_ELASTICSEARCH_URL") or None,
            elasticsearch_index=os.getenv("DATAOPS_ELASTICSEARCH_INDEX", "dataops-knowledge"),
            redis_stream=os.getenv("DATAOPS_REDIS_STREAM", "dataops:audit"),
            redis_group=os.getenv("DATAOPS_REDIS_GROUP", "dataops-workers"),
        )
