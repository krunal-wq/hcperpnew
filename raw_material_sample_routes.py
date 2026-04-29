"""
raw_material_sample_routes.py — Raw Material Sample Request module
==================================================================
Blueprint:  raw_material_sample   at  /raw-material-sample

Module flow:
    NPD / R&D    →  creates request   (status = sent_to_purchase)
    Purchase     →  picks supplier    (status = supplier_finalized)
    Purchase     →  places order      (status = order_placed)
    Purchase     →  enters tracking   (status = order_dispatched)
    NPD / R&D    →  confirms receipt  (status = sample_received)

Access (role-based):
    NPD / R&D users              → can create, can mark received
    Purchase users               → can finalise supplier / place order / dispatch
    Admin / Manager              → full control (see all + edit any stage)
    Everyone with module access  → can view their own requests

Endpoints (page):
    GET  /raw-material-sample/                  Console page (listing)

Endpoints (JSON API):
    GET    /raw-material-sample/api/list        Paginated rows + summary
    POST   /raw-material-sample/api/create      Create new request
    GET    /raw-material-sample/api/<id>        Full record + activity log
    POST   /raw-material-sample/api/<id>/finalize-supplier
    POST   /raw-material-sample/api/<id>/place-order
    POST   /raw-material-sample/api/<id>/dispatch
    POST   /raw-material-sample/api/<id>/receive
    POST   /raw-material-sample/api/<id>/cancel
    POST   /raw-material-sample/api/<id>/edit   (only at request_created /
                                                 sent_to_purchase stage)
    DELETE /raw-material-sample/api/<id>        Soft delete (admin/manager)

    GET    /raw-material-sample/api/notifications
    POST   /raw-material-sample/api/notifications/<id>/read
"""

from datetime import datetime, date
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy import or_, func

from models import db, User
from models.raw_material_sample import (
    RawMaterialSampleRequest, RMSActivityLog, RMSNotification, RMSDailyAck,
    RMS_STATUSES, RMS_STATUS_LABELS,
)
from permissions import get_perm, get_grid_columns, save_grid_columns
from audit_helper import audit


raw_material_sample_bp = Blueprint(
    'raw_material_sample',
    __name__,
    url_prefix='/raw-material-sample',
)


# ════════════════════════════════════════════════════════════════════
#  Role helpers
# ════════════════════════════════════════════════════════════════════

# Roles that are treated as "Purchase team" — they see the Purchase
# action buttons (finalise supplier / place order / dispatch).
PURCHASE_ROLES   = {'purchase', 'purchase_manager', 'purchase_executive'}

# Roles that are treated as "Requester" — NPD / R&D side
REQUESTER_ROLES  = {'npd', 'rd_executive', 'rd_manager', 'npd_manager',
                    'rd', 'npd_executive'}

# Full-access roles
FULL_ACCESS_ROLES = {'admin', 'manager'}


def _role(user) -> str:
    return (getattr(user, 'role', '') or '').lower()


def _is_admin(user) -> bool:
    return _role(user) in FULL_ACCESS_ROLES


def _is_purchase(user) -> bool:
    """
    Purchase team — can take actions (finalise / order / dispatch).
    Admin always counts. Hardcoded purchase roles count. Users whose
    role is unknown/custom but who have been granted can_edit on this
    module via ACP also count (covers setups where Purchase team has
    role='user' with permission grants).
    """
    if _is_admin(user):
        return True
    role = _role(user)
    if role in PURCHASE_ROLES:
        return True
    if role in REQUESTER_ROLES:
        return False   # explicit requester — never treat as Purchase
    # Unknown role → permission-based detection
    try:
        perm = get_perm('raw_material_sample')
        return bool(perm and getattr(perm, 'can_edit', False))
    except Exception:
        return False


def _is_requester(user) -> bool:
    return _is_admin(user) or _role(user) in REQUESTER_ROLES


def _can_view_module() -> bool:
    """Has the user been granted access to this menu at all?"""
    if _is_admin(current_user):
        return True
    perm = get_perm('raw_material_sample')
    return bool(perm and getattr(perm, 'can_view', False))


# ════════════════════════════════════════════════════════════════════
#  Action-level sub-permissions (per-button gating)
# ════════════════════════════════════════════════════════════════════
#
# Each workflow action is gated by a sub-permission key. Admin gets all
# implicitly. Other users need the specific chip enabled in ACP. As a
# legacy fallback, users with `can_edit` on the module who are NOT
# explicit requesters keep their existing access — protects existing
# Purchase users until admin sets up sub-perms granularly.
#
ACTION_KEYS = (
    'finalize_supplier',   # Finalise Supplier
    'mark_dispatched',     # Mark Dispatched
    'mark_received',       # Confirm Receipt
    'cancel_request',      # Cancel
)


def _can_action(action_key: str, user=None) -> bool:
    """
    Check if user can perform a given workflow action.

    Strict permission model:
        1. Admin → always allowed (bypass).
        2. Explicit sub-permission chip set in ACP → use that value.
        3. Otherwise → DENIED.

    There are NO automatic fallbacks based on can_edit, role, or
    request ownership. Every action button must be explicitly granted
    via the ACP panel chips.
    """
    user = user or current_user
    if _is_admin(user):
        return True
    try:
        perm = get_perm('raw_material_sample')
    except Exception:
        return False
    if not perm:
        return False
    try:
        subs = perm.get_sub_permissions() if hasattr(perm, 'get_sub_permissions') else {}
    except Exception:
        subs = {}
    return bool(subs.get(action_key, False))


def _user_action_perms() -> dict:
    """Return {action_key: bool} dict for all 5 actions — for the page template."""
    return {k: _can_action(k) for k in ACTION_KEYS}


def _can_delete(user=None) -> bool:
    """Soft-delete permission — admin OR can_delete flag on the module."""
    user = user or current_user
    if _is_admin(user):
        return True
    try:
        perm = get_perm('raw_material_sample')
        return bool(perm and getattr(perm, 'can_delete', False))
    except Exception:
        return False


def _can_edit(user=None) -> bool:
    """Edit permission — admin OR can_edit flag on the module."""
    user = user or current_user
    if _is_admin(user):
        return True
    try:
        perm = get_perm('raw_material_sample')
        return bool(perm and getattr(perm, 'can_edit', False))
    except Exception:
        return False


def _can_export(user=None) -> bool:
    user = user or current_user
    if _is_admin(user):
        return True
    try:
        perm = get_perm('raw_material_sample')
        return bool(perm and getattr(perm, 'can_export', False))
    except Exception:
        return False


