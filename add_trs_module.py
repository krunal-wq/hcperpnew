"""
add_trs_module.py — One-time migration for the TRS (Testing Requisition Slip) module

What this does:
  1. Creates the tbl_trs_master table (only — no row data)
  2. Verifies the table exists
  3. Prints next steps

Run:
    python add_trs_module.py

Idempotent — re-running is safe.

AFTER running this you still need to do TWO small manual steps in index.py:

  1. Add an import near the other route imports (around line ~33):

         from trs_routes import trs_bp     # TRS (Testing Requisition Slip)

  2. Register the blueprint (around line ~95, next to other register_blueprint
     calls):

         app.register_blueprint(trs_bp)    # TRS (Testing Requisition Slip)

Then restart Flask.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; E = "\033[0m"
def ok(m):   print(f"  {G}\u2705 {m}{E}")
def warn(m): print(f"  {Y}\u26a0\ufe0f  {m}{E}")
def err(m):  print(f"  {R}\u274c {m}{E}")

print(f"\n{'=' * 60}")
print(f"  {B}TESTING REQUISITION SLIP (TRS) \u2014 MODULE MIGRATION{E}")
print(f"{'=' * 60}")

try:
    from index import app
    from models import db
    from models.trs import TrsMaster
except Exception as e:
    err(f"Failed to import app/models: {e}")
    print()
    err("Common causes:")
    err("  \u2022 Are you running from the project root?")
    err("  \u2022 Did you place models/trs.py and trs_routes.py in their")
    err("    correct locations?")
    sys.exit(1)

with app.app_context():
    try:
        # ── Create the table only if missing ──
        engine     = db.engine
        inspector  = db.inspect(engine)
        if 'tbl_trs_master' in inspector.get_table_names():
            warn("tbl_trs_master already exists \u2014 skipping create.")
        else:
            TrsMaster.__table__.create(bind=engine, checkfirst=True)
            ok("Created table: tbl_trs_master")

        # Confirm by counting rows
        try:
            count = TrsMaster.query.filter_by(is_deleted=False).count()
            ok(f"Table is accessible. Existing TRS records: {count}")
        except Exception as e:
            warn(f"Could not query table (might need restart): {e}")

    except Exception as e:
        err(f"Migration failed: {e}")
        import traceback; traceback.print_exc()
        sys.exit(1)

print()
print(f"{'=' * 60}")
print(f"  {B}\u2705 MIGRATION COMPLETE{E}")
print(f"{'=' * 60}")
print()
print("  Final step \u2014 register the blueprint in index.py")
print("  (open index.py and add these two lines):\n")
print(f"    {B}from trs_routes import trs_bp{E}        # near top, w/ other imports")
print(f"    {B}app.register_blueprint(trs_bp){E}       # w/ other register_blueprint calls")
print()
print("  Then restart Flask and open any RM GRN \u2192 click the hamburger menu \u2192")
print("  '\ud83d\udccb TRS' to start creating Testing Requisition Slips per item.")
print()
