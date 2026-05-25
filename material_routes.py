"""
material_routes.py — Item Master Module
Blueprint: material at /material
"""
from datetime import datetime
from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from models import db, Material, MaterialType, MaterialGroup, ItemCategory, UOMMaster
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
    Admin / Manager → sab types (case-insensitive, whitespace-tolerant).
    Non-admin → sirf jinhe permission mili ho.
    Agar kisi bhi type ka perm check nahi set → sab allow (backward compat).
    """
    from flask_login import current_user
    role = (getattr(current_user, 'role', '') or '').strip().lower()
    if role in ('admin', 'manager'):
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

    # ── Auto Item Type: URL se item_type=RM/PM/FG ─────────────────────────
    # Jab /material?item_type=RM se aaye to auto-filter + type selector hide
    auto_type_abbr = request.args.get('item_type', '').strip().upper()
    auto_type = None
    if auto_type_abbr:
        auto_type = next(
            (t for t in types if (t.abbreviation or '').upper() == auto_type_abbr),
            None
        )

    return render_template('material/index.html',
        active_page='material', role=_role(),
        types=types, groups=groups, categories=categories,
        can_add    = _can('add'),
        can_edit   = _can('edit'),
        can_delete = _can('delete'),
        user_name=getattr(current_user,'full_name','') or _cu(),
        auto_type      = auto_type,        # MaterialType object ya None
        auto_type_abbr = auto_type_abbr,   # 'RM', 'PM', 'FG' ya ''
    )


@material_bp.route('/api/upload-image', methods=['POST'])
@login_required
def api_upload_image():
    """Store image as base64 data URL — no file system, returns data URL directly."""
    if not _can('edit'): return jsonify({'status':'error','message':'Access denied'}), 403
    d = request.get_json() or {}
    img_b64 = d.get('image_base64', '')
    if not img_b64:
        return jsonify({'status':'error','message':'No image data'}), 400
    try:
        import base64, io
        from PIL import Image
        # Ensure it's a valid image and compress to reasonable size
        if ',' in img_b64:
            header, data = img_b64.split(',', 1)
        else:
            header, data = 'data:image/png;base64', img_b64
        img_bytes = base64.b64decode(data)
        img = Image.open(io.BytesIO(img_bytes)).convert('RGB')
        # Resize to max 600px
        max_sz = 600
        if max(img.size) > max_sz:
            img.thumbnail((max_sz, max_sz), Image.LANCZOS)
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=85, optimize=True)
        compressed_b64 = base64.b64encode(buf.getvalue()).decode()
        data_url = f'data:image/jpeg;base64,{compressed_b64}'
        return jsonify({'status':'ok', 'url': data_url})
    except Exception as e:
        # Fallback: return original as-is
        if not img_b64.startswith('data:'):
            img_b64 = 'data:image/png;base64,' + img_b64
        return jsonify({'status':'ok', 'url': img_b64})


@material_bp.route('/api/process-image', methods=['POST'])
@login_required
def api_process_image():
    """
    Background removal using OpenCV GrabCut — no model download.
    Product center mein detect hota hai, background hata deta hai.
    Auto-crop to product + white background.
    """
    import base64, io
    import cv2
    import numpy as np
    from PIL import Image

    d = request.get_json() or {}
    img_b64 = d.get('image_base64', '')
    if not img_b64:
        return jsonify({'status': 'error', 'message': 'No image data'}), 400
    try:
        if ',' in img_b64:
            img_b64 = img_b64.split(',', 1)[1]
        img_bytes = base64.b64decode(img_b64)

        # Decode image
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        if img is None:
            return jsonify({'status': 'error', 'message': 'Image decode failed'}), 400

        h, w = img.shape[:2]

        # Resize to max 600px for faster processing
        max_dim = 600
        scale = 1.0
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            img = cv2.resize(img, (int(w*scale), int(h*scale)))
            h, w = img.shape[:2]

        # ── GrabCut background removal ────────────────────────────
        # Rect: 5% margin to assume product is mostly in center
        margin_x = max(5, int(w * 0.05))
        margin_y = max(5, int(h * 0.05))
        rect = (margin_x, margin_y, w - 2*margin_x, h - 2*margin_y)

        mask = np.zeros((h, w), np.uint8)
        bgd_model = np.zeros((1, 65), np.float64)
        fgd_model = np.zeros((1, 65), np.float64)

        cv2.grabCut(img, mask, rect, bgd_model, fgd_model, 8, cv2.GC_INIT_WITH_RECT)

        # 2nd pass: refine using edge info
        # Mark center region as probable foreground
        cx, cy = w//2, h//2
        inner_x = max(1, int(w * 0.2))
        inner_y = max(1, int(h * 0.2))
        mask[cy-inner_y:cy+inner_y, cx-inner_x:cx+inner_x] = cv2.GC_PR_FGD
        cv2.grabCut(img, mask, None, bgd_model, fgd_model, 3, cv2.GC_EVAL)

        # Build binary mask (foreground + probable foreground)
        fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

        # Morphological cleanup
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, kernel, iterations=3)
        fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN,  kernel, iterations=1)

        # ── Find largest contour (main product) ──────────────────
        contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        if contours:
            largest = max(contours, key=cv2.contourArea)
            clean_mask = np.zeros_like(fg_mask)
            cv2.drawContours(clean_mask, [largest], -1, 255, -1)
            # Smooth edges
            clean_mask = cv2.GaussianBlur(clean_mask, (7, 7), 0)
            fg_mask = clean_mask

        # ── Place on white background ─────────────────────────────
        img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        result  = np.ones_like(img_rgb, dtype=np.uint8) * 255  # white
        alpha   = fg_mask.astype(np.float32) / 255.0
        for c in range(3):
            result[:, :, c] = (img_rgb[:, :, c] * alpha + 255 * (1 - alpha)).astype(np.uint8)

        # ── Auto-crop to subject ───────────────────────────────────
        _, thresh = cv2.threshold(fg_mask, 30, 255, cv2.THRESH_BINARY)
        ys, xs = np.where(thresh > 0)
        if len(xs) > 0 and len(ys) > 0:
            x1, x2 = xs.min(), xs.max()
            y1, y2 = ys.min(), ys.max()
            pad = max(15, int(max(x2-x1, y2-y1) * 0.05))
            x1 = max(0, x1-pad); y1 = max(0, y1-pad)
            x2 = min(w, x2+pad); y2 = min(h, y2+pad)
            result = result[y1:y2, x1:x2]

        # ── Encode and return ────────────────────────────────────
        pil_img = Image.fromarray(result)
        # Upscale back if was downsized
        if scale < 1.0:
            new_w = int(pil_img.width / scale)
            new_h = int(pil_img.height / scale)
            pil_img = pil_img.resize((new_w, new_h), Image.LANCZOS)

        buf = io.BytesIO()
        pil_img.save(buf, format='PNG', optimize=True)
        result_b64 = base64.b64encode(buf.getvalue()).decode()

        return jsonify({'status': 'ok', 'processed': 'data:image/png;base64,' + result_b64})

    except Exception as e:
        import traceback
        return jsonify({'status': 'error', 'message': str(e), 'trace': traceback.format_exc()}), 500



@material_bp.route('/api/debug-image/<int:item_id>')
@login_required
def api_debug_image(item_id):
    from sqlalchemy import text
    row = db.session.execute(
        text('SELECT id, material_name, image_data FROM materials WHERE id=:id'),
        {'id': item_id}
    ).fetchone()
    if not row: return jsonify({'status':'error','message':'Not found'})
    return jsonify({'id':row[0],'name':row[1],'has_image':bool(row[2]),'data_url_preview':((row[2] or '')[:50]+'...' if row[2] else None)})


@material_bp.route('/masters')
@login_required
def masters():
    if not _can('view'): abort(403)
    return render_template('material/masters.html',
        active_page='material', role=_role(),
        user_name=getattr(current_user, 'full_name', '') or _cu(),
    )


@material_bp.route('/import-template')
@login_required
def import_template():
    """Download a type-aware sample CSV template for importing items."""
    abbr = request.args.get('item_type', 'RM').strip().upper()
    from flask import Response

    if abbr == 'RM':
        hdrs = 'item_name,code,aliases,category,group,inci_name,uom,msl,last_purchase_rate,opening_balance,hsn_code,gst_rate,taxability,description'
        row1 = f'Mineral Oil Light Grade,{abbr}-001,"Light Oil,Base Oil",Oils,Base Oils,Paraffinum Liquidum,KG,10,95.00,0,27101990,18,Taxable,Optional notes'
        row2 = f'Rose Fragrance Oil,{abbr}-002,"Rose Oil,Floral Scent",Fragrance,,Rosa Damascena Flower Oil,KG,5,1200.00,0,33021090,18,Taxable,'
    elif abbr == 'PM':
        hdrs = 'item_name,code,aliases,pm_type,material_type_hm_cm,brand,category,sku_size,attributes,corrugation_ply,lengthmm,widthmm,heightmm,uom,msl,last_purchase_rate,opening_balance,hsn_code,gst_rate,taxability,description'
        row1 = f'Frosted Glass Bottle 100ml,{abbr}-001,"Glass Bottle,100ml Bottle",PM,HM,Twasa,Bottles,100,"Bottle,Glass,Frosted",,,,,PCS,0,28.50,0,70109090,18,Taxable,'
        row2 = f'Corrugated Box 300x200x150mm 3Ply,{abbr}-002,"Carton Box,Corrugated Carton",Corrugation,HM,Twasa,Cartons,,,"3 Ply",300,200,150,PCS,0,18.00,0,48191000,12,Taxable,'
    elif abbr == 'FG':
        hdrs = 'item_name,code,aliases,brand,category,sku_size,per_box_qty,per_box_weight,per_box_weight_uom,uom,msl,last_purchase_rate,opening_balance,hsn_code,gst_rate,taxability,description'
        row1 = f'Rose Glow Face Wash 100ml,{abbr}-001,"Rose Face Wash,Glow Cleanser",Twasa,Face Wash,100,24,2.880,KG,PCS,0,0.00,0,33049990,18,Taxable,'
        row2 = f'Anti Dandruff Shampoo 250ml,{abbr}-002,"AD Shampoo,Dandruff Shampoo",Twasa,Shampoo,250,12,3.500,KG,PCS,0,0.00,0,33051000,18,Taxable,'
    else:
        hdrs = 'item_name,code,aliases,uom,msl,last_purchase_rate,opening_balance,hsn_code,gst_rate,taxability,description'
        row1 = f'Sample Item 1,{abbr}-001,,KG,10,100.00,0,12345678,18,Taxable,'
        row2 = f'Sample Item 2,{abbr}-002,,KG,5,50.00,0,87654321,12,Taxable,'

    csv_content = hdrs + '\n' + row1 + '\n' + row2 + '\n'
    return Response(
        '\uFEFF' + csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={abbr}_import_template.csv'}
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
    uom_list   = UOMMaster.query.filter_by(status=True, is_deleted=False).order_by(UOMMaster.code).all()

    # ── Auto Item Type from URL param ─────────────────────────────────────
    auto_type_abbr = request.args.get('item_type', '').strip().upper()
    auto_type = None
    if auto_type_abbr:
        auto_type = next(
            (t for t in types if (t.abbreviation or '').upper() == auto_type_abbr),
            None
        )

    return render_template('material/add_item.html',
        active_page='material', role=_role(),
        types=types, groups=groups, item=None,
        brands=brands, categories=categories, uom_list=uom_list,
        user_name=getattr(current_user, 'full_name', '') or _cu(),
        auto_type      = auto_type,
        auto_type_abbr = auto_type_abbr,
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
    uom_list   = UOMMaster.query.filter_by(status=True, is_deleted=False).order_by(UOMMaster.code).all()
    # Pass item_type from URL or from item's type
    auto_type_abbr = request.args.get('item_type', '').strip().upper()
    if not auto_type_abbr and item.material_type:
        auto_type_abbr = (item.material_type.abbreviation or '').upper()
    auto_type = next((t for t in types if (t.abbreviation or '').upper() == auto_type_abbr), None)
    return render_template('material/add_item.html',
        active_page='material', role=_role(),
        types=types, groups=groups, item=item,
        brands=brands, categories=categories, uom_list=uom_list,
        user_name=getattr(current_user, 'full_name', '') or _cu(),
        auto_type=auto_type,
        auto_type_abbr=auto_type_abbr,
    )


@material_bp.route('/api/next-code')
@login_required
def api_next_code():
    """Auto-generate next available code.
    PM sub-type prefixes:
      PM (regular)  → PM-0001
      Corrugation   → PM-CORR-0001
      Sleeves       → PM-SLV-0001
    All other types → ABBR-0001
    Each series is independent.
    """
    abbr     = request.args.get('type_abbr', '').strip().upper()
    pm_sub   = request.args.get('pm_sub', '').strip()   # Corrugation | Sleeves | PM | ''
    if not abbr:
        return jsonify({'status': 'error', 'message': 'type_abbr required'}), 400
    try:
        from sqlalchemy import text

        # ── Determine prefix based on type + PM sub-type ──────────────
        if abbr == 'PM':
            sub_upper = pm_sub.upper()
            if sub_upper == 'CORRUGATION':
                prefix = 'PM-CORR-'
            elif sub_upper == 'SLEEVES':
                prefix = 'PM-SLV-'
            else:
                prefix = 'PM-'   # regular PM
        else:
            prefix = f'{abbr}-'

        # ── Get all existing codes ─────────────────────────────────────
        rows = db.session.execute(
            text("SELECT code FROM materials WHERE (is_deleted IS NULL OR is_deleted = 0)")
        ).fetchall()

        existing_codes = set()
        max_num = 0

        for row in rows:
            c = (row[0] or '').upper().strip()
            if c:
                existing_codes.add(c)
            if c.startswith(prefix):
                suffix = c[len(prefix):]
                try:
                    num = int(suffix)
                    max_num = max(max_num, num)
                except (ValueError, IndexError):
                    pass

        # ── Find next available slot (4-digit, gap-free) ───────────────
        next_num = max_num + 1
        while f'{prefix}{next_num:04d}' in existing_codes:
            next_num += 1

        return jsonify({'status': 'ok', 'code': f'{prefix}{next_num:04d}'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500


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
        ))
    rows = q.order_by(Material.material_name).all()
    return jsonify({'status':'ok','rows':[r.to_dict() for r in rows]})

@material_bp.route('/api/check-name', methods=['POST'])
@login_required
def api_check_name():
    """Check if material_name already exists (case-insensitive). Exclude current id on edit."""
    d    = request.get_json() or {}
    name = d.get('material_name', '').strip()
    _raw_exc = d.get('exclude_id') or d.get('id') or ''
    try:
        exc_int = int(str(_raw_exc).strip()) if str(_raw_exc).strip() else None
    except (ValueError, TypeError):
        exc_int = None
    if not name:
        return jsonify({'exists': False})
    q = Material.query.filter(
        Material.material_name.ilike(name),
        (Material.is_deleted == False) | (Material.is_deleted == None)
    )
    if exc_int:
        q = q.filter(Material.id != exc_int)
    exists = q.first() is not None
    return jsonify({'exists': exists})


@material_bp.route('/api/save', methods=['POST'])
@login_required
def api_save():
    if not _can('edit'): return jsonify({'status':'error','message':'Access denied'}),403
    d = request.get_json() or {}
    name = d.get('material_name','').strip()
    if not name:
        return jsonify({'status':'error','message':'Material Name is required'})
    # Duplicate name check — exclude current item on edit
    _raw_id = d.get('id') or d.get('exclude_id') or ''
    try:
        exc_int = int(str(_raw_id).strip()) if str(_raw_id).strip() else None
    except (ValueError, TypeError):
        exc_int = None

    # If editing: skip check when name hasn't changed from DB value
    _skip_dup = False
    if exc_int:
        _cur = Material.query.filter_by(id=exc_int).first()
        if _cur and (_cur.material_name or '').strip().lower() == name.lower():
            _skip_dup = True   # same name as before — no duplicate issue

    if not _skip_dup:
        dup_q = Material.query.filter(
            Material.material_name.ilike(name),
            (Material.is_deleted == False) | (Material.is_deleted == None)
        )
        if exc_int:
            dup_q = dup_q.filter(Material.id != exc_int)
        if dup_q.first():
            return jsonify({'status':'error','message':f'Item name "{name}" already exists. Please use a unique name.'})

    from sqlalchemy import text

    def _get_all_codes():
        rows = db.session.execute(
            text("SELECT id, code FROM materials WHERE (is_deleted IS NULL OR is_deleted = 0)")
        ).fetchall()
        return {(str(r[0])): (r[1] or '').upper().strip() for r in rows}

    def _next_available_code(abbr, current_id=None):
        """Find next available code for given abbreviation, skipping conflicts."""
        prefix = f'{abbr}-'
        all_codes = _get_all_codes()
        existing = set(v for k, v in all_codes.items() if current_id is None or k != str(current_id))
        max_num = 0
        for code in existing:
            if code.startswith(prefix):
                try:
                    max_num = max(max_num, int(code[len(prefix):]))
                except (ValueError, IndexError):
                    pass
        next_num = max_num + 1
        while f'{prefix}{next_num:03d}' in existing:
            next_num += 1
        return f'{abbr}-{next_num:03d}'

    try:
        eid = d.get('id')
        is_new = not bool(eid)

        if eid:
            m = Material.query.get(eid)
            if not m: return jsonify({'status':'error','message':'Not found'}),404
            m.updated_by = _cu()
        else:
            m = Material()
            m.created_by = _cu()
            db.session.add(m)

        # ── Code: auto-resolve concurrent conflicts ─────────────────
        requested_code = d.get('code', '').strip()
        if requested_code:
            # Check if this code is already taken by a DIFFERENT item
            all_codes = _get_all_codes()
            code_taken = any(
                v == requested_code.upper() and k != str(eid or '')
                for k, v in all_codes.items()
            )
            if code_taken and is_new:
                # Auto-assign next available — extract prefix (everything before last '-NNN')
                import re
                match = re.match(r'^([A-Z]+-)', requested_code.upper())
                abbr = match.group(1).rstrip('-') if match else None
                if abbr:
                    requested_code = _next_available_code(abbr, eid)
                # else keep requested_code (unusual manual code)
        m.code = requested_code

        m.material_name      = d.get('material_name','').strip()
        m.aliases            = d.get('aliases','').strip()
        m.description        = d.get('description','').strip()
        m.uom                = d.get('uom','KG').strip()
        m.inci_name          = d.get('inci_name', '').strip()
        m.brand              = d.get('brand', '').strip()
        m.category           = d.get('category', '').strip()
        m.per_box_qty        = int(d.get('per_box_qty') or 0)
        m.per_box_weight     = float(d.get('per_box_weight') or 0)
        m.per_box_weight_uom = (d.get('per_box_weight_uom') or 'KG').strip()
        m.pm_material_type   = d.get('pm_material_type', '').strip()
        m.pm_client_type     = d.get('pm_client_type', '').strip()
        m.pm_attribute       = d.get('pm_attribute', '').strip()
        m.corrugation_ply    = d.get('corrugation_ply','').strip()
        def _to_decimal(val):
            try:
                v = str(val).strip()
                return float(v) if v else None
            except (ValueError, TypeError):
                return None
        m.dim_length         = _to_decimal(d.get('dim_length'))
        m.dim_width          = _to_decimal(d.get('dim_width'))
        m.dim_height         = _to_decimal(d.get('dim_height'))
        m.material_type_id   = d.get('material_type_id') or None
        m.group_id           = d.get('group_id') or None
        m.sku_sizes          = d.get('sku_sizes','').strip()
        m.opening_balance    = float(d.get('opening_balance') or 0)
        m.msl                = float(d.get('msl') or 0)
        m.lead_time_days     = int(d.get('lead_time_days') or 0)
        m.std_pack_size      = float(d.get('std_pack_size') or 0)
        m.last_purchase_rate = float(d.get('last_purchase_rate') or 0)
        m.hsn_code           = d.get('hsn_code','').strip()
        m.gst_rate           = float(d.get('gst_rate') or 0)
        m.taxability         = d.get('taxability','Taxable')
        m.is_active          = bool(d.get('is_active', True))
        # Image path (PM/FG)
        # Image data (base64) — compress and store directly in DB
        img_data = d.get('image_path')  # frontend sends as image_path key
        if img_data is not None:
            if img_data and img_data.startswith('data:image'):
                # Compress: resize to max 600px, JPEG 85%
                try:
                    import base64 as b64mod, io
                    from PIL import Image as PILImage
                    header, raw = img_data.split(',', 1)
                    img_bytes = b64mod.b64decode(raw)
                    pil_img = PILImage.open(io.BytesIO(img_bytes)).convert('RGB')
                    if max(pil_img.size) > 600:
                        pil_img.thumbnail((600, 600), PILImage.LANCZOS)
                    buf = io.BytesIO()
                    pil_img.save(buf, format='JPEG', quality=85, optimize=True)
                    compressed = b64mod.b64encode(buf.getvalue()).decode()
                    m.image_data = f'data:image/jpeg;base64,{compressed}'
                except Exception:
                    m.image_data = img_data  # fallback: store as-is
            else:
                m.image_data = img_data if img_data else None
        db.session.commit()
        return jsonify({'status':'ok','id':m.id,'code':m.code})
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
