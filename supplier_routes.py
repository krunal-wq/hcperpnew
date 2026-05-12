from flask import Blueprint, render_template, request, jsonify, abort
from flask_login import login_required, current_user
from models import db
from models.supplier import Supplier
from models.employee import StateMaster, CountryMaster
from sqlalchemy import or_
from datetime import datetime

supplier_bp = Blueprint('supplier', __name__, url_prefix='/supplier')


def _role():
    return getattr(current_user, 'role', 'viewer')

def _can(action):
    role = _role()
    if role == 'admin': return True
    # TODO: add proper permission check
    return True


# ── Listing ──────────────────────────────────────────────────────────────────
@supplier_bp.route('/')
@login_required
def index():
    sup_type = request.args.get('supplier_type', '').strip().upper()  # RM or PM only
    if sup_type == 'FG':
        abort(404)  # FG ke liye supplier nahi hai
    return render_template('supplier/index.html',
        active_page='supplier',
        role=_role(),
        sup_type=sup_type,
        can_add=_can('add'),
        can_edit=_can('edit'),
        can_delete=_can('delete'),
    )


# ── API: List ─────────────────────────────────────────────────────────────────
@supplier_bp.route('/api/list')
@login_required
def api_list():
    sup_type = request.args.get('supplier_type', '').strip().upper()
    active   = request.args.get('active', '1')
    search   = request.args.get('search', '').strip()

    q = Supplier.query.filter_by(is_deleted=False)
    if sup_type:
        q = q.filter(Supplier.supplier_type.like(f'%{sup_type}%'))
    if active == '1':
        q = q.filter_by(is_active=True)
    elif active == 'inactive':
        q = q.filter_by(is_active=False)
    if search:
        like = f'%{search}%'
        q = q.filter(
            db.or_(
                Supplier.supplier_name.ilike(like),
                Supplier.supplier_code.ilike(like),
                Supplier.company_name.ilike(like),
                Supplier.phone.ilike(like),
                Supplier.gst_number.ilike(like),
            )
        )
    rows = q.order_by(Supplier.supplier_name).all()
    return jsonify({'rows': [r.to_dict() for r in rows]})


# ── API: Save (Add/Edit) ──────────────────────────────────────────────────────
@supplier_bp.route('/api/save', methods=['POST'])
@login_required
def api_save():
    if not _can('edit'): return jsonify({'status':'error','message':'Access denied'}), 403
    d = request.get_json() or {}
    rid = d.get('id')

    if rid:
        s = Supplier.query.get(rid)
        if not s: return jsonify({'status':'error','message':'Not found'}), 404
    else:
        s = Supplier()
        db.session.add(s)
        # Auto-generate code
        sup_type = d.get('supplier_type','RM').upper()
        prefix = f'SUP-{sup_type}-'
        from sqlalchemy import text
        rows = db.session.execute(text("SELECT supplier_code FROM suppliers WHERE is_deleted=0 OR is_deleted IS NULL")).fetchall()
        max_num = 0
        for row in rows:
            code = (row[0] or '').upper()
            if code.startswith(prefix):
                try: max_num = max(max_num, int(code[len(prefix):]))
                except: pass
        if max_num == 0:
            count = db.session.execute(text(f"SELECT COUNT(*) FROM suppliers WHERE supplier_type='{sup_type}' AND (is_deleted=0 OR is_deleted IS NULL)")).scalar() or 0
            max_num = count
        s.supplier_code = f"{prefix}{max_num+1:03d}"

    s.supplier_name    = d.get('supplier_name','').strip()
    s.supplier_type    = d.get('supplier_type','RM').upper()
    s.contact_person   = d.get('contact_person','').strip()
    s.phone            = d.get('phone','').strip()
    s.email            = d.get('email','').strip()
    s.email_list       = d.get('email_list','').strip()
    s.company_name     = d.get('company_name','').strip()
    import json
    s.addresses        = json.dumps(d.get('addresses', []))
    s.address          = d.get('address','').strip()
    s.billing_state    = d.get('billing_state','').strip()
    s.billing_city     = d.get('billing_city','').strip()
    s.billing_pincode  = d.get('billing_pincode','').strip()
    s.billing_country  = d.get('billing_country','India').strip()
    s.shipping_address = d.get('shipping_address','').strip()
    s.shipping_state   = d.get('shipping_state','').strip()
    s.shipping_city    = d.get('shipping_city','').strip()
    s.shipping_pincode = d.get('shipping_pincode','').strip()
    s.shipping_country = d.get('shipping_country','India').strip()
    s.gst_number       = d.get('gst_number','').strip()
    s.pan_number       = d.get('pan_number','').strip()
    s.payment_type     = d.get('payment_type','').strip()
    s.payment_terms    = d.get('payment_terms','').strip()
    s.credit_days      = int(d.get('credit_days') or 30)
    s.credit_limit     = float(d.get('credit_limit') or 0)
    s.currency         = d.get('currency','INR').strip()
    s.lead_time_days   = int(d.get('lead_time_days') or 7)
    s.bank_name        = d.get('bank_name','').strip()
    s.account_number   = d.get('account_number','').strip()
    s.ifsc_code        = d.get('ifsc_code','').strip()
    s.branch_address   = d.get('branch_address','').strip()
    s.rating           = d.get('rating','').strip()
    s.remarks          = d.get('remarks','').strip()
    s.is_active        = bool(d.get('is_active', True))

    try:
        db.session.commit()
        return jsonify({'status':'ok', 'id': s.id, 'code': s.supplier_code})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}), 500