def _can_import(user=None) -> bool:
    user = user or current_user
    if _is_admin(user):
        return True
    try:
        perm = get_perm('raw_material_sample')
        return bool(perm and getattr(perm, 'can_import', False))
    except Exception:
        return False


# Statuses where the request is still mutable (can edit / delete / cancel).
# Once Purchase has finalised the supplier, the request is locked.
MUTABLE_STATUSES = ('request_created', 'sent_to_purchase')


# ════════════════════════════════════════════════════════════════════
#  Grid columns — user-customisable display
# ════════════════════════════════════════════════════════════════════
# Each entry: (key, label). The 'material' column is a composite cell
# (material_name + inci_name). Front-end uses these labels as table
# headers and renders cells via its own per-key renderer map.

RMS_GRID_COLUMNS = [
    ('request_no',       'Req. No'),
    ('created_at',       'Date'),
    ('material',         'Material'),
    ('quantity',         'Quantity'),
    ('required_by_date', 'Required Date'),
    ('supplier',         'Supplier'),
    ('status',           'Status'),
    ('requested_by',     'Requested By'),
    ('application',      'Application'),
    ('order_no',         'PO No'),
    ('courier_name',     'Courier'),
    ('tracking_no',      'Tracking'),
    ('dispatch_date',    'Dispatch Date'),
    ('received_date',    'Received Date'),
]

RMS_DEFAULT_COLUMNS = [
    'request_no', 'created_at', 'material', 'quantity',
    'required_by_date', 'supplier', 'status',
]

RMS_VALID_COLUMN_KEYS = {k for k, _ in RMS_GRID_COLUMNS}


# Columns accepted in CSV import (case-insensitive header match).
# 'material_name' is required — others optional.
RMS_IMPORT_COLUMNS = [
    'material_name', 'inci_name', 'quantity', 'required_by_date',
    'application', 'suggested_supplier', 'purpose_remarks',
]


# ════════════════════════════════════════════════════════════════════
#  Utility helpers
# ════════════════════════════════════════════════════════════════════

def _gen_request_no() -> str:
    """Generate next RMS-XXXX request number."""
    last = (RawMaterialSampleRequest.query
            .order_by(RawMaterialSampleRequest.id.desc())
            .first())
    nxt = (last.id + 1) if last else 1
    return f'RMS-{nxt:04d}'


def _parse_date(s):
    """Parse a YYYY-MM-DD or DD-MM-YYYY string. Empty → None."""
    if not s:
        return None
    s = str(s).strip()
    for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _log(req, action, from_status='', to_status='', note=''):
    """Append an entry to the request's activity log."""
    log = RMSActivityLog(
        request_id  = req.id,
        user_id     = current_user.id if current_user.is_authenticated else None,
        username    = current_user.username if current_user.is_authenticated else 'system',
        action      = action,
        from_status = from_status or '',
        to_status   = to_status or '',
        note        = note or '',
    )
    db.session.add(log)


def _notify(req, user_ids, title, body):
    """Push notifications for a list of user_ids."""
    for uid in set(uid for uid in user_ids if uid):
        n = RMSNotification(
            request_id=req.id, user_id=uid, title=title, body=body,
        )
        db.session.add(n)


def _purchase_user_ids():
    """Return user_ids of all active users in Purchase roles."""
    rows = User.query.filter(
        User.is_active == True,
        User.role.in_(list(PURCHASE_ROLES)),
    ).all()
    return [u.id for u in rows]


def _requester_followers(req):
    """
    Who should be notified when a Purchase-side update happens?
    The original requester + anyone in NPD/R&D management role.
    """
    ids = {req.requested_by}
    rows = User.query.filter(
        User.is_active == True,
        User.role.in_(['npd_manager', 'rd_manager']),
    ).all()
    ids.update(u.id for u in rows)
    return list(ids)


# ════════════════════════════════════════════════════════════════════
#  PAGE — main listing/console
# ════════════════════════════════════════════════════════════════════

@raw_material_sample_bp.route('/')
@login_required
def index():
    """Render the Raw Material Sample Request console page."""
    if not _can_view_module():
        return render_template(
            'errors/403.html',
            message='You do not have access to Raw Material Sample Request.'
        ), 403

    # Pass role-flags + per-action sub-permissions + grid columns
    user_cols = get_grid_columns(
        'raw_material_sample',
        RMS_DEFAULT_COLUMNS,
        all_valid_cols=list(RMS_VALID_COLUMN_KEYS),
    )
    return render_template(
        'raw_material_sample/index.html',
        active_page='raw_material_sample',
        is_admin     = _is_admin(current_user),
        is_purchase  = _is_purchase(current_user),
        is_requester = _is_requester(current_user),
        rms_perms    = _user_action_perms(),
        can_edit     = _can_edit(),
        can_delete   = _can_delete(),
        can_export   = _can_export(),
        can_import   = _can_import(),
        all_columns  = RMS_GRID_COLUMNS,
        user_columns = user_cols,
        statuses     = RMS_STATUS_LABELS,
    )


# ════════════════════════════════════════════════════════════════════
#  API — list (with filters + summary counts)
# ════════════════════════════════════════════════════════════════════

