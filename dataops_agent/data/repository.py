"""DuckDB persistence for deterministic data ingestion."""

import json
import os
import re
import time
from base64 import b64encode
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

import duckdb


_ALLOWED_TABLES = frozenset({"records", "quarantine_records", "load_batches"})
_IDENTIFIER = r'(?:"(?:[^"]|"")+"|[A-Za-z_][A-Za-z0-9_$]*)'
_CTE_PATTERN = re.compile(
    rf"(?:\bWITH\b|,)\s*(?:RECURSIVE\s+)?(?P<name>{_IDENTIFIER})"
    rf"(?:\s*\(\s*{_IDENTIFIER}(?:\s*,\s*{_IDENTIFIER})*\s*\))?\s+AS\s+"
    rf"(?:MATERIALIZED\s+)?\(",
    re.IGNORECASE,
)
_MUTATING_KEYWORDS = frozenset(
    {
        "ALTER",
        "ATTACH",
        "CALL",
        "COPY",
        "CREATE",
        "DELETE",
        "DETACH",
        "DROP",
        "EXPORT",
        "IMPORT",
        "INSERT",
        "INSTALL",
        "LOAD",
        "MERGE",
        "PRAGMA",
        "REPLACE",
        "TRUNCATE",
        "UPDATE",
        "VACUUM",
    }
)
_DENIED_RELATION_OPERATORS = frozenset({"PIVOT", "TABLE", "UNPIVOT"})
_TOKEN_PATTERN = re.compile(r'"(?:[^"]|"")*"|[A-Za-z_][A-Za-z0-9_$]*|[(),.]')
_IDENTIFIER_PATTERN = re.compile(rf"^{_IDENTIFIER}$")
_FROM_CLAUSE_END = frozenset(
    {
        "EXCEPT",
        "GROUP",
        "HAVING",
        "INTERSECT",
        "LIMIT",
        "ORDER",
        "QUALIFY",
        "UNION",
        "WHERE",
        "WINDOW",
    }
)
_FILE_LOCK_TIMEOUT_SECONDS = 10.0
_FILE_LOCK_POLL_SECONDS = 0.05
_STALE_FILE_LOCK_SECONDS = 60.0


class _FileDatabaseLock:
    """An exclusive, bounded lock for DuckDB files shared by multiple processes."""

    def __init__(self, database_path: Path) -> None:
        self._path = database_path.with_suffix(database_path.suffix + ".dataops.lock")
        self._file_descriptor: int | None = None

    @staticmethod
    def _process_is_running(process_id: int) -> bool:
        if process_id <= 0:
            return False
        try:
            os.kill(process_id, 0)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        else:
            return True

    def _is_stale(self) -> bool:
        try:
            modified_at = self._path.stat().st_mtime
        except OSError:
            return False
        try:
            lock_data = json.loads(self._path.read_text(encoding="utf-8"))
            created_at = float(lock_data["created_at"])
            process_id = int(lock_data["process_id"])
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError):
            return time.time() - modified_at >= _STALE_FILE_LOCK_SECONDS
        return (
            time.time() - created_at >= _STALE_FILE_LOCK_SECONDS
            and not self._process_is_running(process_id)
        )

    def __enter__(self) -> "_FileDatabaseLock":
        deadline = time.monotonic() + _FILE_LOCK_TIMEOUT_SECONDS
        while True:
            try:
                file_descriptor = os.open(
                    self._path,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                )
            except FileExistsError:
                if self._is_stale():
                    try:
                        self._path.unlink()
                    except FileNotFoundError:
                        pass
                    continue
                if time.monotonic() >= deadline:
                    raise TimeoutError(f"Timed out waiting for DuckDB file lock: {self._path}")
                time.sleep(_FILE_LOCK_POLL_SECONDS)
                continue

            self._file_descriptor = file_descriptor
            payload = json.dumps({"process_id": os.getpid(), "created_at": time.time()}).encode()
            os.write(file_descriptor, payload)
            return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        if self._file_descriptor is not None:
            os.close(self._file_descriptor)
            self._file_descriptor = None
        try:
            self._path.unlink()
        except FileNotFoundError:
            pass


def _safe_json_default(value: object) -> object:
    if isinstance(value, bytes):
        return {"type": "bytes", "base64": b64encode(value).decode("ascii")}
    try:
        representation = repr(value)
    except Exception:
        representation = "<unrepresentable>"
    return {"type": type(value).__name__, "repr": representation}


