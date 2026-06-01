#!/usr/bin/env python3
"""
clean_po_grn_stock_mysql.py
===========================
Deletes ALL Purchase Orders, ALL GRNs, and related stock data
(stock ledger + batch on-hand) from the HCP ERP MySQL database.

⚠️  DESTRUCTIVE — there is NO undo from inside the app.
    Script writes a timestamped .sql backup of affected tables
    before touching anything; restore by:
        mysql -u root -p erpdb < <backup_file>.sql

USAGE:
    python3 clean_po_grn_stock_mysql.py
    python3 clean_po_grn_stock_mysql.py --yes
    python3 clean_po_grn_stock_mysql.py --po-type RM
    python3 clean_po_grn_stock_mysql.py --host localhost --user root \\
                                         --password 'Krunal@2424' --db erpdb
    python3 clean_po_grn_stock_mysql.py --no-backup       # NOT recommended
    python3 clean_po_grn_stock_mysql.py --no-reset-seq    # keep AUTO_INCREMENT
"""

import argparse
import os
import subprocess
import sys
from datetime import datetime

try:
    import pymysql
except ImportError:
    print("✗ pymysql not installed. Run:  pip install pymysql")
    sys.exit(1)


# Defaults (match your config.py — override on CLI if different)
DEFAULTS = dict(
    host='localhost',
    port=3306,
    user='root',
    password='Krunal@2424',
    db='erpdb',
)

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

ALL_TABLES = [PO_MASTER] + PO_CHILDREN + [GRN_MASTER] + GRN_CHILDREN + STOCK_TABLES


