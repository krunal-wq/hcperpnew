"""
Run this script ONCE to add middle_name column to employees table.
Usage:  python add_middle_name_column.py
"""
import sqlite3, os

# Sabse pehle current directory mein dhundega, phir subdirs mein
def find_db():
    possible_paths = [
        os.path.join(os.path.dirname(__file__), 'erp.db'),
        os.path.join(os.path.dirname(__file__), 'instance', 'erp.db'),
        os.path.join(os.path.dirname(__file__), 'database', 'erp.db'),
        os.path.join(os.path.dirname(__file__), 'db', 'erp.db'),
    ]
    for path in possible_paths:
        if os.path.exists(path):
            return path
    return None

def migrate():
    db_path = find_db()

    if not db_path:
        print("❌ erp.db file nahi mili!")
        print("👉 Manually DB path batao — script mein DB_PATH variable set karo.")
        print("   Example: DB_PATH = r'D:\\hcperpnew\\instance\\erp.db'")
        return

    print(f"✅ DB found: {db_path}")
    conn = sqlite3.connect(db_path)
    cur  = conn.cursor()

    # All tables list karo
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]
    print(f"📋 Tables in DB: {tables}")

    if 'employees' not in tables:
        print("❌ 'employees' table nahi mili!")
        print(f"👉 Available tables: {tables}")
        conn.close()
        return

    # Check if column already exists
    cur.execute("PRAGMA table_info(employees)")
    cols = [row[1] for row in cur.fetchall()]

    if 'middle_name' not in cols:
        cur.execute("ALTER TABLE employees ADD COLUMN middle_name VARCHAR(100)")
        conn.commit()
        print("✅ middle_name column added successfully.")
    else:
        print("ℹ️  middle_name column already exists — nothing to do.")

    conn.close()

if __name__ == '__main__':
    migrate()
