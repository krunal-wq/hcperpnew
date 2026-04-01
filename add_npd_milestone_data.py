"""
Migration: Add npd_milestone_data column to npd_projects table (MySQL)
Run once: python add_npd_milestone_data.py
"""
import pymysql

# DB Config
DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = 'root'
DB_PASS = 'Krunal@2424'
DB_NAME = 'erpdb'

def run():
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset='utf8mb4'
    )
    cur = conn.cursor()

    cur.execute("""
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA = %s
          AND TABLE_NAME   = 'npd_projects'
          AND COLUMN_NAME  = 'npd_milestone_data'
    """, (DB_NAME,))
    exists = cur.fetchone()[0]

    if exists:
        print("Column already exists — nothing to do.")
    else:
        cur.execute("ALTER TABLE npd_projects ADD COLUMN npd_milestone_data TEXT NULL")
        conn.commit()
        print("Column npd_milestone_data added successfully.")

    cur.close()
    conn.close()

if __name__ == '__main__':
    run()
