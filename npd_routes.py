"""
npd_routes.py — Product Development Workflow
Blueprint: npd at /npd
"""

import os, json, csv, io
from datetime import datetime, date
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, jsonify, current_app)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import (db, User, Lead, NPDMilestoneTemplate,
                    NPDProject, MilestoneMaster, MilestoneLog,
                    NPDFormulation, NPDPackingMaterial, NPDArtwork, NPDActivityLog,
                    OfficeDispatchToken, OfficeDispatchItem)

from permissions import get_perm, get_sub_perm
npd = Blueprint('npd', __name__, url_prefix='/npd')

# ── NPD Grid Columns ──
NPD_COLS_DEFAULT = ['created_at','code','category','client_name','product_name','assigned_members','reference_brand','priority','last_connected','milestones','project_age','status','project_start_date']

NPD_COLS_ALL = {
    'created_at':        'Create Date',
    'code':              'Project No',
    'category':          'Category',
    'client_name':       'Client Name',
    'product_name':      'Product Name',
    'assigned_members':  'Members',
    'reference_brand':   'Reference Brand',
    'priority':          'Priority',
    'last_connected':    'Last Connected',
    'milestones':        'Milestones',
    'project_age':       'TAT',
    'status':            'Status',
    'project_start_date':'Start Date',
    'client_company':    'Company',
    'client_email':      'Client Email',
    'client_phone':      'Client Phone',
    'market_level':      'Market Level',
    'npd_fee_paid':      'NPD Fee',
    'product_category':  'Product Category',
    'area_of_application':'Area of Application',
    'viscosity':         'Viscosity',
    'ph_value':          'pH',
    'fragrance':         'Fragrance',
    'packaging_type':    'Packaging',
    'costing_range':     'Costing Range',
}

def _parse_date(val):
    """Parse DD-MM-YYYY or YYYY-MM-DD date string, return date or None."""
    if not val or not val.strip(): return None
    val = val.strip()
    from datetime import datetime
    for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y'):
        try: return datetime.strptime(val, fmt).date()
        except: pass
    return None

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads', 'npd')
ALLOWED = {'pdf','png','jpg','jpeg','gif','doc','docx','xls','xlsx','txt','zip'}

# ── Default Milestone types ──
# Static fallback (used only if DB has no templates yet)
DEFAULT_MILESTONES = [
    ('ingredients',     'Ingredients List & Marketing Sheet', '📋', 1),
    ('quotation',       'Quotation',                          '💰', 2),
    ('packing_material','Packing Material (PM)',              '📦', 3),
    ('filling_trial',   'Filling Trial',                      '🧪', 4),
    ('artwork',         'Artwork / Design',                   '🎨', 5),
    ('kld_mockup',      'KLD & Mockup Approval',             '🖼️', 6),
    ('qc_fda',          'QC Approval & FDA',                 '✅', 7),
    ('barcode',         'Barcode',                            '🔢', 8),
    ('po_draft',        'Final PO Draft',                     '📄', 9),
    ('pi_po',           'PI Against PO',                      '🧾', 10),
    ('documents',       'Documents Upload',                   '📁', 11),
    ('po_processing',   'PO Processing Form',                 '⚙️', 12),
    ('handover',        'Project Handover',                   '🏁', 13),
]


def get_milestone_templates(project_type=None):
    """Load milestone templates from DB. Falls back to DEFAULT_MILESTONES if empty."""
    try:
        q = NPDMilestoneTemplate.query.filter_by(is_active=True)
        if project_type and project_type != 'both':
            q = q.filter(
                db.or_(
                    NPDMilestoneTemplate.applies_to == 'both',
                    NPDMilestoneTemplate.applies_to == project_type
                )
            )
        templates = q.order_by(NPDMilestoneTemplate.sort_order, NPDMilestoneTemplate.id).all()
        if templates:
            return templates  # return ORM objects — template uses .milestone_type, .title, .sort_order
        # Fallback: return dict-like objects from DEFAULT_MILESTONES
        return [
            type('MS', (), {
                'milestone_type': m[0], 'title': m[1], 'icon': m[2],
                'sort_order': m[3], 'default_selected': True,
                'is_mandatory': False, 'applies_to': 'both',
                'description': '', 'id': None
            })()
            for m in DEFAULT_MILESTONES
        ]
    except Exception:
        return [
            type('MS', (), {
                'milestone_type': m[0], 'title': m[1], 'icon': m[2],
                'sort_order': m[3], 'default_selected': True,
                'is_mandatory': False, 'applies_to': 'both',
                'description': '', 'id': None
            })()
            for m in DEFAULT_MILESTONES
        ]


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED


def save_upload(f):
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    fn = secure_filename(f.filename)
    ts = datetime.now().strftime('%Y%m%d%H%M%S_')
    fname = ts + fn
    f.save(os.path.join(UPLOAD_FOLDER, fname))
    return fname


def gen_npd_code():
    last = NPDProject.query.order_by(NPDProject.id.desc()).first()
    num  = (last.id + 1) if last else 1
    return f"NPD-{num:04d}"


def log_npd(project_id, action, user_id=None):
    uid = user_id or (current_user.id if current_user.is_authenticated else None)
    db.session.add(NPDActivityLog(project_id=project_id, user_id=uid, action=action))


def get_users():
    return User.query.filter_by(is_active=True).order_by(User.full_name).all()


# ══════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════

@npd.route('/dashboard')
@login_required
def dashboard():
    # Stats
    total       = NPDProject.query.filter_by(is_deleted=False).count()
    active      = NPDProject.query.filter(
                    NPDProject.is_deleted==False,
                    NPDProject.status.notin_(['finish','cancelled'])).count()
    completed   = NPDProject.query.filter_by(is_deleted=False, status='complete').count()
    cancelled   = NPDProject.query.filter_by(is_deleted=False, status='cancelled').count()
    npd_count   = NPDProject.query.filter_by(is_deleted=False, project_type='npd').count()
    epd_count   = NPDProject.query.filter_by(is_deleted=False, project_type='existing').count()

    # Pending milestones
    pending_milestones = MilestoneMaster.query.filter(
        MilestoneMaster.status.in_(['pending','in_progress']),
        MilestoneMaster.is_selected==True
    ).count()

    # Projects by status
    from sqlalchemy import func
    status_counts = db.session.query(
        NPDProject.status, func.count(NPDProject.id)
    ).filter_by(is_deleted=False).group_by(NPDProject.status).all()

    # Recent projects
    recent = NPDProject.query.filter_by(is_deleted=False)\
                .order_by(NPDProject.created_at.desc()).limit(10).all()

    # Sampling rejection ratio per project (for chart)
    projects_all = NPDProject.query.filter(
        NPDProject.is_deleted==False,
        NPDProject.project_type=='npd'
    ).all()

    # Milestone completion %
    ms_total = MilestoneMaster.query.filter_by(is_selected=True).count()
    ms_done  = MilestoneMaster.query.filter_by(is_selected=True, status='approved').count()
    ms_pct   = round((ms_done/ms_total)*100, 1) if ms_total else 0

    # SC performance
    from sqlalchemy import case
    sc_stats = []

    return render_template('npd/dashboard.html',
        active_page='npd_dashboard',
        total=total, active=active, completed=completed, cancelled=cancelled,
        npd_count=npd_count, epd_count=epd_count,
        pending_milestones=pending_milestones,
        status_counts=dict(status_counts),
        recent=recent,
        ms_pct=ms_pct, ms_done=ms_done, ms_total=ms_total,
        sc_stats=sc_stats,
        projects_all=projects_all,
    )


# ══════════════════════════════════════════════════════════════
# PROJECT LIST
# ══════════════════════════════════════════════════════════════

@npd.route('/projects')
@login_required
def projects():
    q        = request.args.get('q','').strip()
    ptype    = request.args.get('type','')
    status   = request.args.get('status','')
    sc_id  = ''
    page     = request.args.get('page', 1, type=int)

    query = NPDProject.query.filter_by(is_deleted=False)

    if q:
        query = query.filter(
            db.or_(
                NPDProject.code.ilike(f'%{q}%'),
                NPDProject.product_name.ilike(f'%{q}%'),
                NPDProject.client_name.ilike(f'%{q}%'),
                NPDProject.client_company.ilike(f'%{q}%'),
            )
        )
    if ptype:
        query = query.filter_by(project_type=ptype)
    if status:
        query = query.filter_by(status=status)

    projects = query.order_by(NPDProject.created_at.desc()).paginate(page=page, per_page=25)

    users = get_users()
    return render_template('npd/projects.html',
        active_page='npd_projects',
        projects=projects, q=q, ptype=ptype, status=status, sc_id=sc_id,
        users=users,
    )


# ══════════════════════════════════════════════════════════════
# CREATE PROJECT
# ══════════════════════════════════════════════════════════════

@npd.route('/projects/new', methods=['GET','POST'])
@login_required
def new_project():
    # GET: redirect to type-specific route
    if request.method == 'GET':
        from urllib.parse import urlencode
        ptype = request.args.get('type', 'npd')
        params = {k: v for k, v in request.args.items() if k != 'type'}
        qs = ('?' + urlencode(params)) if params else ''
        if ptype == 'existing':
            return redirect('/npd/epd-new' + qs)
        else:
            return redirect('/npd/npd-new' + qs)

    users = get_users()
    leads = Lead.query.filter_by(is_deleted=False).order_by(Lead.created_at.desc()).limit(200).all()

    # Pre-fill from lead if lead_id passed in URL
    prefill_lead = None
    prefill_lead_id = request.args.get('lead_id') or request.form.get('lead_id')
    if prefill_lead_id:
        try:
            from models import Lead as LeadModel
            prefill_lead = LeadModel.query.get(int(prefill_lead_id))
        except: pass

    # Support client_id param — fetch client data securely from DB
    prefill_url = {'client_id': '', 'client_name': '', 'client_company': '', 'client_email': '', 'client_phone': '', 'product_name': request.args.get('product', '')}
    _cid = request.args.get('client_id')
    if _cid:
        try:
            from models.client import ClientMaster
            _cl = ClientMaster.query.get(int(_cid))
            if _cl:
                prefill_url['client_id']      = str(_cl.id)
                prefill_url['client_name']    = _cl.contact_name or ''
                prefill_url['client_company'] = _cl.company_name or ''
                prefill_url['client_email']   = _cl.email or ''
                prefill_url['client_phone']   = _cl.mobile or ''
        except: pass

    if request.method == 'POST':
        ptype       = request.form.get('project_type','npd')
        product_name= request.form.get('product_name','').strip()
        if not product_name:
            flash('Product name is required', 'error')
            return render_template('npd/project_form.html', active_page='npd_projects',
                                   users=users, leads=leads, edit=None)

        proj = NPDProject(
            code            = gen_npd_code(),
            project_type    = ptype,
            product_name    = product_name,
            product_category= request.form.get('product_category',''),
            product_range   = request.form.get('product_range',''),
            client_name     = request.form.get('client_name',''),
            client_company  = request.form.get('client_company',''),
            client_email    = request.form.get('client_email',''),
            client_phone    = request.form.get('client_phone',''),
            lead_id         = request.form.get('lead_id') or None,
            requirement_spec= request.form.get('requirement_spec',''),
            reference_product= request.form.get('reference_product',''),
            custom_formulation= 'custom_formulation' in request.form,
            order_quantity  = request.form.get('order_quantity',''),
            npd_fee_paid    = 'npd_fee_paid' in request.form,
            npd_fee_amount  = request.form.get('npd_fee_amount', 10000) or 10000,
            status          = 'lead_created',
            created_by      = current_user.id,
        )

        # Handle NPD fee receipt upload
        if 'npd_fee_receipt' in request.files:
            f = request.files['npd_fee_receipt']
            if f and f.filename and allowed_file(f.filename):
                proj.npd_fee_receipt = save_upload(f)

        db.session.add(proj)
        db.session.flush()  # get proj.id

        # Create default milestones
        selected_ms = request.form.getlist('milestones')
        templates = get_milestone_templates(ptype)
        for tmpl in templates:
            ms = MilestoneMaster(
                project_id    = proj.id,
                milestone_type= tmpl.milestone_type,
                title         = tmpl.title,
                sort_order    = tmpl.sort_order,
                is_selected   = True if tmpl.is_mandatory else (
                                    (tmpl.milestone_type in selected_ms) if selected_ms else tmpl.default_selected
                                ),
                status        = 'pending',
                created_by    = current_user.id,
            )
            db.session.add(ms)

        proj.milestone_master_created = True
        db.session.flush()
        log_npd(proj.id, f"Project created: {proj.code} ({ptype.upper()}) — {product_name}")
        db.session.commit()
        flash(f'Project {proj.code} created successfully!', 'success')
        from_lead = request.form.get('from_lead_id')
        if from_lead:
            return redirect(url_for('crm.lead_view', id=from_lead))
        if ptype == 'npd':
            return redirect(url_for('npd.npd_dashboard'))
        else:
            return redirect(url_for('npd.epd_dashboard'))

    return render_template('npd/project_form.html',
        active_page='npd_projects',
        users=users, leads=leads, edit=None,
        default_milestones=get_milestone_templates(),
        prefill_lead=prefill_lead,
        from_lead_id=prefill_lead_id,
        prefill_url=prefill_url,
    )