# ── API: Delete (soft) ────────────────────────────────────────────────────────
@supplier_bp.route('/api/duplicate', methods=['POST'])
@login_required
def api_duplicate():
    """
    Supplier ko dusre type mein copy/link karo.
    Agar same name ka supplier us type mein already hai → update karo.
    Nahi hai → naya create karo.
    """
    if not _can('edit'): return jsonify({'status':'error','message':'Access denied'}), 403
    d = request.get_json() or {}
    src_id = d.get('id')
    target_type = d.get('target_type','').strip().upper()
    if not src_id or target_type not in ('RM','PM'):
        return jsonify({'status':'error','message':'Invalid params'}), 400

    src = Supplier.query.get(src_id)
    if not src: return jsonify({'status':'error','message':'Source not found'}), 404

    try:
        # Check if supplier with same name exists in target type
        existing = Supplier.query.filter(
            Supplier.supplier_name == src.supplier_name,
            Supplier.supplier_type.like(f'%{target_type}%'),
            Supplier.is_deleted == False
        ).first()

        import json
        if existing:
            # Update existing supplier with latest data
            existing.company_name   = src.company_name
            existing.contact_person = src.contact_person
            existing.phone          = src.phone
            existing.email          = src.email
            existing.email_list     = src.email_list
            existing.addresses      = src.addresses
            existing.gst_number     = src.gst_number
            existing.pan_number     = src.pan_number
            existing.payment_type   = src.payment_type
            existing.credit_days    = src.credit_days
            existing.credit_limit   = src.credit_limit
            existing.currency       = src.currency
            existing.lead_time_days = src.lead_time_days
            existing.payment_terms  = src.payment_terms
            existing.bank_name      = src.bank_name
            existing.account_number = src.account_number
            existing.ifsc_code      = src.ifsc_code
            existing.branch_address = src.branch_address
            existing.rating         = src.rating
            existing.remarks        = src.remarks
            db.session.commit()
            return jsonify({'status':'ok','action':'updated','id':existing.id,'code':existing.supplier_code})
        else:
            # Create new supplier for target type
            new_s = Supplier()
            new_s.supplier_type    = target_type
            new_s.supplier_name    = src.supplier_name
            new_s.company_name     = src.company_name
            new_s.contact_person   = src.contact_person
            new_s.phone            = src.phone
            new_s.email            = src.email
            new_s.email_list       = src.email_list
            new_s.addresses        = src.addresses
            new_s.gst_number       = src.gst_number
            new_s.pan_number       = src.pan_number
            new_s.payment_type     = src.payment_type
            new_s.credit_days      = src.credit_days
            new_s.credit_limit     = src.credit_limit
            new_s.currency         = src.currency
            new_s.lead_time_days   = src.lead_time_days
            new_s.payment_terms    = src.payment_terms
            new_s.bank_name        = src.bank_name
            new_s.account_number   = src.account_number
            new_s.ifsc_code        = src.ifsc_code
            new_s.branch_address   = src.branch_address
            new_s.rating           = src.rating
            new_s.remarks          = src.remarks
            new_s.is_active        = src.is_active
            db.session.add(new_s)
            db.session.flush()
            # Auto code
            prefix = f'SUP-{target_type}-'
            from sqlalchemy import text as sql_text
            rows = db.session.execute(sql_text("SELECT supplier_code FROM suppliers WHERE is_deleted=0 OR is_deleted IS NULL")).fetchall()
            max_num=0
            for row in rows:
                code=(row[0] or '').upper()
                if code.startswith(prefix):
                    try: max_num=max(max_num,int(code[len(prefix):]))
                    except: pass
            if max_num==0:
                count=db.session.execute(sql_text(f"SELECT COUNT(*) FROM suppliers WHERE supplier_type LIKE '%{target_type}%' AND (is_deleted=0 OR is_deleted IS NULL)")).scalar() or 0
                max_num=count
            new_s.supplier_code = f"{prefix}{max_num+1:03d}"
            db.session.commit()
            return jsonify({'status':'ok','action':'created','id':new_s.id,'code':new_s.supplier_code})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}), 500