def _safe_json_key(value: object) -> str:
    if isinstance(value, str):
        return value
    try:
        return str(value)
    except Exception:
        return f"<{type(value).__name__}>"


def _normalise_json_value(value: object, ancestors: set[int] | None = None) -> object:
    if not isinstance(value, (dict, list, tuple, set, frozenset)):
        return value

    ancestor_ids = set() if ancestors is None else ancestors
    value_id = id(value)
    if value_id in ancestor_ids:
        return {"type": "circular_reference"}

    ancestor_ids.add(value_id)
    try:
        if isinstance(value, dict):
            return {
                _safe_json_key(key): _normalise_json_value(item, ancestor_ids)
                for key, item in value.items()
            }
        return [_normalise_json_value(item, ancestor_ids) for item in value]
    finally:
        ancestor_ids.remove(value_id)


def _to_json(value: object) -> str:
    return json.dumps(
        _normalise_json_value(value),
        default=_safe_json_default,
        ensure_ascii=False,
    )

def _scrub_sql(sql: str) -> str:
    """Remove quoted text and comments before applying SQL admission checks."""
    result: list[str] = []
    index = 0
    quote: str | None = None
    while index < len(sql):
        character = sql[index]
        if quote:
            if character == quote:
                if index + 1 < len(sql) and sql[index + 1] == quote:
                    index += 2
                    result.extend("  " if quote == "'" else '""')
                    continue
                quote = None
                result.append(" " if character == "'" else character)
            elif quote == "'":
                result.append(" ")
            else:
                result.append(" " if character == ";" else character)
        elif character == "'":
            quote = character
            result.extend("_literal")
        elif character == '"':
            quote = character
            result.append(character)
        elif sql.startswith("--", index):
            newline = sql.find("\n", index)
            if newline == -1:
                result.extend(" " * (len(sql) - index))
                break
            result.extend(" " * (newline - index))
            index = newline - 1
        elif sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            end = len(sql) - 2 if end == -1 else end
            result.extend(" " * (end + 2 - index))
            index = end + 1
        else:
            result.append(character)
        index += 1
    return "".join(result)


def _normalise_identifier(identifier: str) -> str:
    if identifier.startswith('"') and identifier.endswith('"'):
        return identifier[1:-1].replace('""', '"').lower()
    return identifier.lower()


def _has_unquoted_keywords(sql: str, keywords: frozenset[str]) -> bool:
    return any(token.upper() in keywords for token in _TOKEN_PATTERN.findall(sql))


def _referenced_tables(sql: str) -> list[str]:
    """Return table sources while distinguishing FROM commas from SELECT commas."""
    tokens = _TOKEN_PATTERN.findall(sql)
    tables: list[str] = []
    active_from_depths: set[int] = set()
    depth = 0
    index = 0

    def consume_relation(start: int) -> int:
        if start >= len(tokens) or tokens[start] == "(":
            return start
        if not _IDENTIFIER_PATTERN.fullmatch(tokens[start]):
            return start
        parts = [tokens[start]]
        next_index = start + 1
        while (
            next_index + 1 < len(tokens)
            and tokens[next_index] == "."
            and _IDENTIFIER_PATTERN.fullmatch(tokens[next_index + 1])
        ):
            parts.append(tokens[next_index + 1])
            next_index += 2
        tables.append(_normalise_identifier(".".join(parts)))
        return next_index

    while index < len(tokens):
        token = tokens[index]
        upper = token.upper()
        if token == "(":
            depth += 1
            index += 1
        elif token == ")":
            active_from_depths.discard(depth)
            depth = max(0, depth - 1)
            index += 1
        elif upper in {"FROM", "JOIN"}:
            active_from_depths.add(depth)
            index = consume_relation(index + 1)
        elif token == "," and depth in active_from_depths:
            index = consume_relation(index + 1)
        elif upper in _FROM_CLAUSE_END:
            active_from_depths.discard(depth)
            index += 1
        else:
            index += 1
    return tables


def _admit_readonly_sql(sql: str) -> None:
    scrubbed = _scrub_sql(sql)
    if not re.match(r"^\s*(?:SELECT|WITH)\b", scrubbed, re.IGNORECASE):
        raise ValueError("Only SELECT or WITH statements are allowed")
    if _has_unquoted_keywords(scrubbed, _MUTATING_KEYWORDS):
        raise ValueError("Only SELECT or WITH statements are allowed")
    if ";" in scrubbed.rstrip().rstrip(";"):
        raise ValueError("Only SELECT or WITH statements are allowed")
    if _has_unquoted_keywords(scrubbed, _DENIED_RELATION_OPERATORS):
        raise ValueError("Table is not allow-listed")
    cte_names = {
        _normalise_identifier(match.group("name")) for match in _CTE_PATTERN.finditer(scrubbed)
    }
    for table in _referenced_tables(scrubbed):
        if table not in _ALLOWED_TABLES and table not in cte_names:
            raise ValueError(f"Table is not allow-listed: {table}")


