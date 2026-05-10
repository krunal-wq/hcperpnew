"""
migrate_image_to_base64.py
──────────────────────────
Materials table mein image_data (LONGTEXT) column add karo.
Agar purana image_path column hai to usse image_data mein migrate karo.

Run: python migrate_image_to_base64.py
"""
from index import app
from models import db
from sqlalchemy import text, inspect

with app.app_context():
    inspector = inspect(db.engine)
    existing_cols = [c['name'] for c in inspector.get_columns('materials')]
    print(f"Existing columns: {[c for c in existing_cols if 'image' in c]}")

    # Step 1: Add image_data LONGTEXT column
    if 'image_data' not in existing_cols:
        try:
            db.session.execute(text("ALTER TABLE materials ADD COLUMN image_data LONGTEXT NULL"))
            db.session.commit()
            print("✅ image_data (LONGTEXT) column added")
        except Exception as e:
            db.session.rollback()
            print(f"⚠️  image_data add error: {e}")
    else:
        print("✔️  image_data column already exists")

    # Step 2: If old image_path exists, migrate data
    if 'image_path' in existing_cols:
        try:
            db.session.execute(text("""
                UPDATE materials 
                SET image_data = image_path 
                WHERE image_path IS NOT NULL 
                  AND image_path != ''
                  AND (image_data IS NULL OR image_data = '')
            """))
            db.session.commit()
            print("✅ Old image_path data migrated to image_data")
        except Exception as e:
            db.session.rollback()
            print(f"⚠️  Migration error: {e}")

        # Step 3: Drop old image_path column
        try:
            db.session.execute(text("ALTER TABLE materials DROP COLUMN image_path"))
            db.session.commit()
            print("✅ Old image_path column removed")
        except Exception as e:
            db.session.rollback()
            print(f"ℹ️  image_path drop: {e}")

    # Step 4: Add other missing columns
    other_cols = {
        'code':        "VARCHAR(100) DEFAULT ''",
        'inci_name':   "VARCHAR(300) DEFAULT ''",
        'brand':       "VARCHAR(200) DEFAULT ''",
        'category':    "VARCHAR(200) DEFAULT ''",
        'per_box_qty': "INT DEFAULT 0",
    }
    inspector2 = inspect(db.engine)
    existing_cols2 = [c['name'] for c in inspector2.get_columns('materials')]
    for col, col_def in other_cols.items():
        if col not in existing_cols2:
            try:
                db.session.execute(text(f"ALTER TABLE materials ADD COLUMN {col} {col_def}"))
                db.session.commit()
                print(f"✅ Added: {col}")
            except Exception as e:
                db.session.rollback()
                print(f"✔️  {col}: already exists or error - {e}")
        else:
            print(f"✔️  {col}: already exists")

    # Final check
    inspector3 = inspect(db.engine)
    final_cols = [c['name'] for c in inspector3.get_columns('materials')]
    print(f"\n📋 Final image columns: {[c for c in final_cols if 'image' in c]}")
    print("\n🎉 Migration complete! Server restart karo.")