@raw_material_sample_bp.route('/api/list')
@login_required
def api_list():
    """
    Filters (all optional, query-string):
        ?status=<slug or 'all'>
        ?q=<text>            search material/inci/order_no/request_no/supplier
        ?from=YYYY-MM-DD
        ?to=YYYY-MM-DD
        ?my=1                only my own requests
        ?page=1&page_size=25
    Returns JSON: { items:[...], total, page, page_size, summary:{...} }
    """
    if not _can_view_module():
        return jsonify({'error': 'forbidden'}), 403

    f_status = (request.args.get('status') or '').strip()
    f_q      = (request.args.get('q')      or '').strip()
    f_from   = _parse_date(request.args.get('from'))
    f_to     = _parse_date(request.args.get('to'))
    f_my     = request.args.get('my') == '1'
    page     = max(1, request.args.get('page',      type=int) or 1)
    page_size= min(100, max(5, request.args.get('page_size', type=int) or 25))

    base = RawMaterialSampleRequest.query.filter(
        RawMaterialSampleRequest.is_deleted == False
    )

    # Non-admin / non-purchase users see only their own + any they followed
    if not (_is_admin(current_user) or _is_purchase(current_user)):
        base = base.filter(RawMaterialSampleRequest.requested_by == current_user.id)
    elif f_my:
        base = base.filter(RawMaterialSampleRequest.requested_by == current_user.id)

    if f_status and f_status != 'all' and f_status in RMS_STATUSES:
        base = base.filter(RawMaterialSampleRequest.status == f_status)

    if f_from:
        base = base.filter(func.date(RawMaterialSampleRequest.created_at) >= f_from)
    if f_to:
        base = base.filter(func.date(RawMaterialSampleRequest.created_at) <= f_to)

    if f_q:
        like = f'%{f_q}%'
        base = base.filter(or_(
            RawMaterialSampleRequest.material_name.ilike(like),
            RawMaterialSampleRequest.inci_name.ilike(like),
            RawMaterialSampleRequest.request_no.ilike(like),
            RawMaterialSampleRequest.actual_supplier.ilike(like),
            RawMaterialSampleRequest.suggested_supplier.ilike(like),
            RawMaterialSampleRequest.order_no.ilike(like),
            RawMaterialSampleRequest.tracking_no.ilike(like),
        ))

    total = base.count()
    rows  = (base.order_by(RawMaterialSampleRequest.id.desc())
                 .offset((page-1) * page_size)
                 .limit(page_size)
                 .all())

    # ── Summary counts (apply same visibility filter as listing) ──
    counts_q = db.session.query(
        RawMaterialSampleRequest.status,
        func.count(RawMaterialSampleRequest.id)
    ).filter(RawMaterialSampleRequest.is_deleted == False)

    if not (_is_admin(current_user) or _is_purchase(current_user)):
        counts_q = counts_q.filter(
            RawMaterialSampleRequest.requested_by == current_user.id
        )

    counts = dict(counts_q.group_by(RawMaterialSampleRequest.status).all())
    summary = {
        'total'             : sum(counts.values()),
        'request_created'   : counts.get('request_created', 0),
        'sent_to_purchase'  : counts.get('sent_to_purchase', 0),
        'supplier_finalized': counts.get('supplier_finalized', 0),
        'order_placed'      : counts.get('order_placed', 0),
        'order_dispatched'  : counts.get('order_dispatched', 0),
        'sample_received'   : counts.get('sample_received', 0),
        'cancelled'         : counts.get('cancelled', 0),
    }

    return jsonify({
        'items'    : [r.to_dict() for r in rows],
        'total'    : total,
        'page'     : page,
        'page_size': page_size,
        'summary'  : summary,
    })


# ════════════════════════════════════════════════════════════════════
#  API — fetch single record + activity log
# ════════════════════════════════════════════════════════════════════

@raw_material_sample_bp.route('/api/<int:rid>')
@login_required
def api_get(rid):
    if not _can_view_module():
        return jsonify({'error': 'forbidden'}), 403

    r = RawMaterialSampleRequest.query.get_or_404(rid)
    if r.is_deleted:
        return jsonify({'error': 'not found'}), 404

    # Permission gate — non-admin / non-purchase can see only their own
    if not (_is_admin(current_user) or _is_purchase(current_user)):
        if r.requested_by != current_user.id:
            return jsonify({'error': 'forbidden'}), 403

    return jsonify({'item': r.to_dict(include_logs=True)})


# ════════════════════════════════════════════════════════════════════
#  API — create new request   (NPD / R&D)
# ════════════════════════════════════════════════════════════════════

@raw_material_sample_bp.route('/api/create', methods=['POST'])
@login_required
def api_create():
    """Any user with module-add permission can create a request."""
    if not _can_view_module():
        return jsonify({'error': 'forbidden'}), 403

    perm = get_perm('raw_material_sample')
    if not (_is_admin(current_user) or (perm and getattr(perm, 'can_add', False))):
        return jsonify({'error': 'no add permission'}), 403

    data = request.get_json(silent=True) or request.form
    material = (data.get('material_name') or '').strip()
    if not material:
        return jsonify({'error': 'Material name is required'}), 400

    req = RawMaterialSampleRequest(
        request_no         = _gen_request_no(),
        material_name      = material[:300],
        inci_name          = (data.get('inci_name')          or '').strip()[:300],
        quantity           = (data.get('quantity')           or '').strip()[:60],
        purpose_remarks    = (data.get('purpose_remarks')    or '').strip(),
        application        = (data.get('application')        or '').strip()[:200],
        suggested_supplier = (data.get('suggested_supplier') or '').strip()[:300],
        required_by_date   = _parse_date(data.get('required_by_date')),
        requested_by       = current_user.id,
        # On creation: mark as already sent_to_purchase (auto-routed)
        status             = 'sent_to_purchase',
    )
    db.session.add(req)
    db.session.flush()   # need req.id for log + notifications

    _log(req, 'CREATE', from_status='', to_status='sent_to_purchase',
         note=f'Request created and sent to Purchase.')

    # Notify all purchase users
    _notify(
        req, _purchase_user_ids(),
        title=f'New material sample request {req.request_no}',
        body=f'{material} — requested by '
             f'{current_user.full_name or current_user.username}',
    )

    db.session.commit()
    audit('raw_material_sample', 'CREATE',
          current_user.id, current_user.username,
          f'{req.request_no} • {material}',
          commit=True)

    return jsonify({'ok': True, 'item': req.to_dict()})


# ════════════════════════════════════════════════════════════════════
#  API — edit (only allowed BEFORE supplier is finalised)
# ════════════════════════════════════════════════════════════════════

@raw_material_sample_bp.route('/api/<int:rid>/edit', methods=['POST'])
@login_required
def api_edit(rid):
    if not _can_view_module():
        return jsonify({'error': 'forbidden'}), 403

    r = RawMaterialSampleRequest.query.get_or_404(rid)
    if r.is_deleted:
        return jsonify({'error': 'not found'}), 404

    # Edit allowed for: admin, anyone with can_edit on the module.
    if not _can_edit():
        return jsonify({'error': 'You do not have permission to edit.'}), 403

    # Lock editing once Purchase has acted (supplier finalised).
    if r.status not in MUTABLE_STATUSES:
        return jsonify({
            'error': 'This request is locked — supplier already finalised.'
        }), 409

    data = request.get_json(silent=True) or request.form
    if 'material_name' in data:
        m = (data.get('material_name') or '').strip()
        if not m:
            return jsonify({'error': 'Material name cannot be empty'}), 400
        r.material_name = m[:300]

    for k, maxlen in (
        ('inci_name', 300),
        ('quantity', 60),
        ('application', 200),
        ('suggested_supplier', 300),
    ):
        if k in data:
            setattr(r, k, (data.get(k) or '').strip()[:maxlen])

    for k in ('purpose_remarks',):
        if k in data:
            setattr(r, k, (data.get(k) or '').strip())

    if 'required_by_date' in data:
        r.required_by_date = _parse_date(data.get('required_by_date'))

    _log(r, 'EDIT', from_status=r.status, to_status=r.status,
         note='Request details edited.')

    db.session.commit()
    audit('raw_material_sample', 'EDIT',
          current_user.id, current_user.username, r.request_no, commit=True)

    return jsonify({'ok': True, 'item': r.to_dict()})


