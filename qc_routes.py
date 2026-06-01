"""
qc_routes.py — Quality Control module
=====================================
Blueprint:  qc_bp   at  /qc

Pages:
    GET  /qc/trs/rm                  RM TRS list (DataTable UI)
    GET  /qc/trs/pm                  PM TRS list (DataTable UI)

JSON APIs:
    GET  /qc/api/trs?type=RM         List rows + filters
    POST /qc/api/trs/<id>/approve    Approve workflow  (Phase 3)
    POST /qc/api/trs/<id>/reject     Reject workflow   (Phase 3)
    POST /qc/api/trs/<id>/status     Change to any other status (Hold / Under Testing)

QC stock-impact rules:
    RM Approve   →  Stock-in (total_qty − sample_qty) added to batch_stock
                    + GrnStockLedger entry (qty_in)
    PM Approve   →  Sample qty deducted from batch_stock
                    + GrnStockLedger entry (qty_out)
    Reject (after approve)  →  Reverses whatever the approve did.
    Other statuses → no stock impact (informational only)
"""
from datetime import datetime, date
import os
from flask import (Blueprint, render_template, request, jsonify, abort,
                   redirect, url_for, flash, send_file, current_app)
from flask_login import login_required, current_user
from sqlalchemy import or_

from models import db
from models.trs import (
    TrsMaster, QcStatusHistory,
    QC_STATUSES,
    QC_STATUS_PENDING, QC_STATUS_UNDER_TESTING, QC_STATUS_APPROVED,
    QC_STATUS_REJECTED, QC_STATUS_HOLD,
)
from models.grn import GrnMaster, GrnItem, GrnBatchStock, GrnStockLedger


qc_bp = Blueprint('qc', __name__, url_prefix='/qc')


# ─── helpers ──────────────────────────────────────────────────────────
def _username():
    return getattr(current_user, 'username', '') or getattr(current_user, 'name', '') or ''

def _user_id():
    return getattr(current_user, 'id', None)

def _parse_date(s):
    if not s:
        return None
    try:
        return datetime.strptime(s.strip(), '%Y-%m-%d').date()
    except Exception:
        return None


# ═════════════════════════════════════════════════════════════════════
# PAGES
# ═════════════════════════════════════════════════════════════════════
@qc_bp.route('/')
@login_required
def index():
    return redirect(url_for('qc.rm_trs_list'))


@qc_bp.route('/trs/rm')
@login_required
def rm_trs_list():
    return render_template('qc/trs_list.html',
                           active_page='qc',
                           page_title='RM TRS List',
                           grn_type='RM',
                           qc_statuses=QC_STATUSES)


@qc_bp.route('/trs/pm')
@login_required
def pm_trs_list():
    return render_template('qc/trs_list.html',
                           active_page='qc',
                           page_title='PM TRS List',
                           grn_type='PM',
                           qc_statuses=QC_STATUSES)


# ═════════════════════════════════════════════════════════════════════
# QC REVIEW page — open a single TRS, view slip, download COA,
# add remarks, and Approve / Reject (this is the QC Department's
# "edit"/action experience, distinct from the GRN-side TRS form).
# ═════════════════════════════════════════════════════════════════════
@qc_bp.route('/trs/<int:trs_id>/review')
@login_required
def trs_review(trs_id):
    trs = TrsMaster.query.get_or_404(trs_id)
    if trs.is_deleted:
        abort(404)
    grn  = GrnMaster.query.get(trs.grn_id)
    item = GrnItem.query.get(trs.grn_item_id)

    # COA file lives on the GRN item (uploaded at GRN time).
    coa_file = (getattr(item, 'coa_file', '') or '').strip() if item else ''
    has_coa  = bool(coa_file)

    return render_template('qc/trs_review.html',
                           active_page='qc',
                           trs=trs, grn=grn, item=item,
                           has_coa=has_coa,
                           qc_statuses=QC_STATUSES)


