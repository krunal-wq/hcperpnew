"""
fix_rd_menu.py
==============
Run: python fix_rd_menu.py

Kya karta hai:
  1. R&D Trials sidebar se remove karta hai (naam jo bhi ho)
  2. R&D Projects sub-module ensure karta hai
  3. Sample Ready + Sample History R&D ke under add karta hai
  4. NPD mein Sample Ready/History waise hi rehta hai (remove nahi)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; E = "\033[0m"
def ok(m):   print(f"  {G}✅ {m}{E}")
def warn(m): print(f"  {Y}⚠️  {m}{E}")
def err(m):  print(f"  {R}❌ {m}{E}")

print(f"\n{'='*55}")
print(f"  {B}R&D MENU FIX{E}")
print(f"{'='*55}")

try:
    from index import app
    from models import db
except Exception as e:
    err(f"App load failed: {e}")
    sys.exit(1)

with app.app_context():
    from models.permission import Module, RolePermission, UserPermission

    # ── STEP 1: R&D Trials — saare possible names se delete karo ──
    trials_names = ['rd_trials', 'trials', 'rd_trial', 'R&D Trials']
    for tname in trials_names:
        mod = Module.query.filter(
            (Module.name == tname) | (Module.label == tname)
        ).first()
        if mod:
            RolePermission.query.filter_by(module_id=mod.id).delete()
            UserPermission.query.filter_by(module_id=mod.id).delete()
            db.session.delete(mod)
            db.session.commit()
            ok(f"'{tname}' module deleted ✓")

    # Label "R&D Trials" se bhi dhundho
    mod = Module.query.filter(Module.label.ilike('%trial%')).first()
    if mod:
        RolePermission.query.filter_by(module_id=mod.id).delete()
        UserPermission.query.filter_by(module_id=mod.id).delete()
        db.session.delete(mod)
        db.session.commit()
        ok(f"Trials module (label match) deleted ✓")

    # ── STEP 2: R&D parent module ensure ──
    rd = Module.query.filter_by(name='rd').first()
    if not rd:
        err("R&D parent module nahi mila! Pehle migrate.py chalao.")
        sys.exit(1)
    ok(f"R&D parent module found (id={rd.id})")

    # ── STEP 3: Sub-modules define ──
    sub_modules = [
        ('rd_projects',       'R&D Projects',   '🗂️',  '/rd/projects',       10),
        ('rd_sample_ready',   'Sample Ready',   '📦',  '/rd/sample-ready',   11),
        ('rd_sample_history', 'Sample History', '📋',  '/rd/sample-history', 12),
    ]

    for name, label, icon, url, sort in sub_modules:
        existing = Module.query.filter_by(name=name).first()
        if not existing:
            new_mod = Module(
                name=name, label=label, icon=icon,
                url_prefix=url, sort_order=sort,
                is_active=True, parent_id=rd.id
            )
            db.session.add(new_mod)
            db.session.commit()
            ok(f"'{label}' module added under R&D ✓")
        else:
            # parent_id fix karo agar missing hai
            if existing.parent_id != rd.id:
                existing.parent_id = rd.id
                db.session.commit()
                ok(f"'{label}' parent_id fixed → R&D ✓")
            else:
                ok(f"'{label}' already exists ✓")

    # ── STEP 4: R&D Dashboard link bhi ensure karo ──
    rd.url_prefix = rd.url_prefix or '/rd'
    db.session.commit()

    print(f"\n{'='*55}")
    print(f"  {G}{B}✅ DONE! Server restart karo.{E}")
    print(f"{'='*55}\n")
    print("  R&D menu ab aisa dikhega:")
    print("    🧪 R&D")
    print("      ├── R&D Dashboard")
    print("      ├── 🗂️  R&D Projects")
    print("      ├── 📦 Sample Ready")
    print("      └── 📋 Sample History\n")
