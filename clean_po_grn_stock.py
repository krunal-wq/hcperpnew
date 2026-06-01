#!/usr/bin/env python3
"""
clean_po_grn_stock.py
=====================
Deletes ALL Purchase Orders, ALL GRNs, and related stock data
(stock ledger + batch on-hand) from the HCP ERP database.

⚠️  DESTRUCTIVE — there is NO undo from inside the app.
    Script makes a timestamped .bak file of the DB before
    touching anything; restore from there if anything goes wrong.

USAGE:
    python3 clean_po_grn_stock.py                  # full wipe, asks confirmation
    python3 clean_po_grn_stock.py --yes            # skip confirmation
    python3 clean_po_grn_stock.py --po-type RM     # only RM POs/GRNs/stock
    python3 clean_po_grn_stock.py --db app.db      # custom DB path
    python3 clean_po_grn_stock.py --no-backup      # skip backup (NOT recommended)
    python3 clean_po_grn_stock.py --no-reset-seq   # keep auto-increment values
"""

import argparse
import os
import shutil
import sqlite3
import sys
from datetime import datetime


# Tables in safe delete order (children → parents).
# Stock tables have NO enforced FK in this schema, so we wipe them first.
PO_CHILDREN  = ['tbl_purchase_order_items',
                'tbl_purchase_order_terms',
                'tbl_purchase_order_approval_logs',
                'tbl_purchase_order_status_logs']

GRN_CHILDREN = ['tbl_grn_items',
                'tbl_grn_status_logs',
                'tbl_grn_approval_logs']

STOCK_TABLES = ['tbl_grn_stock_ledger',
                'tbl_grn_batch_stock']

PO_MASTER    = 'tbl_purchase_order'
GRN_MASTER   = 'tbl_grn_master'


# ───────────────────────────────────────────────────────────────────
def table_exists(cur, name):
    cur.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None


def row_count(cur, name, where=''):
    if not table_exists(cur, name):
        return None
    sql = f"SELECT COUNT(*) FROM {name}"
    if where:
        sql += f" WHERE {where}"
    cur.execute(sql)
    return cur.fetchone()[0]


def _fmt_count(n):
    return '— (table not in DB)' if n is None else str(n)


def print_counts(cur, label, po_filter='', grn_filter=''):
    print(f"\n── {label} ──")
    print(f"  {PO_MASTER:<40} : {_fmt_count(row_count(cur, PO_MASTER, po_filter))}")
    for t in PO_CHILDREN:
        print(f"  {t:<40} : {_fmt_count(row_count(cur, t))}")
    print(f"  {GRN_MASTER:<40} : {_fmt_count(row_count(cur, GRN_MASTER, grn_filter))}")
    for t in GRN_CHILDREN:
        print(f"  {t:<40} : {_fmt_count(row_count(cur, t))}")
    for t in STOCK_TABLES:
        print(f"  {t:<40} : {_fmt_count(row_count(cur, t))}")


def backup_db(path):
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    bak = f"{path}.bak_{ts}"
    shutil.copy2(path, bak)
    sz = os.path.getsize(bak) / 1024
    print(f"✓ Backup created : {bak}  ({sz:,.1f} KB)")
    return bak


