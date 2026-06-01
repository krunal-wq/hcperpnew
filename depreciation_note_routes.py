"""
Depreciation Note (DN) Routes
═══════════════════════════════════════════════════════════════════════════
Endpoints:
  GET  /depreciation-note                       → listing page
  GET  /depreciation-note/new?grn_id=X          → create form (against a GRN)
  POST /depreciation-note/create                → save new DN
  GET  /depreciation-note/<id>/view             → view DN
  POST /depreciation-note/<id>/mark-sent        → mark Open → Sent
  POST /depreciation-note/<id>/mark-resolved    → mark → Resolved
  POST /depreciation-note/<id>/delete           → soft delete
  GET  /depreciation-note/api/list              → JSON listing
═══════════════════════════════════════════════════════════════════════════
"""
from datetime import datetime, date
from flask import (Blueprint, render_template, request, jsonify,
                   redirect, url_for, flash, abort, current_app)
from flask_login import login_required, current_user
from sqlalchemy import or_, desc

from models import db
from models.depreciation_note import (
    DepreciationNote, DepreciationNoteItem,
    DN_STATUSES, DN_STATUS_OPEN, DN_STATUS_SENT, DN_STATUS_RESOLVED,
    DN_STATUS_COLORS,
)
from models.grn import GrnMaster, GrnItem

dn_bp = Blueprint('depreciation_note', __name__, url_prefix='/depreciation-note')


# ═════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═════════════════════════════════════════════════════════════════════════════
def _username():
    return getattr(current_user, 'username', None) or getattr(current_user, 'name', None) or 'system'


def _to_float(s):
    try:
        return float(s) if s not in (None, '') else 0.0
    except (ValueError, TypeError):
        return 0.0


def _to_int(s):
    try:
        return int(s) if s not in (None, '') else None
    except (ValueError, TypeError):
        return None


def _next_dn_number():
    """Generate next DN number in DPN-XXXX-FY format."""
    today = date.today()
    if today.month >= 4:
        fy = f"{today.year % 100:02d}-{(today.year + 1) % 100:02d}"
        fy_year = today.year
    else:
        fy = f"{(today.year - 1) % 100:02d}-{today.year % 100:02d}"
        fy_year = today.year - 1
    last = (DepreciationNote.query
            .filter_by(dn_fy=fy)
            .order_by(DepreciationNote.dn_serial.desc())
            .first())
    serial = (last.dn_serial + 1) if last else 1
    return f"DPN-{serial:04d}-{fy}", serial, fy, fy_year


# ═════════════════════════════════════════════════════════════════════════════
# LISTING
# ═════════════════════════════════════════════════════════════════════════════
@dn_bp.route('')
@login_required
def index():
    """List all Depreciation Notes (with filters)."""
    return render_template(
        'depreciation_note/index.html',
        active_page='depreciation_note',
        statuses=DN_STATUSES,
        status_colors=DN_STATUS_COLORS,
    )


@dn_bp.route('/api/list')
@login_required
def api_list():
    """JSON listing with filters."""
    status   = (request.args.get('status', '') or '').strip()
    supplier = (request.args.get('supplier', '') or '').strip()
    search   = (request.args.get('q', '') or '').strip()
    date_from= (request.args.get('date_from','') or '').strip()
    date_to  = (request.args.get('date_to','')   or '').strip()

    qs = DepreciationNote.query.filter_by(is_deleted=False)
    if status:
        qs = qs.filter(DepreciationNote.status == status)
    if supplier:
        qs = qs.filter(DepreciationNote.supplier_name.ilike(f'%{supplier}%'))
    if search:
        like = f'%{search}%'
        qs = qs.filter(or_(
            DepreciationNote.dn_number.ilike(like),
            DepreciationNote.grn_number.ilike(like),
            DepreciationNote.invoice_no.ilike(like),
            DepreciationNote.supplier_name.ilike(like),
        ))
    if date_from:
        try:
            d = datetime.strptime(date_from, '%Y-%m-%d').date()
            qs = qs.filter(DepreciationNote.dn_date >= d)
        except ValueError:
            pass
    if date_to:
        try:
            d = datetime.strptime(date_to, '%Y-%m-%d').date()
            qs = qs.filter(DepreciationNote.dn_date <= d)
        except ValueError:
            pass

    rows = qs.order_by(desc(DepreciationNote.id)).all()

    # Aggregates
    total_value = sum(float(r.total_shortage_value or 0) for r in rows)
    open_value  = sum(float(r.total_shortage_value or 0) for r in rows if r.status == DN_STATUS_OPEN)

    return jsonify(
        results=[r.to_dict() for r in rows],
        total_count=len(rows),
        total_shortage_value=total_value,
        open_shortage_value=open_value,
    )


