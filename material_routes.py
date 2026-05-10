"""
material_routes.py — Item Master Module
Blueprint: material at /material
"""
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from models import db, Material, MaterialType, MaterialGroup, ItemCategory
from models.client import ClientBrand
from permissions import get_perm, get_sub_perm

material_bp = Blueprint('material', __name__, url_prefix='/material')

def _cu(): return getattr(current_user, 'username', '') or ''
def _role(): return getattr(current_user, 'role', '') or ''
def _can(action):
    if _role() in ('admin', 'manager'): return True
    p = get_perm('material')
    return bool(p and getattr(p, f'can_{action}', False))

# ── Page ──────────────────────────────────────────────────────────────────────

# Abbreviation → sub_perm key mapping
_TYPE_PERM_MAP = {
    'RM':  'type_rm',
    'PM':  'type_pm',
    'FG':  'type_fg',
    'SFG': 'type_sfg',
    'CON': 'type_con',
    'TG':  'type_tg',
}

def _allowed_types(types):
    """Filter types list based on user's type-level sub-permissions.
    Admin → sab types.
    Non-admin → sirf jinhe permission mili ho.
    Agar kisi bhi type ka perm check nahi set → sab allow (backward compat).
    """
    from flask_login import current_user
    if getattr(current_user, 'role', '') == 'admin':
        return types
    filtered = []
    for t in types:
        abbr = (t.abbreviation or '').upper()
        key  = _TYPE_PERM_MAP.get(abbr)
        if key is None:
            # Unknown type abbreviation → allow by default
            filtered.append(t)
        elif get_sub_perm('material', key):
            filtered.append(t)
    return filtered  # empty list = no types permitted → form dikhayega 'no types available'

@material_bp.route('/')
@material_bp.route('')
@login_required
def index():
    if not _can('view'): abort(403)
    types  = _allowed_types(MaterialType.query.order_by(MaterialType.sort_order, MaterialType.type_name).all())
    groups = MaterialGroup.query.order_by(MaterialGroup.group_name).all()
    categories = ItemCategory.query.filter_by(is_active=True).order_by(ItemCategory.category_name).all()
    return render_template('material/index.html',
        active_page='material', role=_role(),
        types=types, groups=groups, categories=categories,
        can_add    = _can('add'),
        can_edit   = _can('edit'),
        can_delete = _can('delete'),
        user_name=getattr(current_user,'full_name','') or _cu(),
    )


# ── Add Item Page ──────────────────────────────────────────────────────────────
@material_bp.route('/add')
@login_required
def add_item():
    if not _can('add'): abort(403)
    types  = _allowed_types(MaterialType.query.filter_by(is_active=True).order_by(MaterialType.sort_order, MaterialType.type_name).all())
    groups = MaterialGroup.query.order_by(MaterialGroup.group_name).all()
    brands     = ClientBrand.query.filter_by(is_active=True).order_by(ClientBrand.brand_name).all()
    categories = ItemCategory.query.filter_by(is_active=True).order_by(ItemCategory.category_name).all()
    return render_template('material/add_item.html',
        active_page='material', role=_role(),
        types=types, groups=groups, item=None,
        brands=brands, categories=categories,
        user_name=getattr(current_user, 'full_name', '') or _cu(),
    )

# ── Edit Item Page ─────────────────────────────────────────────────────────────
@material_bp.route('/edit/<int:item_id>')
@login_required
def edit_item(item_id):
    if not _can('edit'): abort(403)
    item = Material.query.get_or_404(item_id)
    types  = _allowed_types(MaterialType.query.filter_by(is_active=True).order_by(MaterialType.sort_order, MaterialType.type_name).all())
    groups = MaterialGroup.query.order_by(MaterialGroup.group_name).all()
    brands     = ClientBrand.query.filter_by(is_active=True).order_by(ClientBrand.brand_name).all()
    categories = ItemCategory.query.filter_by(is_active=True).order_by(ItemCategory.category_name).all()
    return render_template('material/add_item.html',
        active_page='material', role=_role(),
        types=types, groups=groups, item=item,
        brands=brands, categories=categories,
        user_name=getattr(current_user, 'full_name', '') or _cu(),
    )