@qc_bp.route('/trs/<int:trs_id>/coa')
@login_required
def coa_download(trs_id):
    """Serve / download the COA file attached to this TRS's GRN item."""
    trs = TrsMaster.query.get_or_404(trs_id)
    item = GrnItem.query.get(trs.grn_item_id)
    coa_file = (getattr(item, 'coa_file', '') or '').strip() if item else ''
    if not coa_file:
        flash('No COA file attached for this item.', 'warning')
        return redirect(url_for('qc.trs_review', trs_id=trs_id))

    # coa_file is stored relative to /static (e.g. 'uploads/grn/<grn>/coa_...')
    static_root = os.path.join(current_app.root_path, 'static')
    abs_path = os.path.join(static_root, coa_file.replace('/', os.sep))
    if not os.path.isfile(abs_path):
        flash('COA file not found on server.', 'danger')
        return redirect(url_for('qc.trs_review', trs_id=trs_id))

    download_name = os.path.basename(abs_path)
    return send_file(abs_path, as_attachment=True, download_name=download_name)


# ═════════════════════════════════════════════════════════════════════
# JSON API — list (used by DataTable)
# ═════════════════════════════════════════════════════════════════════
@qc_bp.route('/api/trs')
@login_required
def api_trs_list():
    grn_type   = (request.args.get('type') or 'RM').upper()
    date_from  = _parse_date(request.args.get('date_from'))
    date_to    = _parse_date(request.args.get('date_to'))
    vendor     = (request.args.get('vendor')     or '').strip()
    item       = (request.args.get('item')       or '').strip()
    grn_no_q   = (request.args.get('grn_no')     or '').strip()
    qc_status  = (request.args.get('qc_status')  or '').strip()

    grn_ids = [g.id for g in (GrnMaster.query
                              .filter_by(grn_type=grn_type, is_deleted=False)
                              .with_entities(GrnMaster.id).all())]

    q = TrsMaster.query.filter(TrsMaster.is_deleted == False)
    if grn_ids:
        q = q.filter(TrsMaster.grn_id.in_(grn_ids))
    else:
        return jsonify(success=True, data=[], total=0)

    if date_from:
        q = q.filter(TrsMaster.trs_date >= date_from)
    if date_to:
        q = q.filter(TrsMaster.trs_date <= date_to)
    if vendor:
        like = f'%{vendor}%'
        q = q.filter(or_(TrsMaster.supplier_name.ilike(like),
                         TrsMaster.previous_supplier.ilike(like)))
    if item:
        like = f'%{item}%'
        q = q.filter(or_(TrsMaster.sample_name.ilike(like),
                         TrsMaster.batch_no.ilike(like)))
    if grn_no_q:
        q = q.filter(TrsMaster.grn_no.ilike(f'%{grn_no_q}%'))
    if qc_status:
        q = q.filter(TrsMaster.qc_status == qc_status)

    rows = q.order_by(TrsMaster.id.desc()).all()
    out = []
    for t in rows:
        out.append({
            'id':          t.id,
            'trs_no':      t.trs_no,
            'trs_date':    t.trs_date.strftime('%d-%b-%Y') if t.trs_date else '',
            'grn_no':      t.grn_no or '',
            'vendor':      t.supplier_name or '',
            'item_code':   t.batch_no or '',
            'item_name':   t.sample_name or '',
            'batch_no':    t.batch_no or '',
            'lot_no':      t.batch_no or '',
            'qc_status':   t.qc_status or QC_STATUS_PENDING,
            'qc_approved_by': t.qc_approved_by_name or '',
            'stock_impact_applied': bool(t.stock_impact_applied),
            'sample_qty':  float(t.sample_qty or 0),
            'total_qty':   float(t.total_qty or 0),
            'uom':         t.uom or '',
            'created_by':  t.verified_by_name or t.created_by_name or '',
            'view_url':    url_for('trs.view_trs', trs_id=t.id),
            'edit_url':    url_for('trs.edit_trs', trs_id=t.id),
            'review_url':  url_for('qc.trs_review', trs_id=t.id),
        })
    return jsonify(success=True, data=out, total=len(out))


