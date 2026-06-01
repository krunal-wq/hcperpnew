"""
trs_routes.py — Testing Requisition Slip (TRS) routes

Blueprint:  trs_bp   at  /trs

Routes:
    GET  /trs/grn/<grn_id>           Per-GRN item-list page
                                       — shows each item with "Create TRS"
                                         or "View Certificate" action.
    GET  /trs/new                    New TRS form (?grn_id=&item_id=)
    POST /trs/save                   Save TRS  → certificate page
    GET  /trs/<trs_id>               View saved TRS (read-only certificate)
    GET  /trs/<trs_id>/edit          Edit form (only by creator/admin)
    POST /trs/<trs_id>/delete        Soft-delete
"""
from datetime import datetime, date

from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, abort, jsonify)
from flask_login import login_required, current_user

from models import db
from models.trs import (
    TrsMaster,
    PHYSICAL_STATES, APPEARANCES, ODOURS, NEW_OLD, YES_NO,
)
from models.grn import GrnMaster, GrnItem
from models.supplier import Supplier


trs_bp = Blueprint('trs', __name__, url_prefix='/trs')


# ─── tiny helpers ─────────────────────────────────────────────────────
def _username():
    return getattr(current_user, 'username', '') or getattr(current_user, 'name', '') or ''

def _user_id():
    return getattr(current_user, 'id', None)


def _qc_options(category, fallback):
    """Active values for a QC dropdown (physical_state / appearance / odour).

    Reads from the qc_param_options master. If the table/data isn't there
    yet (migration not run), falls back to the hard-coded list so the form
    never breaks.
    """
    try:
        from models.master import QCParamOption
        rows = (QCParamOption.query
                .filter_by(category=category, status=True, is_deleted=False)
                .order_by(QCParamOption.sort_order.asc(),
                          QCParamOption.value.asc())
                .all())
        vals = [r.value for r in rows if (r.value or '').strip()]
        return vals if vals else list(fallback)
    except Exception:
        return list(fallback)

def _parse_date(v):
    if not v:
        return None
    try:
        return datetime.strptime(v.strip(), '%Y-%m-%d').date()
    except Exception:
        return None

def _to_float(v, default=0.0):
    try:
        return float(str(v).strip())
    except Exception:
        return default


def _build_trs_no(grn, item_seq):
    """TRS No = GRN_no_short + '/' + item_seq.  Falls back to grn_number."""
    base = (grn.grn_number_short or grn.grn_number or '').strip()
    return f'{base}/{item_seq}' if base else f'GRN-{grn.id}/{item_seq}'


def _supplier_options(ensure_included=None, grn_type=None):
    """Active suppliers for the 'Previous Supplier' dropdown.

    Filters by supplier_type matching the GRN's type (RM → RM suppliers,
    PM → PM suppliers; 'RM,PM' suppliers match both). If `ensure_included`
    is given (e.g. previous-GRN supplier), it is added even if not in the
    active list.
    """
    try:
        q = Supplier.query.filter_by(is_deleted=False)
        # The Supplier model uses is_active/is_deleted — show only active
        try:
            q = q.filter(Supplier.is_active == True)
        except Exception:
            pass
        rows = q.order_by(Supplier.supplier_name.asc()).all()
        # Optional: filter by GRN type (supplier_type can be 'RM', 'PM', or 'RM,PM')
        if grn_type:
            gt = grn_type.upper()
            rows = [s for s in rows if gt in (s.supplier_type or '').upper().split(',')]
        names = [s.supplier_name for s in rows if (s.supplier_name or '').strip()]
    except Exception as e:
        # Don't swallow silently — print so the developer can see in console
        try:
            import traceback
            print(f'[trs_routes] Supplier lookup failed: {e}')
            traceback.print_exc()
        except Exception:
            pass
        names = []

    # Deduplicate while preserving order
    seen = set()
    uniq = []
    for n in names:
        if n not in seen:
            seen.add(n); uniq.append(n)

    if (ensure_included and ensure_included != 'First Time'
            and ensure_included not in seen):
        uniq.append(ensure_included)
        uniq.sort()

    return uniq


