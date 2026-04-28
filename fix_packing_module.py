"""
fix_packing_module.py
=====================
Adds the Packing module to the permissions system. Sidebar mein dikh raha
hai (admin ke liye `get_perm()` ka admin-fallback ki wajah se), lekin
User Permissions panel pe nahi dikh raha kyunki `Module` table mein
'packing' row exist hi nahi karta.

Yeh script `fix_quot_products_and_leaderboard.py` ka same pattern follow
karta hai — woh script aap pehle se safely chala chuke ho.

What this script does
─────────────────────
1. Inserts the 'packing' Module row (top-level, no parent) if missing.
2. Inserts default RolePermission rows for every role:
     admin → full access ; everyone else → all OFF (admin enables per-user).
3. Seeds UserPermission rows:
     • Admin users → can_view/add/edit/delete/export = True
     • Non-admin   → all False (admin selectively enables via ACP panel)

Idempotent: every step checks for existing rows and skips them. Safe to
re-run any number of times.

Usage
─────
    cd /var/www/hcperp
    python fix_packing_module.py

Phir Apache restart karo:
    sudo systemctl restart apache2

Phir browser mein /admin/user-permissions page kholo — Packing module
ab dikhega.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── Tiny ANSI helpers ────────────────────────────────────────────────
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[94m"; E = "\033[0m"
def ok(m):   print(f"  {G}OK   {m}{E}")
def warn(m): print(f"  {Y}WARN {m}{E}")
def err(m):  print(f"  {R}ERR  {m}{E}")
def info(m): print(f"  {B}INFO {m}{E}")

# ─── Imports ──────────────────────────────────────────────────────────
from index import app
from models.base import db
from models.permission import Module, RolePermission, UserPermission
from models.user import User

# ─── Module config ────────────────────────────────────────────────────
PACKING_MODULE = {
    'name':       'packing',
    'label':      'Packing',
    'icon':       '📦',
    'url_prefix': '/packing',
    'sort_order': 17,
}

# Role defaults — admin gets full rights, everyone else starts disabled
# so admin can enable selectively from the User Permissions panel.
ROLE_DEFAULTS = {
    'admin':   dict(view=True,  add=True,  edit=True,  delete=True,  export=True),
    'manager': dict(view=False, add=False, edit=False, delete=False, export=False),
    'sales':   dict(view=False, add=False, edit=False, delete=False, export=False),
    'user':    dict(view=False, add=False, edit=False, delete=False, export=False),
    'hr':      dict(view=False, add=False, edit=False, delete=False, export=False),
    'viewer':  dict(view=False, add=False, edit=False, delete=False, export=False),
    'qc':      dict(view=True,  add=False, edit=True,  delete=False, export=False),
    'qc_common': dict(view=True, add=False, edit=True, delete=False, export=False),
}

# ──────────────────────────────────────────────────────────────────────


def seed_module():
    """Step 1: ensure the Module row for 'packing' exists."""
    existing = Module.query.filter_by(name='packing').first()
    if existing:
        warn(f"Module 'packing' already exists (id={existing.id}) — skip insert")
        # Make sure it's active
        if not existing.is_active:
            existing.is_active = True
            db.session.commit()
            ok("Re-activated existing 'packing' module")
        return existing

    mod = Module(
        name       = PACKING_MODULE['name'],
        label      = PACKING_MODULE['label'],
        icon       = PACKING_MODULE['icon'],
        url_prefix = PACKING_MODULE['url_prefix'],
        sort_order = PACKING_MODULE['sort_order'],
        parent_id  = None,                    # top-level menu, no parent
        is_active  = True,
    )
    db.session.add(mod)
    db.session.flush()
    db.session.commit()
    ok(f"Module added → 'packing' (id={mod.id}, label='Packing')")
    return mod


def seed_role_perms(mod):
    """Step 2: default RolePermission rows for every known role."""
    print()
    info("Setting default RolePermissions...")
    for role, perms in ROLE_DEFAULTS.items():
        existing = RolePermission.query.filter_by(role=role, module_id=mod.id).first()
        if existing:
            warn(f"RolePermission for role='{role}' already exists — skip")
            continue
        rp = RolePermission(
            role       = role,
            module_id  = mod.id,
            can_view   = perms['view'],
            can_add    = perms['add'],
            can_edit   = perms['edit'],
            can_delete = perms['delete'],
            can_export = perms['export'],
            can_import = perms.get('import', False),
        )
        db.session.add(rp)
        ok(f"RolePermission seeded → role='{role}' view={perms['view']}")
    db.session.commit()


def seed_user_perms(mod):
    """Step 3: per-user rows for every existing user.

    Without a UserPermission row, get_perm() returns no-access for
    non-admin users AND the ACP toggle has nothing to flip. Pre-seeding
    a row (with can_view=False for non-admin) makes the toggle work.
    """
    print()
    info("Seeding UserPermission rows for all existing users...")
    users = User.query.all()
    seeded = 0
    skipped = 0
    for user in users:
        existing = UserPermission.query.filter_by(
            user_id=user.id, module_id=mod.id
        ).first()
        if existing:
            skipped += 1
            continue

        is_admin = (user.role == 'admin')
        if is_admin:
            up = UserPermission(
                user_id    = user.id,
                module_id  = mod.id,
                can_view   = True,
                can_add    = True,
                can_edit   = True,
                can_delete = True,
                can_export = True,
                can_import = False,
            )
        else:
            # Look up role default; fall back to all-False
            r_def = ROLE_DEFAULTS.get(user.role, ROLE_DEFAULTS['user'])
            up = UserPermission(
                user_id    = user.id,
                module_id  = mod.id,
                can_view   = r_def['view'],
                can_add    = r_def['add'],
                can_edit   = r_def['edit'],
                can_delete = r_def['delete'],
                can_export = r_def['export'],
                can_import = False,
            )
        up.set_sub_permissions({})
        db.session.add(up)
        seeded += 1
    db.session.commit()
    ok(f"UserPermission rows: {seeded} added, {skipped} skipped (already existed)")


def verify(mod):
    print()
    print(f"  {G}=== Final Verification ==={E}")
    fresh = Module.query.filter_by(name='packing').first()
    if not fresh:
        err("'packing' — NOT FOUND in DB after seeding!")
        return
    rp_total = RolePermission.query.filter_by(module_id=fresh.id).count()
    up_total = UserPermission.query.filter_by(module_id=fresh.id).count()
    up_on    = UserPermission.query.filter_by(
                   module_id=fresh.id, can_view=True
               ).count()
    ok(f"'packing' id={fresh.id} active={fresh.is_active}")
    ok(f"  role-perms = {rp_total}")
    ok(f"  user-perms = {up_total} (can_view ON for {up_on})")


def main():
    with app.app_context():
        print(f"\n{B}=== Seeding Packing module into permissions system ==={E}\n")
        mod = seed_module()
        seed_role_perms(mod)
        seed_user_perms(mod)
        verify(mod)

    print()
    print(f"{G}  Done.{E}")
    print(f"{G}     - Packing ab User Permissions panel par dikhega.{E}")
    print(f"{G}     - Admin users -> menu turant visible (already tha).{E}")
    print(f"{G}     - Non-admin users -> toggle OFF default; admin enable kar sakta hai.{E}")
    print(f"{G}     - Re-run safe (idempotent).{E}")
    print()
    print(f"{Y}  Next steps:{E}")
    print(f"     1. sudo systemctl restart apache2")
    print(f"     2. Browser mein /admin/user-permissions kholo, Packing dikhega")
    print()


if __name__ == '__main__':
    main()