# ═════════════════════════════════════════════════════════════════════════════
# CREATE — manual from a specific GRN
# ═════════════════════════════════════════════════════════════════════════════
@dn_bp.route('/new')
@login_required
def new_dn():
    """Show creation form for a DN against a chosen GRN."""
    grn_id = _to_int(request.args.get('grn_id'))
    if not grn_id:
        flash('Pick a GRN first.', 'warning')
        return redirect(url_for('grn.index'))

    grn = GrnMaster.query.get_or_404(grn_id)
    if grn.is_deleted:
        flash('GRN has been deleted.', 'danger')
        return redirect(url_for('grn.index'))
    if grn.status != 'Completed':
        flash('Depreciation Note can be created only for Completed GRNs.', 'warning')
        return redirect(url_for('grn.view_grn', grn_id=grn.id))

    # Block duplicates — one open DN per GRN
    existing = (DepreciationNote.query
                .filter_by(grn_id=grn.id, is_deleted=False)
                .first())
    if existing:
        flash(f'A Depreciation Note already exists for this GRN: {existing.dn_number}', 'info')
        return redirect(url_for('depreciation_note.view_dn', dn_id=existing.id))

    items = grn.items.order_by(GrnItem.sr_no).all()
    return render_template(
        'depreciation_note/form.html',
        active_page='depreciation_note',
        grn=grn,
        items=items,
    )


@dn_bp.route('/create', methods=['POST'])
@login_required
def create_dn():
    """Save a new Depreciation Note from the form."""
    grn_id = _to_int(request.form.get('grn_id'))
    if not grn_id:
        return jsonify(success=False, error='Missing GRN reference'), 400

    grn = GrnMaster.query.get_or_404(grn_id)
    if grn.is_deleted or grn.status != 'Completed':
        return jsonify(success=False, error='GRN not eligible for DN'), 400

    # Re-check no duplicate
    existing = (DepreciationNote.query
                .filter_by(grn_id=grn.id, is_deleted=False).first())
    if existing:
        return jsonify(success=False,
                       error=f'DN already exists: {existing.dn_number}'), 400

    grn_item_ids = request.form.getlist('grn_item_id[]')
    invoice_qtys = request.form.getlist('invoice_qty[]')
    remarks_list = request.form.getlist('item_remarks[]')

    short_rows = []
    total_inv = total_recv = total_short = 0.0
    total_short_value = 0.0

    for i, gi_id_str in enumerate(grn_item_ids):
        gi_id = _to_int(gi_id_str)
        if not gi_id:
            continue
        inv = _to_float(invoice_qtys[i] if i < len(invoice_qtys) else 0)
        if inv <= 0:
            continue   # user didn't enter — skip
        it = GrnItem.query.get(gi_id)
        if not it or it.grn_id != grn.id:
            continue
        recv = float(it.received_qty or 0)
        if inv - recv <= 0.001:
            continue   # not short
        shortage = inv - recv
        rate = float(it.rate or 0)
        short_value = round(shortage * rate, 2)
        rem = (remarks_list[i] if i < len(remarks_list) else '').strip()

        total_inv         += inv
        total_recv        += recv
        total_short       += shortage
        total_short_value += short_value

        short_rows.append((it, inv, recv, shortage, rate, short_value, rem))

    if not short_rows:
        return jsonify(success=False,
                       error='No items with shortage. Enter an Invoice Qty > Received Qty for at least one item.'), 400

    try:
        dn_number, serial, fy, fy_year = _next_dn_number()
        dn = DepreciationNote(
            dn_number       = dn_number,
            dn_number_short = dn_number,
            dn_serial       = serial,
            dn_fy           = fy,
            dn_year         = fy_year,
            dn_date         = date.today(),
            grn_id          = grn.id,
            grn_number      = grn.grn_number or '',
            grn_type        = grn.grn_type or 'RM',
            po_id           = grn.po_id,
            po_number       = grn.po_number or '',
            supplier_id     = grn.supplier_id,
            supplier_name   = grn.supplier_name or '',
            invoice_no      = grn.invoice_no or '',
            invoice_date    = grn.invoice_date,
            total_invoice_qty    = total_inv,
            total_received_qty   = total_recv,
            total_shortage_qty   = total_short,
            total_shortage_value = total_short_value,
            status               = DN_STATUS_OPEN,
            created_by_id        = getattr(current_user, 'id', None),
            created_by_name      = _username(),
        )
        db.session.add(dn)
        db.session.flush()

        for sr, (it, inv, recv, shortage, rate, short_value, rem) in enumerate(short_rows, 1):
            db.session.add(DepreciationNoteItem(
                dn_id          = dn.id,
                grn_item_id    = it.id,
                sr_no          = sr,
                material_id    = it.material_id,
                item_code      = it.item_code or '',
                item_name      = it.item_name or '',
                hsn_code       = it.hsn_code or '',
                uom            = it.uom or 'KG',
                batch_no       = it.batch_no or '',
                invoice_qty    = inv,
                received_qty   = recv,
                shortage_qty   = shortage,
                rate           = rate,
                shortage_value = short_value,
                remarks        = rem,
            ))

        grn.has_depreciation_note = True
        db.session.commit()
        return jsonify(success=True, dn_id=dn.id, dn_number=dn.dn_number,
                       redirect_url=url_for('depreciation_note.view_dn', dn_id=dn.id))
    except Exception as e:
        db.session.rollback()
        import traceback; traceback.print_exc()
        return jsonify(success=False, error=str(e)), 500