# ════════════════════════════════════════════════════════════════════
#  API — Purchase: finalise supplier
# ════════════════════════════════════════════════════════════════════

@raw_material_sample_bp.route('/api/<int:rid>/finalize-supplier', methods=['POST'])
@login_required
def api_finalize_supplier(rid):
    if not _can_action('finalize_supplier'):
        return jsonify({'error': 'You do not have permission to finalise supplier.'}), 403

    r = RawMaterialSampleRequest.query.get_or_404(rid)
    if r.is_deleted:
        return jsonify({'error': 'not found'}), 404
    if r.status not in ('sent_to_purchase', 'request_created'):
        return jsonify({
            'error': f'Cannot finalise supplier from status "{r.status_label}"'
        }), 409

    data = request.get_json(silent=True) or request.form
    supplier = (data.get('actual_supplier') or '').strip()
    if not supplier:
        return jsonify({'error': 'Supplier name is required'}), 400

    prev = r.status
    r.actual_supplier        = supplier[:300]
    r.supplier_contact       = (data.get('supplier_contact') or '').strip()[:200]
    try:
        r.rate_per_kg = float(data.get('rate_per_kg') or 0)
    except (TypeError, ValueError):
        r.rate_per_kg = 0
    r.moq                    = (data.get('moq')       or '').strip()[:60]
    r.lead_time              = (data.get('lead_time') or '').strip()[:60]
    r.supplier_finalized_at  = datetime.utcnow()
    r.supplier_finalized_by  = current_user.id
    r.status                 = 'supplier_finalized'

    _log(r, 'STATUS_CHANGE', from_status=prev, to_status='supplier_finalized',
         note=f'Supplier finalised: {supplier}')

    _notify(
        r, _requester_followers(r),
        title=f'{r.request_no} — supplier finalised',
        body=f'Supplier "{supplier}" has been selected for {r.material_name}.',
    )

    db.session.commit()
    audit('raw_material_sample', 'FINALIZE_SUPPLIER',
          current_user.id, current_user.username,
          f'{r.request_no} → {supplier}', commit=True)

    return jsonify({'ok': True, 'item': r.to_dict()})


# ════════════════════════════════════════════════════════════════════
#  API — Purchase: place order
# ════════════════════════════════════════════════════════════════════

@raw_material_sample_bp.route('/api/<int:rid>/place-order', methods=['POST'])
@login_required
def api_place_order(rid):
    if not _can_action('place_order'):
        return jsonify({'error': 'You do not have permission to place order.'}), 403

    r = RawMaterialSampleRequest.query.get_or_404(rid)
    if r.is_deleted:
        return jsonify({'error': 'not found'}), 404
    if r.status != 'supplier_finalized':
        return jsonify({
            'error': 'Finalise supplier before placing order.'
        }), 409

    data = request.get_json(silent=True) or request.form
    order_no = (data.get('order_no') or '').strip()
    if not order_no:
        return jsonify({'error': 'Order / PO number is required'}), 400

    prev = r.status
    r.order_no        = order_no[:60]
    r.order_placed_at = datetime.utcnow()
    r.order_placed_by = current_user.id
    r.status          = 'order_placed'

    _log(r, 'STATUS_CHANGE', from_status=prev, to_status='order_placed',
         note=f'Order placed: {order_no}')

    _notify(
        r, _requester_followers(r),
        title=f'{r.request_no} — order placed',
        body=f'PO {order_no} placed with {r.actual_supplier}.',
    )

    db.session.commit()
    audit('raw_material_sample', 'PLACE_ORDER',
          current_user.id, current_user.username,
          f'{r.request_no} → {order_no}', commit=True)

    return jsonify({'ok': True, 'item': r.to_dict()})


# ════════════════════════════════════════════════════════════════════
#  API — Purchase: dispatch / tracking
# ════════════════════════════════════════════════════════════════════

@raw_material_sample_bp.route('/api/<int:rid>/dispatch', methods=['POST'])
@login_required
def api_dispatch(rid):
    if not _can_action('mark_dispatched'):
        return jsonify({'error': 'You do not have permission to mark dispatched.'}), 403

    r = RawMaterialSampleRequest.query.get_or_404(rid)
    if r.is_deleted:
        return jsonify({'error': 'not found'}), 404
    if r.status not in ('order_placed', 'supplier_finalized'):
        return jsonify({
            'error': 'Place the order before marking dispatched.'
        }), 409

    data = request.get_json(silent=True) or request.form
    courier   = (data.get('courier_name') or '').strip()
    tracking  = (data.get('tracking_no')  or '').strip()
    disp_date = _parse_date(data.get('dispatch_date')) or date.today()
    remarks   = (data.get('dispatch_remarks') or '').strip()
    order_no  = (data.get('order_no') or '').strip()
    if not courier and not tracking:
        return jsonify({
            'error': 'Provide at least courier name or tracking number.'
        }), 400

    prev = r.status
    if order_no:
        r.order_no = order_no[:60]
    r.courier_name     = courier[:200]
    r.tracking_no      = tracking[:120]
    r.dispatch_date    = disp_date
    r.dispatch_remarks = remarks
    r.dispatched_at    = datetime.utcnow()
    r.dispatched_by    = current_user.id
    r.status           = 'order_dispatched'

    _log(r, 'STATUS_CHANGE', from_status=prev, to_status='order_dispatched',
         note=f'Dispatched via {courier or "—"}, '
              f'tracking: {tracking or "—"}')

    # ⭐ This is the headline notification — tell NPD & R&D
    _notify(
        r, _requester_followers(r),
        title=f'{r.request_no} — order dispatched ✈️',
        body=f'{r.material_name} dispatched. '
             f'Courier: {courier or "—"}, Tracking: {tracking or "—"}',
    )

    db.session.commit()
    audit('raw_material_sample', 'DISPATCH',
          current_user.id, current_user.username,
          f'{r.request_no} → {courier} {tracking}', commit=True)

    return jsonify({'ok': True, 'item': r.to_dict()})


# ════════════════════════════════════════════════════════════════════
#  API — Requester: confirm sample received
# ════════════════════════════════════════════════════════════════════