# ═════════════════════════════════════════════════════════════════════
# STOCK IMPACT helpers
# ═════════════════════════════════════════════════════════════════════
def _find_batch(item):
    """Return the existing GrnBatchStock row for this item+batch, or None."""
    if not item.material_id:
        return None
    return (GrnBatchStock.query
            .filter_by(material_id=item.material_id,
                       batch_no=item.batch_no or '',
                       location_id=item.storage_location_id)
            .first())


def _stock_in_for_rm(trs, item, grn):
    """RM Approve → add (total_qty − sample_qty) to stock for this batch.
    Also writes one GrnStockLedger row labelled 'TRS_QC_IN'.
    Returns net qty added.
    """
    total_q  = float(trs.total_qty or 0)
    sample_q = float(trs.sample_qty or 0)
    net_q    = max(0.0, total_q - sample_q)
    if net_q <= 0:
        return 0.0

    # Ledger entry
    led = GrnStockLedger(
        txn_type     = 'TRS_QC_IN',
        txn_ref_type = 'TRS',
        txn_ref_id   = trs.id,
        txn_ref_no   = trs.trs_no,
        material_id  = item.material_id or 0,
        item_code    = item.item_code or '',
        item_name    = item.item_name or '',
        batch_no     = item.batch_no or '',
        location_id  = item.storage_location_id,
        location_name= item.storage_location_name or grn.receive_location_name or '',
        qty_in       = net_q,
        qty_out      = 0,
        uom          = item.uom or 'KG',
        rate         = float(item.rate or 0),
        amount       = net_q * float(item.rate or 0),
        remarks      = f'QC Approved (TRS {trs.trs_no}) — '
                       f'received {total_q} − sample {sample_q} = {net_q}',
        actor_name   = _username(),
    )
    db.session.add(led)
    db.session.flush()

    # Batch upsert
    batch = _find_batch(item)
    if batch:
        cur = float(batch.qty_on_hand or 0)
        batch.qty_on_hand   = cur + net_q
        batch.qty_available = batch.qty_on_hand - float(batch.qty_reserved or 0)
        batch.last_inward_at = datetime.utcnow()
    else:
        db.session.add(GrnBatchStock(
            material_id   = item.material_id,
            item_code     = item.item_code or '',
            item_name     = item.item_name or '',
            batch_no      = item.batch_no or '',
            location_id   = item.storage_location_id,
            location_name = item.storage_location_name or grn.receive_location_name or '',
            mfg_date      = item.mfg_date,
            expiry_date   = item.expiry_date,
            qty_on_hand   = net_q,
            qty_available = net_q,
            avg_rate      = float(item.rate or 0),
            uom           = item.uom or 'KG',
            last_inward_at= datetime.utcnow(),
        ))
    trs.stock_ledger_ref = led.id
    return net_q


def _sample_out_for_pm(trs, item, grn):
    """PM Approve → deduct sample_qty from batch_stock.
    Writes a GrnStockLedger row labelled 'TRS_SAMPLE_OUT'.
    Returns sample qty deducted (0 if no stock available).
    """
    sample_q = float(trs.sample_qty or 0)
    if sample_q <= 0:
        return 0.0

    batch = _find_batch(item)
    if batch:
        cur = float(batch.qty_on_hand or 0)
        # Don't go negative — cap to what's available
        deduct = min(sample_q, cur)
        batch.qty_on_hand   = cur - deduct
        batch.qty_available = batch.qty_on_hand - float(batch.qty_reserved or 0)
    else:
        deduct = sample_q  # No batch exists — ledger entry only

    led = GrnStockLedger(
        txn_type     = 'TRS_SAMPLE_OUT',
        txn_ref_type = 'TRS',
        txn_ref_id   = trs.id,
        txn_ref_no   = trs.trs_no,
        material_id  = item.material_id or 0,
        item_code    = item.item_code or '',
        item_name    = item.item_name or '',
        batch_no     = item.batch_no or '',
        location_id  = item.storage_location_id,
        location_name= item.storage_location_name or grn.receive_location_name or '',
        qty_in       = 0,
        qty_out      = deduct,
        uom          = item.uom or 'KG',
        rate         = float(item.rate or 0),
        amount       = deduct * float(item.rate or 0),
        remarks      = f'QC Sample taken (TRS {trs.trs_no}) — {deduct} {item.uom or "KG"}',
        actor_name   = _username(),
    )
    db.session.add(led)
    db.session.flush()
    trs.stock_ledger_ref = led.id
    return deduct


