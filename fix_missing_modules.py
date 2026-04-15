"""
fix_missing_modules.py
======================
crm_sample_orders aur crm_quotations modules database mein add karta hai.

Run karo:
    python fix_missing_modules.py

Yeh script safe hai — agar module already exist karta hai to skip kar dega.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; E = "\033[0m"

def ok(msg):  print(f"  {G}✅ {msg}{E}")
def warn(msg): print(f"  {Y}⚠️  {msg}{E}")
def err(msg):  print(f"  {R}❌ {msg}{E}")

from index import app
from models.base import db
from models.permission import Module, RolePermission, UserPermission

MISSING_MODULES = [
    {
        'name':       'crm_sample_orders',
        'label':      'Sample Orders',
        'icon':       '🧾',
        'url_prefix': '/crm/sample-orders',
        'sort_order': 5,
        'parent':     'crm',
    },
    {
        'name':       'crm_quotations',
        'label':      'Quotations',
        'icon':       '📄',
        'url_prefix': '/crm/quotations',
        'sort_order': 6,
        'parent':     'crm',
    },
    {
        'name':       'crm_quot_products',
        'label':      'Quot. Product List',
        'icon':       '📋',
        'url_prefix': '/crm/quotations/products',
        'sort_order': 7,
        'parent':     'crm',
    },
    {
        'name':       'crm_leaderboard',
        'label':      'Leaderboard',
        'icon':       '🏆',
        'url_prefix': '/crm/leaderboard',
        'sort_order': 8,
        'parent':     'crm',
    },
]

# Default sub-permissions for each missing module
MODULE_SUB_PERMS = {
    'crm_sample_orders': [
        ('lead_view',        'Lead View'),
        ('invoice_download', 'Invoice Download'),
        ('pdf_download',     'Download Sample Order PDF'),
        ('mail_send',        'Mail Send'),
        ('invoice_upload',   'Invoice Upload'),
        ('view_deleted',     'View Deleted Tab'),
        ('restore',          'Restore'),
        ('permanent_delete', 'Permanent Delete'),
    ],
    'crm_quotations': [
        ('quotation',      'Create Quotation'),
        ('send_email',     'Quot: Send Email'),
        ('status_change',  'Quot: Status Change'),
    ],
    'crm_quot_products': [],
    'crm_leaderboard':   [],
}

with app.app_context():
    import json
    crm = Module.query.filter_by(name='crm').first()
    if not crm:
        err("'crm' parent module nahi mila! Pehle migrate.py run karo.")
        sys.exit(1)

    added_modules = []

    for m in MISSING_MODULES:
        existing = Module.query.filter_by(name=m['name']).first()
        if existing:
            warn(f"Module '{m['name']}' already exists (id={existing.id}) — skipping")
            added_modules.append(existing)
            continue

        new_mod = Module(
            name       = m['name'],
            label      = m['label'],
            icon       = m['icon'],
            url_prefix = m['url_prefix'],
            sort_order = m['sort_order'],
            parent_id  = crm.id,
            is_active  = True,
        )
        db.session.add(new_mod)
        db.session.flush()  # ID generate karo
        added_modules.append(new_mod)
        ok(f"Module '{m['name']}' added (id={new_mod.id}, parent=crm id={crm.id})")

    db.session.commit()

    # ── RolePermissions add karo (sabhi roles ke liye) ──
    roles = ['admin', 'manager', 'sales', 'user', 'hr', 'viewer']
    role_defaults = {
        'admin':   dict(can_view=True, can_add=True, can_edit=True, can_delete=True, can_export=True, can_import=True),
        'manager': dict(can_view=True, can_add=True, can_edit=True, can_delete=False, can_export=True),
        'sales':   dict(can_view=True, can_add=True, can_edit=True, can_delete=False, can_export=False),
        'user':    dict(can_view=True, can_add=False, can_edit=False, can_delete=False, can_export=False),
        'hr':      dict(can_view=False),
        'viewer':  dict(can_view=True),
    }

    print(f"\n  Setting RolePermissions...")
    for mod in added_modules:
        for role in roles:
            existing_rp = RolePermission.query.filter_by(role=role, module_id=mod.id).first()
            if existing_rp:
                continue
            defaults = role_defaults.get(role, dict(can_view=False))
            rp = RolePermission(
                role       = role,
                module_id  = mod.id,
                can_view   = defaults.get('can_view', False),
                can_add    = defaults.get('can_add', False),
                can_edit   = defaults.get('can_edit', False),
                can_delete = defaults.get('can_delete', False),
                can_export = defaults.get('can_export', False),
                can_import = defaults.get('can_import', False),
            )
            db.session.add(rp)
        ok(f"RolePermissions set for '{mod.name}'")

    db.session.commit()

    # ── Existing UserPermissions update karo (admin users) ──
    print(f"\n  Updating UserPermissions for existing users...")
    from models.user import User
    admin_users = User.query.filter_by(role='admin').all()

    for user in admin_users:
        for mod in added_modules:
            up = UserPermission.query.filter_by(user_id=user.id, module_id=mod.id).first()
            if up:
                warn(f"UserPermission already exists for user={user.username}, module={mod.name}")
                continue

            sub_keys = [k for k, _ in MODULE_SUB_PERMS.get(mod.name, [])]
            sub_dict = {k: True for k in sub_keys}

            up = UserPermission(
                user_id    = user.id,
                module_id  = mod.id,
                can_view   = True,
                can_add    = True,
                can_edit   = True,
                can_delete = True,
                can_export = True,
                can_import = True,
            )
            up.set_sub_permissions(sub_dict)
            db.session.add(up)
            ok(f"UserPermission added for admin '{user.username}' → '{mod.name}' + {len(sub_keys)} sub-perms")

    db.session.commit()

    # ── Verify ──
    print(f"\n  {G}=== Final Verification ==={E}")
    for m in MISSING_MODULES:
        mod = Module.query.filter_by(name=m['name']).first()
        if mod:
            rp_count = RolePermission.query.filter_by(module_id=mod.id).count()
            up_count = UserPermission.query.filter_by(module_id=mod.id).count()
            ok(f"'{mod.name}' (id={mod.id}) | {rp_count} role perms | {up_count} user perms")
        else:
            err(f"'{m['name']}' — NOT FOUND in DB!")

    print(f"\n{G}  ✅ Done! Ab ACP panel mein Sample Orders aur Quotations ka{E}")
    print(f"{G}     Enable/Disable All button sahi kaam karega.{E}\n")