@raw_material_sample_bp.route('/api/<int:rid>/receive', methods=['POST'])
@login_required
def api_receive(rid):
    if not _can_view_module():
        return jsonify({'error': 'forbidden'}), 403

    r = RawMaterialSampleRequest.query.get_or_404(rid)
    if r.is_deleted:
        return jsonify({'error': 'not found'}), 404

    # Mark received: strictly gated by mark_received sub-perm.
    if not _can_action('mark_received'):
        return jsonify({'error': 'You do not have permission to mark received.'}), 403

    if r.status not in ('order_dispatched', 'order_placed'):
        return jsonify({
            'error': 'Sample can only be marked received after dispatch.'
        }), 409

    data = request.get_json(silent=True) or request.form
    prev = r.status
    r.received_qty    = (data.get('received_qty')    or '').strip()[:60]
    r.batch_no        = (data.get('batch_no')        or '').strip()[:120]
    r.receipt_remarks = (data.get('receipt_remarks') or '').strip()
    r.received_date   = _parse_date(data.get('received_date')) or date.today()
    r.received_at     = datetime.utcnow()
    r.received_by     = current_user.id
    r.status          = 'sample_received'

    _log(r, 'STATUS_CHANGE', from_status=prev, to_status='sample_received',
         note=f'Sample received. Qty: {r.received_qty or "—"}, '
              f'Batch: {r.batch_no or "—"}')

    # Notify Purchase that the loop is closed
    _notify(
        r, _purchase_user_ids(),
        title=f'{r.request_no} — sample received ✅',
        body=f'{r.material_name} marked received by '
             f'{current_user.full_name or current_user.username}.',
    )

    db.session.commit()
    audit('raw_material_sample', 'RECEIVE',
          current_user.id, current_user.username, r.request_no, commit=True)

    return jsonify({'ok': True, 'item': r.to_dict()})


# ════════════════════════════════════════════════════════════════════
#  API — cancel
# ════════════════════════════════════════════════════════════════════

@raw_material_sample_bp.route('/api/<int:rid>/cancel', methods=['POST'])
@login_required
def api_cancel(rid):
    if not _can_view_module():
        return jsonify({'error': 'forbidden'}), 403

    r = RawMaterialSampleRequest.query.get_or_404(rid)
    if r.is_deleted:
        return jsonify({'error': 'not found'}), 404

    # Cancel is strictly permission-gated (Admin or cancel_request sub-perm).
    # No automatic self-cancel for requesters — must be granted explicitly.
    if not _can_action('cancel_request'):
        return jsonify({'error': 'You do not have permission to cancel this request.'}), 403

    # Cancel only allowed BEFORE supplier finalisation. Once Purchase
    # has actively engaged with vendors / placed an order / dispatched,
    # cancellation requires manual coordination, not a single click.
    if r.status not in MUTABLE_STATUSES:
        return jsonify({
            'error': f'Cannot cancel — request is already "{r.status_label}".'
        }), 409

    data = request.get_json(silent=True) or request.form
    reason = (data.get('reason') or '').strip()

    prev = r.status
    r.status = 'cancelled'
    _log(r, 'STATUS_CHANGE', from_status=prev, to_status='cancelled',
         note=f'Cancelled. Reason: {reason or "—"}')

    _notify(
        r, _purchase_user_ids() + _requester_followers(r),
        title=f'{r.request_no} — cancelled',
        body=f'Cancelled by {current_user.full_name or current_user.username}. '
             f'Reason: {reason or "—"}',
    )

    db.session.commit()
    audit('raw_material_sample', 'CANCEL',
          current_user.id, current_user.username, r.request_no, commit=True)
    return jsonify({'ok': True, 'item': r.to_dict()})


# ════════════════════════════════════════════════════════════════════
#  API — soft delete (admin / manager only)
# ════════════════════════════════════════════════════════════════════

@raw_material_sample_bp.route('/api/<int:rid>', methods=['DELETE'])
@login_required
def api_delete(rid):
    if not _can_delete():
        return jsonify({'error': 'You do not have permission to delete.'}), 403

    r = RawMaterialSampleRequest.query.get_or_404(rid)
    if r.is_deleted:
        return jsonify({'error': 'already deleted'}), 404
    if r.status not in MUTABLE_STATUSES:
        return jsonify({
            'error': f'Cannot delete — request is "{r.status_label}". '
                     'Only requests pending Purchase action can be deleted.'
        }), 409
    r.is_deleted = True
    _log(r, 'DELETE', from_status=r.status, to_status=r.status,
         note='Soft-deleted.')
    db.session.commit()
    audit('raw_material_sample', 'DELETE',
          current_user.id, current_user.username, r.request_no, commit=True)
    return jsonify({'ok': True})


# ════════════════════════════════════════════════════════════════════
#  API — BULK actions (multi-select on listing)
# ════════════════════════════════════════════════════════════════════
#
# Each bulk endpoint follows the same shape:
#   - Accepts `ids: [int]` plus the action's payload fields
#   - Iterates: applies action where status allows, skips otherwise
#   - Returns {ok: True, success: N, skipped: M, errors: [{id, msg}]}
#   - Same permission gates as the single-row endpoints

def _parse_bulk_ids(data):
    raw = data.get('ids') or []
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split(',') if x.strip()]
    out = []
    for v in raw:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            pass
    return out[:200]   # safety cap


def _parse_bulk_rows(data):
    """
    Returns a list of (id, fields_dict) tuples.

    Supports two payload formats for backward compatibility:
      1. Per-row (preferred): {'rows': [{'id': 1, 'foo': 'a'}, ...]}
      2. Shared: {'ids': [1, 2, ...], 'foo': 'a'} → same fields applied to all

    Capped at 200 rows for safety.
    """
    rows_in = data.get('rows')
    out = []
    if isinstance(rows_in, list) and rows_in:
        for r in rows_in[:200]:
            if not isinstance(r, dict): continue
            try:
                rid = int(r.get('id'))
            except (TypeError, ValueError):
                continue
            fields = {k: v for k, v in r.items() if k != 'id'}
            out.append((rid, fields))
        return out
    # Fall back to shared-fields format
    ids = _parse_bulk_ids(data)
    shared = {k: v for k, v in data.items() if k not in ('ids', 'rows')}
    return [(rid, dict(shared)) for rid in ids]