# ══════════════════════════════════════════════════════════════
# PROJECT VIEW (Detail)
# ══════════════════════════════════════════════════════════════

@npd.route('/projects/<int:pid>')
@login_required
def project_view(pid):
    proj    = NPDProject.query.filter_by(id=pid, is_deleted=False).first_or_404()
    users   = get_users()

    # Milestone completion %
    selected_ms = [m for m in proj.milestones if m.is_selected]
    ms_done     = sum(1 for m in selected_ms if m.status=='approved')
    ms_pct      = round((ms_done/len(selected_ms))*100) if selected_ms else 0

    # Team members — unique from assigned_members + assigned_rd_members
    from models.employee import Employee
    assigned_ids = set()
    for field in [proj.assigned_members, proj.assigned_rd_members]:
        if field:
            for x in str(field).split(','):
                x = x.strip()
                if x and x.isdigit():
                    assigned_ids.add(int(x))
    team_members = []
    if assigned_ids:
        team_members = Employee.query.filter(
            Employee.id.in_(assigned_ids),
            Employee.is_deleted == False
        ).order_by(Employee.first_name).all()

    from models.npd import NPDActivityLog, NPDComment, NPDNote
    activity_logs     = NPDActivityLog.query.filter_by(project_id=pid)                            .order_by(NPDActivityLog.created_at.desc()).all()
    disc_comments     = NPDComment.query.filter_by(project_id=pid, is_internal=False)                            .order_by(NPDComment.created_at.asc()).all()
    internal_comments = NPDComment.query.filter_by(project_id=pid, is_internal=True)                            .order_by(NPDComment.created_at.asc()).all()
    note              = NPDNote.query.filter_by(project_id=pid).first()
    active_tab        = request.args.get('tab', 'overview')

    return render_template('npd/project_view.html',
        active_page='npd_projects',
        proj=proj, users=users,
        team_members=team_members,
        selected_ms=selected_ms, ms_done=ms_done, ms_pct=ms_pct,
        activity_logs=activity_logs,
        disc_comments=disc_comments,
        internal_comments=internal_comments,
        note=note, active_tab=active_tab,
        now=datetime.now,
    )


@npd.route('/projects/<int:pid>/comment', methods=['POST'])
@login_required
def add_comment(pid):
    from models.npd import NPDComment, NPDActivityLog
    comment_txt = request.form.get('comment','').strip()
    is_internal = request.form.get('is_internal','0') == '1'

    # Handle file upload
    attachment = None
    if 'attachment' in request.files:
        f = request.files['attachment']
        if f and f.filename and f.filename.strip():
            try:
                os.makedirs(UPLOAD_FOLDER, exist_ok=True)
                # Use uuid to avoid filename issues
                import uuid
                ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else 'bin'
                fname = datetime.now().strftime('%Y%m%d%H%M%S_') + str(uuid.uuid4())[:8] + '.' + ext
                fpath = os.path.join(UPLOAD_FOLDER, fname)
                f.save(fpath)
                if os.path.exists(fpath):
                    # Store as "savedname|originalname" for display
                    orig = f.filename
                    attachment = fname + '|' + orig
                else:
                    flash('File could not be saved', 'warning')
            except Exception as e:
                import traceback
                flash(f'Upload error: {traceback.format_exc()[-200:]}', 'warning')

    # Need at least comment or file
    if not comment_txt and not attachment:
        flash('Please add a comment or attach a file','error')
        return redirect(url_for('npd.project_view', pid=pid, tab='internal_discussion' if is_internal else 'discussion'))

    # If only file, use original filename as comment
    if not comment_txt and attachment:
        comment_txt = ''  # empty — chip will show
    db.session.add(NPDComment(
        project_id=pid, user_id=current_user.id,
        comment=comment_txt, is_internal=is_internal,
        attachment=attachment, created_at=datetime.now(),
    ))
    db.session.add(NPDActivityLog(
        project_id=pid, user_id=current_user.id,
        action=f"{'Internal comment' if is_internal else 'Comment'} added by {current_user.full_name}",
        created_at=datetime.now(),
    ))
    db.session.commit()
    flash('Comment added!','success')
    return redirect(url_for('npd.project_view', pid=pid, tab='internal_discussion' if is_internal else 'discussion'))


@npd.route('/projects/<int:pid>/note', methods=['POST'])
@login_required
def save_note(pid):
    from models.npd import NPDNote
    content_html = request.form.get('note_content','')
    note = NPDNote.query.filter_by(project_id=pid).first()
    if note:
        note.content = content_html
        note.updated_by = current_user.id
        note.updated_at = datetime.now()
    else:
        db.session.add(NPDNote(project_id=pid, content=content_html,
                               updated_by=current_user.id, updated_at=datetime.now()))
    db.session.commit()
    flash('Note saved!','success')
    return redirect(url_for('npd.project_view', pid=pid, tab='note'))


# ══════════════════════════════════════════════════════════════
# EDIT PROJECT
# ══════════════════════════════════════════════════════════════

@npd.route('/projects/<int:pid>/edit', methods=['GET','POST'])
@login_required
def edit_project(pid):
    proj  = NPDProject.query.filter_by(id=pid, is_deleted=False).first_or_404()
    users = get_users()
    leads = Lead.query.filter_by(is_deleted=False).order_by(Lead.created_at.desc()).limit(200).all()

    if request.method == 'POST':
        proj.product_name        = request.form.get('product_name', proj.product_name).strip()
        proj.product_category    = request.form.get('product_category', '')
        proj.product_range       = request.form.get('product_range', '')
        proj.client_name         = request.form.get('client_name', '')
        proj.client_company      = request.form.get('client_company', '')
        proj.client_email        = request.form.get('client_email', '')
        proj.client_phone        = request.form.get('client_phone', '')
        proj.client_coordinator  = request.form.get('client_coordinator', '')
        proj.lead_id             = int(request.form.get('lead_id')) if request.form.get('lead_id') and request.form.get('lead_id').strip() not in ('', 'None') else None
        proj.client_id           = int(request.form.get('client_id')) if request.form.get('client_id') and request.form.get('client_id').strip() not in ('', 'None') else None

        # Status
        new_status = request.form.get('status', '').strip()
        if new_status:
            proj.status = new_status

        # Priority
        proj.priority            = request.form.get('priority', 'Normal')

        # Members
        proj.assigned_members     = request.form.get('assigned_members', '')
        proj.assigned_rd_members  = request.form.get('assigned_rd_members', '')
        proj.assigned_sc          = int(request.form.get('assigned_sc')) if request.form.get('assigned_sc') and request.form.get('assigned_sc').strip() not in ('', 'None') else None
        proj.assigned_rd          = int(request.form.get('assigned_rd')) if request.form.get('assigned_rd') and request.form.get('assigned_rd').strip() not in ('', 'None') else None
        proj.npd_poc              = int(request.form.get('npd_poc')) if request.form.get('npd_poc') and request.form.get('npd_poc').strip() not in ('', 'None') else None

        # Product details
        proj.area_of_application  = request.form.get('area_of_application', '')
        proj.market_level         = request.form.get('market_level', '')
        proj.no_of_samples        = int(request.form.get('no_of_samples') or 0)
        proj.moq                  = request.form.get('moq', '')
        proj.product_size         = request.form.get('product_size', '')
        proj.order_quantity       = request.form.get('order_quantity', '')
        proj.variant_type         = request.form.get('variant_type', '')
        proj.appearance           = request.form.get('appearance', '')
        proj.reference_brand      = request.form.get('reference_brand', '')
        proj.reference_product_name = request.form.get('reference_product_name', '')
        proj.reference_product    = request.form.get('reference_product', '')

        # Formulation
        proj.description          = request.form.get('description', '')
        proj.ingredients          = request.form.get('ingredients', '')
        proj.active_ingredients   = request.form.get('active_ingredients', '')
        proj.product_claim        = request.form.get('product_claim', '')
        proj.label_claim          = request.form.get('label_claim', '')
        proj.requirement_spec     = request.form.get('requirement_spec', '')
        proj.costing_range        = request.form.get('costing_range', '')
        proj.ph_value             = request.form.get('ph_value', '')
        proj.packaging_type       = request.form.get('packaging_type', '')
        proj.fragrance            = request.form.get('fragrance', '')
        proj.viscosity            = request.form.get('viscosity', '')
        proj.video_link           = request.form.get('video_link', '')

        # Dates
        def pd(v):
            from datetime import date
            try:
                from datetime import datetime as _dt
                return _dt.strptime(v.strip(), '%Y-%m-%d').date() if v and v.strip() else None
            except Exception:
                return None
        proj.project_start_date   = pd(request.form.get('project_start_date', '')) or proj.project_start_date
        proj.project_end_date     = pd(request.form.get('project_end_date', '')) or proj.project_end_date
        proj.target_sample_date   = pd(request.form.get('target_sample_date', '')) or proj.target_sample_date
        proj.project_lead_days    = int(request.form.get('project_lead_days')) if request.form.get('project_lead_days') and request.form.get('project_lead_days').strip() not in ('', 'None') else proj.project_lead_days

        # Fee & misc
        proj.custom_formulation   = 'custom_formulation' in request.form
        proj.npd_fee_paid         = 'npd_fee_paid' in request.form
        proj.npd_fee_amount       = request.form.get('npd_fee_amount', proj.npd_fee_amount) or proj.npd_fee_amount
        proj.delay_reason         = request.form.get('delay_reason', '')
        proj.updated_by           = current_user.id

        if 'npd_fee_receipt' in request.files:
            f = request.files['npd_fee_receipt']
            if f and f.filename and allowed_file(f.filename):
                proj.npd_fee_receipt = save_upload(f)

        # Update milestone selection
        milestone_ids = request.form.getlist('milestone_ids')
        if milestone_ids:
            from models.npd import MilestoneMaster
            all_ms = MilestoneMaster.query.filter_by(project_id=proj.id).all()
            selected_set = set(int(x) for x in milestone_ids if x.isdigit())
            for ms in all_ms:
                ms.is_selected = (ms.id in selected_set)

        log_npd(proj.id, f"Project updated by {current_user.full_name}")
        db.session.commit()
        flash('Project updated!', 'success')
        if proj.project_type == 'npd':
            return redirect(url_for('npd.npd_dashboard'))
        else:
            return redirect(url_for('npd.epd_dashboard'))

    # Use type-specific form template
    if proj.project_type == 'npd':
        tmpl = 'npd/npd_form.html'
    else:
        tmpl = 'npd/epd_form.html'

    from models.employee import Employee
    from models.master import NPDStatus, CategoryMaster
    from models.client import ClientMaster
    categories = CategoryMaster.query.filter_by(status=True, is_deleted=False).order_by(CategoryMaster.name).all()
    employees = Employee.query.filter_by(is_deleted=False).order_by(Employee.first_name).all()
    rd_employees = Employee.query.filter(
        Employee.is_deleted==False,
        db.or_(
            Employee.department.ilike('%r&d%'),
            Employee.department.ilike('%rd%'),
            Employee.department.ilike('%research%'),
            Employee.department.ilike('%r & d%'),
            Employee.designation.ilike('%r&d%'),
            Employee.designation.ilike('%r & d%'),
            Employee.designation.ilike('%formulation%'),
            Employee.designation.ilike('%scientist%'),
            Employee.designation.ilike('%chemist%'),
        )
    ).order_by(Employee.first_name).all()
    if not rd_employees:
        rd_employees = employees
    npd_statuses = NPDStatus.query.filter_by(is_active=True).order_by(NPDStatus.sort_order).all()
    clients = ClientMaster.query.filter_by(is_deleted=False).order_by(ClientMaster.contact_name).all()

    return render_template(tmpl,
        active_page='npd_projects',
        edit=proj, users=users, leads=leads,
        employees=employees,
        rd_employees=rd_employees,
        npd_statuses=npd_statuses,
        clients=clients,
        categories=categories,
        prefill_lead=None, prefill_url={},
        default_milestones=get_milestone_templates(proj.project_type),
    )


