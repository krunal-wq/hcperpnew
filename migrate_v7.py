"""
migrate_v7.py — Create new tables: employees, contractors, modules,
                role_permissions, user_grid_configs
Run once after setup.
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from index import app, db
from permissions import seed_permissions

with app.app_context():
    print("Creating all tables...")
    db.create_all()
    print("Seeding permissions...")
    seed_permissions()
    print("✅ Migration complete!")
