"""
fix_duplicate_modules.py
========================
Database me duplicate Module entries clean karta hai.
migrate.py me 'leads','clients','hr' tha
permissions.py me 'crm_leads','crm_clients' tha
Dono seed hone se duplicates ban gaye.

Run: python fix_duplicate_modules.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app
from models.base import db
from models.permission import Module, RolePermission, UserPermission

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; E = "\033[0m"
def ok(m):   print(f"  {G}✅ {m}{E}")
def warn(m): print(f"  {Y}⚠️  {m}{E}")

# Old name → New canonical name mapping
# migrate.py ke purane names → permissions.py ke sahi names
RENAME_MAP = {
    'leads'   : 'crm_leads',
    'clients' : 'crm_clients',
    'users'   : 'user_mgmt',
    'admin'   : 'user_mgmt',
    'audit'   : 'audit_logs',
}

# Canonical module definitions (ek hi jagah)
CANONICAL_MODULES = [
    # (name,            label,           icon, url_prefix,              parent_name,    sort)
    ('dashboard',       'Dashboard',     '🏠', '/',                     None,           1),
    ('crm',             'CRM',           '📊', '/crm',                  None,           2),
    ('crm_leads',       'Leads',         '📋', '/crm/leads',            'crm',          3),
    ('crm_clients',     'Clients',       '👥', '/crm/clients',          'crm',          4),
    ('hr',              'HR',            '👔', '/hr',                   None,           5),
    ('hr_employees',    'Employees',     '🪪', '/hr/employees',         'hr',           6),
    ('hr_contractors',  'Contractors',   '🤝', '/hr/contractors',       'hr',           7),
    ('npd',             'NPD',           '🔬', '/npd',                  None,           8),
    ('rd',              'R&D',           '🧪', '/rd',                   None,           9),
    ('masters',         'Masters',       '⚙️', '/masters',              None,           10),
    ('approvals',       'Approvals',     '✅', '/approvals',            None,           11),
    ('user_mgmt',       'Users',         '👤', '/admin/users',          None,           12),
    ('audit_logs',      'Audit Logs',    '🔍', '/admin/audit-logs',     None,           13),
]

with app.app_context():
    print("\n" + "="*55)
    print("  Duplicate Module Fix")
    print("="*55)

    # ── Step 1: Rename old modules to canonical names ──────────
    print("\n  Step 1: Old modules rename kar raha hai...")
    for old_name, new_name in RENAME_MAP.items():
        old_mod = Module.query.filter_by(name=old_name).first()
        new_mod = Module.query.filter_by(name=new_name).first()

        if not old_mod:
            continue  # Already gone

        if new_mod:
            # Both exist — migrate permissions from old to new, then delete old
            warn(f"Duplicate: '{old_name}' aur '{new_name}' dono hain — merge kar raha hai...")

            # Move RolePermissions
            for rp in RolePermission.query.filter_by(module_id=old_mod.id).all():
                exists = RolePermission.query.filter_by(role=rp.role, module_id=new_mod.id).first()
                if not exists:
                    rp.module_id = new_mod.id
                else:
                    db.session.delete(rp)

            # Move UserPermissions
            for up in UserPermission.query.filter_by(module_id=old_mod.id).all():
                exists = UserPermission.query.filter_by(user_id=up.user_id, module_id=new_mod.id).first()
                if not exists:
                    up.module_id = new_mod.id
                else:
                    db.session.delete(up)

            # Update child modules parent_id
            for child in Module.query.filter_by(parent_id=old_mod.id).all():
                child.parent_id = new_mod.id

            db.session.delete(old_mod)
            ok(f"'{old_name}' → '{new_name}' merged & deleted")
        else:
            # Only old exists — rename it
            old_mod.name = new_name
            ok(f"'{old_name}' → '{new_name}' renamed")

    db.session.commit()

    # ── Step 2: Ensure all canonical modules exist ─────────────
    print("\n  Step 2: Canonical modules ensure kar raha hai...")
    added = 0
    for name, label, icon, url, parent_name, sort in CANONICAL_MODULES:
        mod = Module.query.filter_by(name=name).first()
        if not mod:
            parent_id = None
            if parent_name:
                p = Module.query.filter_by(name=parent_name).first()
                if p:
                    parent_id = p.id
            mod = Module(name=name, label=label, icon=icon,
                         url_prefix=url, sort_order=sort,
                         parent_id=parent_id, is_active=True)
            db.session.add(mod)
            added += 1
            ok(f"Module '{name}' added")
        else:
            # Update icon and label if missing
            if not mod.icon or mod.icon == '':
                mod.icon = icon
            mod.label = label
            mod.url_prefix = url
            mod.sort_order = sort

    db.session.commit()
    ok(f"{added} new modules added") if added else ok("All canonical modules already exist")

    # ── Step 3: Fix parent_id for child modules ────────────────
    print("\n  Step 3: Parent-child relationships fix kar raha hai...")
    for name, label, icon, url, parent_name, sort in CANONICAL_MODULES:
        if not parent_name:
            continue
        mod    = Module.query.filter_by(name=name).first()
        parent = Module.query.filter_by(name=parent_name).first()
        if mod and parent and mod.parent_id != parent.id:
            mod.parent_id = parent.id
            ok(f"'{name}' parent → '{parent_name}'")
    db.session.commit()

    # ── Step 4: Show final state ───────────────────────────────
    print("\n  Final modules list:")
    all_mods = Module.query.order_by(Module.sort_order).all()
    for m in all_mods:
        parent_info = f" (parent_id={m.parent_id})" if m.parent_id else ""
        print(f"     [{m.id:2}] {m.icon or '?'} {m.name:<20} → {m.label}{parent_info}")

    print("\n" + "="*55)
    print(f"  {G}✅ Fix complete! Server restart karo.{E}")
    print("="*55 + "\n")
