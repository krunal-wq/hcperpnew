"""
npd_routes.py — Product Development Workflow
Blueprint: npd at /npd
"""

import os, json
from datetime import datetime, date
from flask import (Blueprint, render_template, redirect, url_for,
                   request, flash, jsonify, current_app)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from models import (db, User, Lead, NPDMilestoneTemplate,
                    NPDProject, MilestoneMaster, MilestoneLog,
                    NPDFormulation, NPDPackingMaterial, NPDArtwork, NPDActivityLog)

npd = Blueprint('npd', __name__, url_prefix='/npd')

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
                    NPDProject.status.notin_(['complete','cancelled'])).count()
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
    sc_stats = db.session.query(
        User.full_name,
        func.count(NPDProject.id).label('total'),
        func.sum(case((NPDProject.status=='complete',1),else_=0)).label('completed')
    ).join(NPDProject, NPDProject.assigned_sc==User.id)\
     .filter(NPDProject.is_deleted==False)\
     .group_by(User.id, User.full_name).all()

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
    sc_id    = request.args.get('sc','')
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
    if sc_id:
        query = query.filter_by(assigned_sc=int(sc_id))

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

    # Also support direct client_* URL params (from client list page)
    prefill_url = {
        'client_name':    request.args.get('client_name', ''),
        'client_company': request.args.get('client_company', ''),
        'client_email':   request.args.get('client_email', ''),
        'client_phone':   request.args.get('client_phone', ''),
        'product_name':   request.args.get('product', ''),
    }

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
            assigned_sc     = request.form.get('assigned_sc') or None,
            assigned_rd     = request.form.get('assigned_rd') or None,
            npd_poc         = request.form.get('npd_poc') or None,
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
        # If created from lead page, redirect back to lead NPD tab
        from_lead = request.form.get('from_lead_id')
        if from_lead:
            return redirect(url_for('crm.lead_view', id=from_lead) + '?tab=npd')
        return redirect(url_for('npd.project_view', pid=proj.id))

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

    return render_template('npd/project_view.html',
        active_page='npd_projects',
        proj=proj,
        users=users,
        selected_ms=selected_ms,
        ms_done=ms_done,
        ms_pct=ms_pct,
    )


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
        proj.product_name    = request.form.get('product_name', proj.product_name).strip()
        proj.product_category= request.form.get('product_category', '')
        proj.product_range   = request.form.get('product_range', '')
        proj.client_name     = request.form.get('client_name', '')
        proj.client_company  = request.form.get('client_company', '')
        proj.client_email    = request.form.get('client_email', '')
        proj.client_phone    = request.form.get('client_phone', '')
        proj.lead_id         = request.form.get('lead_id') or None
        proj.assigned_sc     = request.form.get('assigned_sc') or None
        proj.assigned_rd     = request.form.get('assigned_rd') or None
        proj.npd_poc         = request.form.get('npd_poc') or None
        proj.requirement_spec= request.form.get('requirement_spec', '')
        proj.reference_product= request.form.get('reference_product', '')
        proj.custom_formulation= 'custom_formulation' in request.form
        proj.order_quantity  = request.form.get('order_quantity', '')
        proj.npd_fee_paid    = 'npd_fee_paid' in request.form
        proj.npd_fee_amount  = request.form.get('npd_fee_amount', proj.npd_fee_amount) or proj.npd_fee_amount
        proj.delay_reason    = request.form.get('delay_reason', '')
        proj.updated_by      = current_user.id

        if 'npd_fee_receipt' in request.files:
            f = request.files['npd_fee_receipt']
            if f and f.filename and allowed_file(f.filename):
                proj.npd_fee_receipt = save_upload(f)

        log_npd(proj.id, f"Project updated by {current_user.full_name}")
        db.session.commit()
        flash('Project updated!', 'success')
        return redirect(url_for('npd.project_view', pid=proj.id))

    return render_template('npd/project_form.html',
        active_page='npd_projects',
        edit=proj, users=users, leads=leads,
        default_milestones=get_milestone_templates(),
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
    return redirect(url_for('npd.projects'))


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
    sc_stats = db.session.query(
        User.full_name,
        func.count(NPDProject.id).label('total'),
        func.sum(case((NPDProject.status=='complete',1),else_=0)).label('completed'),
        func.sum(case((NPDProject.status=='cancelled',1),else_=0)).label('cancelled'),
    ).join(NPDProject, NPDProject.assigned_sc==User.id)\
     .filter(NPDProject.is_deleted==False)\
     .group_by(User.id, User.full_name).all()

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
        assigned_sc      = lead.assigned_to,
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
