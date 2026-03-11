"""Run this once to add address columns to employees table"""
import sys
sys.path.insert(0, '.')
from index import app
from models import db
from sqlalchemy import text

cols = [
    "ALTER TABLE employees ADD COLUMN address TEXT",
    "ALTER TABLE employees ADD COLUMN city VARCHAR(100)",
    "ALTER TABLE employees ADD COLUMN state VARCHAR(100)",
    "ALTER TABLE employees ADD COLUMN country VARCHAR(100) DEFAULT 'India'",
    "ALTER TABLE employees ADD COLUMN zip_code VARCHAR(20)",
]

with app.app_context():
    with db.engine.connect() as conn:
        for sql in cols:
            col = sql.split('COLUMN ')[1].split(' ')[0]
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"✅ Added: {col}")
            except Exception as ex:
                if '1060' in str(ex) or 'Duplicate column' in str(ex):
                    print(f"— Already exists: {col}")
                else:
                    print(f"❌ {col}: {ex}")

print("\nDone! Restart Flask server.")
