"""
add_wop_to_attendance_status.py
────────────────────────────────
Run this ONCE to extend `attendance.status` ENUM and add 'WOP'
(Week Off Present — employee ne weekly off pe punch kiya hai).

Usage:  python add_wop_to_attendance_status.py
Pre-req: pip install pymysql
"""
import pymysql

# ── DB Config — apna update karo agar zarurat ho ──
DB_HOST = 'localhost'
DB_PORT = 3306
DB_USER = 'root'
DB_PASS = 'Krunal@2424'
DB_NAME = 'erpdb'


def migrate():
    conn = pymysql.connect(
        host=DB_HOST, port=DB_PORT, user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset='utf8mb4'
    )
    cur = conn.cursor()

    # Check current ENUM definition
    cur.execute("""
        SELECT COLUMN_TYPE FROM information_schema.COLUMNS
         WHERE TABLE_SCHEMA = %s AND TABLE_NAME = 'attendance'
           AND COLUMN_NAME = 'status'
    """, (DB_NAME,))
    row = cur.fetchone()
    if not row:
        print("❌ attendance.status column not found")
        return

    current = row[0]
    print(f"Current ENUM: {current}")

    if "'WOP'" in current:
        print("⏭  WOP already in ENUM. Nothing to do.")
        cur.close(); conn.close()
        return

    sql = """
        ALTER TABLE attendance
        MODIFY COLUMN status
        ENUM('Present','Absent','Half Day','Holiday','MIS-PUNCH','WOP')
        NOT NULL DEFAULT 'Present'
    """
    cur.execute(sql)
    conn.commit()
    print("✅ WOP added to attendance.status ENUM")
    cur.close(); conn.close()


if __name__ == '__main__':
    migrate()
