"""
apply_checklist_patch.py
═══════════════════════════════════════════════════════════════════════════════
Add an Item-wise "Check List Material Form" to RM GRN — printable, no DB.

Single-file patch. Just drop this into your project root (same folder as
grn_routes.py and index.py) and run:

    python apply_checklist_patch.py

The script will:
  1. Create templates/grn/checklist.html  (template embedded inside this script)
  2. Add the /grn/<id>/checklist route to grn_routes.py — in the right place
  3. Add the "📝 Check List" button to templates/grn/view.html (RM type only)
  4. Make timestamped .bak backups + verify Python syntax

Self-healing — detects + removes any earlier misplaced paste automatically.
Idempotent — safe to re-run.

Restart Flask after running. Done.
═══════════════════════════════════════════════════════════════════════════════
"""
import os
import sys
import ast
import shutil
import py_compile
from datetime import datetime

HERE   = os.path.dirname(os.path.abspath(__file__))
STAMP  = datetime.now().strftime("%Y%m%d_%H%M%S")

ROUTES_FILE = os.path.join(HERE, "grn_routes.py")
VIEW_HTML   = os.path.join(HERE, "templates", "grn", "view.html")
TARGET_TPL  = os.path.join(HERE, "templates", "grn", "checklist.html")


# ═══════════════════════════════════════════════════════════════════════
# EMBEDDED TEMPLATE — written to templates/grn/checklist.html
# ═══════════════════════════════════════════════════════════════════════
CHECKLIST_TEMPLATE = r"""{% extends 'base.html' %}
{% block title %}Check List Material Form — {{ grn.grn_number }}{% endblock %}
{% block page_title %}📝 Check List Material Form{% endblock %}
{% block bread %}Stores / GRN / {{ grn.grn_number_short or grn.grn_number }} / Check List{% endblock %}

{% block extra_css %}
<style>
/* Top control bar (hidden on print) */
.cl-controls {
  padding: 14px; background: #fff; border-radius: 10px;
  border: 1px solid #e2e8f0; margin-bottom: 18px;
  display: flex; gap: 12px; align-items: center; flex-wrap: wrap;
}
.cl-controls .info  { font-size: 13px; color: #475569; flex: 1; }
.cl-controls .info b { color: #0f172a; }
.cl-controls .cl-btn,
.cl-controls .cl-back {
  padding: 9px 18px; border-radius: 7px; font-size: 13px;
  font-weight: 700; cursor: pointer; border: 0;
  text-decoration: none; display: inline-block;
}
.cl-controls .cl-btn  { background: #16a34a; color: #fff; }
.cl-controls .cl-back { background: #fff; color: #475569; border: 1.5px solid #cbd5e1; }

/* Print area + form card (A4 portrait, one per item, one per page) */
.cl-print-area { background: transparent; }

.cl-form {
  width: 190mm;
  min-height: 270mm;
  margin: 0 auto 14mm auto;
  padding: 15mm 14mm;
  background: #fff;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  box-shadow: 0 1px 3px rgba(15,23,42,.06);
  font-family: Arial, Helvetica, sans-serif;
  color: #1e293b;
  box-sizing: border-box;
  page-break-after: always;
}
.cl-form:last-child { page-break-after: auto; }

.cl-head { display: flex; align-items: center; gap: 22px; padding-bottom: 14px; }
.cl-head .cl-logo { width: 70px; height: 70px; object-fit: contain; flex-shrink: 0; }
.cl-head .cl-title {
  flex: 1; text-align: center;
  font-size: 28pt; font-weight: 800;
  color: #1f2937; letter-spacing: .3px;
}

.cl-info { width: 100%; border-collapse: collapse; margin-top: 6px; font-size: 13pt; }
.cl-info td { padding: 7px 4px; vertical-align: top; }
.cl-info td.k { width: 32%; font-weight: 700; color: #1f2937; white-space: nowrap; }
.cl-info td.v { color: #334155; font-weight: 500; word-break: break-word; }

.cl-rule { border: 0; border-top: 1px solid #94a3b8; margin: 18px 0 14px 0; }

.cl-h2 {
  font-size: 18pt; font-weight: 800; color: #1f2937;
  text-decoration: underline; text-underline-offset: 4px;
  margin: 4px 0 16px 0;
}

.cl-boxes { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
.cl-box {
  border: 1px solid #cbd5e1; border-radius: 6px;
  padding: 14px 16px; min-height: 130px; background: #fff;
}
.cl-box-title { font-size: 14pt; font-weight: 800; color: #1f2937; margin-bottom: 10px; }
.cl-box-row {
  display: flex; align-items: center; gap: 8px;
  font-size: 12pt; color: #334155; padding: 5px 0;
}
.cl-chk {
  width: 14px; height: 14px;
  border: 1.5px solid #475569; border-radius: 2px;
  display: inline-block; flex-shrink: 0; background: #fff;
}

.cl-foot {
  margin-top: 28px;
  display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px;
  font-size: 11pt; color: #475569;
}
.cl-foot .sig {
  border-top: 1px solid #94a3b8; padding-top: 6px;
  text-align: center; font-weight: 600;
}

.cl-empty {
  padding: 40px; text-align: center; color: #64748b;
  background: #fff; border-radius: 10px; border: 1px dashed #cbd5e1;
}

@media print {
  body * { visibility: hidden; }
  .cl-print-area, .cl-print-area * { visibility: visible; }
  .cl-print-area { position: absolute; left: 0; top: 0; width: 100%; }
  .cl-controls, .sidebar, .topbar, header, footer, nav { display: none !important; }

  .cl-form {
    width: 100%; min-height: auto;
    margin: 0; padding: 12mm 12mm;
    border: 0; border-radius: 0; box-shadow: none;
    page-break-after: always;
  }
  .cl-form:last-child { page-break-after: auto; }
  @page { size: A4 portrait; margin: 8mm; }
}
</style>
{% endblock %}

{% block content %}
<div class="cl-controls">
  <div class="info">
    <b>{{ grn.grn_number }}</b> — {{ items|length }} item(s) from
    <b>{{ grn.supplier_name or '—' }}</b>
    <div style="font-size:11px;color:#94a3b8;margin-top:3px;">
      One Check List form per item (A4 portrait). Print karke physically tick karein —
      data store nahi hota.
    </div>
  </div>
  <a href="{{ url_for('grn.view_grn', grn_id=grn.id) }}" class="cl-back">← Back to GRN</a>
  <button class="cl-btn" onclick="window.print()">🖨️ Print Check List</button>
</div>

<div class="cl-print-area">
  {% if items and items|length > 0 %}
    {% for it in items %}
      {% set _packets = (it.no_of_boxes or 0)|float %}
      {% set _per_pkt = (it.per_box_qty or 0)|float %}
      {% set _computed_total = _packets * _per_pkt %}
      {% set _total = _computed_total if _computed_total > 0 else (it.received_qty or 0)|float %}
      {% set _uom = it.uom or '' %}

      <div class="cl-form">
        <div class="cl-head">
          <img class="cl-logo"
               src="{{ url_for('static', filename='images/icons/hcp-logo.png') }}"
               alt="HCP" onerror="this.style.display='none'">
          <div class="cl-title">Check List Material Form</div>
        </div>

        <table class="cl-info">
          <tr><td class="k">Item Name :</td>      <td class="v">{{ it.item_name or '—' }}</td></tr>
          <tr><td class="k">Supplier Name :</td>  <td class="v">{{ grn.supplier_name or '—' }}</td></tr>
          <tr><td class="k">GRN No :</td>         <td class="v">{{ grn.grn_number_short or grn.grn_number }}</td></tr>
          <tr><td class="k">Invoice No :</td>     <td class="v">{{ grn.invoice_no or '—' }}</td></tr>
          <tr><td class="k">No. of Packet :</td>  <td class="v">{{ '%.3f'|format(_packets) }}</td></tr>
          <tr><td class="k">Per Pkt. Qty. :</td>  <td class="v">{{ '%.3f'|format(_per_pkt) }}{% if _uom %} {{ _uom }}{% endif %}</td></tr>
          <tr><td class="k">Total Qty. :</td>     <td class="v">{{ '%.3f'|format(_total) }}{% if _uom %} {{ _uom }}{% endif %}</td></tr>
        </table>

        <hr class="cl-rule">

        <div class="cl-h2">Check List :</div>

        <div class="cl-boxes">
          <div class="cl-box">
            <div class="cl-box-title">Quality Check</div>
            <div class="cl-box-row"><span class="cl-chk"></span>Test Certificate</div>
            <div class="cl-box-row"><span class="cl-chk"></span>Batch On Product</div>
          </div>
          <div class="cl-box">
            <div class="cl-box-title">Physical Verification</div>
            <div class="cl-box-row"><span class="cl-chk"></span>Physical Condition</div>
            <div class="cl-box-row"><span class="cl-chk"></span>Expiry Date</div>
          </div>
          <div class="cl-box">
            <div class="cl-box-title">Other</div>
            <div class="cl-box-row"><span class="cl-chk"></span>Lable</div>
            <div class="cl-box-row"><span class="cl-chk"></span>Rejection Remarks</div>
          </div>
        </div>

        <div class="cl-foot">
          <div class="sig">Checked By</div>
          <div class="sig">Verified By</div>
          <div class="sig">Approved By</div>
        </div>
      </div>
    {% endfor %}
  {% else %}
    <div class="cl-empty">No items found in this GRN.</div>
  {% endif %}
</div>
{% endblock %}
"""


