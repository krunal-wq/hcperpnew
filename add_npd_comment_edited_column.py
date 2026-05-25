"""
Migration: Add `edited_at` column to npd_comments table (MySQL)

This column lets us show an "(edited)" indicator next to comments that have
been modified via the new Edit option on the NPD Discussion Board.

Run once:
    python add_npd_comment_edited_column.py
"""
import pymysql

# Same credentials pattern used by add_milestone_key_column.py
DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = 'admin'
DB_PASS = 'Krunal@2424123'
DB_NAME = 'erpai'


def run():
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset='utf8mb4',
    )
    cur = conn.cursor()

    # Check whether the column already exists
    cur.execute("""
        SELECT COUNT(*) FROM information_schema.COLUMNS
        WHERE TABLE_SCHEMA=%s AND TABLE_NAME='npd_comments' AND COLUMN_NAME='edited_at'
    """, (DB_NAME,))

    if cur.fetchone()[0]:
        print("Column 'edited_at' already exists in npd_comments. Nothing to do.")
    else:
        cur.execute("ALTER TABLE npd_comments ADD COLUMN edited_at DATETIME NULL")
        conn.commit()
        print("edited_at column added to npd_comments.")

    cur.close()
    conn.close()
    print("Migration complete.")


if __name__ == '__main__':
    run()
