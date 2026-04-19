"""
add_rd_sample_log_menu.py
=========================
One-time migration — adds the "R&D Sample Log" sub-menu under R&D.

Run:   python add_rd_sample_log_menu.py

What it does
------------
  1. Ensures the `rd` parent Module exists.
  2. Adds child Module `rd_sample_log` → /rd/sample-log  (if missing).
  3. Seeds RolePermission rows so:
       - admin, manager, npd_manager, rd_manager  → full CRUD
       - rd_executive, sales, hr, user            → view only
  4. Idempotent — safe to run multiple times.

Mirrors the style of fix_rd_menu.py already in the project.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; E = "\033[0m"
def ok(m):   print(f"  {G}✅ {m}{E}")
def warn(m): print(f"  {Y}⚠️  {m}{E}")
def err(m):  print(f"  {R}❌ {m}{E}")

print(f"\n{'=' * 55}")
print(f"  {B}R&D SAMPLE LOG — MENU MIGRATION{E}")
print(f"{'=' * 55}")

try:
    from index import app
    from models import db
except Exception as e:
    err(f"App load failed: {e}")
    sys.exit(1)


with app.app_context():
    from models.permission import Module, RolePermission

    # ── STEP 1: R&D parent must exist ──────────────────────────
    rd = Module.query.filter_by(name='rd').first()
    if not rd:
        err("R&D parent module not found. Run migrate.py / fix_rd_menu.py first.")
        sys.exit(1)
    ok(f"R&D parent module found (id={rd.id})")

    # ── STEP 2: Create rd_sample_log if missing ────────────────
    existing = Module.query.filter_by(name='rd_sample_log').first()
    if existing:
        changed = False
        if existing.parent_id != rd.id:
            existing.parent_id = rd.id; changed = True
        if existing.url_prefix != '/rd/sample-log':
            existing.url_prefix = '/rd/sample-log'; changed = True
        if existing.label != 'R&D Sample Log':
            existing.label = 'R&D Sample Log'; changed = True
        if not existing.is_active:
            existing.is_active = True; changed = True
        if changed:
            db.session.commit()
            ok("'R&D Sample Log' module updated ✓")
        else:
            ok("'R&D Sample Log' module already present ✓")
        mod = existing
    else:
        mod = Module(
            name       = 'rd_sample_log',
            label      = 'R&D Sample Log',
            icon       = '🧪',
            url_prefix = '/rd/sample-log',
            sort_order = 13,            # sits just after rd_sample_history
            parent_id  = rd.id,
            is_active  = True,
        )
        db.session.add(mod)
        db.session.commit()
        ok(f"'R&D Sample Log' module created (id={mod.id}) ✓")

    # ── STEP 3: Seed default role permissions ──────────────────
    ROLE_MATRIX = {
        'admin':        dict(can_view=True, can_add=True,  can_edit=True,  can_delete=True,  can_export=True),
        'manager':      dict(can_view=True, can_add=True,  can_edit=True,  can_delete=False, can_export=True),
        'npd_manager':  dict(can_view=True, can_add=True,  can_edit=True,  can_delete=False, can_export=True),
        'rd_manager':   dict(can_view=True, can_add=True,  can_edit=True,  can_delete=False, can_export=True),
        'rd_executive': dict(can_view=True, can_add=False, can_edit=False, can_delete=False, can_export=False),
        'sales':        dict(can_view=True, can_add=False, can_edit=False, can_delete=False, can_export=False),
        'hr':           dict(can_view=True, can_add=False, can_edit=False, can_delete=False, can_export=False),
        'user':         dict(can_view=True, can_add=False, can_edit=False, can_delete=False, can_export=False),
    }

    seeded = 0; updated = 0
    for role, perms in ROLE_MATRIX.items():
        rp = RolePermission.query.filter_by(role=role, module_id=mod.id).first()
        if rp is None:
            rp = RolePermission(role=role, module_id=mod.id, **perms)
            db.session.add(rp)
            seeded += 1
        else:
            # Only update if the existing record still has all defaults False
            # (don't overwrite manual tweaks by admins)
            if not (rp.can_view or rp.can_add or rp.can_edit or rp.can_delete or rp.can_export):
                for k, v in perms.items():
                    setattr(rp, k, v)
                updated += 1
    db.session.commit()

    ok(f"RolePermission rows seeded: {seeded} new, {updated} refreshed")

    print(f"\n{'=' * 55}")
    print(f"  {G}{B}✅ DONE — restart the server to see the menu.{E}")
    print(f"{'=' * 55}\n")
    print("  R&D menu now:")
    print("    🧪 R&D")
    print("      ├── ◈ R&D Dashboard")
    print("      ├── ⬡ R&D Projects")
    print("      ├── 📦 Sample Ready")
    print("      ├── 📋 Sample History")
    print(f"      └── 🧪 {B}R&D Sample Log  ← NEW{E}\n")
