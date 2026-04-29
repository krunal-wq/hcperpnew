"""
add_raw_material_sample_module.py
=================================
One-time migration — wires the "Raw Material Sample Request" module
into the running app:

    1. Creates two new DB tables
        • raw_material_sample_requests
        • rms_activity_log
        • rms_notifications
    2. Registers the menu/Module row (`raw_material_sample`)
       under the existing R&D parent module so the sidebar link
       appears.
    3. Seeds default RolePermission rows so the right roles get
       sensible defaults (admin / npd / rd / purchase / etc.)

Run:
    python add_raw_material_sample_module.py

Idempotent — running it again is safe.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; E = "\033[0m"
def ok(m):   print(f"  {G}✅ {m}{E}")
def warn(m): print(f"  {Y}⚠️  {m}{E}")
def err(m):  print(f"  {R}❌ {m}{E}")

print(f"\n{'=' * 60}")
print(f"  {B}RAW MATERIAL SAMPLE REQUEST — MODULE MIGRATION{E}")
print(f"{'=' * 60}")

try:
    from index import app
    from models import db
    from models.raw_material_sample import (
        RawMaterialSampleRequest, RMSActivityLog, RMSNotification,
    )
except Exception as e:
    err(f"App load failed: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)


with app.app_context():
    from models.permission import Module, RolePermission

    # ── STEP 1: Create tables (no-op if they already exist) ────────
    try:
        db.create_all()
        ok("Tables synced — raw_material_sample_requests, rms_activity_log, rms_notifications")
    except Exception as e:
        err(f"DB create_all failed: {e}")
        sys.exit(1)

    # ── STEP 2: Top-level module (root) — same as Packing ──────────
    # parent_id stays None so the menu appears at root level, not nested
    # inside R&D. Re-running the migration will move existing rows out
    # of R&D too.
    parent_id = None

    # ── STEP 3: Create / update Module row ─────────────────────────
    existing = Module.query.filter_by(name='raw_material_sample').first()
    if existing:
        changed = False
        if existing.parent_id != parent_id:
            existing.parent_id = parent_id; changed = True
        if existing.url_prefix != '/raw-material-sample':
            existing.url_prefix = '/raw-material-sample'; changed = True
        if existing.label != 'Raw Material Sample':
            existing.label = 'Raw Material Sample'; changed = True
        if not existing.is_active:
            existing.is_active = True; changed = True
        if changed:
            db.session.commit()
            ok("'Raw Material Sample' module updated (now top-level)")
        else:
            ok("'Raw Material Sample' module already present")
        mod = existing
    else:
        mod = Module(
            name       = 'raw_material_sample',
            label      = 'Raw Material Sample',
            icon       = '🧴',
            url_prefix = '/raw-material-sample',
            sort_order = 18,
            parent_id  = parent_id,
            is_active  = True,
        )
        db.session.add(mod)
        db.session.commit()
        ok(f"'Raw Material Sample' module created (id={mod.id})")

    # ── STEP 4: Seed default role permissions ──────────────────────
    # NOTE: The system is currently user-only (see permissions.py),
    # so the RolePermission rows are largely informational. They are
    # still seeded as a hint for the ACP and for any future
    # role-based fallback. Actual access for non-admin users is
    # granted via UserPermission in the Access Control Panel.
    ROLE_MATRIX = {
        # Full control
        'admin'         : dict(can_view=True, can_add=True,  can_edit=True,  can_delete=True,  can_export=True),
        'manager'       : dict(can_view=True, can_add=True,  can_edit=True,  can_delete=False, can_export=True),
        # Requesters
        'npd_manager'   : dict(can_view=True, can_add=True,  can_edit=True,  can_delete=False, can_export=True),
        'rd_manager'    : dict(can_view=True, can_add=True,  can_edit=True,  can_delete=False, can_export=True),
        'rd_executive'  : dict(can_view=True, can_add=True,  can_edit=True,  can_delete=False, can_export=False),
        'npd'           : dict(can_view=True, can_add=True,  can_edit=True,  can_delete=False, can_export=False),
        'rd'            : dict(can_view=True, can_add=True,  can_edit=True,  can_delete=False, can_export=False),
        # Purchase
        'purchase'           : dict(can_view=True, can_add=False, can_edit=True, can_delete=False, can_export=True),
        'purchase_manager'   : dict(can_view=True, can_add=True,  can_edit=True, can_delete=False, can_export=True),
        'purchase_executive' : dict(can_view=True, can_add=False, can_edit=True, can_delete=False, can_export=False),
        # Read-only
        'sales'         : dict(can_view=True, can_add=False, can_edit=False, can_delete=False, can_export=False),
        'user'          : dict(can_view=True, can_add=False, can_edit=False, can_delete=False, can_export=False),
    }

    seeded = 0; updated = 0
    for role, perms in ROLE_MATRIX.items():
        rp = RolePermission.query.filter_by(role=role, module_id=mod.id).first()
        if rp is None:
            rp = RolePermission(role=role, module_id=mod.id, **perms)
            db.session.add(rp)
            seeded += 1
        else:
            # Only refresh if existing record is all-defaults-False
            if not (rp.can_view or rp.can_add or rp.can_edit or rp.can_delete or rp.can_export):
                for k, v in perms.items():
                    setattr(rp, k, v)
                updated += 1
    db.session.commit()
    ok(f"RolePermission rows seeded: {seeded} new, {updated} refreshed")

    print(f"\n{'=' * 60}")
    print(f"  {G}{B}✅ DONE{E}")
    print(f"{'=' * 60}")
    print(f"  Next steps:")
    print(f"    1. Restart the Flask app")
    print(f"    2. Open ACP (/admin/acp) → grant 'Raw Material Sample'")
    print(f"       UserPermissions to the users who need it")
    print(f"    3. Sidebar link should now be visible under R&D for")
    print(f"       admins and any user granted view permission.\n")