# ── API: Materials ─────────────────────────────────────────────────────────────
@material_bp.route('/api/list')
@login_required
def api_list():
    if not _can('view'): return jsonify({'status':'error','message':'Access denied'}),403
    q = Material.query

    # ── Filter by allowed types (permission-based) ──────────────────
    allowed = _allowed_types(
        MaterialType.query.order_by(MaterialType.sort_order).all()
    )
    allowed_ids = [t.id for t in allowed]
    if allowed_ids:
        q = q.filter(Material.material_type_id.in_(allowed_ids))

    tid = request.args.get('type_id')
    gid = request.args.get('group_id')
    search = request.args.get('search','').strip()
    active = request.args.get('active','1')
    if tid: q = q.filter(Material.material_type_id == int(tid))
    if gid: q = q.filter(Material.group_id == int(gid))
    if active == '1': q = q.filter(Material.is_active == True)
    q = q.filter(db.or_(Material.is_deleted == False, Material.is_deleted == None))
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
        m.code               = d.get('code', '').strip()
        m.inci_name          = d.get('inci_name', '').strip()
        m.brand              = d.get('brand', '').strip()
        m.category           = d.get('category', '').strip()
        m.per_box_qty        = int(d.get('per_box_qty') or 0)
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
        m.is_deleted = True
        m.deleted_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'status':'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}),500

@material_bp.route('/api/deleted-list')
@login_required
def api_deleted_list():
    if not _can('view'): return jsonify({'status':'error','message':'Access denied'}),403
    rows = Material.query.filter(Material.is_deleted == True).order_by(Material.deleted_at.desc()).all()
    return jsonify({'status':'ok','rows':[r.to_dict() for r in rows]})

