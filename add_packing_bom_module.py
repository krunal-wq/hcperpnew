"""
add_packing_bom_module.py
=========================
One-time migration -- creates the Packing Material BOM tables:

    - packing_boms        : one row per FG (unique fg_material_id)
    - packing_bom_items   : child rows (which PM, what qty)

Also registers the menu/Module row so the sidebar permission lookup works,
and seeds an admin RolePermission so admin can immediately access the page.

Run:
    python add_packing_bom_module.py

Safe to run repeatedly (idempotent).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; E = "\033[0m"
def ok(m):   print(f"  {G}[OK] {m}{E}")
def warn(m): print(f"  {Y}[!]  {m}{E}")
def err(m):  print(f"  {R}[X]  {m}{E}")

print(f"\n{'=' * 60}")
print(f"  {B}PACKING BOM MODULE -- MIGRATION{E}")
print(f"{'=' * 60}\n")

try:
    from index import app
    from models import db, PackingBOM, PackingBOMItem
except Exception as e:
    err(f"App load failed: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)


with app.app_context():
    from sqlalchemy import inspect

    # ── STEP 1: Create the two tables ─────────────────────────────
    insp = inspect(db.engine)
    before = set(insp.get_table_names())

    try:
        PackingBOM.__table__.create(bind=db.engine, checkfirst=True)
        ok("Table 'packing_boms' ready")
    except Exception as e:
        err(f"Failed to create packing_boms: {e}")
        sys.exit(1)

    try:
        PackingBOMItem.__table__.create(bind=db.engine, checkfirst=True)
        ok("Table 'packing_bom_items' ready")
    except Exception as e:
        err(f"Failed to create packing_bom_items: {e}")
        sys.exit(1)

    insp = inspect(db.engine)
    after = set(insp.get_table_names())
    new = after - before
    if new:
        ok(f"New tables created: {sorted(new)}")
    else:
        warn("No new tables created (already existed)")

    # ── STEP 2: Register the menu Module ──────────────────────────
    try:
        from models.permission import Module, RolePermission
    except Exception as e:
        warn(f"Could not import permission models: {e}")
        Module = RolePermission = None

    pb_module = None
    if Module is not None:
        # Find the 'purchase' parent module by name (so we can attach as child)
        purchase = Module.query.filter_by(name='purchase').first()
        parent_id_val = purchase.id if purchase else None

        pb_module = Module.query.filter_by(name='packing_bom').first()
        if not pb_module:
            try:
                pb_module = Module(
                    name        = 'packing_bom',
                    label       = 'Packing BOM',
                    icon        = 'box',
                    url_prefix  = '/packing-bom',
                    sort_order  = 25,
                    parent_id   = parent_id_val,
                    is_active   = True,
                )
                db.session.add(pb_module)
                db.session.commit()
                ok("Module row 'packing_bom' added")
            except Exception as e:
                db.session.rollback()
                warn(f"Could not add Module row: {e}")
                pb_module = None
        else:
            # Make sure it's active and attached to 'purchase' if a parent exists
            changed = False
            if not pb_module.is_active:
                pb_module.is_active = True; changed = True
            if parent_id_val and pb_module.parent_id != parent_id_val:
                pb_module.parent_id = parent_id_val; changed = True
            if changed:
                db.session.commit()
                ok("Module row 'packing_bom' re-attached / re-activated")
            else:
                ok("Module row 'packing_bom' already exists")

    # ── STEP 3: Seed admin RolePermission ─────────────────────────
    if RolePermission is not None and pb_module is not None:
        try:
            existing = RolePermission.query.filter_by(
                role='admin', module_id=pb_module.id).first()
            if not existing:
                rp = RolePermission(
                    role        = 'admin',
                    module_id   = pb_module.id,
                    can_view    = True,
                    can_add     = True,
                    can_edit    = True,
                    can_delete  = True,
                    can_export  = True,
                )
                db.session.add(rp)
                db.session.commit()
                ok("Admin RolePermission seeded for packing_bom")
            else:
                # Make sure all flags are on
                changed = False
                for f in ('can_view', 'can_add', 'can_edit', 'can_delete', 'can_export'):
                    if not getattr(existing, f, False):
                        setattr(existing, f, True); changed = True
                if changed:
                    db.session.commit()
                    ok("Admin RolePermission flags refreshed")
                else:
                    ok("Admin RolePermission already present")
        except Exception as e:
            db.session.rollback()
            warn(f"Could not seed RolePermission: {e}")

    print()
    print(f"{B}  Done!{E}  Restart the Flask server and the menu item")
    print(f"  'Packing BOM' will appear under Packing Material.\n")