# ═══════════════════════════════════════════════════════════════════════
# THE NEW ROUTE — inserted into grn_routes.py
# ═══════════════════════════════════════════════════════════════════════
NEW_ROUTE = '''
# ═════════════════════════════════════════════════════════════════════════════
# CHECK LIST MATERIAL FORM — Item-wise printable checklist (no data stored)
# ═════════════════════════════════════════════════════════════════════════════
@grn_bp.route('/<int:grn_id>/checklist')
@login_required
def checklist_grn(grn_id):
    """Print item-wise Check List Material Form for an RM GRN.

    Nothing is stored — the form is rendered from existing GRN/item data
    and is meant to be printed on paper and physically ticked.
    """
    if not _can('view'):
        abort(403)
    grn = GrnMaster.query.get_or_404(grn_id)
    if grn.is_deleted:
        abort(404)
    items = grn.items.order_by(GrnItem.sr_no).all()
    return render_template('grn/checklist.html',
                           active_page='grn',
                           grn=grn,
                           items=items)


'''

ROUTES_ANCHOR = "# ═════ Excel Export ═════"

BUTTON_ANCHOR = (
    '<a class="gv-act outline" '
    'href="{{ url_for(\'grn.labels_grn\', grn_id=grn.id) }}" '
    'target="_blank">🏷️ Print Labels</a>'
)

