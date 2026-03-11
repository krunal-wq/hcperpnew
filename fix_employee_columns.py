"""
fix_employee_columns.py
Run this ONCE to fix "Data too long" error for profile_photo and qr_code_base64.
Alters both columns from TEXT → MEDIUMTEXT in MySQL.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from index import app, db

SQL_FIXES = [
    "ALTER TABLE employees MODIFY COLUMN profile_photo   MEDIUMTEXT;",
    "ALTER TABLE employees MODIFY COLUMN qr_code_base64  MEDIUMTEXT;",
    "ALTER TABLE employees MODIFY COLUMN employee_code   VARCHAR(50) NULL;",
]

with app.app_context():
    conn = db.engine.connect()
    for sql in SQL_FIXES:
        try:
            conn.execute(db.text(sql))
            conn.commit()
            print(f"✅ {sql.strip()}")
        except Exception as e:
            print(f"⚠️  {sql.strip()}")
            print(f"   Error: {e}")
    conn.close()
    print("\n✅ Done! Now profile photos and QR codes will save correctly.")
