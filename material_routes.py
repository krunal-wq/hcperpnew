"""
material_routes.py — Item Master Module
Blueprint: material at /material
"""
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from models import db, Material, MaterialType, MaterialGroup
from permissions import get_perm

material_bp = Blueprint('material', __name__, url_prefix='/material')

def _cu(): return getattr(current_user, 'username', '') or ''
def _role(): return getattr(current_user, 'role', '') or ''
def _can(action):
    if _role() in ('admin', 'manager'): return True
    p = get_perm('material')
    return bool(p and getattr(p, f'can_{action}', False))

# ── Page ──────────────────────────────────────────────────────────────────────
@material_bp.route('/')
@material_bp.route('')
@login_required
def index():
    if not _can('view'): abort(403)
    types  = MaterialType.query.filter_by(is_active=True).order_by(MaterialType.sort_order, MaterialType.type_name).all()
    groups = MaterialGroup.query.order_by(MaterialGroup.group_name).all()
    return render_template('material/index.html',
        active_page='material', role=_role(),
        types=types, groups=groups,
        user_name=getattr(current_user,'full_name','') or _cu(),
    )

# ── API: Materials ─────────────────────────────────────────────────────────────
@material_bp.route('/api/list')
@login_required
def api_list():
    if not _can('view'): return jsonify({'status':'error','message':'Access denied'}),403
    q = Material.query
    tid = request.args.get('type_id')
    gid = request.args.get('group_id')
    search = request.args.get('search','').strip()
    active = request.args.get('active','1')
    if tid: q = q.filter(Material.material_type_id == int(tid))
    if gid: q = q.filter(Material.group_id == int(gid))
    if active == '1': q = q.filter(Material.is_active == True)
    if search:
        like = f'%{search}%'
        q = q.filter(db.or_(
            Material.material_name.ilike(like),
            Material.aliases.ilike(like),
            Material.supplier_name.ilike(like),
        ))
    rows = q.order_by(Material.material_name).all()
    return jsonify({'status':'ok','rows':[r.to_dict() for r in rows]})

@material_bp.route('/api/save', methods=['POST'])
@login_required
def api_save():
    if not _can('edit'): return jsonify({'status':'error','message':'Access denied'}),403
    d = request.get_json() or {}
    if not (d.get('material_name','').strip()):
        return jsonify({'status':'error','message':'Material Name is required'})
    try:
        eid = d.get('id')
        if eid:
            m = Material.query.get(eid)
            if not m: return jsonify({'status':'error','message':'Not found'}),404
            m.updated_by = _cu()
        else:
            m = Material()
            m.created_by = _cu()
            db.session.add(m)

        m.material_name      = d.get('material_name','').strip()
        m.aliases            = d.get('aliases','').strip()
        m.description        = d.get('description','').strip()
        m.uom                = d.get('uom','KG').strip()
        m.material_type_id   = d.get('material_type_id') or None
        m.group_id           = d.get('group_id') or None
        m.sku_sizes          = d.get('sku_sizes','').strip()
        m.supplier_name      = d.get('supplier_name','').strip()
        m.supplier_code      = d.get('supplier_code','').strip()
        m.opening_balance    = float(d.get('opening_balance') or 0)
        m.msl                = float(d.get('msl') or 0)
        m.lead_time_days     = int(d.get('lead_time_days') or 0)
        m.std_pack_size      = float(d.get('std_pack_size') or 0)
        m.last_purchase_rate = float(d.get('last_purchase_rate') or 0)
        m.hsn_code           = d.get('hsn_code','').strip()
        m.gst_rate           = float(d.get('gst_rate') or 0)
        m.taxability         = d.get('taxability','Taxable')
        m.type_of_supply     = d.get('type_of_supply','Goods')
        m.is_active          = bool(d.get('is_active', True))
        db.session.commit()
        return jsonify({'status':'ok','id':m.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}),500

