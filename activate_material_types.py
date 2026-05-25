"""
activate_material_types.py
───────────────────────────
Sab material types (RM, PM, FG, SFG, CON, TG) ko is_active=1 set karta hai.
Yeh tab use karo jab Add Item page pe "Aapko koi Item Type allow nahi kiya gaya"
warning aaye, jabki actually user admin hai.

Root cause: material_types table me sab rows is_active=0 ho gayi thi.

Run: python activate_material_types.py
"""
from index import app
from models import db
from sqlalchemy import text

with app.app_context():
    print("=" * 60)
    print("🔧 ACTIVATING ALL MATERIAL TYPES")
    print("=" * 60)

    # ── Before snapshot ──
    print("\n📦 Current status:")
    rows = db.session.execute(text(
        "SELECT id, type_name, abbreviation, is_active, "
        "COALESCE(is_deleted,0) AS del FROM material_types ORDER BY sort_order, id"
    )).fetchall()

    for r in rows:
        act = '✅' if r[3] else '❌'
        deleted = '🗑️' if r[4] else '—'
        print(f"  {r[0]:<3} {r[1]:<20} {r[2] or '':<5} active={act} deleted={deleted}")

    # ── Apply fix ──
    print("\n🔄 Activating all (and undeleting if soft-deleted)...")
    try:
        result = db.session.execute(text(
            "UPDATE material_types "
            "SET is_active=1, is_deleted=0, deleted_at=NULL"
        ))
        db.session.commit()
        print(f"  ✅ Updated {result.rowcount} rows")
    except Exception as e:
        db.session.rollback()
        # Fallback agar is_deleted / deleted_at column nahi hai
        try:
            result = db.session.execute(text(
                "UPDATE material_types SET is_active=1"
            ))
            db.session.commit()
            print(f"  ✅ Updated {result.rowcount} rows (is_active only)")
        except Exception as e2:
            db.session.rollback()
            print(f"  ❌ Failed: {e2}")

    # ── After snapshot ──
    print("\n📦 After fix:")
    rows = db.session.execute(text(
        "SELECT id, type_name, abbreviation, is_active, "
        "COALESCE(is_deleted,0) AS del FROM material_types ORDER BY sort_order, id"
    )).fetchall()
    for r in rows:
        act = '✅' if r[3] else '❌'
        deleted = '🗑️' if r[4] else '—'
        print(f"  {r[0]:<3} {r[1]:<20} {r[2] or '':<5} active={act} deleted={deleted}")

    visible = sum(1 for r in rows if r[3] and not r[4])
    print(f"\n  Visible types: {visible}/{len(rows)}")
    print("\n" + "=" * 60)
    if visible > 0:
        print("✅ Done! Ab browser refresh karke Add New Item kholo.")
    else:
        print("⚠️  Kuch galat hua — manual SQL try karo:")
        print("    UPDATE material_types SET is_active=1, is_deleted=0;")
    print("=" * 60)
