"""Run once to add hierarchy & approval tables"""
import sys; sys.path.insert(0,'.')
from index import app
from models import db
from sqlalchemy import text

with app.app_context():
    with db.engine.connect() as conn:
        sqls = [
            "ALTER TABLE employees ADD COLUMN reports_to INT NULL",
            "ALTER TABLE employees ADD FOREIGN KEY (reports_to) REFERENCES employees(id) ON DELETE SET NULL",
        ]
        for sql in sqls:
            try:
                conn.execute(text(sql)); conn.commit()
                print(f"✅ {sql[:60]}...")
            except Exception as ex:
                print(f"— {str(ex)[:80]}")

        # Create new tables
        db.create_all()
        print("✅ approval_requests + approval_levels tables created")

    print("\nDone! Restart Flask.")