def _reverse_stock_for_rm(trs, item, grn):
    """Undo a previous RM Approve — subtract (total_qty − sample_qty) back."""
    total_q  = float(trs.total_qty or 0)
    sample_q = float(trs.sample_qty or 0)
    net_q    = max(0.0, total_q - sample_q)
    if net_q <= 0:
        return 0.0

    batch = _find_batch(item)
    if batch:
        cur = float(batch.qty_on_hand or 0)
        batch.qty_on_hand   = max(0.0, cur - net_q)
        batch.qty_available = batch.qty_on_hand - float(batch.qty_reserved or 0)

    db.session.add(GrnStockLedger(
        txn_type='TRS_QC_REVERSE', txn_ref_type='TRS',
        txn_ref_id=trs.id, txn_ref_no=trs.trs_no,
        material_id=item.material_id or 0, item_code=item.item_code or '',
        item_name=item.item_name or '', batch_no=item.batch_no or '',
        location_id=item.storage_location_id,
        location_name=item.storage_location_name or '',
        qty_in=0, qty_out=net_q,
        uom=item.uom or 'KG', rate=float(item.rate or 0),
        amount=net_q * float(item.rate or 0),
        remarks=f'QC Reversal (TRS {trs.trs_no}) — qty {net_q} removed from stock',
        actor_name=_username(),
    ))
    return net_q


def _reverse_sample_for_pm(trs, item, grn):
    """Undo a previous PM Approve — re-add sample_qty back to stock."""
    sample_q = float(trs.sample_qty or 0)
    if sample_q <= 0:
        return 0.0

    batch = _find_batch(item)
    if batch:
        cur = float(batch.qty_on_hand or 0)
        batch.qty_on_hand   = cur + sample_q
        batch.qty_available = batch.qty_on_hand - float(batch.qty_reserved or 0)

    db.session.add(GrnStockLedger(
        txn_type='TRS_QC_REVERSE', txn_ref_type='TRS',
        txn_ref_id=trs.id, txn_ref_no=trs.trs_no,
        material_id=item.material_id or 0, item_code=item.item_code or '',
        item_name=item.item_name or '', batch_no=item.batch_no or '',
        location_id=item.storage_location_id,
        location_name=item.storage_location_name or '',
        qty_in=sample_q, qty_out=0,
        uom=item.uom or 'KG', rate=float(item.rate or 0),
        amount=sample_q * float(item.rate or 0),
        remarks=f'QC Reversal (TRS {trs.trs_no}) — sample {sample_q} returned',
        actor_name=_username(),
    ))
    return sample_q


def _log_history(trs, from_status, to_status, remarks='',
                 stock_action='', stock_qty=0):
    db.session.add(QcStatusHistory(
        trs_id=trs.id,
        from_status=from_status or '',
        to_status=to_status,
        remarks=remarks or '',
        actor_id=_user_id(),
        actor_name=_username(),
        stock_action=stock_action or '',
        stock_qty=stock_qty or 0,
    ))


