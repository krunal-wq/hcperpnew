"""
add_prev_salary_column.py
─────────────────────────────────
Run this ONCE to add the `prev_salary_per_month` column to the `employees`
table. Yeh column form mein "Previous Salary (₹/month)" field ke through
add hua hai (Education / Previous Employment tab).

Usage (production server pe):
    cd /var/www/hcperp
    python3 add_prev_salary_column.py

Safe to re-run — INFORMATION_SCHEMA check karta hai pehle ki column
already exist toh nahi karta.
"""

import sys
from index import app
from models import db


# ── Column definitions ────────────────────────────────────────────────
# (column_name, MySQL DDL type)
NEW_COLUMNS = [
    ('prev_salary_per_month', 'DECIMAL(12,2) NULL'),
]


def column_exists(col_name):
    """Check if column exists using INFORMATION_SCHEMA (works on MySQL)."""
    sql = db.text("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME   = 'employees'
          AND COLUMN_NAME  = :col
    """)
    result = db.session.execute(sql, {'col': col_name}).scalar()
    return (result or 0) > 0


def migrate():
    print("=" * 60)
    print("Previous Salary Column Migration")
    print("=" * 60)

    with app.app_context():
        # Sanity check — kya `employees` table exists?
        try:
            db.session.execute(db.text("SELECT 1 FROM employees LIMIT 1"))
        except Exception as e:
            print(f"❌ 'employees' table query failed: {e}")
            print("   Check DB connection / schema name.")
            sys.exit(1)

        added, skipped, failed = 0, 0, 0
        for col_name, ddl_type in NEW_COLUMNS:
            try:
                if column_exists(col_name):
                    print(f"  [SKIP]  {col_name:32s} already exists")
                    skipped += 1
                    continue

                sql = f"ALTER TABLE employees ADD COLUMN {col_name} {ddl_type}"
                db.session.execute(db.text(sql))
                db.session.commit()
                print(f"  [ADD]   {col_name:32s} {ddl_type}")
                added += 1
            except Exception as e:
                db.session.rollback()
                print(f"  [FAIL]  {col_name:32s} {e}")
                failed += 1

        print("=" * 60)
        print(f"  Added:   {added}")
        print(f"  Skipped: {skipped} (already existed)")
        print(f"  Failed:  {failed}")
        print("=" * 60)

        if failed:
            print("\n⚠  Column add nahi ho paaya — error message check karo.")
            sys.exit(2)
        else:
            print("\n✓ Migration complete. Ab Flask service restart karo:")
            print("    systemctl restart hcperp")


if __name__ == '__main__':
    migrate()
