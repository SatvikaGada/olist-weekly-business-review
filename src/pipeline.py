"""Olist ELT pipeline: CSV -> raw -> staging -> DQ checks (alarm) -> mart.
Run:  python src/pipeline.py      (needs env var PG_PASSWORD)
"""
import csv
import logging
import os
import sys
import time
from pathlib import Path

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.engine import URL
from sqlalchemy.exc import OperationalError

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR, SQL_DIR, REPORT_DIR = ROOT / "data", ROOT / "sql", ROOT / "reports"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler(ROOT / "pipeline.log", encoding="utf-8")],
)
log = logging.getLogger("olist")


class PipelineError(Exception):
    """Expected failure (missing file, bad column, DB down)."""


class DataQualityError(PipelineError):
    """A data-quality check still fails after handling."""


# table -> (csv file, columns the pipeline relies on)
SOURCES = {
    "orders": ("olist_orders_dataset.csv",
               ["order_id", "customer_id", "order_status", "order_purchase_timestamp",
                "order_approved_at", "order_delivered_carrier_date",
                "order_delivered_customer_date", "order_estimated_delivery_date"]),
    "customers": ("olist_customers_dataset.csv",
                  ["customer_id", "customer_unique_id", "customer_zip_code_prefix",
                   "customer_city", "customer_state"]),
    "order_items": ("olist_order_items_dataset.csv",
                    ["order_id", "order_item_id", "product_id", "seller_id",
                     "shipping_limit_date", "price", "freight_value"]),
    "order_payments": ("olist_order_payments_dataset.csv",
                       ["order_id", "payment_sequential", "payment_type",
                        "payment_installments", "payment_value"]),
    "order_reviews": ("olist_order_reviews_dataset.csv",
                      ["review_id", "order_id", "review_score",
                       "review_creation_date", "review_answer_timestamp"]),
    "products": ("olist_products_dataset.csv", ["product_id", "product_category_name"]),
    "sellers": ("olist_sellers_dataset.csv",
                ["seller_id", "seller_city", "seller_state"]),
    "geolocation": ("olist_geolocation_dataset.csv",
                    ["geolocation_zip_code_prefix", "geolocation_lat",
                     "geolocation_lng", "geolocation_city", "geolocation_state"]),
}

HANDLING = {
    "null_or_duplicate_order_id": "Dropped null IDs; kept one row per order_id",
    "delivered_before_purchase": "Delivery timestamp set to NULL (impossible value)",
    "payment_not_equal_items_plus_freight": "Flagged (payment_mismatch_flag), rows kept",
    "orders_without_customer": "Dropped (cannot be attributed to a customer/state)",
    "orders_with_multiple_reviews": "Kept latest review per order",
    "delivered_status_but_no_delivery_date": "Flagged, excluded from delay metrics",
}


def get_engine():
    password = os.environ.get("PG_PASSWORD")
    if not password:
        raise PipelineError("Environment variable PG_PASSWORD is not set. "
                            'In PowerShell run: $env:PG_PASSWORD="your_password"')
    url = URL.create(
        "postgresql+psycopg2",
        username=os.environ.get("PG_USER", "postgres"),
        password=password,
        host=os.environ.get("PG_HOST", "localhost"),
        port=int(os.environ.get("PG_PORT", "5432")),
        database=os.environ.get("PG_DB", "olist"),
    )
    engine = create_engine(url, connect_args={"options": "-c client_encoding=UTF8"})
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
    except OperationalError as exc:
        raise PipelineError(f"Cannot connect to PostgreSQL: {exc.orig}") from exc
    log.info("Connected to PostgreSQL")
    return engine


def check_sources():
    """Fail loudly (one message) if any file or expected column is missing."""
    problems = []
    for table, (fname, cols) in SOURCES.items():
        path = DATA_DIR / fname
        if not path.exists():
            problems.append(f"missing file: {path}")
            continue
        with open(path, encoding="utf-8-sig", newline="") as f:
            header = next(csv.reader(f), [])
        absent = [c for c in cols if c not in header]
        if absent:
            problems.append(f"{fname}: missing column(s) {absent}")
    if problems:
        raise PipelineError("Source validation failed:\n  - " + "\n  - ".join(problems))
    log.info("Source validation passed: %d files, all expected columns present", len(SOURCES))


