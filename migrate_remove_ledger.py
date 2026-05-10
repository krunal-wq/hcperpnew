"""
migrate_remove_ledger.py
─────────────────────────
suppliers table se ledger_name column remove karo.
Run: python migrate_remove_ledger.py
"""
from index import app
from models import db
from sqlalchemy import text, inspect

with app.app_context():
    inspector = inspect(db.engine)
    cols = [c['name'] for c in inspector.get_columns('suppliers')]
    if 'ledger_name' in cols:
        try:
            db.session.execute(text("ALTER TABLE suppliers DROP COLUMN ledger_name"))
            db.session.commit()
            print("✅ ledger_name column removed!")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: {e}")
    else:
        print("✔️  ledger_name already removed")
    print("\n🎉 Done!")
