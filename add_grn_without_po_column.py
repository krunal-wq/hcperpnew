"""
add_grn_without_po_column.py
────────────────────────────
Adds `is_without_po` boolean column to tbl_grn_master so a GRN created via the
"NA" supplier flow (Create GRN without PO) can be distinguished from a normal
PO-backed GRN.

Run ONCE:
    python add_grn_without_po_column.py
"""
from index import app
from models import db
from sqlalchemy import text


def migrate():
    with app.app_context():
        # Check whether column already exists (works on MySQL + most dialects)
        try:
            cols = [row[0] for row in db.session.execute(text(
                "SELECT COLUMN_NAME FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_NAME = 'tbl_grn_master' "
                "  AND COLUMN_NAME = 'is_without_po'"
            ))]
        except Exception:
            cols = []

        if cols:
            print("ℹ️  is_without_po column already exists on tbl_grn_master — nothing to do.")
            return

        try:
            db.session.execute(text(
                "ALTER TABLE tbl_grn_master "
                "ADD COLUMN is_without_po BOOLEAN NOT NULL DEFAULT 0"
            ))
            db.session.commit()
            print("✅ is_without_po column added to tbl_grn_master.")
        except Exception as e:
            db.session.rollback()
            print(f"⚠️  Migration error: {e}")
            print("   (If the column already exists this can be ignored.)")


if __name__ == '__main__':
    migrate()