@raw_material_sample_bp.route('/api/bulk/finalize-supplier', methods=['POST'])
@login_required
def api_bulk_finalize(rid=None):
    if not _can_action('finalize_supplier'):
        return jsonify({'error': 'No permission to finalise supplier.'}), 403
    data = request.get_json(silent=True) or request.form
    rows = _parse_bulk_rows(data)
    if not rows:
        return jsonify({'error': 'No requests selected.'}), 400

    success, skipped, errors = 0, 0, []
    for rid, f in rows:
        r = RawMaterialSampleRequest.query.get(rid)
        if not r or r.is_deleted:
            errors.append({'id': rid, 'msg': 'Not found'}); continue
        if r.status not in ('sent_to_purchase', 'request_created'):
            skipped += 1; continue

        actual_supplier = (f.get('actual_supplier') or '').strip()
        if not actual_supplier:
            errors.append({'id': rid, 'msg': 'Actual supplier required'}); continue

        prev = r.status
        r.actual_supplier  = actual_supplier[:300]
        r.supplier_contact = (f.get('supplier_contact') or '').strip()[:200]
        r.moq              = (f.get('moq') or '').strip()[:60]
        r.lead_time        = (f.get('lead_time') or '').strip()[:60]
        try:
            r.rate_per_kg = float(f.get('rate_per_kg') or 0)
        except (TypeError, ValueError):
            r.rate_per_kg = 0
        r.supplier_finalized_at = datetime.utcnow()
        r.supplier_finalized_by = current_user.id
        r.status = 'supplier_finalized'
        _log(r, 'STATUS_CHANGE', from_status=prev, to_status='supplier_finalized',
             note=f'(Bulk) Supplier finalised: {actual_supplier}')
        success += 1

    db.session.commit()
    audit('raw_material_sample', 'BULK_FINALIZE',
          current_user.id, current_user.username,
          f'{success} ok / {skipped} skip', commit=True)
    return jsonify({'ok': True, 'success': success,
                    'skipped': skipped, 'errors': errors})


@raw_material_sample_bp.route('/api/bulk/dispatch', methods=['POST'])
@login_required
def api_bulk_dispatch():
    if not _can_action('mark_dispatched'):
        return jsonify({'error': 'No permission to mark dispatched.'}), 403
    data = request.get_json(silent=True) or request.form
    rows = _parse_bulk_rows(data)
    if not rows:
        return jsonify({'error': 'No requests selected.'}), 400

    success, skipped, errors = 0, 0, []
    for rid, f in rows:
        r = RawMaterialSampleRequest.query.get(rid)
        if not r or r.is_deleted:
            errors.append({'id': rid, 'msg': 'Not found'}); continue
        if r.status not in ('supplier_finalized', 'order_placed'):
            skipped += 1; continue

        courier   = (f.get('courier_name') or '').strip()
        tracking  = (f.get('tracking_no')  or '').strip()
        disp_date = _parse_date(f.get('dispatch_date')) or date.today()
        remarks   = (f.get('dispatch_remarks') or '').strip()
        order_no  = (f.get('order_no') or '').strip()
        if not courier and not tracking:
            errors.append({'id': rid, 'msg': 'Courier or tracking required'}); continue

        prev = r.status
        if order_no: r.order_no = order_no[:60]
        r.courier_name     = courier[:200]
        r.tracking_no      = tracking[:120]
        r.dispatch_date    = disp_date
        r.dispatch_remarks = remarks
        r.dispatched_at    = datetime.utcnow()
        r.dispatched_by    = current_user.id
        r.status           = 'order_dispatched'
        _log(r, 'STATUS_CHANGE', from_status=prev, to_status='order_dispatched',
             note=f'(Bulk) Dispatched via {courier or "—"}, '
                  f'tracking: {tracking or "—"}')
        _notify(r, _requester_followers(r),
                title=f'{r.request_no} — order dispatched ✈️',
                body=f'{r.material_name} dispatched. '
                     f'Courier: {courier or "—"}, Tracking: {tracking or "—"}')
        success += 1

    db.session.commit()
    audit('raw_material_sample', 'BULK_DISPATCH',
          current_user.id, current_user.username,
          f'{success} ok / {skipped} skip', commit=True)
    return jsonify({'ok': True, 'success': success,
                    'skipped': skipped, 'errors': errors})


@raw_material_sample_bp.route('/api/bulk/receive', methods=['POST'])
@login_required
def api_bulk_receive():
    if not _can_action('mark_received'):
        return jsonify({'error': 'No permission to mark received.'}), 403
    data = request.get_json(silent=True) or request.form
    rows = _parse_bulk_rows(data)
    if not rows:
        return jsonify({'error': 'No requests selected.'}), 400

    success, skipped, errors = 0, 0, []
    for rid, f in rows:
        r = RawMaterialSampleRequest.query.get(rid)
        if not r or r.is_deleted:
            errors.append({'id': rid, 'msg': 'Not found'}); continue
        if r.status not in ('order_dispatched', 'order_placed'):
            skipped += 1; continue

        recv_date = _parse_date(f.get('received_date')) or date.today()
        remarks   = (f.get('receipt_remarks') or '').strip()
        qty       = (f.get('received_qty') or '').strip()
        batch     = (f.get('batch_no') or '').strip()

        prev = r.status
        if qty:   r.received_qty = qty[:60]
        if batch: r.batch_no     = batch[:120]
        r.received_date    = recv_date
        r.receipt_remarks  = remarks
        r.received_at      = datetime.utcnow()
        r.received_by      = current_user.id
        r.status           = 'sample_received'
        _log(r, 'STATUS_CHANGE', from_status=prev, to_status='sample_received',
             note=f'(Bulk) Sample received.')
        success += 1

    db.session.commit()
    audit('raw_material_sample', 'BULK_RECEIVE',
          current_user.id, current_user.username,
          f'{success} ok / {skipped} skip', commit=True)
    return jsonify({'ok': True, 'success': success,
                    'skipped': skipped, 'errors': errors})


@raw_material_sample_bp.route('/api/bulk/cancel', methods=['POST'])
@login_required
def api_bulk_cancel():
    if not _can_action('cancel_request'):
        return jsonify({'error': 'No permission to cancel.'}), 403
    data = request.get_json(silent=True) or request.form
    ids  = _parse_bulk_ids(data)
    if not ids:
        return jsonify({'error': 'No requests selected.'}), 400
    reason = (data.get('reason') or '').strip()

    success, skipped, errors = 0, 0, []
    for rid in ids:
        r = RawMaterialSampleRequest.query.get(rid)
        if not r or r.is_deleted:
            errors.append({'id': rid, 'msg': 'Not found'}); continue
        # Cancel only allowed pre-finalization
        if r.status not in MUTABLE_STATUSES:
            skipped += 1; continue
        prev = r.status
        r.status = 'cancelled'
        _log(r, 'STATUS_CHANGE', from_status=prev, to_status='cancelled',
             note=f'(Bulk) Cancelled. Reason: {reason or "—"}')
        _notify(r, _purchase_user_ids() + _requester_followers(r),
                title=f'{r.request_no} — cancelled',
                body=f'Cancelled (bulk) by {current_user.full_name or current_user.username}. '
                     f'Reason: {reason or "—"}')
        success += 1

    db.session.commit()
    audit('raw_material_sample', 'BULK_CANCEL',
          current_user.id, current_user.username,
          f'{success} ok / {skipped} skip', commit=True)
    return jsonify({'ok': True, 'success': success,
                    'skipped': skipped, 'errors': errors})