def _find_last_grn_supplier_for_material(material_id, exclude_grn_id=None):
    """Find the latest completed GRN that contains the given material and
    return (supplier_name, grn_no, grn_date). Returns (None, '', None) if no
    previous GRN exists.

    Used by Phase 3 Previous-Supplier auto-lookup in the TRS form.
    """
    if not material_id:
        return (None, '', None)

    try:
        from models.grn import GRN_STATUS_COMPLETED
        status_filter = GrnMaster.status == GRN_STATUS_COMPLETED
    except Exception:
        # Fallback: just exclude cancelled
        status_filter = GrnMaster.status != 'Cancelled'

    q = (db.session.query(GrnMaster)
         .join(GrnItem, GrnItem.grn_id == GrnMaster.id)
         .filter(GrnItem.material_id == material_id)
         .filter(GrnMaster.is_deleted == False)
         .filter(status_filter))

    if exclude_grn_id:
        q = q.filter(GrnMaster.id != exclude_grn_id)

    q = q.order_by(GrnMaster.grn_date.desc(), GrnMaster.id.desc())
    grn = q.first()
    if grn:
        return (grn.supplier_name or '',
                grn.grn_number_short or grn.grn_number or '',
                grn.grn_date)
    return (None, '', None)


# ═════════════════════════════════════════════════════════════════════
# Per-GRN item list page — entry point from the GRN view hamburger menu
# ═════════════════════════════════════════════════════════════════════
@trs_bp.route('/grn/<int:grn_id>')
@login_required
def grn_items(grn_id):
    grn = GrnMaster.query.get_or_404(grn_id)
    if grn.is_deleted:
        flash('GRN deleted.', 'danger')
        return redirect(url_for('grn.index'))

    items = grn.items.order_by(GrnItem.sr_no).all()

    # Lookup existing TRS for each item (so we show View instead of Create)
    item_ids = [it.id for it in items]
    existing = {t.grn_item_id: t for t in
                TrsMaster.query.filter(TrsMaster.grn_item_id.in_(item_ids),
                                       TrsMaster.is_deleted == False).all()}

    rows = []
    for idx, it in enumerate(items, 1):
        rows.append({
            'seq': idx,
            'item': it,
            'trs': existing.get(it.id),
        })

    return render_template('trs/index.html',
                           active_page='grn',
                           grn=grn,
                           rows=rows)