@material_bp.route('/api/delete', methods=['POST'])
@login_required
def api_delete():
    if not _can('delete'): return jsonify({'status':'error','message':'Access denied'}),403
    rid = (request.get_json() or {}).get('id')
    if not rid: return jsonify({'status':'error','message':'Missing id'}),400
    try:
        m = Material.query.get(rid)
        if not m: return jsonify({'status':'error','message':'Not found'}),404
        db.session.delete(m)
        db.session.commit()
        return jsonify({'status':'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}),500

# ── API: Material Types ────────────────────────────────────────────────────────
@material_bp.route('/api/types')
@login_required
def api_types():
    rows = MaterialType.query.order_by(MaterialType.sort_order, MaterialType.type_name).all()
    return jsonify({'status':'ok','rows':[r.to_dict() for r in rows]})

@material_bp.route('/api/types/save', methods=['POST'])
@login_required
def api_types_save():
    if not _can('edit'): return jsonify({'status':'error','message':'Access denied'}),403
    d = request.get_json() or {}
    if not d.get('type_name','').strip():
        return jsonify({'status':'error','message':'Type Name is required'})
    try:
        eid = d.get('id')
        if eid:
            t = MaterialType.query.get(eid)
            if not t: return jsonify({'status':'error','message':'Not found'}),404
        else:
            t = MaterialType()
            t.created_by = _cu()
            db.session.add(t)
        t.type_name    = d.get('type_name','').strip()
        t.abbreviation = d.get('abbreviation','').strip()
        t.description  = d.get('description','').strip()
        t.color        = d.get('color','#6366f1')
        t.sort_order   = int(d.get('sort_order') or 0)
        t.is_active    = bool(d.get('is_active', True))
        t.has_sku      = bool(d.get('has_sku', False))
        db.session.commit()
        return jsonify({'status':'ok','id':t.id,'row':t.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}),500

@material_bp.route('/api/types/delete', methods=['POST'])
@login_required
def api_types_delete():
    if not _can('delete'): return jsonify({'status':'error','message':'Access denied'}),403
    rid = (request.get_json() or {}).get('id')
    try:
        t = MaterialType.query.get(rid)
        if not t: return jsonify({'status':'error','message':'Not found'}),404
        if t.materials.count() > 0:
            return jsonify({'status':'error','message':f'Cannot delete — {t.materials.count()} materials use this type'})
        db.session.delete(t)
        db.session.commit()
        return jsonify({'status':'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}),500

# ── API: Material Groups ───────────────────────────────────────────────────────
@material_bp.route('/api/groups')
@login_required
def api_groups():
    rows = MaterialGroup.query.order_by(MaterialGroup.group_name).all()
    return jsonify({'status':'ok','rows':[r.to_dict() for r in rows]})

@material_bp.route('/api/groups/save', methods=['POST'])
@login_required
def api_groups_save():
    if not _can('edit'): return jsonify({'status':'error','message':'Access denied'}),403
    d = request.get_json() or {}
    if not d.get('group_name','').strip():
        return jsonify({'status':'error','message':'Group Name is required'})
    try:
        eid = d.get('id')
        if eid:
            g = MaterialGroup.query.get(eid)
            if not g: return jsonify({'status':'error','message':'Not found'}),404
        else:
            g = MaterialGroup()
            g.created_by = _cu()
            db.session.add(g)
        parent_id = d.get('parent_id') or None
        if parent_id and int(parent_id) == (eid or 0):
            return jsonify({'status':'error','message':'Group cannot be its own parent'})
        g.group_name  = d.get('group_name','').strip()
        g.parent_id   = int(parent_id) if parent_id else None
        g.description = d.get('description','').strip()
        db.session.commit()
        return jsonify({'status':'ok','id':g.id,'row':g.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}),500

@material_bp.route('/api/groups/delete', methods=['POST'])
@login_required
def api_groups_delete():
    if not _can('delete'): return jsonify({'status':'error','message':'Access denied'}),403
    rid = (request.get_json() or {}).get('id')
    try:
        g = MaterialGroup.query.get(rid)
        if not g: return jsonify({'status':'error','message':'Not found'}),404
        if g.materials.count() > 0:
            return jsonify({'status':'error','message':f'Cannot delete — {g.materials.count()} materials use this group'})
        if g.children.count() > 0:
            return jsonify({'status':'error','message':'Cannot delete — has child groups'})
        db.session.delete(g)
        db.session.commit()
        return jsonify({'status':'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}),500
