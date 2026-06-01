"""
add_qc_status_workflow.py — Phase 3 migration for QC Approve/Reject workflow

Adds to tbl_trs_master:
    qc_status              VARCHAR(30)  DEFAULT 'Pending'
    qc_remarks             TEXT
    qc_approved_at         DATETIME
    qc_approved_by_id      INTEGER
    qc_approved_by_name    VARCHAR(150)
    qc_rejected_at         DATETIME
    qc_rejected_by_name    VARCHAR(150)
    stock_impact_applied   BOOLEAN      DEFAULT 0   NOT NULL
    stock_ledger_ref       INTEGER

Creates new table:
    tbl_qc_status_history     (audit trail of every status change)

Run from project root:
    python add_qc_status_workflow.py

Idempotent — safe to re-run.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; E = "\033[0m"
def ok(m):   print(f"  {G}[OK] {m}{E}")
def warn(m): print(f"  {Y}[!]  {m}{E}")
def err(m):  print(f"  {R}[X] {m}{E}")

print(f"\n{'=' * 64}")
print(f"  {B}QC STATUS WORKFLOW (Phase 3) - MIGRATION{E}")
print(f"{'=' * 64}")

try:
    from index import app
    from models import db
    from models.trs import TrsMaster, QcStatusHistory
except Exception as e:
    err(f"Could not import app/models: {e}")
    err("Make sure models/trs.py has been updated to the Phase-3 version.")
    sys.exit(1)


# ── columns to add to tbl_trs_master ──────────────────────────────────
# Note: MySQL does NOT allow DEFAULT on TEXT/BLOB/JSON columns. So qc_remarks
#       uses DB-level NULL; the Python model's default='' handles app-side fill.
NEW_COLUMNS = [
    ("qc_status",            "VARCHAR(30)",  "'Pending'"),
    ("qc_remarks",           "TEXT",          None),       # No default on MySQL TEXT
    ("qc_approved_at",       "DATETIME",      None),
    ("qc_approved_by_id",    "INTEGER",       None),
    ("qc_approved_by_name",  "VARCHAR(150)", "''"),
    ("qc_rejected_at",       "DATETIME",      None),
    ("qc_rejected_by_name",  "VARCHAR(150)", "''"),
    ("stock_impact_applied", "BOOLEAN",      "0"),
    ("stock_ledger_ref",     "INTEGER",       None),
]


# Some DBs (MySQL) reject DEFAULT on TEXT/BLOB/JSON
_NO_DEFAULT_TYPES = ('TEXT', 'BLOB', 'JSON', 'LONGTEXT', 'MEDIUMTEXT', 'TINYTEXT')


with app.app_context():
    engine    = db.engine
    inspector = db.inspect(engine)
    dialect   = engine.dialect.name.lower()
    is_mysql  = 'mysql' in dialect
    is_sqlite = 'sqlite' in dialect
    is_pg     = 'postgres' in dialect or 'postgresql' in dialect

    # ── Step 1: ensure tbl_trs_master exists ──
    if 'tbl_trs_master' not in inspector.get_table_names():
        err("tbl_trs_master does NOT exist. Run add_trs_module.py first.")
        sys.exit(1)
    ok("tbl_trs_master found")

    # ── Step 2: add columns one by one (idempotent) ──
    existing_cols = {c['name'] for c in inspector.get_columns('tbl_trs_master')}
    added = 0
    failed = []
    for cname, ctype, cdefault in NEW_COLUMNS:
        if cname in existing_cols:
            warn(f"Column '{cname}' already exists - skipping")
            continue

        # Decide whether to include a DEFAULT clause
        type_upper = ctype.upper().split('(')[0]
        skip_default = (type_upper in _NO_DEFAULT_TYPES)

        if cdefault is None or skip_default:
            sql = f"ALTER TABLE tbl_trs_master ADD COLUMN {cname} {ctype}"
        elif cdefault == 'NULL':
            sql = f"ALTER TABLE tbl_trs_master ADD COLUMN {cname} {ctype}"
        else:
            sql = f"ALTER TABLE tbl_trs_master ADD COLUMN {cname} {ctype} DEFAULT {cdefault}"

        try:
            with engine.begin() as conn:
                from sqlalchemy import text
                conn.execute(text(sql))
            ok(f"Added column: {cname}")
            added += 1
        except Exception as e:
            err(f"Failed to add column '{cname}': {e}")
            failed.append(cname)

    if added:
        ok(f"Added {added} new column(s) to tbl_trs_master")
    elif not failed:
        ok("All workflow columns already present - nothing to add")
    if failed:
        err(f"FAILED columns: {failed}  - investigate before continuing!")
        sys.exit(1)

    # ── Step 3: create tbl_qc_status_history if missing ──
    inspector = db.inspect(engine)   # refresh
    if 'tbl_qc_status_history' in inspector.get_table_names():
        warn("tbl_qc_status_history already exists - skipping create")
    else:
        try:
            QcStatusHistory.__table__.create(bind=engine, checkfirst=True)
            ok("Created table: tbl_qc_status_history")
        except Exception as e:
            err(f"Failed to create tbl_qc_status_history: {e}")
            sys.exit(1)

    # ── Step 4: backfill qc_status=Pending for older rows that have NULL ──
    try:
        from sqlalchemy import text
        with engine.begin() as conn:
            r = conn.execute(text("UPDATE tbl_trs_master SET qc_status='Pending' "
                                  "WHERE qc_status IS NULL OR qc_status=''"))
            try:
                n = r.rowcount
            except Exception:
                n = '?'
        ok(f"Backfilled qc_status='Pending' for legacy rows  ({n} updated)")
    except Exception as e:
        warn(f"Backfill skipped: {e}")

    # ── Step 5: sanity counts ──
    try:
        total   = TrsMaster.query.filter_by(is_deleted=False).count()
        approved = TrsMaster.query.filter_by(qc_status='Approved',
                                             is_deleted=False).count()
        history_n = QcStatusHistory.query.count()
        ok(f"TRS records: {total}  |  Approved: {approved}  |  History rows: {history_n}")
    except Exception as e:
        warn(f"Could not query: {e}")


print()
print(f"{'=' * 64}")
print(f"  {B}MIGRATION COMPLETE{E}")
print(f"{'=' * 64}")
print()
print("  Next steps:")
print("    1. Make sure models/trs.py + qc_routes.py + templates/qc/trs_list.html")
print("       are the new Phase-3 versions (in this ZIP).")
print("    2. Restart Flask:  python .\\index.py")
print("    3. Open /qc/trs/rm  -->  click Approve  -->  see stock-in happen")
print("       (check /grn/stock or /grn/stock-ledger to verify).")
print()
