"""
migrate_audit.py
Run once: adds audit_logs table + missing columns to all tables.
Usage: python migrate_audit.py
"""
from index import app
from models import db
from sqlalchemy import text

def run():
    with app.app_context():
        # 1. Create audit_logs table
        db.create_all()
        print("✅ audit_logs table created (if not exists)")

        conn = db.engine.connect()

        def add_col(table, col, coldef):
            try:
                conn.execute(text(f"ALTER TABLE `{table}` ADD COLUMN `{col}` {coldef}"))
                conn.commit()
                print(f"  ✅ {table}.{col} added")
            except Exception as e:
                if 'Duplicate column' in str(e) or 'already exists' in str(e).lower():
                    print(f"  ℹ️  {table}.{col} already exists")
                else:
                    print(f"  ⚠️  {table}.{col}: {e}")

        # leads
        add_col('leads', 'modified_by', 'INT NULL')

        # client_masters
        add_col('client_masters', 'modified_by', 'INT NULL')

        # employees
        add_col('employees', 'modified_by', 'INT NULL')

        # users
        add_col('users', 'created_by',  'INT NULL')
        add_col('users', 'modified_by', 'INT NULL')
        add_col('users', 'updated_at',  'DATETIME NULL')

        # masters
        for tbl in ['lead_statuses', 'lead_sources', 'lead_categories', 'product_ranges']:
            add_col(tbl, 'created_by',  'INT NULL')
            add_col(tbl, 'modified_by', 'INT NULL')
            add_col(tbl, 'modified_at', 'DATETIME NULL')

        conn.close()
        print("\n✅ Migration complete!")

if __name__ == '__main__':
    run()
