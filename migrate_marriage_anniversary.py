"""Run once — adds marriage_anniversary column to employees table."""
import sys; sys.path.insert(0,'.')
from index import app
from models import db
from sqlalchemy import text

with app.app_context():
    with db.engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE employees ADD COLUMN marriage_anniversary DATE"))
            conn.commit()
            print("✅ marriage_anniversary column added")
        except Exception as ex:
            print(f"— {str(ex)[:80]}")
    print("Done! Restart Flask.")