# ═════════════════════════════════════════════════════════════════════════════
# VIEW
# ═════════════════════════════════════════════════════════════════════════════
@dn_bp.route('/<int:dn_id>/view')
@login_required
def view_dn(dn_id):
    dn = DepreciationNote.query.get_or_404(dn_id)
    if dn.is_deleted:
        flash('Depreciation Note has been deleted.', 'danger')
        return redirect(url_for('depreciation_note.index'))
    items = dn.items.order_by(DepreciationNoteItem.sr_no).all()
    grn = GrnMaster.query.get(dn.grn_id)
    return render_template(
        'depreciation_note/view.html',
        active_page='depreciation_note',
        dn=dn,
        items=items,
        grn=grn,
    )


# ═════════════════════════════════════════════════════════════════════════════
# STATUS ACTIONS
# ═════════════════════════════════════════════════════════════════════════════
@dn_bp.route('/<int:dn_id>/mark-sent', methods=['POST'])
@login_required
def mark_sent(dn_id):
    dn = DepreciationNote.query.get_or_404(dn_id)
    if dn.is_deleted:
        return jsonify(success=False, error='DN deleted'), 404
    if dn.status != DN_STATUS_OPEN:
        return jsonify(success=False,
                       error=f'Cannot mark as Sent (status: {dn.status})'), 400
    data = request.get_json(silent=True) or {}
    email = (data.get('email') or request.form.get('email') or '').strip()
    dn.status = DN_STATUS_SENT
    dn.sent_at = datetime.utcnow()
    dn.sent_to_email = email
    db.session.commit()
    return jsonify(success=True)


@dn_bp.route('/<int:dn_id>/mark-resolved', methods=['POST'])
@login_required
def mark_resolved(dn_id):
    dn = DepreciationNote.query.get_or_404(dn_id)
    if dn.is_deleted:
        return jsonify(success=False, error='DN deleted'), 404
    if dn.status == DN_STATUS_RESOLVED:
        return jsonify(success=False, error='Already resolved'), 400
    data = request.get_json(silent=True) or {}
    remarks = (data.get('remarks') or request.form.get('remarks') or '').strip()
    dn.status = DN_STATUS_RESOLVED
    dn.resolved_at = datetime.utcnow()
    dn.resolved_by_name = _username()
    dn.resolved_remarks = remarks
    db.session.commit()
    return jsonify(success=True)


@dn_bp.route('/<int:dn_id>/delete', methods=['POST'])
@login_required
def delete_dn(dn_id):
    dn = DepreciationNote.query.get_or_404(dn_id)
    if dn.is_deleted:
        return jsonify(success=False, error='Already deleted'), 400
    dn.is_deleted = True
    # Also clear has_depreciation_note flag on parent GRN
    grn = GrnMaster.query.get(dn.grn_id)
    if grn:
        # Check if any other non-deleted DN exists on this GRN
        other = (DepreciationNote.query
                 .filter(DepreciationNote.grn_id == grn.id,
                         DepreciationNote.id != dn.id,
                         DepreciationNote.is_deleted == False)
                 .first())
        if not other:
            grn.has_depreciation_note = False
    db.session.commit()
    return jsonify(success=True)