NEW_BUTTON = '''
    {% if grn.grn_type == 'RM' %}
    <a class="gv-act outline" href="{{ url_for('grn.checklist_grn', grn_id=grn.id) }}" target="_blank">📝 Check List</a>
    {% endif %}'''


# ═══════════════════════════════════════════════════════════════════════
# Tiny helpers
# ═══════════════════════════════════════════════════════════════════════
def ok(msg):    print(f"  ✓ {msg}")
def warn(msg):  print(f"  ⚠ {msg}")
def fail(msg):
    print(f"  ✗ {msg}")
    sys.exit(1)

def read(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()

def write(path, content):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)

def backup(path):
    bak = f"{path}.bak_{STAMP}"
    shutil.copy2(path, bak)
    ok(f"Backup → {os.path.basename(bak)}")


# ═══════════════════════════════════════════════════════════════════════
# Step 1 — Write the template directly into templates/grn/
# ═══════════════════════════════════════════════════════════════════════
def step1_write_template():
    print("\n[1/3] Writing templates/grn/checklist.html …")
    os.makedirs(os.path.dirname(TARGET_TPL), exist_ok=True)
    if os.path.exists(TARGET_TPL):
        warn("templates/grn/checklist.html already exists — overwriting.")
        backup(TARGET_TPL)
    write(TARGET_TPL, CHECKLIST_TEMPLATE)
    ok(f"Wrote {TARGET_TPL}")


# ═══════════════════════════════════════════════════════════════════════
# Step 2 — Add route to grn_routes.py (self-healing)
#
# Detection works by DECORATOR pattern, not function name. So even if the
# previously-pasted function was renamed/typo'd, we still find and remove it.
# ═══════════════════════════════════════════════════════════════════════
CHECKLIST_DECORATOR = "@grn_bp.route('/<int:grn_id>/checklist')"