# ══════════════════════════════════════════════════════════════
# STATUS CHANGE
# ══════════════════════════════════════════════════════════════

@npd.route('/projects/<int:pid>/status', methods=['POST'])
@login_required
def change_status(pid):
    proj       = NPDProject.query.filter_by(id=pid, is_deleted=False).first_or_404()
    new_status = request.form.get('status','')
    note       = request.form.get('note','')

    if new_status == 'cancelled':
        proj.cancel_reason = request.form.get('cancel_reason', '')
        proj.cancelled_at  = datetime.now()
    elif new_status == 'complete':
        proj.completed_at  = datetime.now()
    elif new_status == 'commercial':
        proj.converted_to_commercial   = True
        proj.commercial_converted_at   = datetime.now()
    elif new_status == 'in_progress':
        if not proj.started_at:
            proj.started_at = datetime.now()
    elif new_status == 'not_started':
        proj.started_at = None
    elif new_status in ('finish', 'finished', 'sample_ready'):
        if not proj.finished_at:
            proj.finished_at = datetime.now()
        if proj.started_at and proj.finished_at:
            delta = proj.finished_at - proj.started_at
            proj.total_duration_seconds = int(delta.total_seconds())

    old_status = proj.status
    proj.status    = new_status
    proj.updated_by= current_user.id

    log_npd(proj.id,
            f"Status changed: {old_status} → {new_status}" + (f" | {note}" if note else ""))
    db.session.commit()
    flash(f'Status updated to {proj.status_label}', 'success')
    return redirect(url_for('npd.project_view', pid=pid))


# ══════════════════════════════════════════════════════════════
# SOFT DELETE
# ══════════════════════════════════════════════════════════════

@npd.route('/projects/<int:pid>/delete', methods=['POST'])
@login_required
def delete_project(pid):
    proj = NPDProject.query.filter_by(id=pid, is_deleted=False).first_or_404()
    proj.is_deleted = True
    proj.deleted_at = datetime.now()
    proj.deleted_by = current_user.id
    db.session.commit()
    flash(f'Project {proj.code} deleted.', 'warning')
    return redirect(url_for('npd.npd_projects'))


@npd.route('/projects/<int:pid>/restore', methods=['POST'])
@login_required
def restore_project(pid):
    proj = NPDProject.query.filter_by(id=pid, is_deleted=True).first_or_404()
    proj.is_deleted = False
    proj.deleted_at = None
    proj.deleted_by = None
    db.session.commit()
    flash(f'Project {proj.code} restored successfully!', 'success')
    return redirect(url_for('npd.npd_projects'))


# ══════════════════════════════════════════════════════════════
# MILESTONE — Update
# ══════════════════════════════════════════════════════════════

@npd.route('/milestone/<int:mid>/update', methods=['POST'])
@login_required
def update_milestone(mid):
    ms     = MilestoneMaster.query.get_or_404(mid)
    pid    = ms.project_id
    old_st = ms.status
    new_st = request.form.get('status', ms.status)
    note   = request.form.get('note', '')

    ms.status      = new_st
    ms.notes       = request.form.get('notes', ms.notes or '')
    ms.reject_reason = request.form.get('reject_reason', '')
    ms.assigned_to = request.form.get('assigned_to') or ms.assigned_to
    ms.target_date = request.form.get('target_date') or ms.target_date

    if new_st == 'approved':
        ms.completed_at = datetime.now()
        ms.approved_by  = current_user.id
        ms.approved_at  = datetime.now()

    # Handle file upload
    if 'attachment' in request.files:
        f = request.files['attachment']
        if f and f.filename and allowed_file(f.filename):
            fname = save_upload(f)
            existing = ms.attachments or ''
            ms.attachments = (existing + ',' + fname).strip(',')

    # Log the milestone change
    db.session.add(MilestoneLog(
        milestone_id = mid,
        action       = f"Status: {old_st} → {new_st}" + (f" | {note}" if note else ""),
        old_status   = old_st,
        new_status   = new_st,
        note         = note,
        created_by   = current_user.id,
    ))
    log_npd(pid, f"Milestone '{ms.title}' updated: {old_st} → {new_st}")
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify(success=True, status=new_st,
                       icon=ms.status_icon, color=ms.status_color)
    flash(f'Milestone "{ms.title}" updated!', 'success')
    return redirect(url_for('npd.project_view', pid=pid))


# ══════════════════════════════════════════════════════════════
# FORMULATION / SAMPLING LOOP
# ══════════════════════════════════════════════════════════════

@npd.route('/projects/<int:pid>/formulation/add', methods=['POST'])
@login_required
def add_formulation(pid):
    proj = NPDProject.query.filter_by(id=pid, is_deleted=False).first_or_404()

    # Next iteration number
    last_iter = db.session.query(db.func.max(NPDFormulation.iteration))\
                    .filter_by(project_id=pid).scalar() or 0

    form = NPDFormulation(
        project_id        = pid,
        iteration         = last_iter + 1,
        formulation_name  = request.form.get('formulation_name',''),
        formulation_desc  = request.form.get('formulation_desc',''),
        rd_person         = request.form.get('rd_person') or None,
        rd_notes          = request.form.get('rd_notes',''),
        rd_submitted_at   = datetime.now(),
        feedback_due_date = request.form.get('feedback_due_date') or None,
        status            = 'pending',
        created_by        = current_user.id,
    )

    if 'attachment' in request.files:
        f = request.files['attachment']
        if f and f.filename and allowed_file(f.filename):
            form.attachments = save_upload(f)

    db.session.add(form)

    # Update project status
    if proj.status == 'lead_created':
        proj.status = 'formulation'

    log_npd(pid, f"Formulation #{last_iter+1} added by {current_user.full_name}")
    db.session.commit()
    flash('Formulation added!', 'success')
    return redirect(url_for('npd.project_view', pid=pid))


@npd.route('/formulation/<int:fid>/review', methods=['POST'])
@login_required
def review_formulation(fid):
    form   = NPDFormulation.query.get_or_404(fid)
    pid    = form.project_id
    stage  = request.form.get('stage','sc')   # sc or client
    status = request.form.get('status','')
    notes  = request.form.get('notes','')

    if stage == 'sc':
        form.sc_review_status = status
        form.sc_review_notes  = notes
        form.sc_reviewed_by   = current_user.id
        form.sc_reviewed_at   = datetime.now()
        if status == 'approved':
            form.status = 'sc_approved'
            form.sample_created = True
        else:
            form.status = 'sc_rejected'
    elif stage == 'client':
        form.client_status    = status
        form.client_feedback  = notes
        form.client_responded_at = datetime.now()
        if status == 'approved':
            form.status = 'client_approved'
            # Update project
            proj = NPDProject.query.get(pid)
            if proj:
                proj.status = 'client_approved'
        else:
            form.status = 'client_rejected'
    elif stage == 'dispatch':
        form.sample_sent_at = datetime.now()
        form.sample_sent_to = request.form.get('sent_to','')
        form.status         = 'sample_sent' if form.status == 'sc_approved' else form.status
        proj = NPDProject.query.get(pid)
        if proj and proj.status in ('formulation','lead_created'):
            proj.status = 'sampling'

    log_npd(pid, f"Formulation #{form.iteration} — {stage} review: {status}")
    db.session.commit()
    flash('Formulation review updated!', 'success')
    return redirect(url_for('npd.project_view', pid=pid))


# ══════════════════════════════════════════════════════════════
# PACKING MATERIAL
# ══════════════════════════════════════════════════════════════

@npd.route('/projects/<int:pid>/packing/add', methods=['POST'])
@login_required
def add_packing(pid):
    proj = NPDProject.query.filter_by(id=pid, is_deleted=False).first_or_404()

    pm = NPDPackingMaterial(
        project_id  = pid,
        pm_type     = request.form.get('pm_type',''),
        description = request.form.get('description',''),
        source      = request.form.get('source','company_sourced'),
        supplier    = request.form.get('supplier',''),
        notes       = request.form.get('notes',''),
        status      = 'pending',
        created_by  = current_user.id,
    )
    if 'attachment' in request.files:
        f = request.files['attachment']
        if f and f.filename and allowed_file(f.filename):
            pm.attachments = save_upload(f)

    db.session.add(pm)
    log_npd(pid, f"Packing Material ({pm.pm_type}) added")
    db.session.commit()
    flash('Packing material added!', 'success')
    return redirect(url_for('npd.project_view', pid=pid))


