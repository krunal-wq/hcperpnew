"""
migrate_pm_type.py
──────────────────
materials table mein pm_material_type column add karo.

Run: python migrate_pm_type.py
"""
from index import app
from models import db
from sqlalchemy import text, inspect

with app.app_context():
    inspector = inspect(db.engine)
    existing_cols = [c['name'] for c in inspector.get_columns('materials')]

    if 'pm_material_type' not in existing_cols:
        try:
            db.session.execute(text("ALTER TABLE materials ADD COLUMN pm_material_type VARCHAR(10) DEFAULT ''"))
            db.session.commit()
            print("✅ pm_material_type column added!")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error: {e}")
    else:
        print("✔️  pm_material_type already exists")

    print("\n🎉 Done! Server restart karo.")
