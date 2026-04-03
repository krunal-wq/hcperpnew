"""
Fix Employee Types + Locations
Run: python fix_emp_types.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app, db
from sqlalchemy import text

KEEP_TYPES = ['HCP OFFICE', 'HCP FACTORY STAFF', 'HCP WORKER', 'HCP CONTRACTOR', 'WFH']
KEEP_LOCS  = ['Office', 'Factory']

with app.app_context():
    with db.engine.connect() as conn:

        # ── Employee Types ──
        print("\n── Employee Types ──")
        # Delete all then re-insert in order
        conn.execute(text("DELETE FROM employee_type_master"))
        for i, name in enumerate(KEEP_TYPES):
            conn.execute(text(
                "INSERT INTO employee_type_master (name, sort_order, is_active) VALUES (:n, :s, 1)"
            ), {'n': name, 's': i})
            print(f"  ✅ {name}")

        # ── Locations ──
        print("\n── Locations ──")
        conn.execute(text("DELETE FROM employee_location_master"))
        for i, name in enumerate(KEEP_LOCS):
            conn.execute(text(
                "INSERT INTO employee_location_master (name, sort_order, is_active) VALUES (:n, :s, 1)"
            ), {'n': name, 's': i})
            print(f"  ✅ {name}")

        conn.commit()

    print("\n✅ Done! Server restart karo.\n")
