"""
master_routes.py — CRUD for Lead Masters
Blueprint: masters at /masters
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from models import db, LeadStatus, LeadSource, LeadCategory, ProductRange

masters = Blueprint('masters', __name__, url_prefix='/masters')

MASTER_MAP = {
    'status':   {'model': LeadStatus,   'label': 'Lead Status',    'icon': '🔵'},
    'source':   {'model': LeadSource,   'label': 'Lead Source',    'icon': '📌'},
    'category': {'model': LeadCategory, 'label': 'Lead Category',  'icon': '🏷️'},
    'range':    {'model': ProductRange, 'label': 'Product Range',  'icon': '📦'},
}

# ── List page (all 4 masters on one page) ──
@masters.route('/')
@login_required
def index():
    data = {}
    for key, cfg in MASTER_MAP.items():
        data[key] = cfg['model'].query.order_by(cfg['model'].sort_order, cfg['model'].name).all()
    return render_template('masters/index.html', data=data, active_page='masters')

# ── Quick Add via AJAX (from lead form + button) ──
@masters.route('/quick-add', methods=['POST'])
@login_required
def quick_add():
    mtype = request.json.get('type')
    name  = request.json.get('name', '').strip()
    icon  = request.json.get('icon', '').strip() or None
    if not mtype or not name:
        return jsonify(success=False, error='Missing data'), 400
    cfg = MASTER_MAP.get(mtype)
    if not cfg:
        return jsonify(success=False, error='Unknown type'), 400
    Model = cfg['model']
    if Model.query.filter_by(name=name).first():
        return jsonify(success=False, error=f'"{name}" already exists')
    obj = Model(name=name)
    if icon: obj.icon = icon
    db.session.add(obj)
    db.session.commit()
    return jsonify(success=True, id=obj.id, name=obj.name,
                   icon=getattr(obj, 'icon', ''), label=cfg['label'])

# ── Add ──
@masters.route('/<mtype>/add', methods=['POST'])
@login_required
def add(mtype):
    cfg = MASTER_MAP.get(mtype)
    if not cfg: flash('Unknown master type', 'error'); return redirect(url_for('masters.index'))
    Model = cfg['model']
    name = request.form.get('name','').strip()
    if not name: flash('Name is required','error'); return redirect(url_for('masters.index'))
    if Model.query.filter_by(name=name).first():
        flash(f'"{name}" already exists','warning')
        return redirect(url_for('masters.index'))
    obj = Model(
        name       = name,
        icon       = request.form.get('icon','').strip() or obj.__class__.__dict__.get('icon',''),
        sort_order = int(request.form.get('sort_order', 0) or 0),
        is_active  = 'is_active' in request.form,
    )
    if mtype == 'status':
        obj.color = request.form.get('color','#6b7280')
    db.session.add(obj)
    db.session.commit()
    flash(f'{cfg["label"]} "{name}" added!', 'success')
    return redirect(url_for('masters.index') + f'#{mtype}')

# ── Edit ──
@masters.route('/<mtype>/<int:id>/edit', methods=['POST'])
@login_required
def edit(mtype, id):
    cfg = MASTER_MAP.get(mtype)
    if not cfg: flash('Unknown master type','error'); return redirect(url_for('masters.index'))
    obj = cfg['model'].query.get_or_404(id)
    obj.name       = request.form.get('name', obj.name).strip()
    obj.icon       = request.form.get('icon', obj.icon).strip()
    obj.sort_order = int(request.form.get('sort_order', obj.sort_order) or 0)
    obj.is_active  = 'is_active' in request.form
    if mtype == 'status':
        obj.color = request.form.get('color', obj.color)
    db.session.commit()
    flash(f'Updated successfully!', 'success')
    return redirect(url_for('masters.index') + f'#{mtype}')

# ── Delete ──
@masters.route('/<mtype>/<int:id>/delete', methods=['POST'])
@login_required
def delete(mtype, id):
    cfg = MASTER_MAP.get(mtype)
    if not cfg: flash('Unknown master type','error'); return redirect(url_for('masters.index'))
    obj = cfg['model'].query.get_or_404(id)
    name = obj.name
    db.session.delete(obj)
    db.session.commit()
    flash(f'"{name}" deleted', 'success')
    return redirect(url_for('masters.index') + f'#{mtype}')

# ── Toggle active ──
@masters.route('/<mtype>/<int:id>/toggle', methods=['POST'])
@login_required
def toggle(mtype, id):
    cfg = MASTER_MAP.get(mtype)
    if not cfg: return jsonify(success=False)
    obj = cfg['model'].query.get_or_404(id)
    obj.is_active = not obj.is_active
    db.session.commit()
    return jsonify(success=True, is_active=obj.is_active)

# ── Get all options for a type (used by lead form JS) ──
@masters.route('/options/<mtype>')
@login_required
def options(mtype):
    cfg = MASTER_MAP.get(mtype)
    if not cfg: return jsonify([])
    items = cfg['model'].query.filter_by(is_active=True)\
                .order_by(cfg['model'].sort_order, cfg['model'].name).all()
    return jsonify([{'id': o.id, 'name': o.name,
                     'icon': getattr(o,'icon',''),
                     'color': getattr(o,'color','')} for o in items])
