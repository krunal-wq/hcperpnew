"""Run this script once to create the wish_logs table."""
import sys
sys.path.insert(0, '/path/to/your/erp')  # change to your project path

from index import app, db
from models.employee import WishLog

with app.app_context():
    db.create_all()
    print("✅ wish_logs table created")
