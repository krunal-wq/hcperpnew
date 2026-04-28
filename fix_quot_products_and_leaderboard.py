"""
fix_quot_products_and_leaderboard.py
=====================================
Adds the two CRM modules that show as "⚠️ Module DB mein nahi hai" on the
permissions panel:

    • crm_quot_products  → "Quot. Product List"
    • crm_leaderboard    → "Leaderboard"

These two modules use a SINGLE on/off toggle (just `can_view`) — there are
no sub-permissions and no Add/Edit/Delete grid for them. Admin toggles
ON  → user sees the menu item.
Admin toggles OFF → menu item is hidden.

What this script does
─────────────────────
1. Inserts the two Module rows (parent = 'crm') if missing.
2. Inserts default RolePermission rows for every role we know about.
   admin → can_view=True ; everyone else → can_view=False
   (matches the existing fix_missing_modules.py defaults but tightens
   non-admin roles to start hidden, so the permissions panel can drive
   visibility per-user).
3. Seeds UserPermission rows:
     • Admin users → can_view=True   (so the module is visible day-one)
     • Non-admin users → can_view=False  (so the toggle exists and admin
       can flip it ON per-user from the ACP panel — without the row,
       get_perm() returns no-access AND the toggle has no record to flip)

Idempotent: every step checks for existing rows and skips them. Safe to
re-run any number of times.

Usage
─────
    python fix_quot_products_and_leaderboard.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ─── Tiny ANSI helpers ────────────────────────────────────────────────
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[94m"; E = "\033[0m"
def ok(m):   print(f"  {G}✅ {m}{E}")
def warn(m): print(f"  {Y}⚠️  {m}{E}")
def err(m):  print(f"  {R}❌ {m}{E}")
def info(m): print(f"  {B}ℹ️  {m}{E}")

# ─── Imports ──────────────────────────────────────────────────────────
from index import app
from models.base import db
from models.permission import Module, RolePermission, UserPermission
from models.user import User

# ─── Modules to seed ──────────────────────────────────────────────────
TARGET_MODULES = [
    {
        'name':       'crm_quot_products',
        'label':      'Quot. Product List',
        'icon':       '📋',
        'url_prefix': '/crm/quotations/products',
        'sort_order': 7,
    },
    {
        'name':       'crm_leaderboard',
        'label':      'Leaderboard',
        'icon':       '🏆',
        'url_prefix': '/crm/leaderboard',
        'sort_order': 8,
    },
]

# Roles we set defaults for. admin → ON, baaki sab → OFF (admin enables
# from ACP panel per-user as needed).
ROLE_DEFAULTS = {
    'admin':   True,
    'manager': False,
    'sales':   False,
    'user':    False,
    'hr':      False,
    'viewer':  False,
}

# ──────────────────────────────────────────────────────────────────────


def seed_modules():
    """Step 1: ensure the two Module rows exist under parent 'crm'."""
    crm = Module.query.filter_by(name='crm').first()
    if not crm:
        err("Parent module 'crm' DB mein nahi mila — pehle migrate.py run karo.")
        sys.exit(1)

    seeded = []
    for cfg in TARGET_MODULES:
        existing = Module.query.filter_by(name=cfg['name']).first()
        if existing:
            warn(f"Module '{cfg['name']}' already exists (id={existing.id}) — skip")
            seeded.append(existing)
            continue

        mod = Module(
            name       = cfg['name'],
            label      = cfg['label'],
            icon       = cfg['icon'],
            url_prefix = cfg['url_prefix'],
            sort_order = cfg['sort_order'],
            parent_id  = crm.id,
            is_active  = True,
        )
        db.session.add(mod)
        db.session.flush()
        seeded.append(mod)
        ok(f"Module added → '{cfg['name']}' (id={mod.id}, label='{cfg['label']}')")

    db.session.commit()
    return seeded


def seed_role_perms(modules):
    """Step 2: default role-level permissions. View-only toggle — no
    Add/Edit/Delete/Export/Import for these modules."""
    print()
    info("Setting default RolePermissions (admin=ON, others=OFF)...")
    for mod in modules:
        for role, default_view in ROLE_DEFAULTS.items():
            existing = RolePermission.query.filter_by(
                role=role, module_id=mod.id
            ).first()
            if existing:
                continue
            rp = RolePermission(
                role       = role,
                module_id  = mod.id,
                can_view   = default_view,
                can_add    = False,
                can_edit   = False,
                can_delete = False,
                can_export = False,
                can_import = False,
            )
            db.session.add(rp)
        ok(f"RolePermissions seeded for '{mod.name}'")
    db.session.commit()


def seed_user_perms(modules):
    """Step 3: per-user rows.

    For each user that already exists in the system we add a
    UserPermission row for these modules — because get_perm() falls back
    to "no access" when no UserPermission row is present (non-admin).
    Without a row, the ACP toggle has nothing to flip, so admin can't
    enable visibility per-user. With a row pre-seeded, the toggle works
    as expected.

      • Admin users  → can_view=True  (visible immediately)
      • Non-admin    → can_view=False (admin enables per-user via panel)
    """
    print()
    info("Seeding UserPermission rows...")
    users = User.query.all()
    for user in users:
        is_admin = (user.role == 'admin')
        default_view = is_admin
        for mod in modules:
            existing = UserPermission.query.filter_by(
                user_id=user.id, module_id=mod.id
            ).first()
            if existing:
                continue
            up = UserPermission(
                user_id    = user.id,
                module_id  = mod.id,
                can_view   = default_view,
                can_add    = False,
                can_edit   = False,
                can_delete = False,
                can_export = False,
                can_import = False,
            )
            # No sub-permissions for these modules — single toggle only.
            up.set_sub_permissions({})
            db.session.add(up)
        marker = "ON " if is_admin else "OFF"
        ok(f"User '{user.username}' (role={user.role}) → can_view={marker}")
    db.session.commit()


def verify(modules):
    print()
    print(f"  {G}=== Final Verification ==={E}")
    for cfg in TARGET_MODULES:
        mod = Module.query.filter_by(name=cfg['name']).first()
        if not mod:
            err(f"'{cfg['name']}' — NOT FOUND in DB!")
            continue
        rp_total  = RolePermission.query.filter_by(module_id=mod.id).count()
        up_total  = UserPermission.query.filter_by(module_id=mod.id).count()
        up_on     = UserPermission.query.filter_by(
                        module_id=mod.id, can_view=True
                    ).count()
        ok(f"'{mod.name}' id={mod.id} | role-perms={rp_total} | user-perms={up_total} (ON={up_on})")


def main():
    with app.app_context():
        print(f"\n{B}━━━ Seeding Quot. Product List + Leaderboard ━━━{E}\n")
        modules = seed_modules()
        seed_role_perms(modules)
        seed_user_perms(modules)
        verify(modules)

    print()
    print(f"{G}  ✅ Done.{E}")
    print(f"{G}     • Permissions panel par toggle ab dikhega (warning gone).{E}")
    print(f"{G}     • Admin users → menu mein turant visible.{E}")
    print(f"{G}     • Non-admin users → toggle OFF default — admin selectively ON kar sakta hai.{E}")
    print(f"{G}     • Re-run safe (idempotent).{E}\n")


if __name__ == '__main__':
    main()
