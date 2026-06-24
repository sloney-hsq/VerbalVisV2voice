"""
DuckDB data layer for VerbalVis.
Reads Olist CSVs → builds wide table → exposes query helpers.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import duckdb

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "data" / "olist"

# In-memory DuckDB – fast, no file locking issues
_con: duckdb.DuckDBPyConnection | None = None


def get_connection() -> duckdb.DuckDBPyConnection:
    global _con
    if _con is None:
        raise RuntimeError("Database not initialised – call initialize_db() first")
    return _con


# ------------------------------------------------------------------
# Initialisation
# ------------------------------------------------------------------

def initialize_db() -> None:
    """Read CSVs and build the wide table in memory."""
    global _con
    _con = duckdb.connect(":memory:")
    con = _con

    # Load raw tables
    csv_tables = {
        "orders":       "olist_orders_dataset.csv",
        "items":        "olist_order_items_dataset.csv",
        "reviews":      "olist_order_reviews_dataset.csv",
        "customers":    "olist_customers_dataset.csv",
        "products":     "olist_products_dataset.csv",
        "payments":     "olist_order_payments_dataset.csv",
        "translations": "product_category_name_translation.csv",
    }
    for alias, filename in csv_tables.items():
        path = DATA_DIR / filename
        con.execute(f"CREATE TABLE {alias} AS SELECT * FROM read_csv_auto('{path}', header=true)")

    # Payment totals per order
    con.execute("""
        CREATE TABLE payment_totals AS
        SELECT order_id, SUM(payment_value) AS payment_value
        FROM payments
        GROUP BY order_id
    """)

    # Build wide table
    con.execute("""
        CREATE TABLE main_table AS
        SELECT
            o.order_id,
            strftime(o.order_purchase_timestamp::TIMESTAMP, '%Y-%m')  AS order_month,
            r.review_score::INTEGER                                    AS review_score,
            c.customer_state                                           AS customer_state,
            COALESCE(t.product_category_name_english,
                     p.product_category_name, 'unknown')               AS product_category,
            CASE
                WHEN o.order_delivered_customer_date IS NOT NULL
                     AND o.order_purchase_timestamp IS NOT NULL
                THEN DATE_DIFF('day',
                        o.order_purchase_timestamp::TIMESTAMP,
                        o.order_delivered_customer_date::TIMESTAMP)
                ELSE NULL
            END                                                        AS delivery_days,
            pt.payment_value                                           AS revenue
        FROM orders o
        LEFT JOIN items        i  ON o.order_id = i.order_id
        LEFT JOIN reviews      r  ON o.order_id = r.order_id
        LEFT JOIN customers    c  ON o.customer_id = c.customer_id
        LEFT JOIN products     p  ON i.product_id  = p.product_id
        LEFT JOIN translations t  ON p.product_category_name = t.product_category_name
        LEFT JOIN payment_totals pt ON o.order_id = pt.order_id
        WHERE o.order_status = 'delivered'
    """)

    # De-duplicate: keep one row per order (the first item encountered)
    con.execute("""
        CREATE TABLE main_dedup AS
        SELECT * FROM (
            SELECT *, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY product_category) AS _rn
            FROM main_table
        ) WHERE _rn = 1
    """)
    con.execute("DROP TABLE main_table")
    con.execute("ALTER TABLE main_dedup RENAME TO main_table")
    con.execute("ALTER TABLE main_table DROP COLUMN _rn")

    row = con.execute("SELECT COUNT(DISTINCT order_id) FROM main_table").fetchone()
    assert row is not None
    row_count = row[0]
    log.info("main_table ready: %d rows", row_count)


# ------------------------------------------------------------------
# Valid fields / operators
# ------------------------------------------------------------------

FIELDS = [
    "order_month", "review_score", "customer_state",
    "product_category", "delivery_days", "revenue",
]

OPERATORS = {"eq", "neq", "in", "gte", "lte", "between"}


# ------------------------------------------------------------------
# Filter helpers
# ------------------------------------------------------------------

def build_where(filters: list[dict[str, Any]]) -> str:
    """Build a WHERE clause from a list of filter dicts."""
    clauses: list[str] = []
    for f in filters:
        field = f["field"]
        op = f["operator"]
        val = f["value"]
        if op == "eq":
            clauses.append(f"{field} = {_sql_val(val)}")
        elif op == "neq":
            clauses.append(f"{field} != {_sql_val(val)}")
        elif op == "gte":
            clauses.append(f"{field} >= {_sql_val(val)}")
        elif op == "lte":
            clauses.append(f"{field} <= {_sql_val(val)}")
        elif op == "in":
            vals = ", ".join(_sql_val(v) for v in val)
            clauses.append(f"{field} IN ({vals})")
        elif op == "between":
            clauses.append(f"{field} BETWEEN {_sql_val(val[0])} AND {_sql_val(val[1])}")
    return " AND ".join(clauses) if clauses else "1=1"


def _sql_val(v: Any) -> str:
    if isinstance(v, str):
        safe = v.replace("'", "''")
        return f"'{safe}'"
    return str(v)


# ------------------------------------------------------------------
# Query functions
# ------------------------------------------------------------------

def aggregate_query(
    group_field: str,
    agg_expr: str,
    agg_alias: str = "value",
    filters: list[dict] | None = None,
    order_by: str | None = None,
    extra_group_fields: list[str] | None = None,
) -> list[dict]:
    """
    Run:  SELECT group_field, [extra_group_fields...], agg_expr AS agg_alias
          FROM main_table WHERE ... GROUP BY group_field, [extra_group_fields...] ORDER BY ...

    extra_group_fields lets callers add a secondary grouping dimension (e.g. a
    color-encoding field) so the returned rows actually contain that column —
    without it, charts that group only by `group_field` silently drop any
    color field the caller asked for, since it never appears in the SELECT.
    Returns list of dicts.
    """
    con = get_connection()
    where = build_where(filters or [])
    ob = order_by or group_field
    extra = extra_group_fields or []
    group_cols = [group_field, *extra]
    select_cols = ", ".join(group_cols)
    sql = f"""
        SELECT {select_cols}, {agg_expr} AS {agg_alias}
        FROM main_table
        WHERE {where}
        GROUP BY {select_cols}
        ORDER BY {ob}
    """
    cols = [*group_cols, agg_alias]
    rows = con.execute(sql).fetchall()
    return [dict(zip(cols, row)) for row in rows]


def stats_query(
    field: str,
    filters: list[dict] | None = None,
) -> dict[str, Any]:
    """Basic descriptive stats for a numeric field."""
    con = get_connection()
    where = build_where(filters or [])
    sql = f"""
        SELECT
            COUNT(DISTINCT order_id)           AS row_count,
            AVG({field})       AS mean,
            MEDIAN({field})    AS median,
            MIN({field})       AS min_val,
            MAX({field})       AS max_val
        FROM main_table
        WHERE {where} AND {field} IS NOT NULL
    """
    row = con.execute(sql).fetchone()
    assert row is not None
    return {
        "row_count": row[0],
        "mean": round(row[1], 2) if row[1] is not None else None,
        "median": round(row[2], 2) if row[2] is not None else None,
        "min": row[3],
        "max": row[4],
    }


def raw_query(sql: str) -> list[dict]:
    """Run arbitrary read-only SQL. Returns list of dicts."""
    con = get_connection()
    result = con.execute(sql)
    cols = [d[0] for d in result.description]
    return [dict(zip(cols, row)) for row in result.fetchall()]


def total_rows(filters: list[dict] | None = None) -> int:
    con = get_connection()
    where = build_where(filters or [])
    row = con.execute(f"SELECT COUNT(DISTINCT order_id) FROM main_table WHERE {where}").fetchone()
    assert row is not None
    return row[0]
