"""
add_formulation_module.py
=========================
One-time migration — wires the "Formulation" module under Raw Material:

    1. Creates two new DB tables
        • formulations
        • formulation_ingredients
    2. Registers the menu/Module row (`formulation`) under
       the existing 'purchase' parent module so the sidebar
       permission lookup works.
    3. Seeds default RolePermission rows.

Run:
    python add_formulation_module.py

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
print(f"  {B}FORMULATION MODULE — MIGRATION{E}")
print(f"{'=' * 60}")

try:
    from index import app
    from models import db, Formulation, FormulationIngredient
except Exception as e:
    err(f"App load failed: {e}")
    import traceback; traceback.print_exc()
    sys.exit(1)


with app.app_context():
    from models.permission import Module, RolePermission

    # ── STEP 1: Create tables (no-op if they already exist) ────────
    try:
        db.create_all()
        ok("Tables synced — formulations, formulation_ingredients")
    except Exception as e:
        err(f"DB create_all failed: {e}")
        sys.exit(1)

    # ── STEP 1b: Add v2 cost columns if missing (idempotent) ───────
    try:
        from sqlalchemy import text, inspect
        insp = inspect(db.engine)
        existing = {c['name'] for c in insp.get_columns('formulation_ingredients')}
        v2_cols = {
            'is_additional'    : "TINYINT(1) DEFAULT 0",
            'uom'              : "VARCHAR(20) DEFAULT 'KG'",
            'rm_rate_per_kg'   : "DECIMAL(14,4) DEFAULT 0",
            'bulk_rate_per_kg' : "DECIMAL(14,4) DEFAULT 0",
        }
        added = []
        for col, ddl in v2_cols.items():
            if col not in existing:
                try:
                    db.session.execute(text(
                        f"ALTER TABLE formulation_ingredients ADD COLUMN {col} {ddl}"
                    ))
                    db.session.commit()
                    added.append(col)
                except Exception as e:
                    db.session.rollback()
                    warn(f"Could not add column {col}: {e}")
        if added:
            ok(f"Added v2 cost columns: {', '.join(added)}")
        else:
            ok("v2 cost columns already present")
    except Exception as e:
        warn(f"Column migration step skipped: {e}")

    # ── STEP 2: Module row — under 'purchase' parent ───────────────
    parent_mod = Module.query.filter_by(name='purchase').first()
    parent_id  = parent_mod.id if parent_mod else None

    existing = Module.query.filter_by(name='formulation').first()
    if existing:
        changed = False
        if existing.parent_id != parent_id:
            existing.parent_id = parent_id; changed = True
        if existing.url_prefix != '/formulation':
            existing.url_prefix = '/formulation'; changed = True
        if existing.label != 'Formulation':
            existing.label = 'Formulation'; changed = True
        if not existing.is_active:
            existing.is_active = True; changed = True
        if changed:
            db.session.commit()
            ok("'Formulation' module updated")
        else:
            ok("'Formulation' module already present")
        mod = existing
    else:
        mod = Module(
            name       = 'formulation',
            label      = 'Formulation',
            icon       = '🧪',
            url_prefix = '/formulation',
            sort_order = 24,
            parent_id  = parent_id,
            is_active  = True,
        )
        db.session.add(mod)
        db.session.commit()
        ok(f"'Formulation' module created (id={mod.id})")

    # ── STEP 3: Default role permissions ───────────────────────────
    ROLE_MATRIX = {
        'admin'         : dict(can_view=True,  can_add=True,  can_edit=True,  can_delete=True,  can_export=True),
        'manager'       : dict(can_view=True,  can_add=True,  can_edit=True,  can_delete=False, can_export=True),
        'rd_manager'    : dict(can_view=True,  can_add=True,  can_edit=True,  can_delete=False, can_export=True),
        'rd_executive'  : dict(can_view=True,  can_add=True,  can_edit=True,  can_delete=False, can_export=False),
        'rd'            : dict(can_view=True,  can_add=True,  can_edit=True,  can_delete=False, can_export=False),
        'npd_manager'   : dict(can_view=True,  can_add=True,  can_edit=True,  can_delete=False, can_export=True),
        'npd'           : dict(can_view=True,  can_add=False, can_edit=False, can_delete=False, can_export=False),
        'purchase'      : dict(can_view=True,  can_add=False, can_edit=False, can_delete=False, can_export=True),
        'user'          : dict(can_view=False, can_add=False, can_edit=False, can_delete=False, can_export=False),
    }
    rp_count = 0
    for role, perms in ROLE_MATRIX.items():
        rp = RolePermission.query.filter_by(role=role, module_id=mod.id).first()
        if rp:
            continue
        rp = RolePermission(role=role, module_id=mod.id, **perms)
        db.session.add(rp); rp_count += 1
    if rp_count:
        db.session.commit()
        ok(f"Seeded {rp_count} default RolePermission rows")
    else:
        ok("RolePermission rows already present (no changes)")

    # ── STEP 4: Print quick summary ────────────────────────────────
    from sqlalchemy import inspect
    insp = inspect(db.engine)
    tables = insp.get_table_names()
    for t in ('formulations', 'formulation_ingredients'):
        if t in tables:
            cols = [c['name'] for c in insp.get_columns(t)]
            ok(f"Table '{t}' OK  ({len(cols)} columns)")
        else:
            err(f"Table '{t}' MISSING!")

print(f"\n{B}Done.{E}  Now restart Flask and visit /formulation\n")