# ═════════════════════════════════════════════════════════════════════
# NEW form
# ═════════════════════════════════════════════════════════════════════
@trs_bp.route('/new')
@login_required
def new_trs():
    grn_id  = request.args.get('grn_id',  type=int)
    item_id = request.args.get('item_id', type=int)
    if not grn_id or not item_id:
        flash('grn_id and item_id are required.', 'danger')
        return redirect(url_for('grn.index'))

    grn  = GrnMaster.query.get_or_404(grn_id)
    item = GrnItem.query.get_or_404(item_id)
    if item.grn_id != grn.id:
        abort(404)

    # If a TRS already exists for this item, it has already been generated.
    # Show a clear message and route the user to the right place:
    #   - Approved/Rejected by QC → read-only QC review page
    #   - otherwise → the edit form (so they can review/update)
    existing = (TrsMaster.query
                .filter_by(grn_item_id=item.id, is_deleted=False)
                .first())
    if existing:
        st = (existing.qc_status or '').strip()
        if st in ('Approved', 'Rejected'):
            flash(f'TRS already generated for this item — {existing.trs_no} '
                  f'(QC {st}). Stock/ledger already handled.', 'warning')
            return redirect(url_for('qc.trs_review', trs_id=existing.id))
        flash(f'TRS already generated for this item — {existing.trs_no}. '
              f'Opening it for review.', 'info')
        return redirect(url_for('trs.edit_trs', trs_id=existing.id))

    # Compute item sequence within the GRN
    all_items = grn.items.order_by(GrnItem.sr_no).all()
    item_seq  = next((idx for idx, it in enumerate(all_items, 1)
                      if it.id == item.id), 1)

    # Pre-fill values
    no_pkts  = float(item.no_of_boxes or 0)
    per_pkt  = float(item.per_box_qty or 0)
    computed = no_pkts * per_pkt
    total    = computed if computed > 0 else float(item.received_qty or 0)

    # ── Smart Previous-Supplier lookup ─────────────────────────────
    # If this material has a previous completed GRN, default new_old_material
    # to 'OLD' and pre-select that supplier. Otherwise default to 'NEW' +
    # blank (user picks manually).
    prev_supplier, prev_grn_no, prev_grn_date = \
        _find_last_grn_supplier_for_material(item.material_id, exclude_grn_id=grn.id)

    if prev_supplier:
        prev_new_old      = 'OLD'
        prev_supplier_val = prev_supplier
    else:
        prev_new_old      = 'NEW'
        prev_supplier_val = ''

    prefill = {
        'trs_no': _build_trs_no(grn, item_seq),
        'trs_date': date.today().strftime('%Y-%m-%d'),
        'item_seq': item_seq,
        'department': 'R M STORE',
        'sample_name': item.item_name or '',
        'batch_no': item.batch_no or '',
        'no_of_packets': no_pkts,
        'total_qty': total,
        'uom': item.uom or 'KG',
        'mfg_name': item.manufacturer or '',
        'mfg_date': item.mfg_date.strftime('%Y-%m-%d') if item.mfg_date else '',
        'supplier_name': grn.supplier_name or '',
        'expiry_date': item.expiry_date.strftime('%Y-%m-%d') if item.expiry_date else '',
        'grn_no': grn.grn_number_short or grn.grn_number or '',
        'grn_date': grn.grn_date.strftime('%Y-%m-%d') if grn.grn_date else '',
        'previous_supplier': prev_supplier_val,
        'new_old_material':  prev_new_old,
        'physical_state': '',
        'sample_qty': 0.020,
        'appearance': '',
        'odour': '',
        'coa_available': 'YES' if (getattr(item, 'coa_file', '') or '').strip() else 'NO',
        'verified_by_name': _username(),
        # UI hint for the form (shows where the auto-selected supplier came from)
        '_prev_grn_no':   prev_grn_no   or '',
        '_prev_grn_date': prev_grn_date.strftime('%d-%b-%Y') if prev_grn_date else '',
    }

    return render_template('trs/form.html',
                           active_page='grn',
                           mode='new',
                           trs=None,
                           grn=grn,
                           item=item,
                           prefill=prefill,
                           physical_states=_qc_options('physical_state', PHYSICAL_STATES),
                           appearances=_qc_options('appearance', APPEARANCES),
                           odours=_qc_options('odour', ODOURS),
                           supplier_options=_supplier_options(ensure_included=prev_supplier_val, grn_type=grn.grn_type),
                           new_old=NEW_OLD,
                           yes_no=YES_NO)


# ═════════════════════════════════════════════════════════════════════
# AJAX — fetch previous supplier for a material (used by form on OLD toggle)
# ═════════════════════════════════════════════════════════════════════
@trs_bp.route('/api/previous-supplier')
@login_required
def api_previous_supplier():
    """Return the latest completed-GRN supplier for the given material.

    Query params:
        material_id     (required)
        exclude_grn_id  (optional — typically the current GRN being TRS'd)

    Response JSON:
        { success: true, found: bool, supplier_name: str,
          grn_no: str, grn_date: 'YYYY-MM-DD' }
    """
    material_id    = request.args.get('material_id', type=int)
    exclude_grn_id = request.args.get('exclude_grn_id', type=int)
    if not material_id:
        return jsonify(success=False, error='material_id required'), 400

    supplier, grn_no, grn_date = \
        _find_last_grn_supplier_for_material(material_id, exclude_grn_id=exclude_grn_id)

    return jsonify(success=True,
                   found=bool(supplier),
                   supplier_name=supplier or '',
                   grn_no=grn_no or '',
                   grn_date=grn_date.strftime('%Y-%m-%d') if grn_date else '',
                   grn_date_display=grn_date.strftime('%d-%b-%Y') if grn_date else '')