def _find_all_checklist_blocks(src):
    """Find ALL @grn_bp.route('/<int:grn_id>/checklist') blocks in the file.

    Returns list of (start_line, end_line) 1-based inclusive ranges.
    Each range covers:
      - any banner-style `#` comment block immediately above
      - all decorators above the def
      - the def line + entire indented function body
    Works regardless of the function's name.
    """
    lines = src.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        if CHECKLIST_DECORATOR in lines[i]:
            # ── Walk BACKWARD: pull in preceding decorators and # banner ──
            start = i
            while start > 0:
                prev = lines[start - 1]
                stripped = prev.lstrip()
                if stripped.startswith('@'):
                    start -= 1
                elif stripped.startswith('#'):
                    # Comment line — include it
                    start -= 1
                elif prev.strip() == '':
                    # Blank line — peek above; include only if banner continues
                    if start >= 2 and lines[start - 2].lstrip().startswith('#'):
                        start -= 1
                    else:
                        break
                else:
                    break

            # Trim leading blank lines back off
            while start < i and lines[start].strip() == '':
                start += 1

            # ── Walk FORWARD: skip more decorators, find def, walk body ──
            j = i
            while j + 1 < len(lines) and lines[j + 1].lstrip().startswith('@'):
                j += 1
            # Next line should be a def / async def / class
            end = j
            if j + 1 < len(lines):
                next_stripped = lines[j + 1].lstrip()
                if (next_stripped.startswith('def ')
                        or next_stripped.startswith('async def ')
                        or next_stripped.startswith('class ')):
                    end = j + 1  # include the def line
                    # Walk through indented body
                    while end + 1 < len(lines):
                        ln = lines[end + 1]
                        if ln.strip() == '':
                            end += 1
                            continue
                        if ln[0] in (' ', '\t'):
                            end += 1
                            continue
                        break
                    # Trim trailing blank lines off the block
                    while end > j + 1 and lines[end].strip() == '':
                        end -= 1

            blocks.append((start + 1, end + 1))  # 1-based inclusive
            i = end + 1
        else:
            i += 1
    return blocks


def _grn_bp_line(src):
    """Find the line where grn_bp = Blueprint(...) is assigned.

    Very lenient — handles leading whitespace, comments, alternate quoting.
    Returns None if not found.
    """
    import re as _re
    pat = _re.compile(r'^\s*grn_bp\s*=\s*Blueprint\s*\(')
    for i, ln in enumerate(src.splitlines(), 1):
        if pat.match(ln):
            return i
    return None


def _diagnostic_grn_bp(src):
    """Print every line that mentions grn_bp or Blueprint so the user can
    paste the output if the auto-detection misses their file's format."""
    print('  Diagnostic — searching for grn_bp / Blueprint references:')
    found = False
    for i, ln in enumerate(src.splitlines(), 1):
        if 'Blueprint' in ln or 'grn_bp' in ln:
            preview = ln.rstrip()[:110]
            print(f'    line {i:>5}: {preview}')
            found = True
            if i > 200:  # only show context near the top
                break
    if not found:
        print('    (none found — file may be empty or severely damaged)')
    print()


