"""
add_missing_material_columns.py
────────────────────────────────
Materials table mein missing columns add karo:
code, inci_name, brand, category, per_box_qty, image_path

Run: python add_missing_material_columns.py
"""
from index import app
from models import db
from sqlalchemy import text

COLUMNS = [
    ("code",        "VARCHAR(100)  DEFAULT ''"),
    ("inci_name",   "VARCHAR(300)  DEFAULT ''"),
    ("brand",       "VARCHAR(200)  DEFAULT ''"),
    ("category",    "VARCHAR(200)  DEFAULT ''"),
    ("per_box_qty", "INT           DEFAULT 0"),
    ("image_path",  "VARCHAR(500)  NULL"),
]

with app.app_context():
    for col, col_def in COLUMNS:
        try:
            db.session.execute(text(f"ALTER TABLE materials ADD COLUMN {col} {col_def}"))
            db.session.commit()
            print(f"  ✅ Added: {col}")
        except Exception as e:
            db.session.rollback()
            if 'Duplicate' in str(e) or 'already exists' in str(e).lower():
                print(f"  ✔️  Already exists: {col}")
            else:
                print(f"  ⚠️  {col}: {e}")

    import os
    os.makedirs('static/uploads/materials', exist_ok=True)
    print("\n🎉 Done! Ab Edit mode mein Code, Brand, Category, Image sab aayega.")