@raw_material_sample_bp.route('/api/bulk/delete', methods=['POST'])
@login_required
def api_bulk_delete():
    if not _can_delete():
        return jsonify({'error': 'No permission to delete.'}), 403
    data = request.get_json(silent=True) or request.form
    ids  = _parse_bulk_ids(data)
    if not ids:
        return jsonify({'error': 'No requests selected.'}), 400

    success, skipped, errors = 0, 0, []
    for rid in ids:
        r = RawMaterialSampleRequest.query.get(rid)
        if not r or r.is_deleted:
            errors.append({'id': rid, 'msg': 'Not found'}); continue
        if r.status not in MUTABLE_STATUSES:
            skipped += 1; continue
        r.is_deleted = True
        _log(r, 'DELETE', from_status=r.status, to_status=r.status,
             note='(Bulk) Soft-deleted.')
        success += 1

    db.session.commit()
    audit('raw_material_sample', 'BULK_DELETE',
          current_user.id, current_user.username,
          f'{success} deleted / {skipped} skip', commit=True)
    return jsonify({'ok': True, 'success': success,
                    'skipped': skipped, 'errors': errors})


# ════════════════════════════════════════════════════════════════════
#  API — Export / Import / Column preferences
# ════════════════════════════════════════════════════════════════════

@raw_material_sample_bp.route('/api/export')
@login_required
def api_export():
    """CSV export of current filtered listing."""
    if not _can_export():
        return jsonify({'error': 'No export permission.'}), 403

    import csv, io
    from flask import Response

    f_status = (request.args.get('status') or '').strip()
    f_q      = (request.args.get('q')      or '').strip()
    f_from   = _parse_date(request.args.get('from'))
    f_to     = _parse_date(request.args.get('to'))

    base = RawMaterialSampleRequest.query.filter(
        RawMaterialSampleRequest.is_deleted == False
    )
    # Apply same visibility filter as listing
    if not (_is_admin(current_user) or _is_purchase(current_user)):
        base = base.filter(RawMaterialSampleRequest.requested_by == current_user.id)
    if f_status and f_status != 'all' and f_status in RMS_STATUSES:
        base = base.filter(RawMaterialSampleRequest.status == f_status)
    if f_from:
        base = base.filter(func.date(RawMaterialSampleRequest.created_at) >= f_from)
    if f_to:
        base = base.filter(func.date(RawMaterialSampleRequest.created_at) <= f_to)
    if f_q:
        like = f'%{f_q}%'
        base = base.filter(or_(
            RawMaterialSampleRequest.material_name.ilike(like),
            RawMaterialSampleRequest.inci_name.ilike(like),
            RawMaterialSampleRequest.request_no.ilike(like),
            RawMaterialSampleRequest.actual_supplier.ilike(like),
            RawMaterialSampleRequest.suggested_supplier.ilike(like),
            RawMaterialSampleRequest.order_no.ilike(like),
            RawMaterialSampleRequest.tracking_no.ilike(like),
        ))

    rows = base.order_by(RawMaterialSampleRequest.id.desc()).all()

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([
        'Request No', 'Created At', 'Material', 'INCI', 'Quantity',
        'Required Date', 'Application', 'Suggested Supplier', 'Requested By',
        'Status', 'Actual Supplier', 'Supplier Contact', 'Rate / KG', 'MOQ',
        'Lead Time', 'PO No', 'Courier', 'Tracking No', 'Dispatch Date',
        'Received Qty', 'Batch No', 'Received Date', 'Purpose / Remarks',
    ])
    for r in rows:
        d = r.to_dict()
        w.writerow([
            d.get('request_no', ''), d.get('created_at', ''),
            d.get('material_name', ''), d.get('inci_name', ''),
            d.get('quantity', ''), d.get('required_by_date', ''),
            d.get('application', ''), d.get('suggested_supplier', ''),
            d.get('requester_name', ''), d.get('status_label', ''),
            d.get('actual_supplier', ''), d.get('supplier_contact', ''),
            d.get('rate_per_kg', ''), d.get('moq', ''), d.get('lead_time', ''),
            d.get('order_no', ''), d.get('courier_name', ''),
            d.get('tracking_no', ''), d.get('dispatch_date', ''),
            d.get('received_qty', ''), d.get('batch_no', ''),
            d.get('received_date', ''), d.get('purpose_remarks', ''),
        ])

    audit('raw_material_sample', 'EXPORT',
          current_user.id, current_user.username,
          f'{len(rows)} rows exported', commit=True)

    fname = f"raw_material_samples_{datetime.utcnow():%Y%m%d_%H%M}.csv"
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{fname}"'},
    )


@raw_material_sample_bp.route('/api/import-template')
@login_required
def api_import_template():
    """Empty CSV with proper headers — for users to fill and upload."""
    if not _can_import():
        return jsonify({'error': 'No import permission.'}), 403
    import io
    from flask import Response
    buf = io.StringIO()
    headers = RMS_IMPORT_COLUMNS
    buf.write(','.join(headers) + '\n')
    # Sample row to guide users
    buf.write('Tulsi Extract,Ocimum Sanctum,500 GM,2026-12-31,'
              'Skin Care,Naturex India,For new toner formula\n')
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition':
                 'attachment; filename="raw_material_sample_template.csv"'},
    )


