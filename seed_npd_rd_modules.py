"""
Run this ONCE to seed npd, rd, npd_projects, npd_masters modules into DB.
Usage: python seed_npd_rd_modules.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from index import app, db
from models import Module, RolePermission
from permissions import MODULE_SUB_PERMS

MODULES_TO_SEED = [
    {'name': 'rd',           'label': 'R&D',          'icon': '🔬', 'url_prefix': '/rd',               'sort_order': 13, 'parent': None},
    {'name': 'npd',          'label': 'NPD',          'icon': '🧪', 'url_prefix': '/npd',              'sort_order': 14, 'parent': None},
    {'name': 'npd_projects', 'label': 'NPD Projects', 'icon': '📋', 'url_prefix': '/npd/npd-projects', 'sort_order': 15, 'parent': 'npd'},
    {'name': 'npd_masters',  'label': 'NPD Masters',  'icon': '⚙️', 'url_prefix': '/npd/masters',      'sort_order': 16, 'parent': 'npd'},
]

with app.app_context():
    created = []
    for m in MODULES_TO_SEED:
        existing = Module.query.filter_by(name=m['name']).first()
        if existing:
            print(f"  ✓ Already exists: {m['name']}")
            continue
        parent_id = None
        if m['parent']:
            parent_mod = Module.query.filter_by(name=m['parent']).first()
            if parent_mod:
                parent_id = parent_mod.id
        mod = Module(
            name=m['name'], label=m['label'], icon=m['icon'],
            url_prefix=m['url_prefix'], sort_order=m['sort_order'],
            parent_id=parent_id, is_active=True
        )
        db.session.add(mod)
        db.session.flush()
        print(f"  ✅ Created: {m['name']} (id={mod.id})")
        created.append(mod)

    db.session.commit()
    print(f"\nDone — {len(created)} module(s) created.")
    print("\nModules in DB:")
    for m in Module.query.order_by(Module.sort_order).all():
        print(f"  [{m.id}] {m.name} — {m.label}")
