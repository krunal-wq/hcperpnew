"""
setup_qc_module.py — One-shot setup for TRS + QC modules
=========================================================
This script does everything needed:

  1. Creates the tbl_trs_master table (if missing)
  2. Auto-registers trs_bp and qc_bp in index.py (idempotent, safe)
     - Makes a timestamped backup of index.py first
     - Detects what's already there, only adds what's missing
     - Verifies Python syntax after edits → restores on failure
  3. Verifies the model file is in place
  4. Prints a clear summary of what was done

Run from project root:

    python setup_qc_module.py

Safe to re-run any number of times.
"""

import os
import sys
import shutil
import py_compile
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

HERE  = os.path.dirname(os.path.abspath(__file__))
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; E = "\033[0m"
def ok(m):    print(f"  {G}[OK] {m}{E}")
def warn(m):  print(f"  {Y}[!]  {m}{E}")
def err(m):   print(f"  {R}[X] {m}{E}")
def step(t):  print(f"\n{B}{t}{E}")


def header(t):
    print(f"\n{'=' * 64}")
    print(f"  {B}{t}{E}")
    print(f"{'=' * 64}")


# ──────────────────────────────────────────────────────────────────────
# Step 0 — Required files check
# ──────────────────────────────────────────────────────────────────────
def check_required_files():
    step("[1/4] Checking required files…")
    required = {
        'models/trs.py':                 'TRS model',
        'trs_routes.py':                 'TRS routes blueprint',
        'qc_routes.py':                  'QC routes blueprint',
        'templates/trs/index.html':      'TRS items listing template',
        'templates/trs/form.html':       'TRS form template',
        'templates/trs/certificate.html':'TRS certificate template',
        'templates/qc/trs_list.html':    'QC TRS list template',
        'index.py':                      'Flask app entry point',
    }
    missing = []
    for path, label in required.items():
        full = os.path.join(HERE, path)
        if os.path.exists(full):
            ok(f"{path}  ({label})")
        else:
            err(f"MISSING: {path}  ({label})")
            missing.append(path)
    if missing:
        print()
        err("Some files are missing. Extract the ZIP into the project root")
        err("preserving the folder structure, then re-run this script.")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────
# Step 1 — Patch index.py to register the blueprints
# ──────────────────────────────────────────────────────────────────────
TRS_IMPORT  = "from trs_routes import trs_bp           # TRS (Testing Requisition Slip)"
TRS_REGSTR  = "app.register_blueprint(trs_bp)          # TRS (Testing Requisition Slip)"
QC_IMPORT   = "from qc_routes  import qc_bp            # QC Module (TRS lists, approvals)"
QC_REGSTR   = "app.register_blueprint(qc_bp)           # QC Module (TRS lists, approvals)"

# Anchors used to locate sensible insertion points in index.py
IMPORT_ANCHOR   = "from grn_routes import grn_bp"
REGISTER_ANCHOR = "app.register_blueprint(grn_bp)"


