"""Expand supplier_type column to VARCHAR(20) to support 'RM,PM'"""
from index import app
from models import db
from sqlalchemy import text
with app.app_context():
    try:
        db.session.execute(text("ALTER TABLE suppliers MODIFY COLUMN supplier_type VARCHAR(20) DEFAULT 'RM'"))
        db.session.commit()
        print("✅ supplier_type column expanded!")
    except Exception as e:
        db.session.rollback()
        print(f"Note: {e}")
    print("🎉 Done!")