# ═════════════════════════════════════════════════════════════════════
# AJAX — fetch existing TRS for GRN+item (used by form to auto-load)
# ═════════════════════════════════════════════════════════════════════
@trs_bp.route('/api/existing')
@login_required
def api_existing():
    """Return the latest TRS for a given grn_id + item_id, if any.

    Query params:
      grn_id   (required)
      item_id  (required)

    Response (JSON):
      { exists: bool, trs: {...} | null }
    """
    grn_id  = request.args.get('grn_id',  type=int)
    item_id = request.args.get('item_id', type=int)
    if not grn_id or not item_id:
        return jsonify(success=False, error='grn_id and item_id required'), 400

    trs = (TrsMaster.query
           .filter_by(grn_id=grn_id, grn_item_id=item_id, is_deleted=False)
           .order_by(TrsMaster.id.desc())
           .first())
    return jsonify(success=True,
                   exists=bool(trs),
                   trs=trs.to_dict() if trs else None)


# ═════════════════════════════════════════════════════════════════════
# SAVE
# ═════════════════════════════════════════════════════════════════════
@trs_bp.route('/save', methods=['POST'])
@login_required
def save_trs():
    grn_id  = request.form.get('grn_id', type=int)
    item_id = request.form.get('item_id', type=int)
    trs_id  = request.form.get('trs_id', type=int)

    if not grn_id or not item_id:
        return jsonify(success=False, error='Missing grn_id or item_id'), 400

    grn  = GrnMaster.query.get_or_404(grn_id)
    item = GrnItem.query.get_or_404(item_id)

    # Edit mode?
    if trs_id:
        trs = TrsMaster.query.get_or_404(trs_id)
        if trs.is_deleted:
            abort(404)
    else:
        # Block duplicates
        existing = (TrsMaster.query
                    .filter_by(grn_item_id=item.id, is_deleted=False)
                    .first())
        if existing:
            return jsonify(success=False, error='TRS already exists for this item',
                           trs_id=existing.id), 409
        trs = TrsMaster()
        trs.grn_id      = grn.id
        trs.grn_item_id = item.id
        trs.grn_no      = grn.grn_number_short or grn.grn_number or ''
        trs.grn_date    = grn.grn_date
        trs.item_seq    = request.form.get('item_seq', type=int) or 1
        trs.trs_no      = (request.form.get('trs_no') or
                           _build_trs_no(grn, trs.item_seq))
        trs.created_by_id   = _user_id()
        trs.created_by_name = _username()

    # Fields from form
    trs.trs_date          = _parse_date(request.form.get('trs_date')) or date.today()
    trs.department        = (request.form.get('department') or '').strip()
    trs.sample_name       = (request.form.get('sample_name') or '').strip()
    trs.batch_no          = (request.form.get('batch_no') or '').strip()
    trs.no_of_packets     = _to_float(request.form.get('no_of_packets'))
    trs.total_qty         = _to_float(request.form.get('total_qty'))
    trs.uom               = (request.form.get('uom') or 'KG').strip()
    trs.physical_state    = (request.form.get('physical_state') or '').strip()
    trs.sample_qty        = _to_float(request.form.get('sample_qty'))
    trs.mfg_name          = (request.form.get('mfg_name') or '').strip()
    trs.mfg_date          = _parse_date(request.form.get('mfg_date'))
    trs.supplier_name     = (request.form.get('supplier_name') or '').strip()
    trs.expiry_date       = _parse_date(request.form.get('expiry_date'))
    trs.previous_supplier = (request.form.get('previous_supplier') or '').strip()
    trs.new_old_material  = (request.form.get('new_old_material') or 'OLD').strip().upper()
    trs.appearance        = (request.form.get('appearance') or '').strip()
    trs.odour             = (request.form.get('odour') or '').strip()
    trs.coa_available     = (request.form.get('coa_available') or 'NO').strip().upper()

    trs.verified_by_id   = _user_id()
    trs.verified_by_name = (request.form.get('verified_by_name') or _username()).strip()
    trs.verified_at      = datetime.utcnow()
    trs.updated_by_name  = _username()

    if not trs.id:
        db.session.add(trs)
    db.session.commit()

    is_ajax = (request.headers.get('X-Requested-With') == 'XMLHttpRequest'
               or request.is_json)
    if is_ajax:
        return jsonify(success=True, trs_id=trs.id,
                       redirect=url_for('trs.view_trs', trs_id=trs.id))

    flash(f'TRS {trs.trs_no} saved.', 'success')
    return redirect(url_for('trs.view_trs', trs_id=trs.id))