@npd.route('/packing/<int:pmid>/update', methods=['POST'])
@login_required
def update_packing(pmid):
    pm  = NPDPackingMaterial.query.get_or_404(pmid)
    pid = pm.project_id
    new_status = request.form.get('status', pm.status)

    pm.status      = new_status
    pm.notes       = request.form.get('notes', pm.notes or '')
    pm.reject_reason = request.form.get('reject_reason','')

    if new_status == 'sample_sent':
        pm.sample_sent_at = datetime.now()
    elif new_status == 'client_approved':
        pm.client_approved_at = datetime.now()
    elif new_status == 'filling_trial':
        pm.filling_trial_done = True
        pm.filling_trial_at   = datetime.now()

    if 'attachment' in request.files:
        f = request.files['attachment']
        if f and f.filename and allowed_file(f.filename):
            existing = pm.attachments or ''
            pm.attachments = (existing + ',' + save_upload(f)).strip(',')

    log_npd(pid, f"Packing Material ({pm.pm_type}) → {new_status}")
    db.session.commit()
    flash('Packing material updated!', 'success')
    return redirect(url_for('npd.project_view', pid=pid))


# ══════════════════════════════════════════════════════════════
# ARTWORK & DESIGN
# ══════════════════════════════════════════════════════════════

@npd.route('/projects/<int:pid>/artwork/add', methods=['POST'])
@login_required
def add_artwork(pid):
    last_iter = db.session.query(db.func.max(NPDArtwork.iteration))\
                    .filter_by(project_id=pid).scalar() or 0

    aw = NPDArtwork(
        project_id          = pid,
        iteration           = last_iter + 1,
        title               = request.form.get('title',''),
        description         = request.form.get('description',''),
        designer            = request.form.get('designer') or None,
        ingredients_included= 'ingredients_included' in request.form,
        content_included    = 'content_included' in request.form,
        packaging_details   = 'packaging_details' in request.form,
        barcode_required    = 'barcode_required' in request.form,
        status              = 'draft',
        sc_status           = 'pending',
        client_status       = 'pending',
        qc_status           = 'pending',
        notes               = request.form.get('notes',''),
        created_by          = current_user.id,
    )

    if 'artwork_file' in request.files:
        f = request.files['artwork_file']
        if f and f.filename and allowed_file(f.filename):
            aw.artwork_file = save_upload(f)

    db.session.add(aw)
    log_npd(pid, f"Artwork version #{last_iter+1} uploaded by {current_user.full_name}")
    db.session.commit()
    flash('Artwork added!', 'success')
    return redirect(url_for('npd.project_view', pid=pid))


@npd.route('/artwork/<int:awid>/review', methods=['POST'])
@login_required
def review_artwork(awid):
    aw     = NPDArtwork.query.get_or_404(awid)
    pid    = aw.project_id
    stage  = request.form.get('stage','sc')
    status = request.form.get('status','')
    notes  = request.form.get('notes','')

    if stage == 'sc':
        aw.sc_status       = status
        aw.sc_notes        = notes
        aw.sc_reviewed_by  = current_user.id
        aw.sc_reviewed_at  = datetime.now()
        aw.status = 'client_review' if status=='approved' else 'draft'
    elif stage == 'client':
        aw.client_status     = status
        aw.client_feedback   = notes
        aw.client_approved_at = datetime.now() if status=='approved' else None
        aw.status = 'qc_review' if status=='approved' else 'sc_review'
    elif stage == 'qc':
        aw.qc_status       = status
        aw.qc_notes        = notes
        aw.qc_reviewed_by  = current_user.id
        aw.qc_reviewed_at  = datetime.now()
        if status == 'approved':
            aw.status = 'approved'
            if 'final_file' in request.files:
                f = request.files['final_file']
                if f and f.filename and allowed_file(f.filename):
                    aw.final_file = save_upload(f)
        else:
            aw.status = 'client_review'
    elif stage == 'barcode':
        aw.barcode_paid     = 'barcode_paid' in request.form
        aw.barcode_pi       = request.form.get('barcode_pi','')
        aw.barcode_received = 'barcode_received' in request.form
        if aw.barcode_received:
            aw.barcode_received_at = datetime.now()
        if 'barcode_file' in request.files:
            f = request.files['barcode_file']
            if f and f.filename and allowed_file(f.filename):
                aw.barcode_file = save_upload(f)

    log_npd(pid, f"Artwork v{aw.iteration} — {stage} review: {status}")
    db.session.commit()
    flash('Artwork review updated!', 'success')
    return redirect(url_for('npd.project_view', pid=pid))


# ══════════════════════════════════════════════════════════════
# DELAY REASON UPDATE (weekly)
# ══════════════════════════════════════════════════════════════

@npd.route('/projects/<int:pid>/delay', methods=['POST'])
@login_required
def update_delay(pid):
    proj = NPDProject.query.filter_by(id=pid, is_deleted=False).first_or_404()
    proj.delay_reason       = request.form.get('delay_reason','')
    proj.last_delay_update  = datetime.now()
    proj.target_sample_date = request.form.get('target_sample_date') or proj.target_sample_date
    log_npd(pid, f"Delay reason updated: {proj.delay_reason[:60]}")
    db.session.commit()
    flash('Delay reason updated!', 'success')
    return redirect(url_for('npd.project_view', pid=pid))


# ══════════════════════════════════════════════════════════════
# REPORTS PAGE
# ══════════════════════════════════════════════════════════════

@npd.route('/reports')
@login_required
def reports():
    from sqlalchemy import func, case

    # NPD → Commercial conversion rate
    npd_total      = NPDProject.query.filter_by(is_deleted=False, project_type='npd').count()
    npd_commercial = NPDProject.query.filter_by(is_deleted=False, project_type='npd',
                                                converted_to_commercial=True).count()
    npd_conv_rate  = round((npd_commercial/npd_total)*100, 1) if npd_total else 0

    # EPD → Commercial
    epd_total      = NPDProject.query.filter_by(is_deleted=False, project_type='existing').count()
    epd_commercial = NPDProject.query.filter_by(is_deleted=False, project_type='existing',
                                                converted_to_commercial=True).count()
    epd_conv_rate  = round((epd_commercial/epd_total)*100, 1) if epd_total else 0

    # Sampling rejection ratio
    form_total    = NPDFormulation.query.count()
    form_rejected = NPDFormulation.query.filter(NPDFormulation.status.like('%rejected%')).count()
    rejection_ratio = round((form_rejected/form_total)*100, 1) if form_total else 0

    # SC performance
    sc_stats = []

    # Milestone delay analysis
    overdue_ms = db.session.query(MilestoneMaster, NPDProject).join(
        NPDProject, MilestoneMaster.project_id==NPDProject.id
    ).filter(
        MilestoneMaster.is_selected==True,
        MilestoneMaster.status.in_(['pending','in_progress']),
        MilestoneMaster.target_date < date.today(),
        NPDProject.is_deleted==False,
    ).all()

    # Projects with delay reason not updated this week
    from datetime import timedelta
    one_week_ago = datetime.now() - timedelta(days=7)
    stale_delays = NPDProject.query.filter(
        NPDProject.is_deleted==False,
        NPDProject.status.in_(['formulation','sampling']),
        db.or_(
            NPDProject.last_delay_update == None,
            NPDProject.last_delay_update < one_week_ago,
        )
    ).all()

    return render_template('npd/reports.html',
        active_page='npd_reports',
        npd_total=npd_total, npd_commercial=npd_commercial, npd_conv_rate=npd_conv_rate,
        epd_total=epd_total, epd_commercial=epd_commercial, epd_conv_rate=epd_conv_rate,
        form_total=form_total, form_rejected=form_rejected, rejection_ratio=rejection_ratio,
        sc_stats=sc_stats,
        overdue_ms=overdue_ms,
        stale_delays=stale_delays,
    )


# ══════════════════════════════════════════════════════════════
# AJAX — Quick status update
# ══════════════════════════════════════════════════════════════

@npd.route('/api/project/<int:pid>/status', methods=['POST'])
@login_required
def api_status(pid):
    proj = NPDProject.query.filter_by(id=pid, is_deleted=False).first_or_404()
    new_status = request.json.get('status','')
    if not new_status:
        return jsonify(success=False, error='No status'), 400
    proj.status = new_status
    proj.updated_by = current_user.id
    log_npd(pid, f"Status → {new_status}")
    db.session.commit()
    return jsonify(success=True, status=new_status, label=proj.status_label)


# ══════════════════════════════════════════════════════════════
# NPD MILESTONE MASTER — Admin CRUD
# ══════════════════════════════════════════════════════════════

@npd.route('/milestone-master')
@login_required
def milestone_master():
    templates = NPDMilestoneTemplate.query\
                    .order_by(NPDMilestoneTemplate.sort_order, NPDMilestoneTemplate.id).all()
    return render_template('npd/milestone_master.html',
        active_page='npd_milestone_master',
        templates=templates,
    )


@npd.route('/milestone-master/add', methods=['POST'])
@login_required
def milestone_master_add():
    mtype = request.form.get('milestone_type', '').strip().lower().replace(' ', '_')
    title = request.form.get('title', '').strip()
    if not mtype or not title:
        flash('Type and Title are required', 'error')
        return redirect(url_for('npd.milestone_master'))
    if NPDMilestoneTemplate.query.filter_by(milestone_type=mtype).first():
        flash(f'Milestone type "{mtype}" already exists', 'warning')
        return redirect(url_for('npd.milestone_master'))

    obj = NPDMilestoneTemplate(
        milestone_type   = mtype,
        title            = title,
        description      = request.form.get('description', '').strip(),
        icon             = request.form.get('icon', '📌').strip() or '📌',
        applies_to       = request.form.get('applies_to', 'both'),
        default_selected = 'default_selected' in request.form,
        is_mandatory     = 'is_mandatory' in request.form,
        sort_order       = int(request.form.get('sort_order', 0) or 0),
        is_active        = 'is_active' in request.form,
        created_by       = current_user.id,
    )
    db.session.add(obj)
    db.session.commit()
    flash(f'Milestone "{title}" added!', 'success')
    return redirect(url_for('npd.milestone_master'))


@npd.route('/milestone-master/<int:mid>/edit', methods=['POST'])
@login_required
def milestone_master_edit(mid):
    obj = NPDMilestoneTemplate.query.get_or_404(mid)
    obj.title            = request.form.get('title', obj.title).strip()
    obj.description      = request.form.get('description', obj.description or '').strip()
    obj.icon             = request.form.get('icon', obj.icon).strip() or '📌'
    obj.applies_to       = request.form.get('applies_to', obj.applies_to)
    obj.default_selected = 'default_selected' in request.form
    obj.is_mandatory     = 'is_mandatory' in request.form
    obj.sort_order       = int(request.form.get('sort_order', obj.sort_order) or 0)
    obj.is_active        = 'is_active' in request.form
    obj.modified_by      = current_user.id
    obj.modified_at      = datetime.now()
    db.session.commit()
    flash(f'"{obj.title}" updated!', 'success')
    return redirect(url_for('npd.milestone_master'))


@npd.route('/milestone-master/<int:mid>/delete', methods=['POST'])
@login_required
def milestone_master_delete(mid):
    obj = NPDMilestoneTemplate.query.get_or_404(mid)
    name = obj.title
    db.session.delete(obj)
    db.session.commit()
    flash(f'"{name}" deleted', 'success')
    return redirect(url_for('npd.milestone_master'))


