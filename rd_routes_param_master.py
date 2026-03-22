# ═══════════════════════════════════════════════════════════════════════════
# ADD THIS TO YOUR rd/routes.py
# ═══════════════════════════════════════════════════════════════════════════
# 1. Import the model at the top of routes.py:
#    from .models import RDTestParameter   (or wherever your models live)
#    from flask import request, jsonify
# ═══════════════════════════════════════════════════════════════════════════

# ── Parameter Master Page ────────────────────────────────────────────────────
@rd_bp.route('/param-master')
@login_required
def param_master():
    params = RDTestParameter.query.order_by(RDTestParameter.sort_order, RDTestParameter.id).all()
    return render_template('rd/param_master.html', params=params)


# ── Add Parameter ────────────────────────────────────────────────────────────
@rd_bp.route('/param-master/add', methods=['POST'])
@login_required
def param_master_add():
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify(success=False, error='Name is required')

    # Check duplicate
    existing = RDTestParameter.query.filter(
        db.func.lower(RDTestParameter.name) == name.lower()
    ).first()
    if existing:
        return jsonify(success=False, error=f'Parameter "{name}" already exists')

    # Get next sort_order
    max_order = db.session.query(db.func.max(RDTestParameter.sort_order)).scalar() or 0

    param = RDTestParameter(
        name        = name,
        default_val = (data.get('default_val') or '').strip(),
        unit        = (data.get('unit') or '').strip(),
        sort_order  = max_order + 1,
        is_active   = True
    )
    db.session.add(param)
    db.session.commit()
    return jsonify(success=True, id=param.id)


# ── Inline Update ────────────────────────────────────────────────────────────
@rd_bp.route('/param-master/<int:pid>/update', methods=['POST'])
@login_required
def param_master_update(pid):
    param = RDTestParameter.query.get_or_404(pid)
    data  = request.get_json()
    field = data.get('field')
    value = (data.get('value') or '').strip()

    ALLOWED_FIELDS = {'name', 'default_val', 'unit'}
    if field not in ALLOWED_FIELDS:
        return jsonify(success=False, error='Invalid field')

    if field == 'name' and not value:
        return jsonify(success=False, error='Name cannot be empty')

    setattr(param, field, value)
    db.session.commit()
    return jsonify(success=True)


# ── Toggle Active/Inactive ───────────────────────────────────────────────────
@rd_bp.route('/param-master/<int:pid>/toggle', methods=['POST'])
@login_required
def param_master_toggle(pid):
    param = RDTestParameter.query.get_or_404(pid)
    param.is_active = not param.is_active
    db.session.commit()
    return jsonify(success=True, is_active=param.is_active)


# ── Delete ───────────────────────────────────────────────────────────────────
@rd_bp.route('/param-master/<int:pid>/delete', methods=['POST'])
@login_required
def param_master_delete(pid):
    param = RDTestParameter.query.get_or_404(pid)
    db.session.delete(param)
    db.session.commit()
    return jsonify(success=True)


# ── Reorder (drag & drop) ────────────────────────────────────────────────────
@rd_bp.route('/param-master/reorder', methods=['POST'])
@login_required
def param_master_reorder():
    data  = request.get_json()
    order = data.get('order', [])   # [{id: 1, sort_order: 1}, ...]
    for item in order:
        RDTestParameter.query.filter_by(id=item['id']).update({'sort_order': item['sort_order']})
    db.session.commit()
    return jsonify(success=True)


# ── API: Get active parameters for trial form (used by trials.html JS) ───────
@rd_bp.route('/param-master/list')
@login_required
def param_master_list():
    params = RDTestParameter.query.filter_by(is_active=True)\
                .order_by(RDTestParameter.sort_order).all()
    return jsonify(params=[p.to_dict() for p in params])


# ═══════════════════════════════════════════════════════════════════════════
# ALSO UPDATE YOUR EXISTING trials route to pass parameters from DB:
# ═══════════════════════════════════════════════════════════════════════════

# @rd_bp.route('/trials')
# @login_required
# def trials():
#     ...existing code...
#     test_params = RDTestParameter.query.filter_by(is_active=True)\
#                       .order_by(RDTestParameter.sort_order).all()
#     return render_template('rd/trials.html',
#         ...,
#         test_params=test_params,   # ← ADD THIS
#     )
