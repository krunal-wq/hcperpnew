"""
add_npd_fee_paid_at_column.py
─────────────────────────────
NPD projects table mein `npd_fee_paid_at` column add karo. Yeh us moment
ka timestamp store karta hai jab user ne NPD form me "NPD Fee Received"
checkbox tick kiya (unchecked → checked). Iska use /npd/fees-report
page karta hai from-date / to-date filter ke liye.

Existing rows jin me `npd_fee_paid=1` hai un me backfill ho jaata hai
created_at se — taaki purani entries report me bhi dikhein.

Run:
    python add_npd_fee_paid_at_column.py
"""
from index import app
from models import db
from sqlalchemy import text

with app.app_context():
    print("🔧 Adding npd_fee_paid_at column to npd_projects table...\n")

    # ── Add the column ──
    try:
        db.session.execute(text(
            "ALTER TABLE npd_projects ADD COLUMN npd_fee_paid_at DATETIME NULL"
        ))
        db.session.commit()
        print("  ✅ Added column: npd_fee_paid_at")
    except Exception as e:
        db.session.rollback()
        err = str(e).lower()
        if 'duplicate' in err or 'already exists' in err:
            print("  ✔️  Column already exists: npd_fee_paid_at")
        else:
            print(f"  ⚠️  Error adding column: {e}")

    # ── Backfill existing rows where fee is already paid ──
    # Use created_at as a sensible default. Without this, all old paid
    # rows would have NULL fee_paid_at and silently disappear from the
    # date-range report.
    try:
        result = db.session.execute(text("""
            UPDATE npd_projects
               SET npd_fee_paid_at = created_at
             WHERE npd_fee_paid = 1
               AND npd_fee_paid_at IS NULL
        """))
        db.session.commit()
        try:
            count = result.rowcount
        except Exception:
            count = '?'
        print(f"  ✅ Backfilled {count} existing paid row(s) with created_at")
    except Exception as e:
        db.session.rollback()
        print(f"  ⚠️  Backfill failed: {e}")

    print("\n🎉 Done. NPD Fees Report available at /npd/fees-report")