@npd.route('/milestone-master/<int:mid>/toggle', methods=['POST'])
@login_required
def milestone_master_toggle(mid):
    obj = NPDMilestoneTemplate.query.get_or_404(mid)
    obj.is_active   = not obj.is_active
    obj.modified_by = current_user.id
    obj.modified_at = datetime.now()
    db.session.commit()
    return jsonify(success=True, is_active=obj.is_active)


@npd.route('/milestone-master/reorder', methods=['POST'])
@login_required
def milestone_master_reorder():
    """AJAX: receive ordered list of IDs and update sort_order."""
    ids = request.json.get('ids', [])
    for i, mid in enumerate(ids):
        obj = NPDMilestoneTemplate.query.get(mid)
        if obj:
            obj.sort_order = i + 1
    db.session.commit()
    return jsonify(success=True)


# ══════════════════════════════════════════════════════════════
# AJAX — Get Lead data for auto-fill in NPD project form
# ══════════════════════════════════════════════════════════════

@npd.route('/api/lead/<int:lid>/info')
@login_required
def api_lead_info(lid):
    from models import Lead as LeadModel
    lead = LeadModel.query.get_or_404(lid)
    return jsonify({
        'id':           lead.id,
        'contact_name': lead.contact_name or '',
        'company_name': lead.company_name or '',
        'email':        lead.email or '',
        'phone':        lead.phone or lead.alternate_mobile or '',
        'product_name': lead.product_name or '',
        'category':     lead.category or '',
        'product_range':lead.product_range or '',
        'requirement':  lead.requirement_spec or lead.notes or '',
        'order_qty':    lead.order_quantity or '',
        'assigned_to':  lead.assigned_to or '',
        'code':         lead.code or str(lead.id),
    })


# ══════════════════════════════════════════════════════════════
# CONVERT LEAD → NPD/EPD PROJECT (Direct — No Form)
# Lead se seedha project create karo, status update karo
# ══════════════════════════════════════════════════════════════

@npd.route('/convert-lead/<int:lead_id>/<project_type>', methods=['POST'])
@login_required
def convert_lead(lead_id, project_type):
    """
    Lead view Actions → NPD / EPD click karne pe yahan aata hai.

    Logic:
      - Agar lead.client_id pehle se hai:
          → Lead status update karo
          → NPD/EPD project create karo (client already linked)
          → Redirect: client view page
      - Agar lead.client_id nahi hai:
          → Lead status update karo
          → NPD/EPD project create karo
          → Redirect: NPD project view page
    """
    from models import Lead, LeadActivityLog as CRMActivityLog

    if project_type not in ('npd', 'existing'):
        flash('Invalid project type', 'error')
        return redirect(url_for('crm.lead_view', id=lead_id))

    lead = Lead.query.get_or_404(lead_id)

    # ── 1. Update Lead Status ──
    new_status = 'NPD Project' if project_type == 'npd' else 'Existing Project'
    old_status = lead.status
    lead.status      = new_status
    lead.updated_at  = datetime.now()
    lead.modified_by = current_user.id

    # ── 2. Create NPD/EPD Project from Lead data ──
    proj = NPDProject(
        code             = gen_npd_code(),
        project_type     = project_type,
        status           = 'lead_created',
        lead_id          = lead.id,
        client_name      = lead.contact_name or '',
        client_company   = lead.company_name or '',
        client_email     = lead.email or '',
        client_phone     = lead.phone or '',
        product_name     = lead.product_name or lead.title or f'Project from Lead #{lead.id}',
        product_category = lead.category or '',
        product_range    = lead.product_range or '',
        order_quantity   = lead.order_quantity or '',
        requirement_spec = lead.requirement_spec or lead.notes or '',
        npd_fee_paid     = False,
        npd_fee_amount   = 10000 if project_type == 'npd' else 0,
        milestone_master_created = True,
        created_by       = current_user.id,
        created_at       = datetime.now(),
    )

    db.session.add(proj)
    db.session.flush()  # get proj.id

    # ── 3. Create Milestones from Templates ──
    templates = get_milestone_templates(project_type)
    for tmpl in templates:
        if tmpl.applies_to == 'npd' and project_type != 'npd':
            continue
        if tmpl.applies_to == 'existing' and project_type != 'existing':
            continue
        db.session.add(MilestoneMaster(
            project_id     = proj.id,
            milestone_type = tmpl.milestone_type,
            title          = tmpl.title,
            sort_order     = tmpl.sort_order,
            is_selected    = True if tmpl.is_mandatory else tmpl.default_selected,
            status         = 'pending',
            created_by     = current_user.id,
        ))

    # ── 4. NPD Activity Log ──
    log_npd(proj.id,
        f"Project created from Lead #{lead.id} ({lead.contact_name or ''}) "
        f"— Type: {project_type.upper()} — by {current_user.full_name}"
        + (f" — Client #{lead.client_id} already linked" if lead.client_id else ""))

    # ── 5. CRM Lead Activity Log ──
    db.session.add(CRMActivityLog(
        lead_id    = lead.id,
        user_id    = current_user.id,
        action     = (f"Lead converted to {project_type.upper()} Project: {proj.code}"
                      f" — Status: {old_status} → {new_status}"
                      + (f" — Client already exists (ID: {lead.client_id})" if lead.client_id else "")),
        created_at = datetime.now(),
    ))

    db.session.commit()

    # ── 6. Redirect Logic ──
    if lead.client_id:
        # Client pehle se exist karta hai → seedha client view pe bhejo
        flash(
            f'✅ {project_type.upper()} Project {proj.code} created! '
            f'Lead status → "{new_status}". '
            f'Client already linked — opening client profile.',
            'success'
        )
        return redirect(url_for('crm.client_view', id=lead.client_id))
    else:
        # Client nahi hai → client create form pe bhejo
        # lead_id pass karo taaki client create hone ke baad lead se link ho
        flash(
            f'✅ {project_type.upper()} Project {proj.code} created! '
            f'Lead status → "{new_status}". '
            f'Ab client create karo — details pre-filled hain.',
            'info'
        )
        return redirect(url_for('crm.client_add',
            lead_id      = lead.id,
            proj_id      = proj.id,
            contact_name = lead.contact_name or '',
            company_name = lead.company_name or '',
            email        = lead.email or '',
            mobile       = lead.phone or '',
            city         = lead.city or '',
            state        = lead.state or '',
        ))


# ══════════════════════════════════════════════════════════════
# UPDATE LEAD client_id after client is created
# ══════════════════════════════════════════════════════════════

@npd.route('/link-client/<int:project_id>', methods=['POST'])
@login_required
def link_client(project_id):
    """Link a client_master to a lead via the NPD project."""
    from models import Lead
    proj      = NPDProject.query.get_or_404(project_id)
    client_id = request.form.get('client_id', type=int)

    if not client_id:
        return jsonify(success=False, error='client_id required'), 400

    # Update project
    proj.updated_by = current_user.id
    log_npd(project_id, f"Client #{client_id} linked to project")

    # Update linked lead too
    if proj.lead_id:
        lead = Lead.query.get(proj.lead_id)
        if lead:
            lead.client_id  = client_id
            lead.updated_at = datetime.now()
            lead.modified_by= current_user.id
            db.session.add(lead)

    db.session.commit()
    return jsonify(success=True)


# ══════════════════════════════════════════════════════════════
# NPD SPECIFIC ROUTES
# ══════════════════════════════════════════════════════════════

@npd.route('/npd-dashboard')
@login_required
def npd_dashboard():
    from sqlalchemy import func, case
    ptype = 'npd'
    projects = NPDProject.query.filter_by(is_deleted=False, project_type=ptype)\
                   .order_by(NPDProject.created_at.desc()).all()
    total     = len(projects)
    active    = sum(1 for p in projects if p.status not in ('finish','cancelled'))
    completed = sum(1 for p in projects if p.status == 'complete')
    cancelled = sum(1 for p in projects if p.status == 'cancelled')

    status_counts = {}
    for p in projects:
        status_counts[p.status] = status_counts.get(p.status, 0) + 1

    ms_total = MilestoneMaster.query.join(NPDProject, MilestoneMaster.project_id==NPDProject.id)\
                .filter(NPDProject.project_type==ptype, MilestoneMaster.is_selected==True).count()
    ms_done  = MilestoneMaster.query.join(NPDProject, MilestoneMaster.project_id==NPDProject.id)\
                .filter(NPDProject.project_type==ptype, MilestoneMaster.is_selected==True,
                        MilestoneMaster.status=='approved').count()
    ms_pct   = round((ms_done/ms_total)*100, 1) if ms_total else 0

    sc_stats = []

    perm = get_perm('npd')
    return render_template('npd/npd_dashboard.html',
        active_page='npd_npd_dashboard',
        projects=projects, total=total, active=active,
        completed=completed, cancelled=cancelled,
        status_counts=status_counts,
        ms_pct=ms_pct, ms_done=ms_done, ms_total=ms_total,
        sc_stats=sc_stats, perm=perm,
    )


@npd.route('/npd-projects')
@login_required
def npd_projects():
    q            = request.args.get('q','').strip()
    status       = request.args.get('status','')
    show_deleted = request.args.get('deleted','') == '1'
    sc_id        = ''
    page         = request.args.get('page', 1, type=int)

    if show_deleted:
        query = NPDProject.query.filter_by(is_deleted=True, project_type='npd')
    else:
        query = NPDProject.query.filter_by(is_deleted=False, project_type='npd')

    if q:
        query = query.filter(db.or_(
            NPDProject.code.ilike(f'%{q}%'),
            NPDProject.product_name.ilike(f'%{q}%'),
            NPDProject.client_name.ilike(f'%{q}%'),
            NPDProject.client_company.ilike(f'%{q}%'),
        ))
    if status and not show_deleted:
        query = query.filter_by(status=status)

    deleted_count = NPDProject.query.filter_by(is_deleted=True, project_type='npd').count()
    projects = query.order_by(NPDProject.created_at.desc()).paginate(page=page, per_page=25)
    users    = get_users()
    perm = get_perm('npd')
    from models.master import NPDStatus
    from permissions import get_grid_columns
    from datetime import datetime as _dt
    npd_statuses = NPDStatus.query.filter_by(is_active=True).order_by(NPDStatus.sort_order).all()
    grid_cols = get_grid_columns('npd_projects', NPD_COLS_DEFAULT, list(NPD_COLS_ALL.keys()))
    return render_template('npd/npd_projects.html',
        active_page='npd_npd_projects',
        projects=projects, q=q, status=status, sc_id=sc_id, users=users, perm=perm,
        npd_statuses=npd_statuses,
        grid_cols=grid_cols, all_cols=NPD_COLS_ALL,
        now=_dt.now,
        show_deleted=show_deleted,
        deleted_count=deleted_count,
    )


