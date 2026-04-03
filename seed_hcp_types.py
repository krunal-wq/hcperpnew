"""
Quick seed: HCP Employee Types + Locations
Run: python seed_hcp_types.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app, db
from models.employee import EmployeeTypeMaster, EmployeeLocationMaster

HCP_EMP_TYPES = [
    'HCP OFFICE',
    'HCP FACTORY STAFF',
    'HCP WORKER',
    'HCP CONTRACTOR',
    'WFH',
]

HCP_LOCATIONS = [
    'Factory',
    'Office',
]

with app.app_context():
    print("\n── Employee Types ──")
    for i, name in enumerate(HCP_EMP_TYPES):
        if not EmployeeTypeMaster.query.filter_by(name=name).first():
            db.session.add(EmployeeTypeMaster(name=name, sort_order=i, is_active=True))
            print(f"  Added: {name}")
        else:
            print(f"  Exists: {name}")

    print("\n── Locations ──")
    for i, name in enumerate(HCP_LOCATIONS):
        if not EmployeeLocationMaster.query.filter_by(name=name).first():
            db.session.add(EmployeeLocationMaster(name=name, sort_order=i, is_active=True))
            print(f"  Added: {name}")
        else:
            print(f"  Exists: {name}")

    db.session.commit()
    print("\nDone!")
