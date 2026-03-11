"""Run once — changes documents_json column from TEXT to MEDIUMTEXT."""
import sys; sys.path.insert(0, '.')
from index import app
from models import db
from sqlalchemy import text

with app.app_context():
    with db.engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE employees MODIFY COLUMN documents_json MEDIUMTEXT"))
            conn.commit()
            print("✅ documents_json → MEDIUMTEXT done!")
        except Exception as ex:
            print(f"Error: {ex}")
    print("Restart Flask server.")