class DuckDBRepository:
    """Owns the durable tables used by the ingestion pipeline."""

    def __init__(self, database: str = ":memory:") -> None:
        self._database = database
        self._database_path = None if database == ":memory:" else Path(database).resolve()
        self._connection = None
        self._operation_lock = RLock()
        if self._database_path is None:
            self._open_connection()

    @property
    def connection(self):
        if self._connection is None:
            self._open_connection()
        return self._connection

    @property
    def is_file_backed(self) -> bool:
        return self._database_path is not None

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    def _open_connection(self) -> None:
        connection = duckdb.connect(self._database)
        try:
            self._initialise_schema(connection)
        except BaseException:
            connection.close()
            raise
        self._connection = connection

    @staticmethod
    def _initialise_schema(connection) -> None:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS records (
                record_id VARCHAR PRIMARY KEY,
                source VARCHAR NOT NULL,
                payload JSON NOT NULL,
                batch_id VARCHAR NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS quarantine_records (
                batch_id VARCHAR NOT NULL,
                raw_record JSON NOT NULL,
                reason VARCHAR NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS load_batches (
                batch_id VARCHAR PRIMARY KEY,
                received INTEGER NOT NULL,
                loaded INTEGER NOT NULL,
                duplicates INTEGER NOT NULL,
                quarantined INTEGER NOT NULL,
                status VARCHAR NOT NULL
            )
            """
        )

    def close(self) -> None:
        if self._connection is not None:
            self._connection.close()
            self._connection = None

    def batch_completed(self, batch_id: str) -> bool:
        return bool(
            self.connection.execute(
                "SELECT 1 FROM load_batches WHERE batch_id = ? AND status = 'completed'",
                [batch_id],
            ).fetchone()
        )

    @contextmanager
    def batch_lock(self, batch_id: str):
        del batch_id
        with self._operation_lock:
            if self._database_path is None:
                yield
            else:
                with _FileDatabaseLock(self._database_path):
                    yield

    @contextmanager
    def transaction(self):
        self.connection.execute("BEGIN TRANSACTION")
        try:
            yield
        except BaseException:
            self.connection.execute("ROLLBACK")
            raise
        else:
            self.connection.execute("COMMIT")

    def insert_record(self, record_id: str, source: str, record: dict, batch_id: str) -> bool:
        existing = self.connection.execute(
            "SELECT 1 FROM records WHERE record_id = ?", [record_id]
        ).fetchone()
        if existing:
            return False
        self.connection.execute(
            "INSERT INTO records VALUES (?, ?, ?, ?)",
            [record_id, source, _to_json(record), batch_id],
        )
        return True

    def claim_batch(self, batch_id: str) -> bool:
        try:
            self.connection.execute(
                "INSERT INTO load_batches VALUES (?, 0, 0, 0, 0, 'processing')",
                [batch_id],
            )
        except duckdb.ConstraintException:
            return False
        return True

    def quarantine_record(self, batch_id: str, record: object, reason: str) -> None:
        self.connection.execute(
            "INSERT INTO quarantine_records VALUES (?, ?, ?)",
            [batch_id, _to_json(record), reason],
        )

    def record_batch(
        self, batch_id: str, received: int, loaded: int, duplicates: int, quarantined: int
    ) -> None:
        self.connection.execute(
            """
            UPDATE load_batches
            SET received = ?, loaded = ?, duplicates = ?, quarantined = ?, status = 'completed'
            WHERE batch_id = ? AND status = 'processing'
            """,
            [received, loaded, duplicates, quarantined, batch_id],
        )

    def count_rows(self, table: str) -> int:
        if table not in {"records", "quarantine_records", "load_batches"}:
            raise ValueError(f"Unknown table: {table}")
        return self.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]


def execute_readonly_sql(repository: DuckDBRepository, sql: str) -> list[dict[str, object]]:
    """Run a single read-only SELECT and return JSON-compatible row mappings."""
    _admit_readonly_sql(sql)
    cursor = repository.connection.execute(sql)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
