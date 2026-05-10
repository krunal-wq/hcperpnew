"""
add_image_column.py
───────────────────
materials table mein image_path column add karo.
Run: python add_image_column.py
"""
from index import app
from models import db
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text(
            "ALTER TABLE materials ADD COLUMN image_path VARCHAR(500) NULL"
        ))
        db.session.commit()
        print("✅ image_path column added to materials table!")
    except Exception as e:
        db.session.rollback()
        print(f"ℹ️  Note: {e}")
        print("   (Column might already exist — that's OK)")
    
    # Create upload directory
    import os
    os.makedirs('static/uploads/materials', exist_ok=True)
    print("✅ static/uploads/materials/ directory ready")
    print("\n🎉 Done! PM/FG items mein ab Product Image upload kar sakte hain.")
