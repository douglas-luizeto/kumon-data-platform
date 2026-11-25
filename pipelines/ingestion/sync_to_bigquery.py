"""
PostgreSQL to BigQuery Replication Pipeline (Staging + MERGE Pattern)

Extracts all 14 master (catalogs + entities) and transactional tables from a local
PostgreSQL instance, serializes records into an in-memory PyArrow Parquet buffer
with strict typing, loads into a temporary BigQuery staging table, and executes
an idempotent MERGE or full replacement into the target dataset.
"""

import argparse
import io
import logging
import os
import sys
import time
import uuid
from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, List, Optional

import psycopg
from psycopg.rows import dict_row
import pyarrow as pa
import pyarrow.parquet as pq
from google.api_core.exceptions import NotFound
from google.cloud import bigquery

# ==========================================
# LOGGING & ENVIRONMENT CONFIGURATION
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("sync_to_bigquery")

BASE_DIR = Path(__file__).resolve().parent.parent.parent


def load_dotenv_file(env_path: Path) -> None:
    """Lightweight .env loader without external package dependencies."""
    if not env_path.exists():
        return
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            os.environ.setdefault(key.strip(), val.strip().strip("'\""))


load_dotenv_file(BASE_DIR / "infra/.env")


# ==========================================
# DECLARATIVE TABLE MANIFEST (14 TABLES)
# ==========================================
@dataclass(frozen=True)
class TableConfig:
    table_name: str
    pg_schema: str
    pk: str
    mode: str  # 'full' or 'incremental'
    bq_schema: List[bigquery.SchemaField]
    watermark_col: Optional[str] = None
    min_lookback_days: int = 5
    custom_incremental_sql: Optional[str] = None