# ═════════════════════════════════════════════════════════════════════
# APPROVE
# ═════════════════════════════════════════════════════════════════════
@qc_bp.route('/api/trs/<int:trs_id>/approve', methods=['POST'])
@login_required
def api_approve(trs_id):
    trs = TrsMaster.query.get_or_404(trs_id)
    if trs.is_deleted:
        return jsonify(success=False, error='TRS deleted'), 404

    if trs.qc_status == QC_STATUS_APPROVED and trs.stock_impact_applied:
        return jsonify(success=False,
                       error='TRS already approved (stock already moved).'), 409

    grn  = GrnMaster.query.get(trs.grn_id)
    item = GrnItem.query.get(trs.grn_item_id)
    if not grn or not item:
        return jsonify(success=False, error='Linked GRN or item missing'), 404

    payload = request.get_json(silent=True) or {}
    remarks = (payload.get('remarks') or '').strip()

    grn_type = (grn.grn_type or '').upper()
    stock_action = ''
    stock_qty    = 0.0

    try:
        if grn_type == 'RM':
            stock_qty    = _stock_in_for_rm(trs, item, grn)
            stock_action = 'stock_in'
        elif grn_type == 'PM':
            stock_qty    = _sample_out_for_pm(trs, item, grn)
            stock_action = 'sample_out'
        else:
            # For other GRN types we still approve, but no stock impact
            stock_action = 'none'

        prev_status = trs.qc_status or QC_STATUS_PENDING
        trs.qc_status            = QC_STATUS_APPROVED
        trs.qc_remarks           = remarks or trs.qc_remarks or ''
        trs.qc_approved_at       = datetime.utcnow()
        trs.qc_approved_by_id    = _user_id()
        trs.qc_approved_by_name  = _username()
        trs.stock_impact_applied = True
        trs.updated_by_name      = _username()

        _log_history(trs, prev_status, QC_STATUS_APPROVED, remarks,
                     stock_action, stock_qty)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=f'Approve failed: {e}'), 500

    return jsonify(success=True,
                   trs_id=trs.id,
                   qc_status=trs.qc_status,
                   stock_action=stock_action,
                   stock_qty=stock_qty,
                   grn_type=grn_type)


# ═════════════════════════════════════════════════════════════════════
# REJECT
# ═════════════════════════════════════════════════════════════════════
@qc_bp.route('/api/trs/<int:trs_id>/reject', methods=['POST'])
@login_required
def api_reject(trs_id):
    trs = TrsMaster.query.get_or_404(trs_id)
    if trs.is_deleted:
        return jsonify(success=False, error='TRS deleted'), 404

    grn  = GrnMaster.query.get(trs.grn_id)
    item = GrnItem.query.get(trs.grn_item_id)
    if not grn or not item:
        return jsonify(success=False, error='Linked GRN or item missing'), 404

    payload = request.get_json(silent=True) or {}
    remarks = (payload.get('remarks') or '').strip()
    if not remarks:
        return jsonify(success=False,
                       error='Reject reason (remarks) is required.'), 400

    grn_type = (grn.grn_type or '').upper()
    stock_action = ''
    stock_qty    = 0.0

    try:
        # If a previous Approve added stock, reverse it
        if trs.stock_impact_applied:
            if grn_type == 'RM':
                stock_qty    = _reverse_stock_for_rm(trs, item, grn)
                stock_action = 'reverse_stock_in'
            elif grn_type == 'PM':
                stock_qty    = _reverse_sample_for_pm(trs, item, grn)
                stock_action = 'reverse_sample_out'
            trs.stock_impact_applied = False

        prev_status = trs.qc_status or QC_STATUS_PENDING
        trs.qc_status           = QC_STATUS_REJECTED
        trs.qc_remarks          = remarks
        trs.qc_rejected_at      = datetime.utcnow()
        trs.qc_rejected_by_name = _username()
        trs.updated_by_name     = _username()

        _log_history(trs, prev_status, QC_STATUS_REJECTED, remarks,
                     stock_action, stock_qty)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=f'Reject failed: {e}'), 500

    return jsonify(success=True,
                   trs_id=trs.id,
                   qc_status=trs.qc_status,
                   stock_action=stock_action or 'none',
                   stock_qty=stock_qty,
                   grn_type=grn_type)