def load_raw(engine, table, fname):
    """Load a CSV as-is (all TEXT). DROP+CREATE+COPY in ONE transaction => idempotent."""
    path = DATA_DIR / fname
    with open(path, encoding="utf-8-sig", newline="") as f:
        header = next(csv.reader(f))
    col_defs = ", ".join(f'"{c}" TEXT' for c in header)
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute("CREATE SCHEMA IF NOT EXISTS raw")
        cur.execute(f"DROP TABLE IF EXISTS raw.{table}")
        cur.execute(f"CREATE TABLE raw.{table} ({col_defs})")
        with open(path, encoding="utf-8", newline="") as f:
            cur.copy_expert(f"COPY raw.{table} FROM STDIN WITH (FORMAT csv, HEADER true)", f)
        cur.execute(f"SELECT COUNT(*) FROM raw.{table}")
        n = cur.fetchone()[0]
        raw.commit()
    except Exception:
        raw.rollback()
        raise
    finally:
        raw.close()
    log.info("raw.%-15s loaded %9d rows", table, n)


def run_script(engine, filename):
    log.info("Running %s", filename)
    sql = (SQL_DIR / filename).read_text(encoding="utf-8")
    with engine.begin() as conn:
        conn.exec_driver_sql(sql)


def parse_checks(path):
    checks, name = {}, None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("-- name:"):
            name = line.split(":", 1)[1].strip()
            checks[name] = []
        elif name:
            checks[name].append(line)
    return {k: "\n".join(v).strip().rstrip(";") for k, v in checks.items()}


def run_checks(engine, checks):
    out = {}
    with engine.connect() as conn:
        for name, query in checks.items():
            out[name] = conn.exec_driver_sql(
                f"SELECT COUNT(*) FROM ({query}) AS failing").scalar_one()
    return out


def main():
    start = time.time()
    try:
        engine = get_engine()
        check_sources()

        for table, (fname, _) in SOURCES.items():
            load_raw(engine, table, fname)

        run_script(engine, "staging.sql")

        checks = parse_checks(SQL_DIR / "data_quality.sql")
        before = run_checks(engine, checks)
        for name, n in before.items():
            log.info("DQ BEFORE handling | %-40s | failing rows: %d", name, n)

        run_script(engine, "dq_handling.sql")

        after = run_checks(engine, checks)
        REPORT_DIR.mkdir(exist_ok=True)
        pd.DataFrame({
            "check": list(checks),
            "failing_before": [before[c] for c in checks],
            "failing_after": [after[c] for c in checks],
            "handling": [HANDLING.get(c, "") for c in checks],
        }).to_csv(REPORT_DIR / "dq_results.csv", index=False)

        failed = {k: v for k, v in after.items() if v > 0}
        for name, n in after.items():
            log.info("DQ AFTER  handling | %-40s | failing rows: %d", name, n)
        if failed:
            raise DataQualityError(f"DATA QUALITY ALARM - checks still failing: {failed}")

        run_script(engine, "mart.sql")

        with engine.connect() as conn:
            mart_n, stg_n, mart_distinct = conn.exec_driver_sql(
                "SELECT (SELECT COUNT(*) FROM mart.order_summary),"
                "       (SELECT COUNT(*) FROM staging.orders),"
                "       (SELECT COUNT(DISTINCT order_id) FROM mart.order_summary)").one()
        if not (mart_n == stg_n == mart_distinct):
            raise PipelineError(f"Mart is not one row per order: mart={mart_n}, "
                                f"staging={stg_n}, distinct={mart_distinct}")
        log.info("mart.order_summary: %d rows, one per order", mart_n)
        log.info("Pipeline finished OK in %.1fs", time.time() - start)
    except PipelineError as exc:
        log.error("PIPELINE FAILED: %s", exc)
        sys.exit(1)
    except Exception:
        log.exception("PIPELINE CRASHED (unexpected error)")
        sys.exit(2)


if __name__ == "__main__":
    main()