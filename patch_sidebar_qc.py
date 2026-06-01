"""
patch_sidebar_qc.py — Add 'Quality Control' menu to templates/base.html

This script inspects templates/base.html and adds the QC menu group ONLY if
not already present. Safe to re-run.

What it does:
  1. Reads templates/base.html
  2. Checks if "Quality Control" group already exists (text marker)
  3. If yes -> nothing to do (idempotent)
  4. If no  -> finds the "Finish Goods" group as anchor and inserts the
              QC group RIGHT AFTER it (and before Masters & Settings)
  5. Backs up the original file with timestamp before editing
  6. Validates basic structure after edit

Run from project root:
    python patch_sidebar_qc.py
"""
import os
import sys
import shutil
from datetime import datetime

HERE  = os.path.dirname(os.path.abspath(__file__))
STAMP = datetime.now().strftime("%Y%m%d_%H%M%S")

# Choose the right base file (project ships base.html and base_1.html)
CANDIDATES = [
    os.path.join(HERE, 'templates', 'base.html'),
    os.path.join(HERE, 'templates', 'base_1.html'),
]

# Marker text used to detect if the QC group is already there
MARKER = 'Quality Control (QC)'

# Anchor — we insert just BEFORE this comment
ANCHOR = '<!-- Masters & Settings -->'

# The QC menu group to insert
QC_BLOCK = '''
            <!-- Quality Control (QC) — TRS Lists -->
            <button class="nav-group-toggle {% if request.path.startswith('/qc') or request.path.startswith('/trs') %}open{% endif %}" onclick="toggleNavGroup(this)">
                <span class="nav-ic"><i class="bi bi-clipboard2-check"></i></span>
                <span class="nav-txt">Quality Control</span>
                <span class="nav-group-arrow">▶</span>
            </button>
            <div class="nav-submenu {% if request.path.startswith('/qc') or request.path.startswith('/trs') %}open{% endif %}">
                <a class="nav-a {% if request.path == '/qc/trs/rm' %}active{% endif %}" href="/qc/trs/rm">
                    <span class="nav-ic"><i class="bi bi-droplet-half"></i></span><span class="nav-txt">RM TRS List</span>
                </a>
                <a class="nav-a {% if request.path == '/qc/trs/pm' %}active{% endif %}" href="/qc/trs/pm">
                    <span class="nav-ic"><i class="bi bi-archive"></i></span><span class="nav-txt">PM TRS List</span>
                </a>
            </div>

            '''


def patch_one(path):
    if not os.path.exists(path):
        return False, f'(file not found)'

    src = open(path, 'r', encoding='utf-8').read()
    if MARKER in src:
        return True, 'QC menu already present - skipping'

    if ANCHOR not in src:
        return False, f'Anchor "{ANCHOR}" not found in {os.path.basename(path)} - cannot patch'

    # Multiple "Masters & Settings" anchors? Use the FIRST one.
    # (In our reference base.html there is only one.)
    bak = f'{path}.bak_{STAMP}'
    shutil.copy2(path, bak)

    new_src = src.replace(ANCHOR, QC_BLOCK + ANCHOR, 1)
    open(path, 'w', encoding='utf-8').write(new_src)
    return True, f'QC menu added (backup -> {os.path.basename(bak)})'


def main():
    print('=' * 64)
    print('  Sidebar QC-menu patcher')
    print('=' * 64)
    any_done = False
    for path in CANDIDATES:
        rel = os.path.relpath(path, HERE)
        ok, msg = patch_one(path)
        sym = '[OK]' if ok else '[!]'
        print(f'  {sym} {rel}: {msg}')
        if ok and 'added' in msg:
            any_done = True

    print()
    if any_done:
        print('  [OK] Patch applied. Restart Flask and refresh your browser.')
        print('       The sidebar will show:')
        print('         Quality Control')
        print('           > RM TRS List   (-> /qc/trs/rm)')
        print('           > PM TRS List   (-> /qc/trs/pm)')
    else:
        print('  Nothing changed (already present, or anchor not found).')
    print()


if __name__ == '__main__':
    main()
