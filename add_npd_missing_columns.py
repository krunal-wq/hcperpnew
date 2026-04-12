"""
Run this script ONCE to add missing columns to npd_projects table.
Usage: python add_npd_missing_columns.py

Install pymysql if needed: pip install pymysql
"""
import pymysql

# ── DB Config — apna update karo ──
DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = 'root'
DB_PASS = 'Krunal@2424'        # apna password
DB_NAME = 'erpdb' # apna DB name

COLUMNS = [
    ("started_at",             "DATETIME"),
    ("finished_at",            "DATETIME"),
    ("total_duration_seconds", "INT"),
    ("completed_at",           "DATETIME"),
    ("cancelled_at",           "DATETIME"),
    ("cancel_reason",          "TEXT"),
    ("last_connected",         "DATETIME"),
    ("delay_reason",           "TEXT"),
    ("last_delay_update",      "DATETIME"),
    ("advance_paid",           "BOOLEAN DEFAULT 0"),
    ("advance_amount",         "DECIMAL(10,2) DEFAULT 2000"),
    ("advance_receipt",        "VARCHAR(300)"),
    ("rd_param_defaults",      "TEXT"),
    ("npd_milestone_data",     "TEXT"),
]

def migrate():
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset='utf8mb4'
    )
    cur = conn.cursor()

    # Get existing columns
    cur.execute("SHOW COLUMNS FROM npd_projects")
    existing = {row[0] for row in cur.fetchall()}
    print(f"Existing columns: {len(existing)}")

    added = []
    skipped = []
    for col, col_type in COLUMNS:
        if col in existing:
            skipped.append(col)
            print(f"  Skip: {col} (already exists)")
        else:
            cur.execute(f"ALTER TABLE npd_projects ADD COLUMN {col} {col_type}")
            added.append(col)
            print(f"  Added: {col}")

    conn.commit()
    cur.close()
    conn.close()

    print(f"\nAdded: {len(added)} columns")
    print(f"Skipped: {len(skipped)} columns (already existed)")

if __name__ == '__main__':
    migrate()
