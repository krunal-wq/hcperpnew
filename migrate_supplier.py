"""
migrate_supplier.py
────────────────────
Suppliers table create karo.
Run: python migrate_supplier.py
"""
from index import app
from models import db

with app.app_context():
    db.create_all()
    print("✅ suppliers table created!")
    print("🎉 Done! Server restart karo.")