@supplier_bp.route('/api/delete', methods=['POST'])
@login_required
def api_delete():
    if not _can('delete'): return jsonify({'status':'error','message':'Access denied'}), 403
    rid = (request.get_json() or {}).get('id')
    if not rid: return jsonify({'status':'error','message':'Missing id'}), 400
    s = Supplier.query.get(rid)
    if not s: return jsonify({'status':'error','message':'Not found'}), 404
    s.is_deleted = True
    s.deleted_at = datetime.utcnow()
    try:
        db.session.commit()
        return jsonify({'status':'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}), 500


# ── API: Deleted list ─────────────────────────────────────────────────────────
@supplier_bp.route('/api/deleted-list')
@login_required
def api_deleted_list():
    sup_type = request.args.get('supplier_type','').strip().upper()
    q = Supplier.query.filter_by(is_deleted=True)
    if sup_type: q = q.filter(Supplier.supplier_type.like(f'%{sup_type}%'))
    rows = q.order_by(Supplier.deleted_at.desc()).all()
    return jsonify({'rows': [r.to_dict() for r in rows]})


# ── API: Restore ──────────────────────────────────────────────────────────────
@supplier_bp.route('/api/restore', methods=['POST'])
@login_required
def api_restore():
    rid = (request.get_json() or {}).get('id')
    s = Supplier.query.get(rid)
    if not s: return jsonify({'status':'error','message':'Not found'}), 404
    s.is_deleted = False; s.deleted_at = None
    db.session.commit()
    return jsonify({'status':'ok'})


# ── API: Permanent Delete ─────────────────────────────────────────────────────
@supplier_bp.route('/api/permanent-delete', methods=['POST'])
@login_required
def api_permanent_delete():
    if not _can('delete'): return jsonify({'status':'error','message':'Access denied'}), 403
    rid = (request.get_json() or {}).get('id')
    s = Supplier.query.get(rid)
    if not s: return jsonify({'status':'error','message':'Not found'}), 404
    try:
        db.session.delete(s)
        db.session.commit()
        return jsonify({'status':'ok'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status':'error','message':str(e)}), 500


# ── Add/Edit Pages ────────────────────────────────────────────────────────────
@supplier_bp.route('/add')
@login_required
def add_supplier():
    sup_type = request.args.get('supplier_type', 'RM').strip().upper()
    if sup_type == 'FG': abort(404)
    return render_template('supplier/add_supplier.html',
        active_page='supplier', role=_role(),
        supplier=None, sup_type=sup_type,
    )

@supplier_bp.route('/edit/<int:sup_id>')
@login_required
def edit_supplier(sup_id):
    s = Supplier.query.get_or_404(sup_id)
    sup_type = request.args.get('supplier_type', s.supplier_type or 'RM').strip().upper()
    return render_template('supplier/add_supplier.html',
        active_page='supplier', role=_role(),
        supplier=s, sup_type=sup_type,
    )


@supplier_bp.route('/import-template')
@login_required
def import_template():
    """Download sample CSV template for importing suppliers."""
    sup_type = request.args.get('supplier_type', 'RM').strip().upper()
    headers = (
        'supplier_name,company_name,contact_person,phone,email,email_list,'
        'gst_number,pan_number,'
        'payment_type,credit_days,credit_limit,currency,lead_time_days,'
        'bank_name,account_number,ifsc_code,branch_address,'
        'rating,remarks,'
        'billing_address,billing_city,billing_state,billing_pincode,'
        'shipping_address,shipping_city,shipping_state,shipping_pincode'
    )
    row1 = (
        'Sample Supplier 1,Sample Pvt Ltd,Rajesh Kumar,+91 98765 43210,'
        'supplier@email.com,info@sample.com|sales@sample.com,'
        '24AABCU9603R1ZX,AABCU9603R,'
        'Credit,30,50000,INR,7,'
        'HDFC Bank,12345678901,HDFC0001234,Mumbai Branch,'
        'Good,Sample remarks here,'
        '123 Industrial Area,Mumbai,Maharashtra,400001,'
        '456 Warehouse Road,Pune,Maharashtra,411001'
    )
    row2 = (
        'Sample Supplier 2,Another Pvt Ltd,Suresh Shah,+91 98765 43211,'
        'info@another.com,,'
        '29AABCU9603R2ZX,BBCDE1234F,'
        'Advance NEFT,15,25000,INR,5,'
        ',,,,'
        'Excellent,,'
        '789 Market Street,Delhi,Delhi,110001,'
        ',,,,'
    )
    csv = f'{headers}\n{row1}\n{row2}'
    from flask import Response
    return Response(
        '\uFEFF' + csv,
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={sup_type}_supplier_template.csv'}
    )


# ═════════════════════════════════════════════════════════════════════════════
#  GEO masters (countries + states) — used by supplier form address dropdowns
# ═════════════════════════════════════════════════════════════════════════════
@supplier_bp.route('/api/countries')
@login_required
def api_countries():
    """List active countries. Optional ?q= search term."""
    q = (request.args.get('q', '') or '').strip()
    qs = CountryMaster.query.filter(CountryMaster.is_active == True)
    if q:
        like = f'%{q}%'
        qs = qs.filter(or_(
            CountryMaster.name.ilike(like),
            CountryMaster.iso2.ilike(like),
            CountryMaster.iso3.ilike(like),
        ))
    rows = qs.order_by(CountryMaster.sort_order, CountryMaster.name).limit(300).all()
    return jsonify(results=[{
        'id'        : r.id,
        'name'      : r.name,
        'iso2'      : r.iso2 or '',
        'iso3'      : r.iso3 or '',
        'phone_code': r.phone_code or '',
    } for r in rows])


@supplier_bp.route('/api/states')
@login_required
def api_states():
    """List active states. Optional ?country_id=<id>&q=<search>.
    Returned objects always include country_id so the client can cache + filter."""
    q   = (request.args.get('q', '') or '').strip()
    cid = (request.args.get('country_id', '') or '').strip()
    qs = StateMaster.query.filter(StateMaster.is_active == True)
    if cid.isdigit():
        qs = qs.filter(StateMaster.country_id == int(cid))
    if q:
        like = f'%{q}%'
        qs = qs.filter(or_(
            StateMaster.name.ilike(like),
            StateMaster.short_name.ilike(like),
            StateMaster.state_code.ilike(like),
        ))
    rows = qs.order_by(StateMaster.sort_order, StateMaster.name).limit(1000).all()
    return jsonify(results=[{
        'id'        : r.id,
        'name'      : r.name,
        'short_name': r.short_name or '',
        'code'      : r.state_code or '',
        'country_id': r.country_id,
    } for r in rows])