TABLE_MANIFEST: Dict[str, TableConfig] = {
    # ------------------------------------------
    # 1. MASTER CATALOG / LOOKUP TABLES (6)
    # ------------------------------------------
    "time_slots": TableConfig(
        table_name="time_slots",
        pg_schema="master",
        pk="time_slot_id",
        mode="full",
        bq_schema=[
            bigquery.SchemaField("time_slot_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("day_of_week", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("slot_time", "TIME", mode="REQUIRED"),
            bigquery.SchemaField("max_capacity", "INT64", mode="REQUIRED"),
        ],
    ),
    "subjects": TableConfig(
        table_name="subjects",
        pg_schema="master",
        pk="subject_id",
        mode="full",
        bq_schema=[
            bigquery.SchemaField("subject_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("subject_name", "STRING", mode="REQUIRED"),
        ],
    ),
    "stages": TableConfig(
        table_name="stages",
        pg_schema="master",
        pk="stage_id",
        mode="full",
        bq_schema=[
            bigquery.SchemaField("stage_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("subject_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("stage_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("stage_order", "INT64", mode="REQUIRED"),
        ],
    ),
    "status": TableConfig(
        table_name="status",
        pg_schema="master",
        pk="status_id",
        mode="full",
        bq_schema=[
            bigquery.SchemaField("status_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("status_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
        ],
    ),
    "payment_methods": TableConfig(
        table_name="payment_methods",
        pg_schema="master",
        pk="payment_method_id",
        mode="full",
        bq_schema=[
            bigquery.SchemaField("payment_method_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("method_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("settlement_days", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("fee_fixed", "NUMERIC", mode="REQUIRED"),
            bigquery.SchemaField("fee_pct", "NUMERIC", mode="REQUIRED"),
        ],
    ),
    "cost_centers": TableConfig(
        table_name="cost_centers",
        pg_schema="master",
        pk="cost_center_id",
        mode="full",
        bq_schema=[
            bigquery.SchemaField("cost_center_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("cost_center_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("flow_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("cost_nature", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
        ],
    ),
    # ------------------------------------------
    # 2. MASTER CORE ENTITIES (3)
    # ------------------------------------------
    "employees": TableConfig(
        table_name="employees",
        pg_schema="master",
        pk="emp_id",
        mode="full",
        bq_schema=[
            bigquery.SchemaField("emp_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("emp_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("employee_type", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("teaches_m", "BOOL", mode="REQUIRED"),
            bigquery.SchemaField("teaches_p", "BOOL", mode="REQUIRED"),
            bigquery.SchemaField("teaches_i", "BOOL", mode="REQUIRED"),
            bigquery.SchemaField("teaches_j", "BOOL", mode="REQUIRED"),
            bigquery.SchemaField("phone1", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("phone2", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("email", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("salary", "NUMERIC", mode="REQUIRED"),
            bigquery.SchemaField("contract_start", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("contract_end", "DATE", mode="NULLABLE"),
        ],
    ),
    "customers": TableConfig(
        table_name="customers",
        pg_schema="master",
        pk="customer_id",
        mode="full",
        bq_schema=[
            bigquery.SchemaField("customer_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("cpf", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("customer_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("email", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("phone1", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("phone2", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("street", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("address_number", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("complement", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("district", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("zip_code", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("city", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("state", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("country", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("due_day", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("default_payment_method_id", "INT64", mode="REQUIRED"),
        ],
    ),
    "accounts": TableConfig(
        table_name="accounts",
        pg_schema="master",
        pk="account_id",
        mode="full",
        bq_schema=[
            bigquery.SchemaField("account_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("kumon_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("account_name", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("birth_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("gender", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("customer_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("subject_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("initial_stage_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("enroll_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("cancellation_date", "DATE", mode="NULLABLE"),
            bigquery.SchemaField("declared_churn_reason", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("modality", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("study_medium", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("time_slot_1", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("emp_1", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("time_slot_2", "INT64", mode="NULLABLE"),
            bigquery.SchemaField("emp_2", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("monthly_fee", "NUMERIC", mode="REQUIRED"),
        ],
    ),
    # ------------------------------------------
    # 3. TRANSACTIONAL TABLES (5)
    # ------------------------------------------
    "interactions": TableConfig(
        table_name="interactions",
        pg_schema="transactional",
        pk="interaction_id",
        mode="incremental",
        watermark_col="expected_date",
        min_lookback_days=5,
        bq_schema=[
            bigquery.SchemaField("interaction_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("account_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("expected_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("expected_time_slot_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("rescheduled_from_id", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("is_justified_absence", "BOOL", mode="REQUIRED"),
            bigquery.SchemaField("start_ts", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("end_ts", "TIMESTAMP", mode="NULLABLE"),
            bigquery.SchemaField("days_studied_since_last", "INT64", mode="NULLABLE"),
            bigquery.SchemaField("did_corrections", "BOOL", mode="NULLABLE"),
            bigquery.SchemaField("study_quality", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("behavior_tags", "STRING", mode="REPEATED"),
        ],
    ),
    "monthly_performance": TableConfig(
        table_name="monthly_performance",
        pg_schema="transactional",
        pk="performance_id",
        mode="incremental",
        watermark_col="reference_month",
        min_lookback_days=45,
        bq_schema=[
            bigquery.SchemaField("performance_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("account_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("reference_month", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("final_stage_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("final_lesson_number", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("sheets_completed", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("status_id", "STRING", mode="REQUIRED"),
        ],
    ),
    "tuition_invoices": TableConfig(
        table_name="tuition_invoices",
        pg_schema="transactional",
        pk="invoice_id",
        mode="incremental",
        watermark_col="competence_date",
        min_lookback_days=45,
        bq_schema=[
            bigquery.SchemaField("invoice_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("customer_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("competence_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("due_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("total_amount", "NUMERIC", mode="REQUIRED"),
        ],
    ),
    "tuition_invoice_items": TableConfig(
        table_name="tuition_invoice_items",
        pg_schema="transactional",
        pk="invoice_item_id",
        mode="full",
        bq_schema=[
            bigquery.SchemaField("invoice_item_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("invoice_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("account_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("amount", "NUMERIC", mode="REQUIRED"),
        ],
    ),
    "financial_transactions": TableConfig(
        table_name="financial_transactions",
        pg_schema="transactional",
        pk="transaction_id",
        mode="incremental",
        watermark_col="transaction_date",
        min_lookback_days=5,
        bq_schema=[
            bigquery.SchemaField("transaction_id", "STRING", mode="REQUIRED"),
            bigquery.SchemaField("cost_center_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("payment_method_id", "INT64", mode="REQUIRED"),
            bigquery.SchemaField("competence_date", "DATE", mode="NULLABLE"),
            bigquery.SchemaField("invoice_id", "STRING", mode="NULLABLE"),
            bigquery.SchemaField("transaction_date", "DATE", mode="REQUIRED"),
            bigquery.SchemaField("amount", "NUMERIC", mode="REQUIRED"),
            bigquery.SchemaField("description", "STRING", mode="NULLABLE"),
        ],
    ),
}


# ==========================================
# PYARROW SCHEMA & SERIALIZATION HELPERS
# ==========================================
def bq_field_to_arrow(field: bigquery.SchemaField) -> pa.Field:
    """Maps a BigQuery SchemaField to an explicit PyArrow Field."""
    type_map = {
        "STRING": pa.string(),
        "INT64": pa.int64(),
        "BOOL": pa.bool_(),
        "NUMERIC": pa.decimal128(38, 9),
        "DATE": pa.date32(),
        "TIME": pa.time64("us"),
        "TIMESTAMP": pa.timestamp("us", tz="UTC"),
    }
    base_type = type_map[field.field_type]
    if field.mode == "REPEATED":
        return pa.field(field.name, pa.list_(base_type), nullable=False)
    return pa.field(field.name, base_type, nullable=(field.mode != "REQUIRED"))


def build_arrow_schema(bq_schema: List[bigquery.SchemaField]) -> pa.Schema:
    """Constructs a complete PyArrow Schema matching the target BigQuery Schema."""
    return pa.schema([bq_field_to_arrow(f) for f in bq_schema])


def normalize_record(row: Dict[str, Any], bq_schema: List[bigquery.SchemaField]) -> Dict[str, Any]:
    """Normalizes Python objects from psycopg into strict PyArrow-compatible types."""
    normalized: Dict[str, Any] = {}
    for field in bq_schema:
        col = field.name
        val = row.get(col)

        if field.mode == "REPEATED":
            normalized[col] = [] if val is None else [str(item) for item in val]
            continue

        if val is None:
            normalized[col] = None
            continue

        if field.field_type == "STRING":
            normalized[col] = str(val) if isinstance(val, uuid.UUID) else str(val)
        elif field.field_type == "NUMERIC":
            normalized[col] = val if isinstance(val, Decimal) else Decimal(str(val))
        elif field.field_type == "INT64":
            normalized[col] = int(val)
        elif field.field_type == "BOOL":
            normalized[col] = bool(val)
        elif field.field_type == "TIME":
            normalized[col] = val if isinstance(val, dt_time) else val
        elif field.field_type == "TIMESTAMP":
            if isinstance(val, datetime):
                normalized[col] = (
                    val.astimezone(timezone.utc)
                    if val.tzinfo
                    else val.replace(tzinfo=timezone.utc)
                )
            else:
                normalized[col] = val
        else:
            normalized[col] = val

    return normalized


def rows_to_parquet_buffer(
    rows: List[Dict[str, Any]], bq_schema: List[bigquery.SchemaField]
) -> io.BytesIO:
    """Serializes normalized dictionary records into an in-memory Parquet buffer."""
    arrow_schema = build_arrow_schema(bq_schema)
    clean_rows = [normalize_record(r, bq_schema) for r in rows]
    arrow_table = pa.Table.from_pylist(clean_rows, schema=arrow_schema)

    buffer = io.BytesIO()
    pq.write_table(arrow_table, buffer, compression="SNAPPY")
    buffer.seek(0)
    return buffer


# ==========================================
# EXTRACTION & BIGQUERY SYNC ENGINE
# ==========================================
def get_reference_anchor_date(pg_conn: psycopg.Connection, cfg: TableConfig) -> date:
    """
    Finds the latest watermark date in the source table so incremental loads work
    seamlessly on both historical synthetic datasets and real-time operational data.
    """
    fq_table = f"{cfg.pg_schema}.{cfg.table_name}"
    with pg_conn.cursor() as cur:
        cur.execute(f"SELECT MAX({cfg.watermark_col}) FROM {fq_table};")
        max_d = cur.fetchone()[0]
    return max_d if isinstance(max_d, date) else date.today()


def extract_from_postgres(
    pg_conn: psycopg.Connection,
    cfg: TableConfig,
    full_extract: bool,
    lookback_days: int,
) -> List[Dict[str, Any]]:
    """Extracts records from PostgreSQL using full or incremental watermark filtering."""
    cols = ", ".join(f.name for f in cfg.bq_schema)
    fq_table = f"{cfg.pg_schema}.{cfg.table_name}"

    with pg_conn.cursor(row_factory=dict_row) as cur:
        if full_extract or cfg.mode == "full":
            sql = f"SELECT {cols} FROM {fq_table};"
            cur.execute(sql)
        else:
            eff_lookback = max(lookback_days, cfg.min_lookback_days)
            anchor_date = get_reference_anchor_date(pg_conn, cfg)
            cutoff_date = anchor_date - timedelta(days=eff_lookback)

            if cfg.custom_incremental_sql:
                cur.execute(cfg.custom_incremental_sql, (cutoff_date, cutoff_date))
            else:
                sql = f"SELECT {cols} FROM {fq_table} WHERE {cfg.watermark_col} >= %s;"
                cur.execute(sql, (cutoff_date,))

        return cur.fetchall()


def table_exists(bq_client: bigquery.Client, table_ref: str) -> bool:
    """Checks if a BigQuery table already exists."""
    try:
        bq_client.get_table(table_ref)
        return True
    except NotFound:
        return False


def sync_table_to_bigquery(
    pg_conn: psycopg.Connection,
    bq_client: bigquery.Client,
    project_id: str,
    dataset_id: str,
    cfg: TableConfig,
    full_refresh: bool,
    lookback_days: int,
) -> Dict[str, Any]:
    """Executes extraction, Parquet staging upload, MERGE/Replace, and cleanup."""
    t_start = time.perf_counter()
    target_table_id = f"{project_id}.{dataset_id}.{cfg.table_name}"
    staging_table_id = f"{project_id}.{dataset_id}._stg_{cfg.table_name}"

    # Check if target table exists in BigQuery; if not, force a full initial extraction
    target_present = table_exists(bq_client, target_table_id)
    force_full = full_refresh or (cfg.mode == "full") or (not target_present)

    planned_strategy = (
        "INITIAL_CREATE"
        if not target_present
        else ("FULL_REPLACE" if force_full else "INCREMENTAL_MERGE")
    )

    logger.info(
        f"[{cfg.pg_schema}.{cfg.table_name}] Extracting from PostgreSQL (strategy={planned_strategy})..."
    )
    rows = extract_from_postgres(pg_conn, cfg, force_full, lookback_days)
    row_count = len(rows)

    if row_count == 0:
        elapsed = time.perf_counter() - t_start
        logger.info(f"[{cfg.table_name}] 0 rows extracted. Skipping BigQuery load.")
        return {
            "table": cfg.table_name,
            "rows": 0,
            "strategy": "SKIPPED (0 ROWS)",
            "elapsed_sec": elapsed,
        }

    parquet_buffer = rows_to_parquet_buffer(rows, cfg.bq_schema)

    try:
        # 1. Load Parquet buffer into staging table
        job_config = bigquery.LoadJobConfig(
            source_format=bigquery.SourceFormat.PARQUET,
            schema=cfg.bq_schema,
            write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE,
        )
        logger.info(f"[{cfg.table_name}] Uploading {row_count:,} rows to staging ({staging_table_id})...")
        load_job = bq_client.load_table_from_file(
            parquet_buffer, staging_table_id, job_config=job_config
        )
        load_job.result()

        # 2. Apply Initial Create, Full Replace, or Incremental MERGE
        if not target_present or force_full:
            applied_strategy = "INITIAL_CREATE" if not target_present else "FULL_REPLACE"
            logger.info(f"[{cfg.table_name}] Applying {applied_strategy} on {target_table_id}...")
            copy_config = bigquery.CopyJobConfig(
                write_disposition=bigquery.WriteDisposition.WRITE_TRUNCATE
            )
            copy_job = bq_client.copy_table(
                staging_table_id, target_table_id, job_config=copy_config
            )
            copy_job.result()
        else:
            applied_strategy = "INCREMENTAL_MERGE"
            all_cols = [f.name for f in cfg.bq_schema]
            non_pk_cols = [c for c in all_cols if c != cfg.pk]

            update_clause = ", ".join(f"T.{c} = S.{c}" for c in non_pk_cols)
            insert_cols = ", ".join(all_cols)
            insert_vals = ", ".join(f"S.{c}" for c in all_cols)

            merge_sql = f"""
                MERGE `{target_table_id}` AS T
                USING `{staging_table_id}` AS S
                ON T.{cfg.pk} = S.{cfg.pk}
                WHEN MATCHED THEN
                    UPDATE SET {update_clause}
                WHEN NOT MATCHED THEN
                    INSERT ({insert_cols})
                    VALUES ({insert_vals})
            """
            logger.info(f"[{cfg.table_name}] Executing MERGE into {target_table_id}...")
            query_job = bq_client.query(merge_sql)
            query_job.result()

    finally:
        # 3. Always clean up staging table
        bq_client.delete_table(staging_table_id, not_found_ok=True)
        logger.info(f"[{cfg.table_name}] Cleaned up temporary staging table.")

    elapsed = time.perf_counter() - t_start
    logger.info(f"[{cfg.table_name}] Sync completed in {elapsed:.2f}s.")
    return {
        "table": cfg.table_name,
        "rows": row_count,
        "strategy": applied_strategy,
        "elapsed_sec": elapsed,
    }


# ==========================================
# CLI & MAIN ENTRYPOINT
# ==========================================
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replicate PostgreSQL tables to BigQuery using Staging + MERGE."
    )
    parser.add_argument(
        "--tables",
        nargs="+",
        choices=list(TABLE_MANIFEST.keys()),
        default=list(TABLE_MANIFEST.keys()),
        help="Specific table names to sync (default: all 14 tables in dependency order).",
    )
    parser.add_argument(
        "--full-refresh",
        action="store_true",
        help="Ignore incremental lookback windows and replace target tables with full history.",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=5,
        help="Number of lookback days for incremental extraction (default: 5).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    overall_start = time.perf_counter()

    pg_config = {
        "host": os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(os.environ.get("POSTGRES_PORT", 5432)),
        "dbname": os.environ.get("POSTGRES_DB", "kumon_db"),
        "user": os.environ.get("POSTGRES_USER", "postgres"),
        "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
    }

    gcp_project = os.environ.get("GCP_PROJECT_ID")
    bq_dataset = os.environ.get("BQ_DATASET_RAW", "raw_postgres")

    if not gcp_project:
        logger.error("Missing required environment variable: GCP_PROJECT_ID.")
        sys.exit(1)

    logger.info(
        f"Starting BigQuery replication (Project: {gcp_project}, Dataset: {bq_dataset})"
    )

    bq_client = bigquery.Client(project=gcp_project)
    summary: List[Dict[str, Any]] = []

    try:
        with psycopg.connect(**pg_config) as pg_conn:
            for tbl_name in args.tables:
                cfg = TABLE_MANIFEST[tbl_name]
                res = sync_table_to_bigquery(
                    pg_conn=pg_conn,
                    bq_client=bq_client,
                    project_id=gcp_project,
                    dataset_id=bq_dataset,
                    cfg=cfg,
                    full_refresh=args.full_refresh,
                    lookback_days=args.lookback_days,
                )
                summary.append(res)
    except Exception as exc:
        logger.exception(f"Replication pipeline aborted due to error: {exc}")
        sys.exit(1)

    total_elapsed = time.perf_counter() - overall_start

    # Print Execution Summary
    print("\n" + "=" * 72)
    print(f"{'BIGQUERY REPLICATION SUMMARY':^72}")
    print("=" * 72)
    print(f"{'Table Name':<26} | {'Rows Extracted':>14} | {'Strategy':<18} | {'Time (s)':>8}")
    print("-" * 72)
    for item in summary:
        print(
            f"{item['table']:<26} | {item['rows']:>14,} | {item['strategy']:<18} | {item['elapsed_sec']:>8.2f}"
        )
    print("-" * 72)
    print(f"Total Execution Time: {total_elapsed:.2f} seconds")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    main()