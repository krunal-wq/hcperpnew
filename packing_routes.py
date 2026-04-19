"""
packing_routes.py — Packing Department Sample Receipt Log
Blueprint: packing  at  /packing
"""

from datetime import datetime, date
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from models import db, PackingEntry
from permissions import get_perm

packing = Blueprint('packing', __name__, url_prefix='/packing')


# ── helpers ───────────────────────────────────────────────────────────────────

def _can_view():
    if not current_user.is_authenticated:
        return False
    if current_user.role in ('admin', 'manager'):
        return True
    perm = get_perm('packing')
    return bool(perm and perm.can_view)


def _can_edit():
    if not current_user.is_authenticated:
        return False
    if current_user.role in ('admin', 'manager'):
        return True
    perm = get_perm('packing')
    return bool(perm and perm.can_edit)


def _can_delete():
    if not current_user.is_authenticated:
        return False
    if current_user.role == 'admin':
        return True
    perm = get_perm('packing')
    return bool(perm and perm.can_delete)


def _is_qc():
    return (getattr(current_user, 'role', '') or '').lower() in ('qc', 'qc_common')


def _parse_date(s):
    """Safely parse YYYY-MM-DD string to date, return None on failure."""
    if not s:
        return None
    try:
        return datetime.strptime(str(s).strip(), '%Y-%m-%d').date()
    except Exception:
        return None


# ── Page ──────────────────────────────────────────────────────────────────────

@packing.route('/')
@packing.route('')
@login_required
def packing_page():
    if not _can_view():
        from flask import abort
        abort(403)

    from_date = _parse_date(request.args.get('from', ''))
    to_date   = _parse_date(request.args.get('to', ''))

    # Default: current month
    if not from_date:
        today = date.today()
        from_date = date(today.year, today.month, 1)
    if not to_date:
        to_date = date.today()

    q = PackingEntry.query
    q = q.filter(PackingEntry.entry_date >= from_date)
    q = q.filter(PackingEntry.entry_date <= to_date)
    q = q.order_by(PackingEntry.entry_date.desc(), PackingEntry.id.desc())
    entries = q.all()

    # Brands for autocomplete
    try:
        brand_rows = db.session.execute(
            db.text("SELECT name, color FROM procurement_brands ORDER BY name ASC")
        ).fetchall()
        brands = [{'name': r[0], 'color': r[1]} for r in brand_rows]
    except Exception:
        brands = []

    return render_template(
        'packing/packing.html',
        active_page='packing',
        role=getattr(current_user, 'role', ''),
        user_name=getattr(current_user, 'full_name', '') or getattr(current_user, 'username', ''),
        entries=entries,
        brands=brands,
        from_date=from_date.strftime('%Y-%m-%d'),
        to_date=to_date.strftime('%Y-%m-%d'),
    )


# ── API: List ─────────────────────────────────────────────────────────────────

@packing.route('/api/list')
@login_required
def api_list():
    if not _can_view():
        return jsonify({'status': 'error', 'message': 'Access denied'}), 403
    try:
        from_date = _parse_date(request.args.get('from', ''))
        to_date   = _parse_date(request.args.get('to', ''))

        q = PackingEntry.query
        if from_date:
            q = q.filter(PackingEntry.entry_date >= from_date)
        if to_date:
            q = q.filter(PackingEntry.entry_date <= to_date)
        q = q.order_by(PackingEntry.entry_date.desc(), PackingEntry.id.desc())

        rows = [r.to_dict() for r in q.all()]
        return jsonify({'status': 'ok', 'rows': rows})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── API: Save (Insert / Update) ───────────────────────────────────────────────

@packing.route('/api/save', methods=['POST'])
@login_required
def api_save():
    if not _can_edit():
        return jsonify({'status': 'error', 'message': 'Access denied'}), 403

    d = request.get_json() or {}
    if not (d.get('product_name') or '').strip():
        return jsonify({'status': 'error', 'message': 'Product Name is required'})

    try:
        eid      = d.get('id')
        qc_only  = _is_qc() and bool(eid)

        if eid:
            entry = PackingEntry.query.get(eid)
            if not entry:
                return jsonify({'status': 'error', 'message': 'Entry not found'}), 404

            if qc_only:
                # QC users can only update status / received_date / remark
                entry.status         = d.get('status', entry.status)
                entry.received_date  = _parse_date(d.get('received_date'))
                entry.received_by    = (d.get('received_by') or '').strip()
                entry.testing_status = d.get('testing_status', entry.testing_status)
                entry.remark         = (d.get('remark') or '').strip()
            else:
                _fill_entry(entry, d)
        else:
            entry = PackingEntry()
            _fill_entry(entry, d)
            entry.created_by = getattr(current_user, 'username', '') or ''
            db.session.add(entry)

        db.session.commit()
        return jsonify({'status': 'ok', 'id': entry.id})

    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


def _fill_entry(entry, d):
    """Fill all editable fields from request dict into a PackingEntry object."""
    entry.entry_date         = _parse_date(d.get('entry_date')) or date.today()
    entry.brand              = (d.get('brand')              or '').strip()
    entry.product_name       = (d.get('product_name')       or '').strip()
    entry.batch_no           = (d.get('batch_no')           or '').strip()
    entry.mfg_date           = (d.get('mfg_date')           or '').strip()
    entry.exp_date           = (d.get('exp_date')           or '').strip()
    entry.sku_size           = (d.get('sku_size')           or '').strip()
    entry.packaging_material = (d.get('packaging_material') or '')
    entry.quantity           = int(d.get('quantity')  or 0)
    entry.samples_sent_by    = (d.get('samples_sent_by')    or '').strip()
    entry.mrp                = d.get('mrp') or None
    entry.received_by        = (d.get('received_by')        or '').strip()
    entry.status             = d.get('status', 'Pending')
    entry.received_date      = _parse_date(d.get('received_date'))
    entry.testing_status     = d.get('testing_status', 'Pending')
    entry.remark             = (d.get('remark')             or '').strip()


