"""
add_procurement_modules.py
──────────────────────────
Procurement module hierarchy DB mein setup karo.

Structure:
  Procurement (top-level parent)
  └── Purchase (child of Procurement)
      ├── Raw Material     → /material?item_type=RM
      ├── Packing Material → /material?item_type=PM
      └── Finish Goods     → /material?item_type=FG

Purana standalone 'material' module deactivate ho jaayega.

Run: python add_procurement_modules.py
"""

from index import app
from models import db
from models.permission import Module

with app.app_context():

    print("🔧 Procurement Module Hierarchy Setup...")

    # ── 1. Procurement (top-level parent) ─────────────────────────────
    proc = Module.query.filter_by(name='procurement').first()
    if not proc:
        proc = Module(
            name       = 'procurement',
            label      = 'Procurement',
            icon       = '🛒',
            url_prefix = '',
            sort_order = 19,
            is_active  = True,
            parent_id  = None,
        )
        db.session.add(proc)
        db.session.flush()
        print(f"  ✅ Created 'procurement' module (id={proc.id})")
    else:
        proc.is_active  = True
        proc.parent_id  = None
        proc.sort_order = 19
        proc.label      = 'Procurement'
        proc.icon       = '🛒'
        print(f"  ✔️  'procurement' already exists (id={proc.id}) — updated")

    # ── 2. Purchase (child of Procurement) ────────────────────────────
    purchase = Module.query.filter_by(name='purchase').first()
    if not purchase:
        purchase = Module(
            name       = 'purchase',
            label      = 'Purchase',
            icon       = '🛍️',
            url_prefix = '',
            sort_order = 20,
            is_active  = True,
            parent_id  = proc.id,
        )
        db.session.add(purchase)
        db.session.flush()
        print(f"  ✅ Created 'purchase' module (id={purchase.id})")
    else:
        purchase.parent_id  = proc.id
        purchase.is_active  = True
        purchase.sort_order = 20
        purchase.label      = 'Purchase'
        purchase.icon       = '🛍️'
        print(f"  ✔️  'purchase' already exists (id={purchase.id}) — updated")

    # ── 3. Raw Material (grandchild) ──────────────────────────────────
    rm = Module.query.filter_by(name='purchase_rm').first()
    if not rm:
        rm = Module(
            name       = 'purchase_rm',
            label      = 'Raw Material',
            icon       = '🧪',
            url_prefix = '/material?item_type=RM',
            sort_order = 21,
            is_active  = True,
            parent_id  = purchase.id,
        )
        db.session.add(rm)
        print(f"  ✅ Created 'purchase_rm' module")
    else:
        rm.parent_id  = purchase.id
        rm.is_active  = True
        rm.url_prefix = '/material?item_type=RM'
        print(f"  ✔️  'purchase_rm' already exists — updated")

    # ── 4. Packing Material (grandchild) ──────────────────────────────
    pm = Module.query.filter_by(name='purchase_pm').first()
    if not pm:
        pm = Module(
            name       = 'purchase_pm',
            label      = 'Packing Material',
            icon       = '📦',
            url_prefix = '/material?item_type=PM',
            sort_order = 22,
            is_active  = True,
            parent_id  = purchase.id,
        )
        db.session.add(pm)
        print(f"  ✅ Created 'purchase_pm' module")
    else:
        pm.parent_id  = purchase.id
        pm.is_active  = True
        pm.url_prefix = '/material?item_type=PM'
        print(f"  ✔️  'purchase_pm' already exists — updated")

    # ── 5. Finish Goods (grandchild) ──────────────────────────────────
    fg = Module.query.filter_by(name='purchase_fg').first()
    if not fg:
        fg = Module(
            name       = 'purchase_fg',
            label      = 'Finish Goods',
            icon       = '✅',
            url_prefix = '/material?item_type=FG',
            sort_order = 23,
            is_active  = True,
            parent_id  = purchase.id,
        )
        db.session.add(fg)
        print(f"  ✅ Created 'purchase_fg' module")
    else:
        fg.parent_id  = purchase.id
        fg.is_active  = True
        fg.url_prefix = '/material?item_type=FG'
        print(f"  ✔️  'purchase_fg' already exists — updated")

    # ── 6. Purana standalone 'material' module deactivate karo ───────
    old_material = Module.query.filter_by(name='material').first()
    if old_material:
        old_material.is_active = False
        print(f"  🔕 Deactivated old standalone 'material' module (id={old_material.id})")
    
    db.session.commit()

    print("\n🎉 Done! Procurement hierarchy setup complete.")
    print("   Sidebar mein dikhega:")
    print("   PROCUREMENT")
    print("   └── 🛍️ Purchase")
    print("       ├── 🧪 Raw Material     → /material?item_type=RM")
    print("       ├── 📦 Packing Material → /material?item_type=PM")
    print("       └── ✅ Finish Goods     → /material?item_type=FG")
    print("\n   Note: Raw Material click karne par Item Type automatically")
    print("   'Raw Material' set ho jaayega — koi selection nahi hoga.")
