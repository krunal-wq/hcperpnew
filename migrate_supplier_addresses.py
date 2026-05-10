"""
migrate_supplier_addresses.py
─────────────────────────────
suppliers table mein addresses JSON column add karo.
Run: python migrate_supplier_addresses.py
"""
from index import app
from models import db
from sqlalchemy import text, inspect

with app.app_context():
    inspector = inspect(db.engine)
    try:
        cols = [c['name'] for c in inspector.get_columns('suppliers')]
        if 'addresses' not in cols:
            db.session.execute(text("ALTER TABLE suppliers ADD COLUMN addresses TEXT NULL"))
            db.session.commit()
            print("✅ addresses column added!")
        else:
            print("✔️  addresses already exists")
    except Exception as e:
        db.session.rollback()
        print(f"Error: {e}")
    print("\n🎉 Done!")
