"""
Migration: Change comment column to LONGTEXT in npd_comments table
Run once: python fix_comment_column.py
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

    # Check current column type
    cur.execute("""
        SELECT COLUMN_TYPE FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME='npd_comments' AND COLUMN_NAME='comment'
    """, (DB_NAME,))
    row = cur.fetchone()
    print("Current type:", row[0] if row else 'not found')

    cur.execute("ALTER TABLE npd_comments MODIFY COLUMN comment LONGTEXT NOT NULL")
    conn.commit()
    print("comment column changed to LONGTEXT successfully.")

    cur.close()
    conn.close()

if __name__ == '__main__':
    run()