@raw_material_sample_bp.route('/api/import', methods=['POST'])
@login_required
def api_import():
    """Bulk-create requests from a CSV file upload."""
    if not _can_import():
        return jsonify({'error': 'No import permission.'}), 403

    f = request.files.get('file')
    if not f:
        return jsonify({'error': 'No file uploaded.'}), 400

    import csv, io
    try:
        text = f.read().decode('utf-8-sig')   # handle BOM
    except UnicodeDecodeError:
        return jsonify({'error': 'File must be UTF-8 CSV.'}), 400

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return jsonify({'error': 'CSV has no header row.'}), 400

    # Normalise header lookup (case-insensitive, trim, snake_case)
    def norm(s): return (s or '').strip().lower().replace(' ', '_')
    hdr_map = {norm(h): h for h in reader.fieldnames}

    if 'material_name' not in hdr_map:
        return jsonify({
            'error': 'Required column missing: material_name. '
                     'Download the template for correct headers.'
        }), 400

    success, errors = 0, []
    notified_purchase_ids = _purchase_user_ids()

    for i, row in enumerate(reader, start=2):   # row 2 = first data row
        def g(k):
            real = hdr_map.get(k)
            return (row.get(real, '') or '').strip() if real else ''
        material = g('material_name')
        if not material:
            errors.append({'row': i, 'msg': 'material_name empty'})
            continue
        try:
            req = RawMaterialSampleRequest(
                request_no         = _gen_request_no(),
                material_name      = material[:300],
                inci_name          = g('inci_name')[:300],
                quantity           = g('quantity')[:60],
                purpose_remarks    = g('purpose_remarks'),
                application        = g('application')[:200],
                suggested_supplier = g('suggested_supplier')[:300],
                required_by_date   = _parse_date(g('required_by_date')),
                requested_by       = current_user.id,
                status             = 'sent_to_purchase',
            )
            db.session.add(req)
            db.session.flush()
            _log(req, 'CREATE', from_status='', to_status='sent_to_purchase',
                 note='(Imported via CSV)')
            _notify(
                req, notified_purchase_ids,
                title=f'New sample request: {req.request_no}',
                body=f'{req.material_name} (qty: {req.quantity or "—"}) '
                     f'imported by {current_user.full_name or current_user.username}',
            )
            success += 1
        except Exception as e:
            db.session.rollback()
            errors.append({'row': i, 'msg': str(e)[:200]})
            continue

    db.session.commit()
    audit('raw_material_sample', 'IMPORT',
          current_user.id, current_user.username,
          f'{success} imported / {len(errors)} errors', commit=True)
    return jsonify({'ok': True, 'success': success, 'errors': errors})


@raw_material_sample_bp.route('/api/columns', methods=['GET', 'POST'])
@login_required
def api_columns():
    """Per-user grid column preferences."""
    if not _can_view_module():
        return jsonify({'error': 'forbidden'}), 403

    if request.method == 'POST':
        data = request.get_json(silent=True) or request.form
        cols = data.get('columns') or []
        if isinstance(cols, str):
            cols = [c.strip() for c in cols.split(',') if c.strip()]
        # Filter to valid keys only
        cols = [c for c in cols if c in RMS_VALID_COLUMN_KEYS]
        if not cols:
            return jsonify({'error': 'At least one column must be selected.'}), 400
        try:
            save_grid_columns('raw_material_sample', cols)
        except Exception as e:
            return jsonify({'error': f'Save failed: {e}'}), 500
        return jsonify({'ok': True, 'columns': cols})

    # GET → return user's saved cols (or default)
    cols = get_grid_columns(
        'raw_material_sample',
        RMS_DEFAULT_COLUMNS,
        all_valid_cols=list(RMS_VALID_COLUMN_KEYS),
    )
    return jsonify({'columns': cols})


# ════════════════════════════════════════════════════════════════════
#  API — Daily Pending Reminder
# ════════════════════════════════════════════════════════════════════
# Shows once per user per day. Lists every non-terminal request the
# user is responsible for (admin/purchase see all; requesters see own).

@raw_material_sample_bp.route('/api/daily-reminder')
@login_required
def api_daily_reminder():
    if not _can_view_module():
        return jsonify({'show': False, 'reason': 'forbidden'})

    today = date.today()

    # Already acknowledged today?
    ack = RMSDailyAck.query.filter_by(
        user_id=current_user.id, ack_date=today
    ).first()
    if ack:
        return jsonify({'show': False, 'reason': 'already_acknowledged'})

    # Pending = anything not received and not cancelled
    base = RawMaterialSampleRequest.query.filter(
        RawMaterialSampleRequest.is_deleted == False,
        ~RawMaterialSampleRequest.status.in_(['sample_received', 'cancelled']),
    )
    # Role-based visibility — same rule as listing
    if not (_is_admin(current_user) or _is_purchase(current_user)):
        base = base.filter(RawMaterialSampleRequest.requested_by == current_user.id)

    rows = base.order_by(RawMaterialSampleRequest.id.desc()).all()
    if not rows:
        return jsonify({'show': False, 'reason': 'no_pending'})

    # Find earliest creation date among pending — used in the popup banner
    earliest = None
    for r in rows:
        if r.created_at:
            d = r.created_at.date()
            if earliest is None or d < earliest:
                earliest = d

    items = []
    for r in rows[:100]:    # cap for safety
        items.append({
            'id'            : r.id,
            'request_no'    : r.request_no,
            'material_name' : r.material_name or '—',
            'status'        : r.status,
            'status_label'  : RMS_STATUS_LABELS.get(r.status, r.status),
            'created_at'    : r.created_at.strftime('%Y-%m-%d') if r.created_at else '',
        })

    return jsonify({
        'show'                 : True,
        'count'                : len(rows),
        'earliest_pending_date': earliest.strftime('%d %b %Y') if earliest else '',
        'items'                : items,
    })


@raw_material_sample_bp.route('/api/daily-reminder/acknowledge', methods=['POST'])
@login_required
def api_daily_reminder_ack():
    if not _can_view_module():
        return jsonify({'error': 'forbidden'}), 403

    today = date.today()
    existing = RMSDailyAck.query.filter_by(
        user_id=current_user.id, ack_date=today
    ).first()
    if existing:
        return jsonify({'ok': True, 'already': True})

    data = request.get_json(silent=True) or {}
    try:
        cnt = int(data.get('pending_count') or 0)
    except (TypeError, ValueError):
        cnt = 0

    ack = RMSDailyAck(
        user_id=current_user.id,
        ack_date=today,
        pending_count=cnt,
    )
    db.session.add(ack)
    db.session.commit()
    return jsonify({'ok': True})



@raw_material_sample_bp.route('/api/notifications')
@login_required
def api_notifications():
    """Return up to 30 recent notifications for current user."""
    rows = (RMSNotification.query
            .filter(RMSNotification.user_id == current_user.id)
            .order_by(RMSNotification.id.desc())
            .limit(30)
            .all())
    unread = (RMSNotification.query
              .filter_by(user_id=current_user.id, is_read=False)
              .count())
    return jsonify({
        'items' : [n.to_dict() for n in rows],
        'unread': unread,
    })


@raw_material_sample_bp.route('/api/notifications/<int:nid>/read', methods=['POST'])
@login_required
def api_notif_read(nid):
    n = RMSNotification.query.get_or_404(nid)
    if n.user_id != current_user.id and not _is_admin(current_user):
        return jsonify({'error': 'forbidden'}), 403
    n.is_read = True
    db.session.commit()
    return jsonify({'ok': True})


@raw_material_sample_bp.route('/api/notifications/read-all', methods=['POST'])
@login_required
def api_notif_read_all():
    (RMSNotification.query
     .filter_by(user_id=current_user.id, is_read=False)
     .update({'is_read': True}))
    db.session.commit()
    return jsonify({'ok': True})
