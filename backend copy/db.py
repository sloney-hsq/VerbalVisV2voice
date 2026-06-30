"""
DuckDB data layer for VerbalVis.
Reads Olist CSVs → builds two fact tables:
  - fact_order: 1 row per delivered order_id (for order-grain views)
  - fact_item:  1 row per (order_id, order_item_id) (for category/product views)
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
    """Read CSVs and build fact_order + fact_item in memory."""
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

    # Payment totals per order (collapse installments)
    con.execute("""
        CREATE TABLE payment_totals AS
        SELECT order_id, SUM(payment_value) AS payment_value
        FROM payments
        GROUP BY order_id
    """)

    # Some orders have multiple review rows. Keep the latest one per order so
    # the join in fact_order doesn't multiply rows.
    con.execute("""
        CREATE TABLE reviews_dedup AS
        SELECT * FROM (
            SELECT *, ROW_NUMBER() OVER (
                PARTITION BY order_id ORDER BY review_creation_date DESC
            ) AS _rn FROM reviews
        ) WHERE _rn = 1
    """)

    # ------------------------------------------------------------------
    # fact_order — order grain. One row per delivered order.
    # Carries every order-level fact (review, state, delivery, payment).
    # ------------------------------------------------------------------
    con.execute("""
        CREATE TABLE fact_order AS
        SELECT
            o.order_id,
            c.customer_unique_id,
            strftime(o.order_purchase_timestamp::TIMESTAMP, '%Y-%m')      AS order_month,
            CAST(o.order_purchase_timestamp::TIMESTAMP AS DATE)           AS order_date,
            strftime(o.order_purchase_timestamp::TIMESTAMP, '%G-W%V')     AS order_week,
            isodow(o.order_purchase_timestamp::TIMESTAMP)::INTEGER        AS order_dow,
            EXTRACT(HOUR FROM o.order_purchase_timestamp::TIMESTAMP)::INTEGER AS order_hour,
            r.review_score::INTEGER                                       AS review_score,
            c.customer_state                                              AS customer_state,
            CASE
                WHEN o.order_delivered_customer_date IS NOT NULL
                     AND o.order_purchase_timestamp IS NOT NULL
                THEN DATE_DIFF('day',
                        o.order_purchase_timestamp::TIMESTAMP,
                        o.order_delivered_customer_date::TIMESTAMP)
                ELSE NULL
            END                                                       AS delivery_days,
            pt.payment_value                                          AS order_revenue
        FROM orders o
        LEFT JOIN reviews_dedup   r  ON o.order_id    = r.order_id
        LEFT JOIN customers       c  ON o.customer_id = c.customer_id
        LEFT JOIN payment_totals pt  ON o.order_id    = pt.order_id
        WHERE o.order_status = 'delivered'
    """)

    # ------------------------------------------------------------------
    # fact_item — item grain. One row per order item of a delivered order.
    # Redundantly carries the order-level filter fields so any filter can
    # be evaluated in a single WHERE on this table too.
    # ------------------------------------------------------------------
    con.execute("""
        CREATE TABLE fact_item AS
        SELECT
            i.order_id,
            i.order_item_id,
            i.product_id,
            i.seller_id,
            i.price,
            i.freight_value,
            (i.price + i.freight_value)                              AS item_revenue,
            COALESCE(t.product_category_name_english,
                     p.product_category_name, 'unknown')             AS product_category,
            f.customer_unique_id,
            f.order_month,
            f.order_date,
            f.order_week,
            f.order_dow,
            f.order_hour,
            f.review_score,
            f.customer_state,
            f.delivery_days,
            f.order_revenue
        FROM items i
        JOIN  fact_order   f  ON i.order_id   = f.order_id
        LEFT JOIN products p  ON i.product_id = p.product_id
        LEFT JOIN translations t ON p.product_category_name = t.product_category_name
    """)

    n_order = con.execute("SELECT COUNT(*) FROM fact_order").fetchone()[0]
    n_item  = con.execute("SELECT COUNT(*) FROM fact_item").fetchone()[0]
    log.info("fact_order ready: %d rows | fact_item ready: %d rows", n_order, n_item)


# ------------------------------------------------------------------
# Valid fields / operators
# ------------------------------------------------------------------

FIELDS = [
    "order_month", "order_week", "order_date", "order_dow", "order_hour",
    "review_score", "customer_state",
    "product_category", "delivery_days", "revenue",
]

OPERATORS = {"eq", "neq", "in", "gte", "lte", "between"}

# Filter-field name → physical column name, per source table.
# `product_category` only exists on fact_item; cross-grain filters from
# fact_order are rewritten in build_where() as an order_id subquery.
_FIELD_COL: dict[str, dict[str, str]] = {
    "fact_order": {
        "order_month":    "order_month",
        "order_week":     "order_week",
        "order_date":     "order_date",
        "order_dow":      "order_dow",
        "order_hour":     "order_hour",
        "review_score":   "review_score",
        "customer_state": "customer_state",
        "delivery_days":  "delivery_days",
        "revenue":        "order_revenue",
    },
    "fact_item": {
        "order_month":      "order_month",
        "order_week":       "order_week",
        "order_date":       "order_date",
        "order_dow":        "order_dow",
        "order_hour":       "order_hour",
        "review_score":     "review_score",
        "customer_state":   "customer_state",
        "delivery_days":    "delivery_days",
        "revenue":          "order_revenue",
        "product_category": "product_category",
    },
}


def resolve_column(field: str, table: str = "fact_order") -> str:
    """Resolve a filter-system field name to the physical column on `table`.

    Returns the field unchanged if it's already a physical column on that
    table (used by scatter/group_field paths that pass column names directly).
    """
    cols = _FIELD_COL.get(table, {})
    if field in cols:
        return cols[field]
    return field


# ------------------------------------------------------------------
# Filter helpers
# ------------------------------------------------------------------

def build_where(filters: list[dict[str, Any]], table: str = "fact_order") -> str:
    """Build a WHERE clause from filter dicts, targeted at `table`.

    Cross-grain rule: filtering on `product_category` against fact_order is
    rewritten as `order_id IN (SELECT DISTINCT order_id FROM fact_item WHERE …)`
    so the filter has the right semantic ("orders containing item X") instead
    of erroring on a missing column.
    """
    clauses: list[str] = []
    for f in filters:
        field = f["field"]
        op = f["operator"]
        val = f["value"]

        # Cross-grain: product_category lives on fact_item only.
        if field == "product_category" and table == "fact_order":
            inner = _clause("product_category", op, val)
            clauses.append(
                f"order_id IN (SELECT DISTINCT order_id FROM fact_item WHERE {inner})"
            )
            continue

        col = resolve_column(field, table)
        clauses.append(_clause(col, op, val))
    return " AND ".join(clauses) if clauses else "1=1"


def _clause(col: str, op: str, val: Any) -> str:
    if op == "eq":
        return f"{col} = {_sql_val(val)}"
    if op == "neq":
        return f"{col} != {_sql_val(val)}"
    if op == "gte":
        return f"{col} >= {_sql_val(val)}"
    if op == "lte":
        return f"{col} <= {_sql_val(val)}"
    if op == "in":
        vals = ", ".join(_sql_val(v) for v in val)
        return f"{col} IN ({vals})"
    if op == "between":
        return f"{col} BETWEEN {_sql_val(val[0])} AND {_sql_val(val[1])}"
    raise ValueError(f"Unknown operator: {op}")


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
    table: str = "fact_order",
) -> list[dict]:
    """
    SELECT group_field, [extra_group_fields…], agg_expr AS agg_alias
    FROM <table> WHERE … GROUP BY group_field, [extra…] ORDER BY …
    """
    con = get_connection()
    where = build_where(filters or [], table=table)
    ob = order_by or group_field
    extra = extra_group_fields or []
    group_cols = [group_field, *extra]
    select_cols = ", ".join(group_cols)
    sql = f"""
        SELECT {select_cols}, {agg_expr} AS {agg_alias}
        FROM {table}
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
    table: str = "fact_order",
) -> dict[str, Any]:
    """Basic descriptive stats for a numeric field on the given table."""
    con = get_connection()
    where = build_where(filters or [], table=table)
    col = resolve_column(field, table)
    sql = f"""
        SELECT
            COUNT(DISTINCT order_id)  AS row_count,
            AVG({col})                AS mean,
            MEDIAN({col})             AS median,
            MIN({col})                AS min_val,
            MAX({col})                AS max_val
        FROM {table}
        WHERE {where} AND {col} IS NOT NULL
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
    """Distinct delivered-order count after applying filters."""
    con = get_connection()
    where = build_where(filters or [], table="fact_order")
    row = con.execute(
        f"SELECT COUNT(DISTINCT order_id) FROM fact_order WHERE {where}"
    ).fetchone()
    assert row is not None
    return row[0]