@npd.route('/sample-ready')
@login_required
def sample_ready():
    from models.npd import NPDFormulation
    q    = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

    # Fix: NPD projects jinka status = 'sample_ready' ho
    query = NPDProject.query.filter_by(
        is_deleted=False,
        project_type='npd',
        status='sample_ready'
    )

    if q:
        query = query.filter(db.or_(
            NPDProject.code.ilike(f'%{q}%'),
            NPDProject.product_name.ilike(f'%{q}%'),
            NPDProject.client_name.ilike(f'%{q}%'),
            NPDProject.client_company.ilike(f'%{q}%'),
        ))

    projects = query.order_by(NPDProject.created_at.desc()).paginate(page=page, per_page=25)

    # Har project ki formulations fetch karo (saari - for context)
    proj_ids = [p.id for p in projects.items]
    formulations = []
    if proj_ids:
        formulations = NPDFormulation.query.filter(
            NPDFormulation.project_id.in_(proj_ids)
        ).order_by(NPDFormulation.iteration).all()
    form_map = {}
    for f in formulations:
        form_map.setdefault(f.project_id, []).append(f)

    perm  = get_perm('npd')
    users = get_users()

    # R&D members resolve karo — assigned_rd_members = comma-sep Employee IDs
    from models.employee import Employee
    rd_members_map = {}  # {project_id: ["Sneha Dagar", "Riya Chandesariya"]}

    # Sab projects ke RD member IDs ek saath collect karo (efficient)
    all_rd_ids = set()
    for p in projects.items:
        if p.assigned_rd_members:
            for x in str(p.assigned_rd_members).split(','):
                x = x.strip()
                if x and x.isdigit():
                    all_rd_ids.add(int(x))

    # Batch fetch — Employee table se
    emp_name_map = {}
    if all_rd_ids:
        emps = Employee.query.filter(
            Employee.id.in_(all_rd_ids),
            Employee.is_deleted == False
        ).all()
        for e in emps:
            emp_name_map[e.id] = e.full_name

    for p in projects.items:
        names = []
        # assigned_rd → single User (R&D head)
        if p.rd_user and p.rd_user.full_name:
            names.append(p.rd_user.full_name)
        # assigned_rd_members → multiple Employees
        if p.assigned_rd_members:
            for x in str(p.assigned_rd_members).split(','):
                x = x.strip()
                if x and x.isdigit():
                    n = emp_name_map.get(int(x))
                    if n and n not in names:
                        names.append(n)
        rd_members_map[p.id] = names

    # Saare R&D department employees (fallback dropdown)
    from models.employee import Employee
    rd_all = Employee.query.filter(
        Employee.is_deleted == False,
        Employee.department.ilike('%r&d%')
    ).order_by(Employee.first_name).all()
    # Agar R&D department filter se koi nahi mila to emp_name_map ke saare names use karo
    if rd_all:
        rd_all_names = [e.full_name for e in rd_all if e.full_name]
    else:
        # emp_name_map already built upar — saare assigned RD names
        rd_all_names = list(set(emp_name_map.values()))
        rd_all_names.sort()

    return render_template('npd/sample_ready.html',
        active_page='npd_sample_ready',
        projects=projects,
        q=q,
        form_map=form_map,
        perm=perm,
        users=users,
        rd_members_map=rd_members_map,
        rd_all_names=rd_all_names,
        total=projects.total,
    )


@npd.route('/npd-projects/grid-config', methods=['POST'])
@login_required
def npd_grid_config():
    from permissions import save_grid_columns
    data = request.get_json()
    cols = data.get('cols', [])
    valid = [c for c in cols if c in NPD_COLS_ALL]
    if not valid:
        return jsonify(success=False, error='No valid columns')
    save_grid_columns('npd_projects', valid)
    return jsonify(success=True)


# ══════════════════════════════════════════════════════════════
# NPD EXPORT
# ══════════════════════════════════════════════════════════════

@npd.route('/npd-projects/bulk-delete', methods=['POST'])
@login_required
def npd_bulk_delete():
    data = request.get_json()
    ids  = data.get('ids', [])
    if not ids:
        return jsonify(success=False, error='No IDs')
    NPDProject.query.filter(
        NPDProject.id.in_([int(i) for i in ids]),
        NPDProject.is_deleted==False
    ).update({
        'is_deleted': True,
        'deleted_at': datetime.now(),
        'deleted_by': current_user.id
    }, synchronize_session=False)
    db.session.commit()
    return jsonify(success=True, deleted=len(ids))


@npd.route('/npd-projects/export')
@login_required
def npd_export():
    from models.employee import Employee
    q      = request.args.get('q','').strip()
    status = request.args.get('status','')
    sc_id  = request.args.get('sc','')

    query = NPDProject.query.filter_by(is_deleted=False, project_type='npd')
    if q:
        query = query.filter(db.or_(
            NPDProject.code.ilike(f'%{q}%'),
            NPDProject.product_name.ilike(f'%{q}%'),
            NPDProject.client_name.ilike(f'%{q}%'),
        ))
    if status:
        query = query.filter_by(status=status)
    projects = query.order_by(NPDProject.created_at.desc()).all()

    # Build employee id→name map
    emp_map = {str(e.id): e.full_name for e in Employee.query.filter_by(is_deleted=False).all()}
    user_map = {u.id: u.full_name for u in User.query.filter_by(is_active=True).all()}

    def emp_names(ids_str):
        if not ids_str: return ''
        return ', '.join(emp_map.get(i.strip(), i.strip()) for i in ids_str.split(',') if i.strip())

    output = io.StringIO()
    writer = csv.writer(output)

    headers = [
        'Project No', 'Type', 'Status', 'Priority',
        'Product Name', 'Category', 'Product Range',
        'Client Name', 'Client Company', 'Client Email', 'Client Phone', 'Client Coordinator',
        'Area of Application', 'Market Level', 'No of Samples', 'MOQ', 'Product Size',
        'Description', 'Ingredients', 'Active Ingredients',
        'Reference Brand', 'Reference Product', 'Reference Product Name',
        'Variant Type', 'Appearance', 'Product Claim', 'Label Claim',
        'Costing Range', 'pH Value', 'Packaging Type', 'Fragrance', 'Viscosity',
        'Video Link', 'Custom Formulation', 'Requirement Spec', 'Order Quantity',
        'NPD Fee Paid', 'NPD Fee Amount',
        'Assigned Members', 'Assigned RD Members',
        'Project Start Date', 'Project End Date', 'Lead Days', 'Target Sample Date',
        'Delay Reason', 'Converted to Commercial',
        'Created At', 'Created By',
    ]
    writer.writerow(headers)

    for p in projects:
        writer.writerow([
            p.code, p.project_type, p.status, p.priority,
            p.product_name, p.product_category or '', p.product_range or '',
            p.client_name or '', p.client_company or '', p.client_email or '', p.client_phone or '', p.client_coordinator or '',
            p.area_of_application or '', p.market_level or '', p.no_of_samples or 0, p.moq or '', p.product_size or '',
            p.description or '', p.ingredients or '', p.active_ingredients or '',
            p.reference_brand or '', p.reference_product or '', p.reference_product_name or '',
            p.variant_type or '', p.appearance or '', p.product_claim or '', p.label_claim or '',
            p.costing_range or '', p.ph_value or '', p.packaging_type or '', p.fragrance or '', p.viscosity or '',
            p.video_link or '', 'Yes' if p.custom_formulation else 'No', p.requirement_spec or '', p.order_quantity or '',
            'Yes' if p.npd_fee_paid else 'No', float(p.npd_fee_amount) if p.npd_fee_amount else '',
            emp_names(p.assigned_members), emp_names(p.assigned_rd_members),
            p.project_start_date.strftime('%d-%m-%Y') if p.project_start_date else '',
            p.project_end_date.strftime('%d-%m-%Y') if p.project_end_date else '',
            p.project_lead_days or '',
            p.target_sample_date.strftime('%d-%m-%Y') if p.target_sample_date else '',
            p.delay_reason or '', 'Yes' if p.converted_to_commercial else 'No',
            p.created_at.strftime('%d-%m-%Y %H:%M') if p.created_at else '',
            user_map.get(p.created_by, '') if p.created_by else '',
        ])

    from flask import Response
    output.seek(0)
    filename = f"NPD_Projects_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename={filename}'}
    )


# ══════════════════════════════════════════════════════════════
# NPD IMPORT
# ══════════════════════════════════════════════════════════════

@npd.route('/npd-projects/import', methods=['GET', 'POST'])
@login_required
def npd_import():
    if request.method == 'GET':
        # Return sample CSV template
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow([
            'Product Name*', 'Category', 'Product Range', 'Status',
            'Priority', 'Client Name', 'Client Company', 'Client Email', 'Client Phone',
            'Client Coordinator', 'Area of Application', 'Market Level', 'No of Samples',
            'MOQ', 'Product Size', 'Description', 'Ingredients', 'Active Ingredients',
            'Reference Brand', 'Reference Product', 'Variant Type', 'Appearance',
            'Product Claim', 'Label Claim', 'Costing Range', 'pH Value',
            'Packaging Type', 'Fragrance', 'Viscosity', 'Order Quantity',
            'Project Start Date (DD-MM-YYYY)', 'Project End Date (DD-MM-YYYY)',
            'Target Sample Date (DD-MM-YYYY)', 'Requirement Spec',
        ])
        # Sample row
        writer.writerow([
            'Sample Face Wash', 'Skin Care', 'Herbal', 'not_started',
            'Normal', 'John Doe', 'ABC Corp', 'john@abc.com', '9999999999',
            'Sneha', 'Face', 'Premium', '3',
            '1000 units', '100ml', 'Gentle face wash', '', '',
            'Foxtale', 'Oil Face Wash', 'Regular', 'Clear gel',
            '', '', 'As per benchmark', '5.5-6.5',
            'Flip cap bottle', 'Fresh', 'Medium', '5000 units',
            '01-04-2026', '30-06-2026', '15-04-2026', 'Must be SLS free',
        ])
        output.seek(0)
        from flask import Response
        return Response(
            output.getvalue(),
            mimetype='text/csv',
            headers={'Content-Disposition': 'attachment; filename=NPD_Import_Template.csv'}
        )

    # POST — process uploaded CSV
    if 'file' not in request.files:
        flash('No file uploaded', 'error')
        return redirect(url_for('npd.npd_projects'))

    f = request.files['file']
    if not f.filename.endswith('.csv'):
        flash('Only CSV files are supported', 'error')
        return redirect(url_for('npd.npd_projects'))

    stream = io.StringIO(f.stream.read().decode('utf-8-sig'))
    reader = csv.DictReader(stream)

    added = 0
    errors = []

    for i, row in enumerate(reader, start=2):
        product_name = (row.get('Product Name*') or row.get('Product Name') or '').strip()
        if not product_name:
            errors.append(f'Row {i}: Product Name is required')
            continue
        try:
            def pd(val):
                v = (val or '').strip()
                if not v: return None
                for fmt in ('%d-%m-%Y', '%Y-%m-%d', '%d/%m/%Y'):
                    try: return datetime.strptime(v, fmt).date()
                    except: pass
                return None

            proj = NPDProject(
                code=gen_npd_code(),
                project_type='npd',
                product_name=product_name,
                product_category=(row.get('Category') or '').strip(),
                product_range=(row.get('Product Range') or '').strip(),
                status=(row.get('Status') or 'not_started').strip(),
                priority=(row.get('Priority') or 'Normal').strip(),
                client_name=(row.get('Client Name') or '').strip(),
                client_company=(row.get('Client Company') or '').strip(),
                client_email=(row.get('Client Email') or '').strip(),
                client_phone=(row.get('Client Phone') or '').strip(),
                client_coordinator=(row.get('Client Coordinator') or '').strip(),
                area_of_application=(row.get('Area of Application') or '').strip(),
                market_level=(row.get('Market Level') or '').strip(),
                no_of_samples=int(row.get('No of Samples') or 0),
                moq=(row.get('MOQ') or '').strip(),
                product_size=(row.get('Product Size') or '').strip(),
                description=(row.get('Description') or '').strip(),
                ingredients=(row.get('Ingredients') or '').strip(),
                active_ingredients=(row.get('Active Ingredients') or '').strip(),
                reference_brand=(row.get('Reference Brand') or '').strip(),
                reference_product=(row.get('Reference Product') or '').strip(),
                variant_type=(row.get('Variant Type') or '').strip(),
                appearance=(row.get('Appearance') or '').strip(),
                product_claim=(row.get('Product Claim') or '').strip(),
                label_claim=(row.get('Label Claim') or '').strip(),
                costing_range=(row.get('Costing Range') or '').strip(),
                ph_value=(row.get('pH Value') or '').strip(),
                packaging_type=(row.get('Packaging Type') or '').strip(),
                fragrance=(row.get('Fragrance') or '').strip(),
                viscosity=(row.get('Viscosity') or '').strip(),
                order_quantity=(row.get('Order Quantity') or '').strip(),
                requirement_spec=(row.get('Requirement Spec') or '').strip(),
                project_start_date=pd(row.get('Project Start Date (DD-MM-YYYY)')),
                project_end_date=pd(row.get('Project End Date (DD-MM-YYYY)')),
                target_sample_date=pd(row.get('Target Sample Date (DD-MM-YYYY)')),
                milestone_master_created=True,
                created_by=current_user.id,
            )
            db.session.add(proj)
            db.session.flush()
            # Add default milestones
            templates = get_milestone_templates('npd')
            for tmpl in templates:
                if tmpl.applies_to == 'existing': continue
                db.session.add(MilestoneMaster(
                    project_id=proj.id, milestone_type=tmpl.milestone_type,
                    title=tmpl.title, sort_order=tmpl.sort_order,
                    is_selected=True if tmpl.is_mandatory else tmpl.default_selected,
                    status='pending', created_by=current_user.id,
                ))
            added += 1
        except Exception as e:
            errors.append(f'Row {i}: {str(e)}')

    db.session.commit()

    if added:
        flash(f'✅ {added} project(s) imported successfully!', 'success')
    if errors:
        flash('⚠️ Errors: ' + ' | '.join(errors[:5]), 'warning')

    return redirect(url_for('npd.npd_projects'))


