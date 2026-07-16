"""
scripts/diff_schema.py

READ-ONLY schema diff helper.

Connects to the (shared, production) database in a strictly read-only,
autocommit session and compares `information_schema.columns` against this
app's SQLAlchemy model metadata (models.py + subscription_models.py), for
THIS APP'S TABLES ONLY.

This is diagnostic only:
  - It runs ONLY SELECTs against information_schema.
  - It never runs DDL and never writes anything.
  - It never touches other apps' tables (candidates/tenants/users plural,
    or anything prefixed bc_) — the comparison is scoped to the table names
    present in our own SQLAlchemy metadata.

Usage:
    PROD_DB_DSN="postgresql://user:pw@host/dbname" python scripts/diff_schema.py

SECURITY NOTE: the DSN (including its password) must be supplied via the
PROD_DB_DSN environment variable, never hardcoded here. This file is tracked
in git, so a literal credential here would be a permanent leak into repo
history. Do NOT commit a DSN/password into this file.
"""

import os
import sys

import psycopg2

from models import Base
import subscription_models  # noqa: F401  (registers subscription tables on Base.metadata)

PROD_DSN = os.environ.get("PROD_DB_DSN")


def get_app_tables():
    """Return {table_name: set(column_names)} from our SQLAlchemy metadata."""
    return {
        table_name: set(table.columns.keys())
        for table_name, table in Base.metadata.tables.items()
    }


def get_prod_columns(conn, table_names):
    """Return {table_name: set(column_names)} from prod information_schema,
    restricted to the given table names only."""
    result = {t: set() for t in table_names}
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND table_name = ANY(%s)
            """,
            (list(table_names),),
        )
        for table_name, column_name in cur.fetchall():
            result[table_name].add(column_name)
    return result


def main():
    if not PROD_DSN:
        print("ERROR: set PROD_DB_DSN to a read-only-capable Postgres DSN before running "
              "this script (never hardcode credentials in this tracked file).")
        sys.exit(2)

    app_tables = get_app_tables()
    table_names = sorted(app_tables.keys())

    print(f"Comparing {len(table_names)} app tables against prod (READ-ONLY): {table_names}\n")

    conn = psycopg2.connect(PROD_DSN)
    # Enforce read-only, autocommit: this connection must never write.
    conn.set_session(readonly=True, autocommit=True)

    try:
        prod_tables = get_prod_columns(conn, table_names)
    finally:
        conn.close()

    any_missing_from_model = False
    any_missing_from_prod = False

    for table_name in table_names:
        model_cols = app_tables[table_name]
        prod_cols = prod_tables.get(table_name, set())

        if not prod_cols:
            print(f"[{table_name}] NOT FOUND in prod (table does not exist there yet)")
            continue

        missing_from_model = sorted(prod_cols - model_cols)
        missing_from_prod = sorted(model_cols - prod_cols)

        if missing_from_model:
            any_missing_from_model = True
            print(f"[{table_name}] columns in PROD but MISSING from model: {missing_from_model}")
        if missing_from_prod:
            any_missing_from_prod = True
            print(f"[{table_name}] columns in MODEL but not yet in prod: {missing_from_prod}")
        if not missing_from_model and not missing_from_prod:
            print(f"[{table_name}] OK - columns match")

    print()
    if any_missing_from_model:
        print("RESULT: FAIL - prod has columns the model/baseline does not declare. "
              "A future autogenerate would try to DROP these. Add them to the model "
              "(nullable, additive) and regenerate the baseline.")
        sys.exit(1)
    else:
        print("RESULT: PASS - no prod column is missing from the model metadata. "
              f"({'Some model-only columns not yet in prod (harmless; additive migration will add them).' if any_missing_from_prod else 'Full parity.'})")


if __name__ == "__main__":
    main()