# ═════════════════════════════════════════════════════════════════════
# VIEW (= certificate)
# ═════════════════════════════════════════════════════════════════════
@trs_bp.route('/<int:trs_id>')
@login_required
def view_trs(trs_id):
    trs = TrsMaster.query.get_or_404(trs_id)
    if trs.is_deleted:
        abort(404)
    grn  = GrnMaster.query.get(trs.grn_id)
    item = GrnItem.query.get(trs.grn_item_id)
    return render_template('trs/certificate.html',
                           active_page='grn',
                           trs=trs, grn=grn, item=item)


@trs_bp.route('/<int:trs_id>/sticker')
@login_required
def trs_sticker(trs_id):
    """QC-APPROVED sticker (small printable label) for an approved TRS."""
    trs = TrsMaster.query.get_or_404(trs_id)
    if trs.is_deleted:
        abort(404)
    return render_template('trs/sticker.html', trs=trs)


# ═════════════════════════════════════════════════════════════════════
# EDIT
# ═════════════════════════════════════════════════════════════════════
@trs_bp.route('/<int:trs_id>/edit')
@login_required
def edit_trs(trs_id):
    trs = TrsMaster.query.get_or_404(trs_id)
    if trs.is_deleted:
        abort(404)
    grn  = GrnMaster.query.get_or_404(trs.grn_id)
    item = GrnItem.query.get_or_404(trs.grn_item_id)

    prefill = trs.to_dict()

    # Make sure the saved previous_supplier is included in the dropdown options,
    # even if that supplier is no longer in the active master.
    return render_template('trs/form.html',
                           active_page='grn',
                           mode='edit',
                           trs=trs,
                           grn=grn,
                           item=item,
                           prefill=prefill,
                           physical_states=_qc_options('physical_state', PHYSICAL_STATES),
                           appearances=_qc_options('appearance', APPEARANCES),
                           odours=_qc_options('odour', ODOURS),
                           supplier_options=_supplier_options(ensure_included=trs.previous_supplier, grn_type=grn.grn_type),
                           new_old=NEW_OLD,
                           yes_no=YES_NO)


# ═════════════════════════════════════════════════════════════════════
# DELETE (soft)
# ═════════════════════════════════════════════════════════════════════
@trs_bp.route('/<int:trs_id>/delete', methods=['POST'])
@login_required
def delete_trs(trs_id):
    trs = TrsMaster.query.get_or_404(trs_id)
    role = (getattr(current_user, 'role', '') or '').lower()
    if role not in ('admin', 'director', 'manager') and trs.created_by_id != _user_id():
        return jsonify(success=False, error='Permission denied'), 403
    trs.is_deleted     = True
    trs.updated_by_name = _username()
    db.session.commit()
    return jsonify(success=True, redirect=url_for('trs.grn_items', grn_id=trs.grn_id))