# ── API: Delete ───────────────────────────────────────────────────────────────

@packing.route('/api/delete', methods=['POST'])
@login_required
def api_delete():
    if _is_qc():
        return jsonify({'status': 'error', 'message': 'QC users cannot delete packing entries'}), 403
    if not _can_delete():
        return jsonify({'status': 'error', 'message': 'Access denied'}), 403

    rid = (request.get_json() or {}).get('id')
    if not rid:
        return jsonify({'status': 'error', 'message': 'Missing id'}), 400
    try:
        entry = PackingEntry.query.get(rid)
        if not entry:
            return jsonify({'status': 'error', 'message': 'Entry not found'}), 404
        db.session.delete(entry)
        db.session.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── API: CSV Import ───────────────────────────────────────────────────────────

@packing.route('/api/import', methods=['POST'])
@login_required
def api_import():
    if _is_qc():
        return jsonify({'status': 'error', 'message': 'QC users cannot import entries'}), 403
    if not _can_edit():
        return jsonify({'status': 'error', 'message': 'Access denied'}), 403

    f = request.files.get('file')
    if not f or not f.filename.endswith('.csv'):
        return jsonify({'status': 'error', 'message': 'Please upload a valid .csv file'}), 400

    import csv, io
    try:
        stream    = io.StringIO(f.stream.read().decode('utf-8-sig'), newline=None)
        reader    = csv.DictReader(stream)

        # CSV column name → model field mapping
        # Matches both our export format and original packing.html export format
        COL_MAP = {
            'date':               'entry_date',
            'Date':               'entry_date',
            'brand':              'brand',
            'Brand':              'brand',
            'product name':       'product_name',
            'Product Name':       'product_name',
            'batch no':           'batch_no',
            'Batch No':           'batch_no',
            'mfg date':           'mfg_date',
            'Mfg Date':           'mfg_date',
            'exp date':           'exp_date',
            'Exp Date':           'exp_date',
            'sku size':           'sku_size',
            'SKU Size':           'sku_size',
            'packaging material': 'packaging_material',
            'Packaging Material': 'packaging_material',
            'quantity':           'quantity',
            'Quantity':           'quantity',
            'samples sent by':    'samples_sent_by',
            'Samples sent By':    'samples_sent_by',
            'Samples Sent By':    'samples_sent_by',
            'mrp':                'mrp',
            'MRP':                'mrp',
            'receiving status':   'status',
            'Receiving Status':   'status',
            'received date':      'received_date',
            'Received Date':      'received_date',
            'remark':             'remark',
            'Remark':             'remark',
        }

        inserted = 0
        skipped  = 0
        errors   = []
        created_by = getattr(current_user, 'username', '') or ''

        for i, row in enumerate(reader, start=2):  # row 1 = header
            # Normalize keys using COL_MAP
            norm = {}
            for csv_col, val in row.items():
                key = (csv_col or '').strip()
                field = COL_MAP.get(key)
                if field:
                    norm[field] = (val or '').strip()

            # Skip if no product name
            product_name = norm.get('product_name', '').strip()
            if not product_name:
                skipped += 1
                continue

            # Skip if no brand
            brand = norm.get('brand', '').strip()
            if not brand:
                skipped += 1
                continue

            try:
                entry = PackingEntry()
                entry.entry_date         = _parse_date(norm.get('entry_date'))  or date.today()
                entry.brand              = brand
                entry.product_name       = product_name
                entry.batch_no           = norm.get('batch_no', '')
                entry.mfg_date           = norm.get('mfg_date', '')
                entry.exp_date           = norm.get('exp_date', '')
                entry.sku_size           = norm.get('sku_size', '')
                entry.packaging_material = norm.get('packaging_material', '')
                entry.quantity           = int(float(norm.get('quantity') or 0))
                entry.samples_sent_by    = norm.get('samples_sent_by', '')
                _mrp = norm.get('mrp', '')
                entry.mrp                = float(_mrp) if _mrp else None
                entry.received_by        = norm.get('received_by', '')
                entry.status             = norm.get('status', 'Pending') or 'Pending'
                entry.received_date      = _parse_date(norm.get('received_date'))
                entry.testing_status     = norm.get('testing_status', 'Pending') or 'Pending'
                entry.remark             = norm.get('remark', '')
                entry.created_by         = created_by
                db.session.add(entry)
                inserted += 1

            except Exception as row_err:
                errors.append(f'Row {i}: {row_err}')
                skipped += 1
                continue

        db.session.commit()
        msg = f'{inserted} records imported successfully'
        if skipped:
            msg += f', {skipped} skipped'
        if errors:
            msg += f'. Errors: {"; ".join(errors[:3])}'
        return jsonify({'status': 'ok', 'inserted': inserted, 'skipped': skipped, 'message': msg})

    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500


# ── API: Brands (from procurement_brands table) ───────────────────────────────

@packing.route('/api/brands')
@login_required
def api_brands():
    try:
        rows = db.session.execute(
            db.text("SELECT id, name, color FROM procurement_brands ORDER BY name ASC")
        ).fetchall()
        brands = [{'id': r[0], 'name': r[1], 'color': r[2]} for r in rows]
        return jsonify({'status': 'ok', 'brands': brands})
    except Exception:
        # procurement_brands table nahi hai toh empty list return karo
        return jsonify({'status': 'ok', 'brands': []})