def patch_index_py():
    step("[2/4] Patching index.py (registering blueprints)…")
    idx = os.path.join(HERE, 'index.py')
    src = open(idx, 'r', encoding='utf-8').read()

    # Detect what's already there
    has_trs_import = 'from trs_routes' in src
    has_qc_import  = 'from qc_routes'  in src
    has_trs_reg    = 'register_blueprint(trs_bp)' in src
    has_qc_reg     = 'register_blueprint(qc_bp)'  in src

    if has_trs_import and has_qc_import and has_trs_reg and has_qc_reg:
        ok("All 4 lines already present in index.py — nothing to do.")
        return

    # ── Make a backup ──
    bak = f'{idx}.bak_{STAMP}'
    shutil.copy2(idx, bak)
    ok(f"Backup → {os.path.basename(bak)}")

    new = src

    # ── Add imports just after the grn_routes import ──
    if IMPORT_ANCHOR not in new:
        err(f'Anchor not found in index.py: "{IMPORT_ANCHOR}"')
        err('Cannot safely patch — please add the lines manually (see README).')
        return

    lines_to_add = []
    if not has_trs_import:
        lines_to_add.append(TRS_IMPORT)
    if not has_qc_import:
        lines_to_add.append(QC_IMPORT)
    if lines_to_add:
        # Find the line that contains the anchor and insert AFTER it
        idx_lines = new.splitlines(keepends=True)
        for i, ln in enumerate(idx_lines):
            if IMPORT_ANCHOR in ln:
                # Preserve trailing newline of the anchor line
                indent = ''
                add = ''.join(indent + a + '\n' for a in lines_to_add)
                idx_lines.insert(i + 1, add)
                break
        new = ''.join(idx_lines)
        ok(f"Added {len(lines_to_add)} import line(s)")

    # ── Add register_blueprint calls just after grn_bp register ──
    reg_to_add = []
    if not has_trs_reg:
        reg_to_add.append(TRS_REGSTR)
    if not has_qc_reg:
        reg_to_add.append(QC_REGSTR)
    if reg_to_add:
        if REGISTER_ANCHOR not in new:
            err(f'Anchor not found in index.py: "{REGISTER_ANCHOR}"')
            err('Cannot safely patch — please add the register_blueprint lines manually.')
            shutil.copy2(bak, idx)   # rollback
            return
        idx_lines = new.splitlines(keepends=True)
        for i, ln in enumerate(idx_lines):
            if REGISTER_ANCHOR in ln:
                add = ''.join(a + '\n' for a in reg_to_add)
                idx_lines.insert(i + 1, add)
                break
        new = ''.join(idx_lines)
        ok(f"Added {len(reg_to_add)} register_blueprint line(s)")

    # ── Write + syntax check ──
    open(idx, 'w', encoding='utf-8').write(new)
    try:
        py_compile.compile(idx, doraise=True)
        ok("Python syntax OK on patched index.py")
    except py_compile.PyCompileError as e:
        shutil.copy2(bak, idx)   # rollback
        err("Syntax error after patch — restored from backup.")
        err(f"  Error: {e}")
        sys.exit(1)


# ──────────────────────────────────────────────────────────────────────
# Step 2 — Create the TRS table
# ──────────────────────────────────────────────────────────────────────
def create_table():
    step("[3/4] Creating database table tbl_trs_master…")
    try:
        from index import app
        from models import db
        from models.trs import TrsMaster
    except Exception as e:
        err(f"Could not import app/models: {e}")
        err("  Make sure Flask app loads cleanly (check syntax of all modules).")
        sys.exit(1)

    with app.app_context():
        inspector = db.inspect(db.engine)
        if 'tbl_trs_master' in inspector.get_table_names():
            warn("Table tbl_trs_master already exists — skipping create.")
        else:
            try:
                TrsMaster.__table__.create(bind=db.engine, checkfirst=True)
                ok("Table tbl_trs_master created.")
            except Exception as e:
                err(f"Create failed: {e}")
                sys.exit(1)

        try:
            n = TrsMaster.query.filter_by(is_deleted=False).count()
            ok(f"Table is accessible. Existing TRS records: {n}")
        except Exception as e:
            warn(f"Could not query table: {e}")


# ──────────────────────────────────────────────────────────────────────
# Step 3 — Final summary
# ──────────────────────────────────────────────────────────────────────
def final_summary():
    step("[4/4] Summary")
    print()
    print(f"  {G}Setup complete.{E}")
    print()
    print("  Next steps:")
    print("    1. Restart Flask (Ctrl+C, then  python .\\index.py)")
    print("    2. Sidebar: 'Quality Control' group appears with")
    print("         - RM TRS List   (-> /qc/trs/rm)")
    print("         - PM TRS List   (-> /qc/trs/pm)")
    print("    3. In any RM/PM GRN view, hamburger menu shows 'TRS'")
    print("    4. Per item: + Create TRS -> form -> Save -> certificate")
    print("    5. Re-open an item with existing TRS -> form auto-loads saved data")
    print()
    print(f"  Rollback: restore the .bak_{STAMP} files inside the project.")
    print()


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────
def main():
    header("TRS + QC Module \u2014 One-shot setup")
    print(f"  Project root: {HERE}")

    check_required_files()
    patch_index_py()
    create_table()
    final_summary()


if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(1)