@material_bp.route('/api/restore', methods=['POST'])
@login_required
def api_restore():
    if not _can('delete'): return jsonify({'status':'error','message':'Access denied'}),403
    rid = (request.get_json() or {}).get('id')
    try:
        m = Material.query.get(rid)
        if not m: return jsonify({'status':'error','message':'Not found'}),404
        m.is_deleted = False
        m.deleted_at = None
        db.session.commit()
        return jsonify({'status':'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}),500

@material_bp.route('/api/permanent-delete', methods=['POST'])
@login_required
def api_permanent_delete():
    if not _can('delete'): return jsonify({'status':'error','message':'Access denied'}),403
    rid = (request.get_json() or {}).get('id')
    try:
        m = Material.query.get(rid)
        if not m: return jsonify({'status':'error','message':'Not found'}),404
        if not m.is_deleted:
            return jsonify({'status':'error','message':'Move to trash first'})
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
    rows = MaterialType.query.filter(db.or_(MaterialType.is_deleted==False,MaterialType.is_deleted==None)).order_by(MaterialType.sort_order, MaterialType.type_name).all()
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
        if t.materials.filter_by(is_deleted=False).count() > 0:
            return jsonify({'status':'error','message':f'Cannot delete — {t.materials.filter_by(is_deleted=False).count()} active materials use this type'})
        t.is_deleted = True; t.deleted_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'status':'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}),500

@material_bp.route('/api/types/deleted-list')
@login_required
def api_types_deleted_list():
    rows = MaterialType.query.filter_by(is_deleted=True).order_by(MaterialType.deleted_at.desc()).all()
    return jsonify({'status':'ok','rows':[r.to_dict() for r in rows]})

@material_bp.route('/api/types/restore', methods=['POST'])
@login_required
def api_types_restore():
    if not _can('delete'): return jsonify({'status':'error','message':'Access denied'}),403
    rid = (request.get_json() or {}).get('id')
    t = MaterialType.query.get(rid)
    if not t: return jsonify({'status':'error','message':'Not found'}),404
    t.is_deleted = False; t.deleted_at = None
    db.session.commit()
    return jsonify({'status':'ok'})

@material_bp.route('/api/types/permanent-delete', methods=['POST'])
@login_required
def api_types_perm_delete():
    if not _can('delete'): return jsonify({'status':'error','message':'Access denied'}),403
    rid = (request.get_json() or {}).get('id')
    t = MaterialType.query.get(rid)
    if not t: return jsonify({'status':'error','message':'Not found'}),404
    db.session.delete(t); db.session.commit()
    return jsonify({'status':'ok'})

# ── API: Material Groups ───────────────────────────────────────────────────────
@material_bp.route('/api/groups')
@login_required
def api_groups():
    rows = MaterialGroup.query.filter(db.or_(MaterialGroup.is_deleted==False,MaterialGroup.is_deleted==None)).order_by(MaterialGroup.group_name).all()
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
        g.is_deleted = True; g.deleted_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'status':'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}),500

@material_bp.route('/api/groups/deleted-list')
@login_required
def api_groups_deleted_list():
    rows = MaterialGroup.query.filter_by(is_deleted=True).order_by(MaterialGroup.deleted_at.desc()).all()
    return jsonify({'status':'ok','rows':[r.to_dict() for r in rows]})

@material_bp.route('/api/groups/restore', methods=['POST'])
@login_required
def api_groups_restore():
    if not _can('delete'): return jsonify({'status':'error','message':'Access denied'}),403
    rid = (request.get_json() or {}).get('id')
    g = MaterialGroup.query.get(rid)
    if not g: return jsonify({'status':'error','message':'Not found'}),404
    g.is_deleted = False; g.deleted_at = None
    db.session.commit()
    return jsonify({'status':'ok'})

@material_bp.route('/api/groups/permanent-delete', methods=['POST'])
@login_required
def api_groups_perm_delete():
    if not _can('delete'): return jsonify({'status':'error','message':'Access denied'}),403
    rid = (request.get_json() or {}).get('id')
    g = MaterialGroup.query.get(rid)
    if not g: return jsonify({'status':'error','message':'Not found'}),404
    db.session.delete(g); db.session.commit()
    return jsonify({'status':'ok'})

# ── API: Item Categories ───────────────────────────────────────────────────────
@material_bp.route('/api/categories')
@login_required
def api_categories():
    rows = ItemCategory.query.filter(db.or_(ItemCategory.is_deleted==False,ItemCategory.is_deleted==None)).order_by(ItemCategory.category_name).all()
    return jsonify({'status': 'ok', 'rows': [r.to_dict() for r in rows]})

@material_bp.route('/api/categories/save', methods=['POST'])
@login_required
def api_categories_save():
    if not _can('edit'): return jsonify({'status': 'error', 'message': 'Access denied'}), 403
    d = request.get_json() or {}
    if not d.get('category_name', '').strip():
        return jsonify({'status': 'error', 'message': 'Category Name required'})
    try:
        eid = d.get('id')
        if eid:
            cat = ItemCategory.query.get(eid)
            if not cat: return jsonify({'status': 'error', 'message': 'Not found'}), 404
        else:
            cat = ItemCategory()
            cat.created_by = _cu()
            db.session.add(cat)
        cat.category_name = d.get('category_name', '').strip()
        cat.description   = d.get('description', '').strip()
        cat.is_active     = bool(d.get('is_active', True))
        db.session.commit()
        return jsonify({'status': 'ok', 'id': cat.id, 'row': cat.to_dict()})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@material_bp.route('/api/categories/delete', methods=['POST'])
@login_required
def api_categories_delete():
    if not _can('delete'): return jsonify({'status': 'error', 'message': 'Access denied'}), 403
    rid = (request.get_json() or {}).get('id')
    try:
        cat = ItemCategory.query.get(rid)
        if not cat: return jsonify({'status': 'error', 'message': 'Not found'}), 404
        cat.is_deleted = True; cat.deleted_at = datetime.utcnow()
        db.session.commit()
        return jsonify({'status': 'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@material_bp.route('/api/categories/deleted-list')
@login_required
def api_categories_deleted_list():
    rows = ItemCategory.query.filter_by(is_deleted=True).order_by(ItemCategory.deleted_at.desc()).all()
    return jsonify({'status':'ok','rows':[r.to_dict() for r in rows]})

@material_bp.route('/api/categories/restore', methods=['POST'])
@login_required
def api_categories_restore():
    if not _can('delete'): return jsonify({'status':'error','message':'Access denied'}),403
    rid = (request.get_json() or {}).get('id')
    cat = ItemCategory.query.get(rid)
    if not cat: return jsonify({'status':'error','message':'Not found'}),404
    cat.is_deleted = False; cat.deleted_at = None
    db.session.commit()
    return jsonify({'status':'ok'})

@material_bp.route('/api/categories/permanent-delete', methods=['POST'])
@login_required
def api_categories_perm_delete():
    if not _can('delete'): return jsonify({'status':'error','message':'Access denied'}),403
    rid = (request.get_json() or {}).get('id')
    cat = ItemCategory.query.get(rid)
    if not cat: return jsonify({'status':'error','message':'Not found'}),404
    db.session.delete(cat); db.session.commit()
    return jsonify({'status':'ok'})

# ── API: Brands (from Client Master) ──────────────────────────────────────────
@material_bp.route('/api/brands')
@login_required
def api_brands():
    brands = ClientBrand.query.filter_by(is_active=True).order_by(ClientBrand.brand_name).all()
    return jsonify({'status': 'ok', 'rows': [
        {'id': b.id, 'brand_name': b.brand_name,
         'client': b.client.company_name or b.client.contact_name if b.client else ''}
        for b in brands
    ]})
