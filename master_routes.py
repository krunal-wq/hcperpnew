"""
master_routes.py — CRUD for Lead Masters
Blueprint: masters at /masters
"""
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required
from models import db, LeadStatus, LeadSource, LeadCategory, ProductRange, CategoryMaster, UOMMaster, HSNCode
from flask_login import current_user
from datetime import datetime

masters = Blueprint('masters', __name__, url_prefix='/masters')

MASTER_MAP = {
    'status':   {'model': LeadStatus,    'label': 'Lead Status',    'icon': '🔵'},
    'source':   {'model': LeadSource,    'label': 'Lead Source',    'icon': '📌'},
    'category': {'model': LeadCategory,  'label': 'Lead Category',  'icon': '🏷️'},
    'range':    {'model': ProductRange,  'label': 'Product Range',  'icon': '📦'},
}

# Separate map for new full-featured masters
FULL_MASTER_MAP = {
    'cat_master': {'model': CategoryMaster, 'label': 'Category Master', 'icon': '🗂️'},
    'uom':        {'model': UOMMaster,      'label': 'UOM Master',      'icon': '📐'},
    'hsn':        {'model': HSNCode,        'label': 'HSN Code Master', 'icon': '🔢'},
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


# ══════════════════════════════════════
# CATEGORY MASTER — Full CRUD
# ══════════════════════════════════════

@masters.route('/uom-options')
@login_required
def uom_options():
    items = UOMMaster.query.filter_by(status=True, is_deleted=False).order_by(UOMMaster.code).all()
    return jsonify([{'id': u.id, 'code': u.code, 'name': u.name} for u in items])


@masters.route('/category-options')
@login_required
def category_options():
    items = CategoryMaster.query.filter_by(status=True, is_deleted=False).order_by(CategoryMaster.name).all()
    return jsonify([{'id': ct.id, 'name': ct.name} for ct in items])


@masters.route('/category-master')
@login_required
def category_master_list():
    search = request.args.get('search','')
    q = CategoryMaster.query.filter_by(is_deleted=False)
    if search:
        q = q.filter(CategoryMaster.name.ilike(f'%{search}%'))
    items = q.order_by(CategoryMaster.name).all()
    return render_template('masters/category_master.html', items=items, search=search, active_page='cat_master')

@masters.route('/category-master/add', methods=['POST'])
@login_required
def category_master_add():
    name = request.form.get('name','').strip()
    if not name:
        flash('Name required', 'danger'); return redirect(url_for('masters.category_master_list'))
    if CategoryMaster.query.filter_by(name=name, is_deleted=False).first():
        flash(f'"{name}" already exists', 'warning'); return redirect(url_for('masters.category_master_list'))
    obj = CategoryMaster(name=name, status=True, created_by=current_user.id)
    db.session.add(obj); db.session.commit()
    flash(f'Category "{name}" added!', 'success')
    return redirect(url_for('masters.category_master_list'))

@masters.route('/category-master/<int:id>/edit', methods=['POST'])
@login_required
def category_master_edit(id):
    obj = CategoryMaster.query.get_or_404(id)
    obj.name        = request.form.get('name', obj.name).strip()
    obj.status      = request.form.get('status') == '1'
    obj.modified_by = current_user.id
    obj.modified_at = datetime.now()
    db.session.commit(); flash('Updated!', 'success')
    return redirect(url_for('masters.category_master_list'))

@masters.route('/category-master/<int:id>/delete', methods=['POST'])
@login_required
def category_master_delete(id):
    obj = CategoryMaster.query.get_or_404(id)
    obj.is_deleted = True; obj.modified_by = current_user.id; obj.modified_at = datetime.now()
    db.session.commit(); flash(f'"{obj.name}" deleted', 'success')
    return redirect(url_for('masters.category_master_list'))

@masters.route('/category-master/<int:id>/toggle', methods=['POST'])
@login_required
def category_master_toggle(id):
    obj = CategoryMaster.query.get_or_404(id)
    obj.status = not obj.status; obj.modified_by = current_user.id; obj.modified_at = datetime.now()
    db.session.commit(); return jsonify(success=True, status=obj.status)


# ══════════════════════════════════════
# UOM MASTER — Full CRUD
# ══════════════════════════════════════

@masters.route('/uom-master')
@login_required
def uom_master_list():
    search = request.args.get('search','')
    q = UOMMaster.query.filter_by(is_deleted=False)
    if search:
        q = q.filter(UOMMaster.name.ilike(f'%{search}%') | UOMMaster.code.ilike(f'%{search}%'))
    items = q.order_by(UOMMaster.name).all()
    return render_template('masters/uom_master.html', items=items, search=search, active_page='uom_master')

@masters.route('/uom-master/add', methods=['POST'])
@login_required
def uom_master_add():
    code = request.form.get('code','').strip().upper()
    name = request.form.get('name','').strip()
    if not code or not name:
        flash('Code and Name both required', 'danger'); return redirect(url_for('masters.uom_master_list'))
    if UOMMaster.query.filter_by(code=code, is_deleted=False).first():
        flash(f'Code "{code}" already exists', 'warning'); return redirect(url_for('masters.uom_master_list'))
    obj = UOMMaster(code=code, name=name, status=True, created_by=current_user.id)
    db.session.add(obj); db.session.commit()
    flash(f'UOM "{code} - {name}" added!', 'success')
    return redirect(url_for('masters.uom_master_list'))

@masters.route('/uom-master/<int:id>/edit', methods=['POST'])
@login_required
def uom_master_edit(id):
    obj = UOMMaster.query.get_or_404(id)
    obj.code        = request.form.get('code', obj.code).strip().upper()
    obj.name        = request.form.get('name', obj.name).strip()
    obj.status      = request.form.get('status') == '1'
    obj.modified_by = current_user.id
    obj.modified_at = datetime.now()
    db.session.commit(); flash('Updated!', 'success')
    return redirect(url_for('masters.uom_master_list'))

@masters.route('/uom-master/<int:id>/delete', methods=['POST'])
@login_required
def uom_master_delete(id):
    obj = UOMMaster.query.get_or_404(id)
    obj.is_deleted = True; obj.modified_by = current_user.id; obj.modified_at = datetime.now()
    db.session.commit(); flash(f'"{obj.name}" deleted', 'success')
    return redirect(url_for('masters.uom_master_list'))

@masters.route('/uom-master/<int:id>/toggle', methods=['POST'])
@login_required
def uom_master_toggle(id):
    obj = UOMMaster.query.get_or_404(id)
    obj.status = not obj.status; obj.modified_by = current_user.id; obj.modified_at = datetime.now()
    db.session.commit(); return jsonify(success=True, status=obj.status)


# ══════════════════════════════════════
# HSN CODE MASTER — Full CRUD
# ══════════════════════════════════════

@masters.route('/hsn-master')
@login_required
def hsn_master_list():
    search = request.args.get('search','')
    q = HSNCode.query.filter_by(is_deleted=False)
    if search:
        q = q.filter(HSNCode.hsn_code.ilike(f'%{search}%') | HSNCode.description.ilike(f'%{search}%'))
    items = q.order_by(HSNCode.hsn_code).all()
    return render_template('masters/hsn_master.html', items=items, search=search, active_page='hsn_master')

@masters.route('/hsn-master/add', methods=['POST'])
@login_required
def hsn_master_add():
    hsn_code = request.form.get('hsn_code','').strip()
    if not hsn_code:
        flash('HSN Code required', 'danger'); return redirect(url_for('masters.hsn_master_list'))
    if HSNCode.query.filter_by(hsn_code=hsn_code, is_deleted=False).first():
        flash(f'HSN "{hsn_code}" already exists', 'warning'); return redirect(url_for('masters.hsn_master_list'))
    gst = float(request.form.get('gst_rate','0') or 0)
    obj = HSNCode(
        hsn_code    = hsn_code,
        description = request.form.get('description','').strip(),
        gst_rate    = gst,
        cgst        = round(gst/2, 2),
        sgst        = round(gst/2, 2),
        igst        = gst,
        cess        = float(request.form.get('cess','0') or 0),
        status      = True,
        created_by  = current_user.id,
    )
    db.session.add(obj); db.session.commit()
    flash(f'HSN Code "{hsn_code}" added!', 'success')
    return redirect(url_for('masters.hsn_master_list'))

@masters.route('/hsn-master/<int:id>/edit', methods=['POST'])
@login_required
def hsn_master_edit(id):
    obj = HSNCode.query.get_or_404(id)
    gst = float(request.form.get('gst_rate', obj.gst_rate) or 0)
    obj.hsn_code    = request.form.get('hsn_code', obj.hsn_code).strip()
    obj.description = request.form.get('description', obj.description or '').strip()
    obj.gst_rate    = gst
    obj.cgst        = round(gst/2, 2)
    obj.sgst        = round(gst/2, 2)
    obj.igst        = gst
    obj.cess        = float(request.form.get('cess', obj.cess or 0) or 0)
    obj.status      = request.form.get('status') == '1'
    obj.modified_by = current_user.id
    obj.modified_at = datetime.now()
    db.session.commit(); flash('Updated!', 'success')
    return redirect(url_for('masters.hsn_master_list'))

@masters.route('/hsn-master/<int:id>/delete', methods=['POST'])
@login_required
def hsn_master_delete(id):
    obj = HSNCode.query.get_or_404(id)
    obj.is_deleted = True; obj.modified_by = current_user.id; obj.modified_at = datetime.now()
    db.session.commit(); flash(f'HSN "{obj.hsn_code}" deleted', 'success')
    return redirect(url_for('masters.hsn_master_list'))

@masters.route('/hsn-master/<int:id>/toggle', methods=['POST'])
@login_required
def hsn_master_toggle(id):
    obj = HSNCode.query.get_or_404(id)
    obj.status = not obj.status; obj.modified_by = current_user.id; obj.modified_at = datetime.now()
    db.session.commit(); return jsonify(success=True, status=obj.status)
