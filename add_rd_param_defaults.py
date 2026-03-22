"""
Migration: Add rd_param_defaults column to npd_projects table
Run once: python add_rd_param_defaults.py
"""
import sqlite3
import os

# Adjust this path to your actual database file
DB_PATH = os.environ.get('DB_PATH', 'app.db')

def run():
    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    # Check if column already exists
    cur.execute("PRAGMA table_info(npd_projects)")
    cols = [row[1] for row in cur.fetchall()]

    if 'rd_param_defaults' in cols:
        print("Column already exists — nothing to do.")
    else:
        cur.execute("ALTER TABLE npd_projects ADD COLUMN rd_param_defaults TEXT")
        conn.commit()
        print("✅ Column rd_param_defaults added to npd_projects.")

    conn.close()

if __name__ == '__main__':
    run()
