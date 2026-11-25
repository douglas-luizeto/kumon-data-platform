"""
Database Ingestion Script for Kumon Unit Analytics
Loads generated master and transactional CSV files into PostgreSQL using pure psycopg
and the native COPY protocol, strictly respecting foreign key dependencies.
"""

import csv
import os
from pathlib import Path
import psycopg

# ==========================================
# PATHS & DATABASE CONFIGURATION
# ==========================================
BASE_DIR = Path(__file__).resolve().parent.parent.parent
DATA_DIR = BASE_DIR / "data"


def load_dotenv_file(env_path: Path):
    """Lightweight .env loader to avoid extra external dependencies."""
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

DB_CONFIG = {
    "host": os.environ.get("POSTGRES_HOST", "localhost"),
    "port": int(os.environ.get("POSTGRES_PORT", 5432)),
    "dbname": os.environ.get("POSTGRES_DB", "kumon_db"),
    "user": os.environ.get("POSTGRES_USER", "postgres"),
    "password": os.environ.get("POSTGRES_PASSWORD", "postgres"),
}

# Ordered strictly by Foreign Key dependency hierarchy
# Note: tuition_invoices must be loaded before tuition_invoice_items and financial_transactions
LOAD_MANIFEST = [
    ("master.employees", "employees.csv"),
    ("master.customers", "customers.csv"),
    ("master.accounts", "accounts.csv"),
    ("transactional.interactions", "interactions.csv"),
    ("transactional.monthly_performance", "monthly_performance.csv"),
    ("transactional.tuition_invoices", "tuition_invoices.csv"),
    ("transactional.tuition_invoice_items", "tuition_invoice_items.csv"),
    ("transactional.financial_transactions", "financial_transactions.csv"),
]


# ==========================================
# CORE INGESTION FUNCTIONS
# ==========================================
def truncate_target_tables(cur):
    """Clears target tables in reverse order to allow clean, idempotent reloads."""
    tables_list = ", ".join(table for table, _ in reversed(LOAD_MANIFEST))
    print("Truncating existing records in target tables...")
    cur.execute(f"TRUNCATE TABLE {tables_list} RESTART IDENTITY CASCADE;")


def copy_csv_to_table(cur, table_name: str, csv_path: Path):
    """Streams a CSV file directly into PostgreSQL via COPY FROM STDIN."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Missing required CSV file: {csv_path}")

    # Read header dynamically to guarantee column alignment with the CSV
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        columns = next(reader)

    col_names = ", ".join(columns)
    copy_sql = (
        f"COPY {table_name} ({col_names}) "
        f"FROM STDIN WITH (FORMAT CSV, HEADER TRUE, NULL '')"
    )

    with open(csv_path, "rb") as f:
        with cur.copy(copy_sql) as copy:
            while chunk := f.read(65536):
                copy.write(chunk)

    cur.execute(f"SELECT COUNT(*) FROM {table_name};")
    row_count = cur.fetchone()[0]
    print(f"[OK] {table_name:<38} <- {csv_path.name:<28} ({row_count:,} rows)")


def sync_sequences(cur):
    """Synchronizes serial sequences after explicit ID insertions."""
    cur.execute(
        """
        SELECT setval(
            pg_get_serial_sequence('transactional.monthly_performance', 'performance_id'),
            COALESCE(MAX(performance_id), 1)
        )
        FROM transactional.monthly_performance;
        """
    )


# ==========================================
# MAIN EXECUTION
# ==========================================
def main():
    print(
        f"Connecting to PostgreSQL at {DB_CONFIG['host']}:{DB_CONFIG['port']} "
        f"(DB: {DB_CONFIG['dbname']})..."
    )

    try:
        with psycopg.connect(**DB_CONFIG) as conn:
            with conn.cursor() as cur:
                truncate_target_tables(cur)

                print("\nStarting bulk CSV ingestion via COPY protocol...")
                for table_name, filename in LOAD_MANIFEST:
                    csv_path = DATA_DIR / filename
                    copy_csv_to_table(cur, table_name, csv_path)

                sync_sequences(cur)

            conn.commit()
            print("\n" + "=" * 65)
            print("DATABASE INGESTION COMPLETED SUCCESSFULLY!")
            print("=" * 65)

    except Exception as exc:
        print(f"\n[ERROR] Ingestion failed and transaction was rolled back:\n{exc}")
        raise


if __name__ == "__main__":
    main()