def step2_add_route():
    print("\n[2/3] Adding route to grn_routes.py …")
    if not os.path.exists(ROUTES_FILE):
        fail(f"grn_routes.py not found at: {ROUTES_FILE}\n"
             f"      Run this script from your project root folder.")

    src = read(ROUTES_FILE)
    blocks  = _find_all_checklist_blocks(src)
    bp_line = _grn_bp_line(src)

    if bp_line is None:
        warn("Could not auto-detect 'grn_bp = Blueprint(...)' line.")
        _diagnostic_grn_bp(src)
        warn("Proceeding anyway — will remove ALL existing checklist blocks "
             "and insert one fresh copy at the anchor (which is well past "
             "any Blueprint definition).")
        # Treat all existing blocks as needing removal
        misplaced = blocks
        correct   = []
    else:
        # ── Classify each block as misplaced (before grn_bp) or correctly placed ──
        misplaced = [b for b in blocks if b[0] < bp_line]
        correct   = [b for b in blocks if b[0] >= bp_line]

    if blocks:
        ranges_str = ', '.join(f'{a}-{b}' for a, b in blocks)
        print(f'  ℹ Found {len(blocks)} existing checklist block(s) at lines: {ranges_str}')
        if misplaced and bp_line is not None:
            print(f'  ⚠ {len(misplaced)} block(s) are BEFORE grn_bp (line {bp_line}) — will remove.')

    # ── If exactly one correctly-placed block exists and no misplaced — skip insert ──
    if len(correct) == 1 and not misplaced:
        warn(f"Route already present at correct location (lines "
             f"{correct[0][0]}-{correct[0][1]}). Nothing to do.")
        return

    # ── Otherwise: remove ALL existing blocks, then do a clean insert ──
    if blocks:
        backup(ROUTES_FILE)
        lines = src.splitlines(keepends=True)
        # Remove from BOTTOM up so line numbers don't shift
        for start, end in sorted(blocks, key=lambda b: -b[0]):
            # Convert back to 0-based slice
            del lines[start - 1:end]
            # Also strip a single trailing blank line if it was left behind
            if start - 1 < len(lines) and lines[start - 1].strip() == '':
                del lines[start - 1]
        src = ''.join(lines)
        write(ROUTES_FILE, src)
        ok(f'Removed {len(blocks)} existing block(s)')

    # ── Now insert at the anchor ──
    if ROUTES_ANCHOR not in src:
        fail(f'Anchor not found in grn_routes.py:\n      "{ROUTES_ANCHOR}"')
    if src.count(ROUTES_ANCHOR) > 1:
        fail(f'Anchor "{ROUTES_ANCHOR}" appears more than once — ambiguous.')

    bak_path = f"{ROUTES_FILE}.bak_{STAMP}"
    if not os.path.exists(bak_path):
        backup(ROUTES_FILE)

    new_src = src.replace(ROUTES_ANCHOR, NEW_ROUTE + ROUTES_ANCHOR, 1)
    write(ROUTES_FILE, new_src)

    # ── Verify syntax + verify no more misplaced decorators ──
    try:
        py_compile.compile(ROUTES_FILE, doraise=True)
    except py_compile.PyCompileError as e:
        shutil.copy2(bak_path, ROUTES_FILE)
        fail(f"Syntax error after insert — restored original.\n      Error: {e}")

    # Final sanity check
    final = read(ROUTES_FILE)
    final_blocks = _find_all_checklist_blocks(final)
    final_bp    = _grn_bp_line(final)
    if final_bp is not None:
        final_misp = [b for b in final_blocks if b[0] < final_bp]
        if final_misp:
            shutil.copy2(bak_path, ROUTES_FILE)
            fail(f"Misplaced block STILL present after insert — restored original.\n"
                 f"      Misplaced ranges: {final_misp}")
    if len(final_blocks) != 1:
        shutil.copy2(bak_path, ROUTES_FILE)
        fail(f"Expected exactly 1 checklist block after insert, found "
             f"{len(final_blocks)} — restored original.")

    ok('Python syntax OK')
    if final_bp is not None:
        ok(f'Route inserted at line {final_blocks[0][0]} (after grn_bp at line {final_bp})')
    else:
        ok(f'Route inserted at line {final_blocks[0][0]} (grn_bp not detected but anchor was used)')


# ═══════════════════════════════════════════════════════════════════════
# Step 3 — Add button to templates/grn/view.html
# ═══════════════════════════════════════════════════════════════════════
def step3_add_button():
    print("\n[3/3] Adding button to templates/grn/view.html …")
    if not os.path.exists(VIEW_HTML):
        fail(f"view.html not found at: {VIEW_HTML}")

    src = read(VIEW_HTML)

    if "url_for('grn.checklist_grn'" in src:
        warn("Check List button already present in view.html — skipping.")
        return

    if BUTTON_ANCHOR not in src:
        fail(f"Anchor not found in view.html:\n      {BUTTON_ANCHOR}")
    if src.count(BUTTON_ANCHOR) > 1:
        fail("Anchor appears more than once — ambiguous.")

    backup(VIEW_HTML)
    new_src = src.replace(BUTTON_ANCHOR, BUTTON_ANCHOR + NEW_BUTTON, 1)
    write(VIEW_HTML, new_src)
    ok("Button added (visible on RM type GRNs only)")


# ═══════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════
def main():
    print("═" * 72)
    print("Check List Material Form patch")
    print("═" * 72)
    print(f"Project root: {HERE}")

    step1_write_template()
    step2_add_route()
    step3_add_button()

    print("\n" + "═" * 72)
    print(" ✅  Patch applied successfully.")
    print("═" * 72)
    print("\n  Next steps:")
    print("    1. Restart your Flask app  (Ctrl+C → start again)")
    print("    2. Open any RM (Raw Material) GRN → click \"📝 Check List\"")
    print("    3. Click \"🖨️ Print Check List\" → A4 portrait, one page per item")
    print(f"\n  Rollback: restore the .bak_{STAMP} files.\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nAborted by user.")
        sys.exit(1)