# ───────────────────────────────────────────────────────────────────
def table_exists(cur, db, name):
    cur.execute(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_schema=%s AND table_name=%s", (db, name))
    return cur.fetchone() is not None


def row_count(cur, name, where=''):
    sql = f"SELECT COUNT(*) FROM `{name}`"
    if where:
        sql += f" WHERE {where}"
    try:
        cur.execute(sql)
        return cur.fetchone()[0]
    except pymysql.err.ProgrammingError:
        return None


def _fmt(n):
    return '— (table not in DB)' if n is None else str(n)


def print_counts(cur, db, label, po_filter='', grn_filter=''):
    print(f"\n── {label} ──")
    for t in ALL_TABLES:
        if not table_exists(cur, db, t):
            print(f"  {t:<40} : {_fmt(None)}")
            continue
        if   t == PO_MASTER:  print(f"  {t:<40} : {row_count(cur, t, po_filter)}")
        elif t == GRN_MASTER: print(f"  {t:<40} : {row_count(cur, t, grn_filter)}")
        else:                 print(f"  {t:<40} : {row_count(cur, t)}")


def backup_with_mysqldump(host, port, user, password, db, tables, out_path):
    """Try mysqldump first; if not on PATH, return False so caller falls back."""
    cmd = ['mysqldump', f'-h{host}', f'-P{port}', f'-u{user}',
           f'-p{password}', '--single-transaction', '--no-tablespaces',
           db] + tables
    try:
        with open(out_path, 'w') as f:
            r = subprocess.run(cmd, stdout=f, stderr=subprocess.PIPE, timeout=120)
        if r.returncode != 0:
            os.remove(out_path)
            print(f"  mysqldump error: {r.stderr.decode(errors='replace').strip()[:200]}")
            return False
        return True
    except FileNotFoundError:
        return False
    except Exception as e:
        print(f"  mysqldump failed: {e}")
        return False


def backup_with_python(conn, cur, db, tables, out_path):
    """Fallback: write INSERT statements for affected tables."""
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(f"-- HCP ERP backup before clean_po_grn_stock\n")
        f.write(f"-- {datetime.now().isoformat()}\n")
        f.write(f"-- Restore:  mysql -u root -p {db} < {os.path.basename(out_path)}\n\n")
        f.write("SET FOREIGN_KEY_CHECKS=0;\n\n")
        for t in tables:
            if not table_exists(cur, db, t):
                continue
            cur.execute(f"SELECT * FROM `{t}`")
            rows = cur.fetchall()
            cols = [d[0] for d in cur.description]
            f.write(f"-- {t}: {len(rows)} rows\n")
            if not rows:
                continue
            col_list = ', '.join(f'`{c}`' for c in cols)
            for r in rows:
                vals = []
                for v in r:
                    if   v is None:           vals.append('NULL')
                    elif isinstance(v, bool): vals.append('1' if v else '0')
                    elif isinstance(v, (int, float)): vals.append(str(v))
                    else:
                        s = str(v).replace('\\', '\\\\').replace("'", "\\'")
                        vals.append(f"'{s}'")
                f.write(f"INSERT INTO `{t}` ({col_list}) VALUES ({', '.join(vals)});\n")
            f.write("\n")
        f.write("SET FOREIGN_KEY_CHECKS=1;\n")
    return True


# ───────────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="Delete all POs, GRNs, and related stock from HCP ERP MySQL DB.")
    ap.add_argument('--host',     default=DEFAULTS['host'])
    ap.add_argument('--port',     default=DEFAULTS['port'], type=int)
    ap.add_argument('--user',     default=DEFAULTS['user'])
    ap.add_argument('--password', default=DEFAULTS['password'])
    ap.add_argument('--db',       default=DEFAULTS['db'])
    ap.add_argument('--po-type',  default=None,
                    help="Only delete POs of this type (e.g. RM, PM, FG).")
    ap.add_argument('--yes',           action='store_true', help="Skip confirmation.")
    ap.add_argument('--no-backup',     action='store_true', help="Skip backup (NOT recommended).")
    ap.add_argument('--no-reset-seq',  action='store_true', help="Do not reset AUTO_INCREMENT.")
    args = ap.parse_args()

    print(f"Connecting to mysql://{args.user}@{args.host}:{args.port}/{args.db} ...")
    try:
        conn = pymysql.connect(
            host=args.host, port=args.port, user=args.user,
            password=args.password, db=args.db, autocommit=False,
            charset='utf8mb4')
    except Exception as e:
        print(f"✗ Connection failed: {e}")
        sys.exit(1)
    cur = conn.cursor()
    print("✓ Connected")

    # ── Filters ──
    po_filter  = ''
    grn_filter = ''
    if args.po_type:
        pt = args.po_type.strip().upper().replace("'", "''")
        po_filter  = f"po_type = '{pt}'"
        grn_filter = (f"po_id IN (SELECT id FROM `{PO_MASTER}` "
                      f"WHERE po_type = '{pt}')")
        print(f"⚠  Filter: po_type = {pt}")
    else:
        print("⚠  No filter — will delete ALL POs, ALL GRNs, ALL stock.")

    print_counts(cur, args.db, "BEFORE", po_filter, grn_filter)

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
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        suffix = f"_{args.po_type.upper()}" if args.po_type else ""
        out_path = f"erpdb_backup_po_grn{suffix}_{ts}.sql"
        existing = [t for t in ALL_TABLES if table_exists(cur, args.db, t)]
        print(f"Creating backup → {out_path}")
        ok = backup_with_mysqldump(args.host, args.port, args.user,
                                   args.password, args.db, existing, out_path)
        if not ok:
            print("  mysqldump not available — using Python fallback")
            backup_with_python(conn, cur, args.db, existing, out_path)
        sz = os.path.getsize(out_path) / 1024
        print(f"✓ Backup saved   : {out_path}  ({sz:,.1f} KB)")
    else:
        print("⚠  Skipped backup (--no-backup)")

    # ── Resolve target IDs (filtered case) ──
    po_ids = grn_ids = None
    if args.po_type:
        cur.execute(f"SELECT id FROM `{PO_MASTER}` WHERE {po_filter}")
        po_ids = [r[0] for r in cur.fetchall()]
        cur.execute(f"SELECT id FROM `{GRN_MASTER}` WHERE {grn_filter}")
        grn_ids = [r[0] for r in cur.fetchall()]
        print(f"  → {len(po_ids)} POs and {len(grn_ids)} GRNs match the filter")

    def in_clause(ids):
        return '(' + ','.join(str(i) for i in ids) + ')'

    deleted = {}
    skipped = []

    def safe_delete(sql, table_for_log):
        if not table_exists(cur, args.db, table_for_log):
            skipped.append(table_for_log)
            return None
        cur.execute(sql)
        return cur.rowcount

    try:
        # Disable FK checks while wiping
        cur.execute("SET FOREIGN_KEY_CHECKS = 0")

        # 1. STOCK
        if args.po_type and grn_ids:
            n = safe_delete(
                f"DELETE FROM `tbl_grn_stock_ledger` "
                f"WHERE txn_ref_type='GRN' AND txn_ref_id IN {in_clause(grn_ids)}",
                'tbl_grn_stock_ledger')
            if n is not None: deleted['tbl_grn_stock_ledger'] = n
            # Batch stock: remove orphans (no longer referenced by any ledger row)
            if table_exists(cur, args.db, 'tbl_grn_stock_ledger'):
                n = safe_delete(
                    "DELETE FROM `tbl_grn_batch_stock` "
                    "WHERE (material_id, batch_no, COALESCE(location_id,-1)) NOT IN ("
                    "  SELECT material_id, batch_no, COALESCE(location_id,-1) "
                    "  FROM `tbl_grn_stock_ledger`)",
                    'tbl_grn_batch_stock')
            else:
                n = safe_delete("DELETE FROM `tbl_grn_batch_stock`",
                                'tbl_grn_batch_stock')
            if n is not None: deleted['tbl_grn_batch_stock'] = n
        elif not args.po_type:
            n = safe_delete("DELETE FROM `tbl_grn_stock_ledger`", 'tbl_grn_stock_ledger')
            if n is not None: deleted['tbl_grn_stock_ledger'] = n
            n = safe_delete("DELETE FROM `tbl_grn_batch_stock`",  'tbl_grn_batch_stock')
            if n is not None: deleted['tbl_grn_batch_stock'] = n

        # 2. GRN children + master
        if args.po_type and grn_ids:
            for t in GRN_CHILDREN:
                n = safe_delete(f"DELETE FROM `{t}` WHERE grn_id IN {in_clause(grn_ids)}", t)
                if n is not None: deleted[t] = n
            n = safe_delete(f"DELETE FROM `{GRN_MASTER}` WHERE id IN {in_clause(grn_ids)}",
                            GRN_MASTER)
            if n is not None: deleted[GRN_MASTER] = n
        elif not args.po_type:
            for t in GRN_CHILDREN:
                n = safe_delete(f"DELETE FROM `{t}`", t)
                if n is not None: deleted[t] = n
            n = safe_delete(f"DELETE FROM `{GRN_MASTER}`", GRN_MASTER)
            if n is not None: deleted[GRN_MASTER] = n

        # 3. PO children + master
        if args.po_type and po_ids:
            for t in PO_CHILDREN:
                n = safe_delete(f"DELETE FROM `{t}` WHERE po_id IN {in_clause(po_ids)}", t)
                if n is not None: deleted[t] = n
            n = safe_delete(f"DELETE FROM `{PO_MASTER}` WHERE id IN {in_clause(po_ids)}",
                            PO_MASTER)
            if n is not None: deleted[PO_MASTER] = n
        elif not args.po_type:
            for t in PO_CHILDREN:
                n = safe_delete(f"DELETE FROM `{t}`", t)
                if n is not None: deleted[t] = n
            n = safe_delete(f"DELETE FROM `{PO_MASTER}`", PO_MASTER)
            if n is not None: deleted[PO_MASTER] = n

        # 4. Reset AUTO_INCREMENT counters (full wipe only)
        if not args.po_type and not args.no_reset_seq:
            for t in ALL_TABLES:
                if table_exists(cur, args.db, t):
                    cur.execute(f"ALTER TABLE `{t}` AUTO_INCREMENT = 1")
            print("✓ Reset AUTO_INCREMENT on existing tables")

        cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        conn.commit()
        print("\n✓ Commit successful.")

    except Exception as e:
        conn.rollback()
        try: cur.execute("SET FOREIGN_KEY_CHECKS = 1")
        except: pass
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

    print_counts(cur, args.db, "AFTER", po_filter, grn_filter)

    conn.close()
    print("\nDone. Refresh the browser (Ctrl+Shift+R) to see empty lists.")


if __name__ == '__main__':
    main()