@npd.route('/npd-new', methods=['GET', 'POST'])
@login_required
def npd_new():
    """NPD only form"""
    users = get_users()
    leads = Lead.query.filter_by(is_deleted=False).order_by(Lead.created_at.desc()).limit(200).all()
    prefill_lead = None
    prefill_lead_id = request.args.get('lead_id') or request.form.get('lead_id')
    if prefill_lead_id:
        try: prefill_lead = Lead.query.get(int(prefill_lead_id))
        except: pass
    prefill_url = {'client_id': '', 'client_name': '', 'client_company': '', 'client_email': '', 'client_phone': ''}
    _cid = request.args.get('client_id')
    if _cid:
        try:
            from models.client import ClientMaster
            _cl = ClientMaster.query.get(int(_cid))
            if _cl:
                prefill_url['client_id']      = str(_cl.id)
                prefill_url['client_name']    = _cl.contact_name or ''
                prefill_url['client_company'] = _cl.company_name or ''
                prefill_url['client_email']   = _cl.email or ''
                prefill_url['client_phone']   = _cl.mobile or ''
        except: pass

    if request.method == 'POST':
        product_name = request.form.get('product_name','').strip()
        if not product_name:
            flash('Product name required','error')
            return render_template('npd/npd_form.html', active_page='npd_npd_projects',
                                   users=users, leads=leads, prefill_lead=prefill_lead,
                                   prefill_url=prefill_url, edit=None)

        g = request.form.get  # shorthand
        proj = NPDProject(
            code=gen_npd_code(), project_type='npd',
            status=g('status','not_started'),
            product_name=product_name,
            product_category=g('product_category',''),
            product_range=g('product_range',''),
            client_name=g('client_name',''),
            client_company=g('client_company',''),
            client_email=g('client_email',''),
            client_phone=g('client_phone',''),
            client_coordinator=g('client_coordinator',''),
            lead_id=g('lead_id') or None,
            requirement_spec=g('requirement_spec',''),
            reference_product=g('reference_product',''),
            reference_brand=g('reference_brand',''),
            reference_product_name=g('reference_product_name',''),
            custom_formulation='custom_formulation' in request.form,
            order_quantity=g('order_quantity',''),
            npd_fee_paid='npd_fee_paid' in request.form,
            npd_fee_amount=g('npd_fee_amount',10000) or 10000,
            # Extended fields
            area_of_application=g('area_of_application',''),
            market_level=g('market_level',''),
            no_of_samples=int(g('no_of_samples') or 0),
            moq=g('moq',''),
            product_size=g('product_size',''),
            description=g('description',''),
            ingredients=g('ingredients',''),
            active_ingredients=g('active_ingredients',''),
            video_link=g('video_link',''),
            variant_type=g('variant_type',''),
            appearance=g('appearance',''),
            product_claim=g('product_claim',''),
            label_claim=g('label_claim',''),
            costing_range=g('costing_range',''),
            ph_value=g('ph_value',''),
            packaging_type=g('packaging_type',''),
            fragrance=g('fragrance',''),
            viscosity=g('viscosity',''),
            priority=g('priority','Normal'),
            project_start_date=_parse_date(g('project_start_date')),
            project_lead_days=int(g('project_lead_days') or 0) or None,
            project_end_date=_parse_date(g('project_end_date')),
            target_sample_date=g('target_sample_date') or None,
            assigned_members=g('assigned_members',''),
            assigned_rd_members=g('assigned_rd_members',''),
            client_id=g('client_id') or None,
            milestone_master_created=True,
            created_by=current_user.id,
        )
        if 'npd_fee_receipt' in request.files:
            f = request.files['npd_fee_receipt']
            if f and f.filename and allowed_file(f.filename):
                proj.npd_fee_receipt = save_upload(f)

        db.session.add(proj)
        db.session.flush()

        templates = get_milestone_templates('npd')
        for tmpl in templates:
            if tmpl.applies_to == 'existing': continue
            db.session.add(MilestoneMaster(
                project_id=proj.id, milestone_type=tmpl.milestone_type,
                title=tmpl.title, sort_order=tmpl.sort_order,
                is_selected=True if tmpl.is_mandatory else tmpl.default_selected,
                status='pending', created_by=current_user.id,
            ))

        log_npd(proj.id, f"NPD Project created: {proj.code} — {product_name}")
        db.session.commit()
        flash(f'NPD Project {proj.code} created!', 'success')
        return redirect(url_for('npd.project_view', pid=proj.id))

    if request.method == 'GET':
        from models.employee import Employee
        from models.master import NPDStatus, CategoryMaster
        from models.client import ClientMaster
        categories = CategoryMaster.query.filter_by(status=True, is_deleted=False).order_by(CategoryMaster.name).all()
        employees = Employee.query.filter_by(is_deleted=False).order_by(Employee.first_name).all()
        rd_employees = Employee.query.filter(
            Employee.is_deleted==False,
            db.or_(
                Employee.department.ilike('%r&d%'),
                Employee.department.ilike('%rd%'),
                Employee.department.ilike('%research%'),
                Employee.department.ilike('%r & d%'),
                Employee.designation.ilike('%r&d%'),
                Employee.designation.ilike('%r & d%'),
                Employee.designation.ilike('%formulation%'),
                Employee.designation.ilike('%scientist%'),
                Employee.designation.ilike('%chemist%'),
            )
        ).order_by(Employee.first_name).all()
        # Fallback: if no R&D-tagged employees found, show all employees
        if not rd_employees:
            rd_employees = employees
        npd_statuses = NPDStatus.query.filter_by(is_active=True).order_by(NPDStatus.sort_order).all()
        clients = ClientMaster.query.filter_by(is_deleted=False).order_by(ClientMaster.contact_name).all()
        return render_template('npd/npd_form.html',
            active_page='npd_npd_projects',
            users=users, leads=leads, edit=None,
            employees=employees,
            rd_employees=rd_employees,
            npd_statuses=npd_statuses,
            clients=clients,
            categories=categories,
            prefill_lead=prefill_lead, prefill_url=prefill_url,
            default_milestones=get_milestone_templates('npd'),
        )


# ══════════════════════════════════════════════════════════════
# EPD SPECIFIC ROUTES
# ══════════════════════════════════════════════════════════════

@npd.route('/epd-dashboard')
@login_required
def epd_dashboard():
    from sqlalchemy import func, case
    ptype = 'existing'
    projects = NPDProject.query.filter_by(is_deleted=False, project_type=ptype)\
                   .order_by(NPDProject.created_at.desc()).all()
    total     = len(projects)
    active    = sum(1 for p in projects if p.status not in ('finish','cancelled'))
    completed = sum(1 for p in projects if p.status == 'complete')
    cancelled = sum(1 for p in projects if p.status == 'cancelled')

    status_counts = {}
    for p in projects:
        status_counts[p.status] = status_counts.get(p.status, 0) + 1

    ms_total = MilestoneMaster.query.join(NPDProject, MilestoneMaster.project_id==NPDProject.id)\
                .filter(NPDProject.project_type==ptype, MilestoneMaster.is_selected==True).count()
    ms_done  = MilestoneMaster.query.join(NPDProject, MilestoneMaster.project_id==NPDProject.id)\
                .filter(NPDProject.project_type==ptype, MilestoneMaster.is_selected==True,
                        MilestoneMaster.status=='approved').count()
    ms_pct   = round((ms_done/ms_total)*100, 1) if ms_total else 0

    sc_stats = []

    return render_template('npd/epd_dashboard.html',
        active_page='npd_epd_dashboard',
        projects=projects, total=total, active=active,
        completed=completed, cancelled=cancelled,
        status_counts=status_counts,
        ms_pct=ms_pct, ms_done=ms_done, ms_total=ms_total,
        sc_stats=sc_stats,
    )


@npd.route('/epd-projects')
@login_required
def epd_projects():
    q      = request.args.get('q','').strip()
    status = request.args.get('status','')
    sc_id  = request.args.get('sc','')
    page   = request.args.get('page', 1, type=int)

    query = NPDProject.query.filter_by(is_deleted=False, project_type='existing')
    if q:
        query = query.filter(db.or_(
            NPDProject.code.ilike(f'%{q}%'),
            NPDProject.product_name.ilike(f'%{q}%'),
            NPDProject.client_name.ilike(f'%{q}%'),
            NPDProject.client_company.ilike(f'%{q}%'),
        ))
    if status:
        query = query.filter_by(status=status)

    projects = query.order_by(NPDProject.created_at.desc()).paginate(page=page, per_page=25)
    users    = get_users()
    return render_template('npd/epd_projects.html',
        active_page='npd_epd_projects',
        projects=projects, q=q, status=status, sc_id=sc_id, users=users,
    )


