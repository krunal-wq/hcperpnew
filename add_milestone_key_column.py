"""
Migration: Add milestone_key column to npd_comments table (MySQL)
Run once: python add_milestone_key_column.py
"""
import pymysql

DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = 'root'
DB_PASS = 'Krunal@2424'
DB_NAME = 'erpdb'

def run():
    conn = pymysql.connect(host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS, database=DB_NAME, charset='utf8mb4')
    cur = conn.cursor()
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME='npd_comments' AND COLUMN_NAME='milestone_key'
    """, (DB_NAME,))
    if cur.fetchone()[0]:
        print("Column already exists.")
    else:
        cur.execute("ALTER TABLE npd_comments ADD COLUMN milestone_key VARCHAR(20) NULL")
        conn.commit()
        print("milestone_key column added to npd_comments.")
    cur.close()
    conn.close()

if __name__ == '__main__':
    run()
