"""
add_packing_filling_columns.py
──────────────────────────────
Run this script ONCE to add new columns to the npd_packing_materials table:
  - filling_image   VARCHAR(300) DEFAULT ''        → Filling image upload
  - coa_file        VARCHAR(300) DEFAULT ''        → COA file upload
  - filling_status  VARCHAR(30)  DEFAULT 'pending' → pending/in_process/hold/cancel/done

Usage:  python add_packing_filling_columns.py

Pre-req:  pip install pymysql
"""
import pymysql

# ── DB Config — apna update karo agar zarurat ho ──
DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = 'root'
DB_PASS = 'Krunal@2424'
DB_NAME = 'erpdb'

TABLE = 'npd_packing_materials'

COLUMNS = [
    ("filling_image",  "VARCHAR(300) NOT NULL DEFAULT ''"),
    ("coa_file",       "VARCHAR(300) NOT NULL DEFAULT ''"),
    ("filling_status", "VARCHAR(30)  NOT NULL DEFAULT 'pending'"),
]


def migrate():
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset='utf8mb4'
    )
    cur = conn.cursor()

    # Confirm table exists
    cur.execute("SHOW TABLES LIKE %s", (TABLE,))
    if not cur.fetchone():
        print(f"❌ Table '{TABLE}' not found in DB '{DB_NAME}'. Aborting.")
        cur.close(); conn.close()
        return

    # Existing columns
    cur.execute(f"SHOW COLUMNS FROM {TABLE}")
    existing = {row[0] for row in cur.fetchall()}
    print(f"📋 Existing columns in {TABLE}: {len(existing)}")

    added, skipped = [], []
    for col, col_type in COLUMNS:
        if col in existing:
            skipped.append(col)
            print(f"  ⏭  Skip: {col} (already exists)")
        else:
            sql = f"ALTER TABLE {TABLE} ADD COLUMN {col} {col_type}"
            try:
                cur.execute(sql)
                added.append(col)
                print(f"  ✅ Added: {col}")
            except Exception as ex:
                print(f"  ❌ Failed: {col} — {ex}")

    # Backfill — purani rows ke liye filling_status ko 'pending' karo
    if 'filling_status' in [c[0] for c in COLUMNS]:
        try:
            cur.execute(f"""
                UPDATE {TABLE}
                   SET filling_status = 'pending'
                 WHERE filling_status IS NULL OR filling_status = ''
            """)
            print(f"  🔄 Backfilled filling_status='pending' for {cur.rowcount} row(s)")
        except Exception as ex:
            print(f"  ⚠️  Backfill skipped: {ex}")

    conn.commit()
    cur.close()
    conn.close()

    print()
    print(f"✅ Done. Added: {len(added)}, Skipped: {len(skipped)}")
    print()
    print("Next steps:")
    print("  1. Replace models/npd.py, npd_routes.py, templates/npd/project_view.html")
    print("  2. Restart Flask app (clear pycache if needed)")
    print("  3. Open any NPD project → Milestones → Packing Material to verify")


if __name__ == '__main__':
    migrate()