@npd.route('/epd-new', methods=['GET','POST'])
@login_required
def epd_new():
    """EPD only form"""
    users = get_users()
    leads = Lead.query.filter_by(is_deleted=False).order_by(Lead.created_at.desc()).limit(200).all()
    prefill_lead = None
    prefill_lead_id = request.args.get('lead_id') or request.form.get('lead_id')
    if prefill_lead_id:
        try: prefill_lead = Lead.query.get(int(prefill_lead_id))
        except: pass
    prefill_url = {'client_id': '', 'client_name': '', 'client_company': '', 'client_email': '', 'client_phone': ''}
    _cid = request.args.get('client_id')
    if _cid:
        try:
            from models.client import ClientMaster
            _cl = ClientMaster.query.get(int(_cid))
            if _cl:
                prefill_url['client_id']      = str(_cl.id)
                prefill_url['client_name']    = _cl.contact_name or ''
                prefill_url['client_company'] = _cl.company_name or ''
                prefill_url['client_email']   = _cl.email or ''
                prefill_url['client_phone']   = _cl.mobile or ''
        except: pass

    if request.method == 'POST':
        product_name = request.form.get('product_name','').strip()
        if not product_name:
            flash('Product name required','error')
            return render_template('npd/epd_form.html', active_page='npd_epd_projects',
                                   users=users, leads=leads, prefill_lead=prefill_lead,
                                   prefill_url=prefill_url, edit=None)

        proj = NPDProject(
            code=gen_npd_code(), project_type='existing', status='not_started',
            product_name=product_name,
            product_category=request.form.get('product_category',''),
            product_range=request.form.get('product_range',''),
            client_name=request.form.get('client_name',''),
            client_company=request.form.get('client_company',''),
            client_email=request.form.get('client_email',''),
            client_phone=request.form.get('client_phone',''),
            lead_id=request.form.get('lead_id') or None,
            requirement_spec=request.form.get('requirement_spec',''),
            reference_product=request.form.get('reference_product',''),
            order_quantity=request.form.get('order_quantity',''),
            advance_paid='advance_paid' in request.form,
            advance_amount=request.form.get('advance_amount',2000) or 2000,
            milestone_master_created=True,
            created_by=current_user.id,
        )
        db.session.add(proj)
        db.session.flush()

        templates = get_milestone_templates('existing')
        for tmpl in templates:
            if tmpl.applies_to == 'npd': continue
            db.session.add(MilestoneMaster(
                project_id=proj.id, milestone_type=tmpl.milestone_type,
                title=tmpl.title, sort_order=tmpl.sort_order,
                is_selected=True if tmpl.is_mandatory else tmpl.default_selected,
                status='pending', created_by=current_user.id,
            ))

        log_npd(proj.id, f"EPD Project created: {proj.code} — {product_name}")
        db.session.commit()
        flash(f'EPD Project {proj.code} created!', 'success')
        return redirect(url_for('npd.project_view', pid=proj.id))

    from models.master import CategoryMaster
    categories = CategoryMaster.query.filter_by(status=True, is_deleted=False).order_by(CategoryMaster.name).all()
    return render_template('npd/epd_form.html',
        active_page='npd_epd_projects',
        users=users, leads=leads, edit=None,
        categories=categories,
        prefill_lead=prefill_lead, prefill_url=prefill_url,
        default_milestones=get_milestone_templates('existing'),
    )



@npd.route('/uploads/<path:filename>')
@login_required
def serve_upload(filename):
    """Serve uploaded NPD files"""
    from flask import send_from_directory
    return send_from_directory(UPLOAD_FOLDER, filename)


@npd.route('/sample-history/<int:tid>/delete', methods=['POST'])
@login_required
def sample_history_delete(tid):
    try:
        token = OfficeDispatchToken.query.get_or_404(tid)
        # Projects ka status wapas sample_ready karo
        for item in token.items:
            proj = NPDProject.query.get(item.project_id)
            if proj:
                proj.status = 'sample_ready'
        db.session.delete(token)
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500


@npd.route('/sample-ready/send-to-office', methods=['POST'])
@login_required
def send_to_office():
    data     = request.get_json()
    proj_ids = data.get('project_ids', [])
    notes    = data.get('notes', '')
    if not proj_ids:
        return jsonify(success=False, error='Koi project select nahi kiya')

    # Same day ka existing token check karo
    today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    today_end   = datetime.now().replace(hour=23, minute=59, second=59, microsecond=999999)
    token = OfficeDispatchToken.query.filter(
        OfficeDispatchToken.dispatched_at >= today_start,
        OfficeDispatchToken.dispatched_at <= today_end
    ).order_by(OfficeDispatchToken.dispatched_at.desc()).first()

    is_new_token = False
    if not token:
        last     = OfficeDispatchToken.query.order_by(OfficeDispatchToken.id.desc()).first()
        next_num = (last.id + 1) if last else 1
        token_no = f'ODT-{next_num:04d}'
        token    = OfficeDispatchToken(token_no=token_no, dispatched_by=current_user.id,
                                       dispatched_at=datetime.now(), notes=notes)
        db.session.add(token)
        db.session.flush()
        is_new_token = True
    else:
        token_no = token.token_no
        # Notes append karo agar naya notes hai
        if notes:
            token.notes = ((token.notes + ' | ') if token.notes else '') + notes
    sample_codes  = data.get('sample_codes', {})   # {project_id: "SC-001, SC-002"}
    handover_map  = data.get('handover_to', {})    # {project_id: "Sneha Dagar"}
    submitted_map = data.get('submitted_by', {})   # {project_id: "Aaquib"}
    # Existing items ke project IDs (duplicate avoid)
    existing_pids = {item.project_id for item in token.items}
    for pid in proj_ids:
        if int(pid) in existing_pids:
            continue  # Already is token mein hai
        sc  = sample_codes.get(str(pid),  '').strip()
        ht  = handover_map.get(str(pid),  '').strip()
        sb  = submitted_map.get(str(pid), '').strip()
        db.session.add(OfficeDispatchItem(
            token_id     = token.id,
            project_id   = int(pid),
            sample_code  = sc if sc else None,
            handover_to  = ht if ht else None,
            submitted_by = sb if sb else None,
        ))
    # Project status → send_to_office + list se remove
    for pid in proj_ids:
        proj = NPDProject.query.get(int(pid))
        if proj:
            proj.status = 'sent_to_office'
    db.session.commit()
    return jsonify(success=True, token_no=token_no, token_id=token.id)


@npd.route('/sample-history')
@login_required
def sample_history():
    from models.employee import Employee
    page         = request.args.get('page', 1, type=int)
    q                = request.args.get('q', '').strip()
    from_date        = request.args.get('from_date', '').strip()
    to_date          = request.args.get('to_date', '').strip()
    submitted_by_list = request.args.getlist('submitted_by')   # multi-select
    handover_to_list  = request.args.getlist('handover_to')    # multi-select
    submitted_by_list = [x.strip() for x in submitted_by_list if x.strip()]
    handover_to_list  = [x.strip() for x in handover_to_list  if x.strip()]

    # Base query
    query = OfficeDispatchToken.query

    # Date filter
    if from_date:
        try:
            fd = datetime.strptime(from_date, '%Y-%m-%d')
            query = query.filter(OfficeDispatchToken.dispatched_at >= fd)
        except: pass
    if to_date:
        try:
            td = datetime.strptime(to_date, '%Y-%m-%d')
            from datetime import timedelta
            query = query.filter(OfficeDispatchToken.dispatched_at < td + timedelta(days=1))
        except: pass

    # Product name / submitted_by / handover_to filter — via items join
    if q or submitted_by_list or handover_to_list:
        query = query.join(OfficeDispatchItem, OfficeDispatchItem.token_id == OfficeDispatchToken.id)
        if q:
            query = query.join(NPDProject, NPDProject.id == OfficeDispatchItem.project_id)                         .filter(NPDProject.product_name.ilike(f'%{q}%'))
        if submitted_by_list:
            query = query.filter(OfficeDispatchItem.submitted_by.in_(submitted_by_list))
        if handover_to_list:
            query = query.filter(OfficeDispatchItem.handover_to.in_(handover_to_list))
        query = query.distinct()

    tokens = query.order_by(OfficeDispatchToken.dispatched_at.desc()).paginate(page=page, per_page=25)

    # Dropdowns — all R&D employees for submitted_by
    rd_employees = Employee.query.filter(
        Employee.is_deleted == False,
        Employee.department.ilike('%r&d%')
    ).order_by(Employee.first_name).all()
    rd_names = [e.full_name for e in rd_employees if e.full_name]

    # Handover To — saare employees EXCEPT R&D department
    from models.employee import Employee as _Emp
    handover_emps = _Emp.query.filter(
        _Emp.is_deleted == False,
        db.or_(
            _Emp.department == None,
            _Emp.department == '',
            ~_Emp.department.ilike('%r&d%')
        )
    ).order_by(_Emp.first_name).all()
    handover_names = [e.full_name for e in handover_emps if e.full_name]

    return render_template('npd/sample_history.html',
        active_page='npd_sample_history',
        tokens=tokens,
        q=q, from_date=from_date, to_date=to_date,
        submitted_by_list=submitted_by_list, handover_to_list=handover_to_list,
        rd_names=rd_names,
        handover_names=handover_names,
    )


@npd.route('/sample-history/item/<int:iid>/delete', methods=['POST'])
@login_required
def sample_history_item_delete(iid):
    try:
        item = OfficeDispatchItem.query.get_or_404(iid)
        token = item.token
        # Project status wapas sample_ready
        proj = NPDProject.query.get(item.project_id)
        if proj:
            proj.status = 'sample_ready'
        db.session.delete(item)
        # Agar token mein koi item nahi bacha to token bhi delete
        db.session.flush()
        remaining = OfficeDispatchItem.query.filter_by(token_id=token.id).count()
        if remaining == 0:
            db.session.delete(token)
        db.session.commit()
        return jsonify(success=True, token_deleted=(remaining == 0))
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500


@npd.route('/sample-history/item/<int:iid>/update', methods=['POST'])
@login_required
def sample_history_item_update(iid):
    try:
        item  = OfficeDispatchItem.query.get_or_404(iid)
        data  = request.get_json()
        item.handover_to  = data.get('handover_to',  '').strip() or None
        item.submitted_by = data.get('submitted_by', '').strip() or None
        item.sample_code  = data.get('sample_code',  '').strip() or None
        db.session.commit()
        return jsonify(success=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(success=False, error=str(e)), 500


@npd.route('/sample-history/<int:tid>/items')
@login_required
def sample_history_items(tid):
    token = OfficeDispatchToken.query.get_or_404(tid)
    items = []
    for it in token.items:
        p = it.project
        items.append({
            'item_id'     : it.id,
            'project_id'  : p.id,
            'code'        : p.code or '—',
            'product_name': p.product_name,
            'client_name' : p.client_name or '—',
            'category'    : p.product_category or '—',
            'priority'    : p.priority or 'Normal',
            'status_label': p.status_label,
            'status_color': p.status_color,
            'sample_code' : it.sample_code or '',
            'handover_to' : it.handover_to  or '',
            'submitted_by': it.submitted_by or '',
        })
    return jsonify(token_no=token.token_no,
        dispatched_at=token.dispatched_at.strftime('%d %b %Y, %I:%M %p'),
        dispatcher=token.dispatcher.full_name if token.dispatcher else '—',
        notes=token.notes or '', count=len(items), items=items)