# ───────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="Delete all POs, GRNs, and related stock from HCP ERP DB.")
    ap.add_argument('--db', default='app.db', help='Path to SQLite DB (default: app.db)')
    ap.add_argument('--po-type', default=None,
                    help="Only delete POs of this type (e.g. RM, PM, FG). "
                         "Default: delete ALL types.")
    ap.add_argument('--yes', action='store_true',
                    help="Skip 'YES' confirmation prompt.")
    ap.add_argument('--no-backup', action='store_true',
                    help="Skip DB backup (NOT recommended).")
    ap.add_argument('--no-reset-seq', action='store_true',
                    help="Do not reset auto-increment counters.")
    args = ap.parse_args()

    if not os.path.exists(args.db):
        print(f"✗ DB not found: {args.db}")
        sys.exit(1)

    # ── Build filters ──
    po_filter  = ''
    grn_filter = ''
    if args.po_type:
        pt = args.po_type.strip().upper()
        po_filter  = f"po_type = '{pt}'"
        # GRNs filtered by linked PO type
        grn_filter = (f"po_id IN (SELECT id FROM {PO_MASTER} "
                      f"WHERE po_type = '{pt}')")
        print(f"⚠  Filter active: po_type = {pt}")
    else:
        print("⚠  No filter — will delete ALL POs, ALL GRNs, ALL stock.")

    conn = sqlite3.connect(args.db)
    conn.execute("PRAGMA foreign_keys = ON")
    cur  = conn.cursor()

    print_counts(cur, "BEFORE", po_filter, grn_filter)

    # ── Confirm ──
    if not args.yes:
        print("\nType  YES  (uppercase) to proceed, anything else to abort:")
        ans = input("> ").strip()
        if ans != 'YES':
            print("Aborted. Nothing changed.")
            conn.close()
            sys.exit(0)

    # ── Backup ──
    if not args.no_backup:
        backup_db(args.db)
    else:
        print("⚠  Skipped backup (--no-backup)")

    # ── Resolve target IDs ──
    if args.po_type:
        cur.execute(f"SELECT id FROM {PO_MASTER} WHERE {po_filter}")
        po_ids = [r[0] for r in cur.fetchall()]
        cur.execute(f"SELECT id FROM {GRN_MASTER} WHERE {grn_filter}")
        grn_ids = [r[0] for r in cur.fetchall()]
    else:
        po_ids  = None   # means "all"
        grn_ids = None

    def in_clause(ids):
        return '(' + ','.join(str(i) for i in ids) + ')'

    deleted = {}
    skipped = []

    def safe_delete(sql, table_for_log):
        """Run a DELETE only if the target table exists. Returns rowcount or None."""
        if not table_exists(cur, table_for_log):
            skipped.append(table_for_log)
            return None
        cur.execute(sql)
        return cur.rowcount

    try:
        # 1. STOCK — wipe ledger + batch stock
        #    If filtered, only wipe entries linked to target GRN ids.
        if args.po_type and grn_ids:
            n = safe_delete(
                f"DELETE FROM tbl_grn_stock_ledger "
                f"WHERE txn_ref_type='GRN' AND txn_ref_id IN {in_clause(grn_ids)}",
                'tbl_grn_stock_ledger')
            if n is not None: deleted['tbl_grn_stock_ledger'] = n
            # Batch stock — only rows whose (material, batch, location) no longer
            # have any ledger entry (i.e. became orphans after the wipe above).
            n = safe_delete(
                "DELETE FROM tbl_grn_batch_stock "
                "WHERE (material_id, batch_no, COALESCE(location_id,-1)) NOT IN ("
                "  SELECT material_id, batch_no, COALESCE(location_id,-1) "
                "  FROM tbl_grn_stock_ledger)"
                if table_exists(cur, 'tbl_grn_stock_ledger')
                else "DELETE FROM tbl_grn_batch_stock",
                'tbl_grn_batch_stock')
            if n is not None: deleted['tbl_grn_batch_stock'] = n
        elif not args.po_type:
            # Full wipe — straightforward
            n = safe_delete("DELETE FROM tbl_grn_stock_ledger", 'tbl_grn_stock_ledger')
            if n is not None: deleted['tbl_grn_stock_ledger'] = n
            n = safe_delete("DELETE FROM tbl_grn_batch_stock", 'tbl_grn_batch_stock')
            if n is not None: deleted['tbl_grn_batch_stock'] = n

        # 2. GRN children + master
        if args.po_type and grn_ids:
            for t in GRN_CHILDREN:
                n = safe_delete(f"DELETE FROM {t} WHERE grn_id IN {in_clause(grn_ids)}", t)
                if n is not None: deleted[t] = n
            n = safe_delete(f"DELETE FROM {GRN_MASTER} WHERE id IN {in_clause(grn_ids)}",
                            GRN_MASTER)
            if n is not None: deleted[GRN_MASTER] = n
        elif not args.po_type:
            for t in GRN_CHILDREN:
                n = safe_delete(f"DELETE FROM {t}", t)
                if n is not None: deleted[t] = n
            n = safe_delete(f"DELETE FROM {GRN_MASTER}", GRN_MASTER)
            if n is not None: deleted[GRN_MASTER] = n

        # 3. PO children + master
        if args.po_type and po_ids:
            for t in PO_CHILDREN:
                n = safe_delete(f"DELETE FROM {t} WHERE po_id IN {in_clause(po_ids)}", t)
                if n is not None: deleted[t] = n
            n = safe_delete(f"DELETE FROM {PO_MASTER} WHERE id IN {in_clause(po_ids)}",
                            PO_MASTER)
            if n is not None: deleted[PO_MASTER] = n
        elif not args.po_type:
            for t in PO_CHILDREN:
                n = safe_delete(f"DELETE FROM {t}", t)
                if n is not None: deleted[t] = n
            n = safe_delete(f"DELETE FROM {PO_MASTER}", PO_MASTER)
            if n is not None: deleted[PO_MASTER] = n

        # 4. Reset auto-increment counters (full wipe only) — only for tables that exist
        if not args.po_type and not args.no_reset_seq:
            if table_exists(cur, 'sqlite_sequence'):
                seq_targets = [PO_MASTER, GRN_MASTER] + PO_CHILDREN + GRN_CHILDREN + STOCK_TABLES
                seq_targets = [t for t in seq_targets if table_exists(cur, t)]
                cur.executemany(
                    "DELETE FROM sqlite_sequence WHERE name = ?",
                    [(t,) for t in seq_targets])
                print(f"✓ Reset auto-increment for {len(seq_targets)} tables")

        conn.commit()
        print("\n✓ Commit successful.")

    except Exception as e:
        conn.rollback()
        print(f"\n✗ ERROR — rolled back: {e}")
        conn.close()
        sys.exit(2)

    # ── Summary ──
    print("\n── DELETED ROWS ──")
    total = 0
    for tbl, n in deleted.items():
        print(f"  {tbl:<40} : {n}")
        total += n
    print(f"  {'TOTAL':<40} : {total}")

    if skipped:
        print("\n── SKIPPED (table does not exist) ──")
        for t in skipped:
            print(f"  {t}")

    print_counts(cur, "AFTER", po_filter, grn_filter)

    conn.close()
    print("\nDone. Restart Flask app (or just refresh the page) to see the empty lists.")


if __name__ == '__main__':
    main()
