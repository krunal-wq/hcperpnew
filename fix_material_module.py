"""
fix_material_module.py
─────────────────────
Material module ko DB mein register karo taaki permissions panel mein show ho.
Run: python fix_material_module.py
"""

from index import app          # ← app.py nahi, index.py hai
from models import db, Module  # ← Module model yahan hai

with app.app_context():

    # ── 1. Module table mein 'material' add karo ──────────────────
    existing = Module.query.filter_by(name='material').first()
    if existing:
        print(f"✅ 'material' module already exists (id={existing.id})")
    else:
        m = Module(
            name        = 'material',
            label       = 'Item Master',
            icon        = '📦',
            url_prefix  = '/material',
            sort_order  = 19,
            is_active   = True,
        )
        db.session.add(m)
        db.session.commit()
        print(f"✅ 'material' module registered successfully! (id={m.id})")

    # ── 2. Verify ─────────────────────────────────────────────────
    mat = Module.query.filter_by(name='material').first()
    print(f"\nModule details:")
    print(f"  id        : {mat.id}")
    print(f"  name      : {mat.name}")
    print(f"  label     : {mat.label}")
    print(f"  is_active : {mat.is_active}")

    print("\n🎉 Done! Ab /admin/acp permissions panel mein")
    print("   'Procurement — Item Master' section dikhega.")
    print("\n   Agar nahi dikha to browser mein visit karo:")
    print("   http://127.0.0.1:5000/seed-modules")