# ═════════════════════════════════════════════════════════════════════
# Change to any other status (Hold / Under Testing)
# ═════════════════════════════════════════════════════════════════════
@qc_bp.route('/api/trs/<int:trs_id>/status', methods=['POST'])
@login_required
def api_set_status(trs_id):
    """Move to Hold / Under Testing / Pending. Will refuse to set Approved/
    Rejected here — those go through their dedicated endpoints."""
    trs = TrsMaster.query.get_or_404(trs_id)
    if trs.is_deleted:
        return jsonify(success=False, error='TRS deleted'), 404

    payload  = request.get_json(silent=True) or {}
    new_st   = (payload.get('status') or '').strip()
    remarks  = (payload.get('remarks') or '').strip()

    if new_st not in (QC_STATUS_PENDING, QC_STATUS_UNDER_TESTING, QC_STATUS_HOLD):
        return jsonify(success=False,
                       error='Use /approve or /reject for those statuses.'), 400

    if trs.stock_impact_applied:
        return jsonify(success=False,
                       error='Stock already moved by Approve. Reject first to reverse, '
                             'then change status.'), 409

    prev = trs.qc_status or QC_STATUS_PENDING
    trs.qc_status        = new_st
    trs.qc_remarks       = remarks or trs.qc_remarks or ''
    trs.updated_by_name  = _username()

    _log_history(trs, prev, new_st, remarks)
    db.session.commit()
    return jsonify(success=True, trs_id=trs.id, qc_status=new_st)


# ═════════════════════════════════════════════════════════════════════
# RE-OPEN  — undo an Approve/Reject so QC can change the decision
#   (e.g. someone clicked Approved by mistake). If stock was moved by
#   a previous Approve, it is reversed first, then status → Pending.
# ═════════════════════════════════════════════════════════════════════
@qc_bp.route('/api/trs/<int:trs_id>/reopen', methods=['POST'])
@login_required
def api_reopen(trs_id):
    trs = TrsMaster.query.get_or_404(trs_id)
    if trs.is_deleted:
        return jsonify(success=False, error='TRS deleted'), 404

    grn  = GrnMaster.query.get(trs.grn_id)
    item = GrnItem.query.get(trs.grn_item_id)
    if not grn or not item:
        return jsonify(success=False, error='Linked GRN or item missing'), 404

    payload = request.get_json(silent=True) or {}
    remarks = (payload.get('remarks') or '').strip()

    grn_type = (grn.grn_type or '').upper()
    stock_action = 'none'
    stock_qty    = 0.0

    try:
        # If a previous Approve added/deducted stock, reverse it now.
        if trs.stock_impact_applied:
            if grn_type == 'RM':
                stock_qty    = _reverse_stock_for_rm(trs, item, grn)
                stock_action = 'reverse_stock_in'
            elif grn_type == 'PM':
                stock_qty    = _reverse_sample_for_pm(trs, item, grn)
                stock_action = 'reverse_sample_out'
            trs.stock_impact_applied = False

        prev_status = trs.qc_status or QC_STATUS_PENDING

        # Reset the workflow back to Pending and clear approve/reject stamps
        trs.qc_status           = QC_STATUS_PENDING
        trs.qc_approved_at      = None
        trs.qc_approved_by_id   = None
        trs.qc_approved_by_name = ''
        trs.qc_rejected_at      = None
        trs.qc_rejected_by_name = ''
        trs.stock_ledger_ref    = None
        trs.updated_by_name     = _username()

        _log_history(trs, prev_status, QC_STATUS_PENDING,
                     remarks or 'Re-opened to change decision',
                     stock_action, stock_qty)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=f'Re-open failed: {e}'), 500

    return jsonify(success=True,
                   trs_id=trs.id,
                   qc_status=trs.qc_status,
                   stock_action=stock_action,
                   stock_qty=stock_qty,
                   grn_type=grn_type)


# ═════════════════════════════════════════════════════════════════════
# History API
# ═════════════════════════════════════════════════════════════════════
@qc_bp.route('/api/trs/<int:trs_id>/history')
@login_required
def api_history(trs_id):
    rows = (QcStatusHistory.query
            .filter_by(trs_id=trs_id)
            .order_by(QcStatusHistory.id.desc()).all())
    return jsonify(success=True,
                   data=[{
                       'id': r.id,
                       'from_status': r.from_status,
                       'to_status':   r.to_status,
                       'remarks':     r.remarks,
                       'actor_name':  r.actor_name,
                       'created_at':  r.created_at.strftime('%d-%b-%Y %H:%M') if r.created_at else '',
                       'stock_action': r.stock_action,
                       'stock_qty':   float(r.stock_qty or 0),
                   } for r in rows])
