"""
Run this script ONCE to add invoice_file column to sample_orders table.
Usage:  python add_invoice_column.py
"""
import sqlite3, os

DB_PATH = os.path.join(os.path.dirname(__file__), 'erp.db')   # adjust path if needed

def migrate():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()
    # Check if column already exists
    cur.execute("PRAGMA table_info(sample_orders)")
    cols = [row[1] for row in cur.fetchall()]
    if 'invoice_file' not in cols:
        cur.execute("ALTER TABLE sample_orders ADD COLUMN invoice_file VARCHAR(300)")
        conn.commit()
        print("✅ invoice_file column added successfully.")
    else:
        print("ℹ️  invoice_file column already exists — nothing to do.")
    conn.close()

if __name__ == '__main__':
    migrate()
