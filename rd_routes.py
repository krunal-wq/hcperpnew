"""
rd_routes.py — R&D NPD Management System
Blueprint: rd at /rd
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db, User

from permissions import get_perm, get_sub_perm
rd = Blueprint('rd', __name__, url_prefix='/rd')


# ── Helper: get all RD users (employees assigned to R&D) ──
def get_rd_users():
    """Return all active Users who are R&D executives/managers + 
    Employees in R&D dept who have linked user accounts"""
    from models.employee import Employee

    # Base: Users with rd roles
    rd_users = User.query.filter(
        User.is_active == True,
        User.role.in_(['rd_executive', 'rd_manager', 'admin'])
    ).order_by(User.full_name).all()

    # Also: Employees in R&D department who have a linked user_id
    rd_emp_users = Employee.query.filter(
        Employee.is_deleted == False,
        Employee.department.ilike('%r&d%'),
        Employee.user_id != None
    ).order_by(Employee.first_name).all()

    # Add their linked User objects if not already in list
    existing_ids = {u.id for u in rd_users}
    for emp in rd_emp_users:
        u = User.query.get(emp.user_id)
        if u and u.id not in existing_ids and u.is_active:
            # Tag with designation for display
            u._display_role = emp.designation or 'R&D Executive'
            rd_users.append(u)
            existing_ids.add(u.id)

    return rd_users


# ══════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════

@rd.route('/')
@rd.route('/dashboard')
@login_required
def dashboard():
    from models.npd import NPDProject, NPDFormulation, MilestoneMaster
    from sqlalchemy import func

    # Stats
    active_projects = NPDProject.query.filter(
        NPDProject.is_deleted == False,
        NPDProject.status.notin_(['complete', 'cancelled'])
    ).count()

    total_trials = NPDFormulation.query.count()

    completed = NPDProject.query.filter_by(is_deleted=False, status='complete').count()
    total_proj = NPDProject.query.filter_by(is_deleted=False).count()
    success_rate = round((completed / total_proj * 100), 1) if total_proj else 0

    total_users = User.query.filter_by(is_active=True).count()

    # Recent projects — R&D Manager sees all, executive sees only assigned
    is_rd_manager = current_user.role in ('rd_manager', 'admin')
    if is_rd_manager:
        recent_projects = NPDProject.query.filter_by(is_deleted=False)\
            .order_by(NPDProject.created_at.desc()).limit(6).all()
    else:
        recent_projects = NPDProject.query.filter_by(is_deleted=False)\
            .filter(NPDProject.assigned_rd == current_user.id)\
            .order_by(NPDProject.created_at.desc()).limit(6).all()

    # Recent trials (formulations)
    recent_trials = NPDFormulation.query\
        .order_by(NPDFormulation.created_at.desc()).limit(6).all()

    # SC workload
    from models.npd import NPDProject as NP
    sc_workload = db.session.query(
        User.full_name, User.id,
        func.count(NP.id).label('project_count')
    ).join(NP, NP.assigned_sc == User.id)\
     .filter(NP.is_deleted == False, NP.status.notin_(['complete', 'cancelled']))\
     .group_by(User.id, User.full_name).all()

    perm = get_perm('rd')
    return render_template('rd/dashboard.html',
        active_page='rd_dashboard', perm=perm,
        active_projects=active_projects,
        total_trials=total_trials,
        success_rate=success_rate,
        total_users=total_users,
        recent_projects=recent_projects,
        recent_trials=recent_trials,
        sc_workload=sc_workload,
    )


# ══════════════════════════════════════════════════════════════
# PROJECTS
# ══════════════════════════════════════════════════════════════

@rd.route('/projects')
@login_required
def projects():
    from models.npd import NPDProject, NPDFormulation
    q       = request.args.get('q', '').strip()
    cat     = request.args.get('cat', '')   # npd / existing
    status  = request.args.get('status', '')

    query = NPDProject.query.filter_by(is_deleted=False)
    if q:
        query = query.filter(db.or_(
            NPDProject.product_name.ilike(f'%{q}%'),
            NPDProject.code.ilike(f'%{q}%'),
            NPDProject.client_company.ilike(f'%{q}%'),
        ))
    if cat:
        query = query.filter_by(project_type=cat)
    if status == 'active':
        query = query.filter(NPDProject.status.notin_(['complete', 'cancelled']))
    elif status == 'inactive':
        query = query.filter(NPDProject.status.in_(['complete', 'cancelled']))

    projects = query.order_by(NPDProject.created_at.desc()).all()
    users    = get_rd_users()
    is_rd_manager = current_user.role in ('rd_manager', 'admin')

    # Unallotted = no R&D team member assigned (rd_manager alone doesn't count)
    # A project is "allotted" only when an rd_executive is assigned
    rd_exec_ids = {u.id for u in User.query.filter(
        User.is_active == True,
        User.role == 'rd_executive'
    ).all()}

    CLOSED_STATUSES = {'completed', 'complete', 'closed', 'done', 'project_closed', 'cancelled', 'finish', 'finished'}

    # Project is allotted if it has ANY active RDSubAssignment OR assigned_rd is set
    from models.npd import RDSubAssignment
    assigned_project_ids = {
        s.project_id for s in RDSubAssignment.query.filter_by(is_active=True).all()
    }

    unallotted = [p for p in projects if p.id not in assigned_project_ids and (p.status or '').lower() not in CLOSED_STATUSES]
    allotted   = [p for p in projects if p.id in assigned_project_ids and (p.status or '').lower() not in CLOSED_STATUSES]
    closed     = [p for p in projects if (p.status or '').lower() in CLOSED_STATUSES]

    rd_sub = {
        'unalloted_npd': get_sub_perm('rd', 'unalloted_npd'),
        'alloted_npd':   get_sub_perm('rd', 'alloted_npd'),
        'closed_npd':    get_sub_perm('rd', 'closed_npd'),
        'assign':        get_sub_perm('rd', 'assign'),
    }
    # Build emp_id → name map + user_id → name map for template
    from models.employee import Employee as _EmpM
    _all_emp_ids = set()
    _all_user_ids = set()
    for p in projects:
        if p.assigned_rd_members:
            for token in str(p.assigned_rd_members).split(','):
                token = token.strip()
                if token.startswith('u_'):
                    try: _all_user_ids.add(int(token[2:]))
                    except: pass
                elif token.isdigit():
                    _all_emp_ids.add(int(token))
    rd_emp_names = {}
    if _all_emp_ids:
        for e in _EmpM.query.filter(_EmpM.id.in_(_all_emp_ids), _EmpM.is_deleted==False).all():
            rd_emp_names[e.id] = e.full_name
    # Also map u_<id> → user full_name
    if _all_user_ids:
        for u in User.query.filter(User.id.in_(_all_user_ids)).all():
            rd_emp_names[f'u_{u.id}'] = u.full_name

    return render_template('rd/projects.html',
        active_page='rd_projects',
        projects=projects, q=q, cat=cat, status=status,
        users=users, unallotted=unallotted, allotted=allotted, closed=closed,
        is_rd_manager=is_rd_manager, perm=get_perm('rd'),
        rd_sub=rd_sub,
        rd_emp_names=rd_emp_names,
    )


# ══════════════════════════════════════════════════════════════
# R&D TRIALS (Formulations)
# ══════════════════════════════════════════════════════════════

@rd.route('/trials')
@login_required
def trials():
    from models.npd import NPDFormulation, NPDProject
    q          = request.args.get('q', '').strip()
    result     = request.args.get('result', '')
    project_id = request.args.get('project_id', type=int)

    # ── Trials query ──
    is_admin = current_user.role in ('admin', 'rd_manager')
    query = NPDFormulation.query
    if project_id:
        query = query.filter(NPDFormulation.project_id == project_id)
    if q:
        query = query.filter(db.or_(
            NPDFormulation.formulation_name.ilike(f'%{q}%'),
            NPDFormulation.formulation_desc.ilike(f'%{q}%'),
        ))
    if result == 'pass':
        query = query.filter(NPDFormulation.client_status == 'approved')
    elif result == 'fail':
        query = query.filter(NPDFormulation.status.like('%rejected%'))
    elif result == 'pending':
        query = query.filter(NPDFormulation.client_status == 'pending')

    # Admin/manager = sare trials, executive = sirf apne
    if not is_admin:
        query = query.filter(NPDFormulation.rd_person == current_user.id)

    trials = query.order_by(NPDFormulation.created_at.desc()).all()
    users  = get_rd_users()

    # ── All active projects for modal dropdown ──
    all_projects = NPDProject.query.filter(
        NPDProject.is_deleted == False,
        NPDProject.status.notin_(['complete', 'cancelled'])
    ).order_by(NPDProject.created_at.desc()).all()

    # ── project_filter for banner (when coming from projects page) ──
    project_filter = NPDProject.query.get(project_id) if project_id else None

    # ── Grid 1: my_projects ──
    # Admin/manager = sare active projects
    # Executive = sirf apne assigned (assigned_rd == current_user.id)
    active_q = NPDProject.query.filter(
        NPDProject.is_deleted == False,
        NPDProject.status.notin_(['complete', 'cancelled'])
    )
    if is_admin:
        my_projects = active_q.order_by(NPDProject.created_at.desc()).all()
    else:
        my_projects = active_q.filter(
            NPDProject.assigned_rd == current_user.id
        ).order_by(NPDProject.created_at.desc()).all()

    # ── test_params for parameter table in modal ──
    try:
        from models.npd import RDTestParameter
        test_params = RDTestParameter.query.filter_by(is_active=True)\
                          .order_by(RDTestParameter.sort_order).all()
    except Exception:
        test_params = []

    return render_template('rd/trials.html',
        active_page='rd_trials',
        trials=trials, q=q, result=result,
        users=users, all_projects=all_projects,
        my_projects=my_projects,
        project_filter=project_filter,
        test_params=test_params,
    )


@rd.route('/trials/add', methods=['POST'])
@login_required
def add_trial():
    from models.npd import NPDFormulation, NPDProject, NPDActivityLog
    project_id = request.form.get('project_id')
    if not project_id:
        flash('Project is required', 'error')
        return redirect(url_for('rd.trials'))

    proj = NPDProject.query.get_or_404(int(project_id))
    last_iter = db.session.query(db.func.max(NPDFormulation.iteration))\
                    .filter_by(project_id=proj.id).scalar() or 0

    trial = NPDFormulation(
        project_id        = proj.id,
        iteration         = last_iter + 1,
        formulation_name  = request.form.get('formulation_name', ''),
        formulation_desc  = request.form.get('parameters', ''),
        rd_person         = request.form.get('exec_id') or None,
        rd_notes          = request.form.get('observations', ''),
        rd_submitted_at   = datetime.now(),
        status            = 'pending',
        created_by        = current_user.id,
        created_at        = datetime.now(),
    )
    db.session.add(trial)
    db.session.add(NPDActivityLog(
        project_id = proj.id,
        user_id    = current_user.id,
        action     = f"R&D Trial #{last_iter+1} logged: {trial.formulation_name}",
        created_at = datetime.now(),
    ))
    db.session.commit()
    flash(f'Trial #{last_iter+1} logged successfully!', 'success')
    return redirect(url_for('rd.trials'))


@rd.route('/trials/<int:tid>/result', methods=['POST'])
@login_required
def update_trial_result(tid):
    from models.npd import NPDFormulation
    trial  = NPDFormulation.query.get_or_404(tid)
    result = request.form.get('result', '')  # pass / fail / pending

    if result == 'pass':
        trial.client_status = 'approved'
        trial.client_responded_at = datetime.now()
        trial.status = 'client_approved'
    elif result == 'fail':
        trial.status = 'client_rejected'
        trial.client_status = 'rejected'
    else:
        trial.client_status = 'pending'
        trial.status = 'pending'

    trial.client_feedback = request.form.get('notes', '')
    db.session.commit()
    return jsonify(success=True, result=result)


# ══════════════════════════════════════════════════════════════
# EXECUTIVES (R&D Team)
# ══════════════════════════════════════════════════════════════

@rd.route('/executives')
@login_required
def executives():
    from models.npd import NPDProject, NPDFormulation
    q      = request.args.get('q', '').strip()
    status = request.args.get('status', '')

    query = User.query
    if q:
        query = query.filter(User.full_name.ilike(f'%{q}%'))
    if status == 'active':
        query = query.filter_by(is_active=True)
    elif status == 'inactive':
        query = query.filter_by(is_active=False)

    users = query.order_by(User.full_name).all()

    # Build stats per user
    user_stats = {}
    for u in users:
        proj_count = NPDProject.query.filter(
            NPDProject.assigned_rd == u.id,
            NPDProject.is_deleted == False
        ).count()
        completed = NPDProject.query.filter(
            NPDProject.assigned_rd == u.id,
            NPDProject.is_deleted == False,
            NPDProject.status == 'complete'
        ).count()
        trials_pass = NPDFormulation.query.filter(
            NPDFormulation.rd_person == u.id,
            NPDFormulation.client_status == 'approved'
        ).count()
        trials_fail = NPDFormulation.query.filter(
            NPDFormulation.rd_person == u.id,
            NPDFormulation.status.like('%rejected%')
        ).count()
        total_t = trials_pass + trials_fail
        user_stats[u.id] = {
            'proj_count': proj_count,
            'completed':  completed,
            'trials_pass': trials_pass,
            'trials_fail': trials_fail,
            'success_rate': round(trials_pass / total_t * 100) if total_t else 0,
        }

    return render_template('rd/executives.html',
        active_page='rd_executives',
        users=users, q=q, status=status, user_stats=user_stats,
    )


# ══════════════════════════════════════════════════════════════
# PERFORMANCE
# ══════════════════════════════════════════════════════════════

@rd.route('/performance')
@login_required
def performance():
    from models.npd import NPDProject, NPDFormulation
    users = User.query.filter_by(is_active=True).order_by(User.full_name).all()

    perf = []
    for u in users:
        proj_count = NPDProject.query.filter(
            NPDProject.assigned_rd == u.id,
            NPDProject.is_deleted == False
        ).count()
        completed = NPDProject.query.filter(
            NPDProject.assigned_rd == u.id,
            NPDProject.status == 'complete',
            NPDProject.is_deleted == False
        ).count()
        t_pass = NPDFormulation.query.filter(
            NPDFormulation.rd_person == u.id,
            NPDFormulation.client_status == 'approved'
        ).count()
        t_fail = NPDFormulation.query.filter(
            NPDFormulation.rd_person == u.id,
            NPDFormulation.status.like('%rejected%')
        ).count()
        total_t = t_pass + t_fail
        trial_rate  = round(t_pass / total_t * 100) if total_t else 0
        ontime_rate = 80  # placeholder — can be calculated from project dates
        score = round(trial_rate * 0.4 + ontime_rate * 0.3 + completed * 10)
        perf.append({
            'user': u,
            'proj_count': proj_count,
            'completed':  completed,
            'trial_pass': t_pass,
            'trial_total': total_t,
            'trial_rate':  trial_rate,
            'ontime_rate': ontime_rate,
            'score': score,
        })

    perf.sort(key=lambda x: x['score'], reverse=True)

    return render_template('rd/performance.html',
        active_page='rd_performance',
        perf=perf,
    )


# ══════════════════════════════════════════════════════════════
# DISCUSSION BOARD
# ══════════════════════════════════════════════════════════════

@rd.route('/discussion')
@login_required
def discussion():
    from models.npd import NPDProject, NPDComment
    projects = NPDProject.query.filter(
        NPDProject.is_deleted == False,
        NPDProject.status.notin_(['complete', 'cancelled'])
    ).order_by(NPDProject.created_at.desc()).all()

    # Load all comments for all active projects (grouped by project_id)
    pid = request.args.get('pid', type=int)
    selected_project = None
    comments = []

    if pid:
        selected_project = NPDProject.query.filter_by(id=pid, is_deleted=False).first()
        if selected_project:
            comments = NPDComment.query.filter_by(project_id=pid)                           .order_by(NPDComment.created_at.desc()).all()
    elif projects:
        selected_project = projects[0]
        comments = NPDComment.query.filter_by(project_id=projects[0].id)                       .order_by(NPDComment.created_at.desc()).all()

    return render_template('rd/discussion.html',
        active_page='rd_discussion',
        projects=projects,
        selected_project=selected_project,
        comments=comments,
        pid=pid or (projects[0].id if projects else None),
    )



@rd.route('/discussion/messages')
@login_required
def discussion_messages():
    from models.npd import NPDComment
    pid = request.args.get('pid', type=int)
    if not pid:
        return jsonify(comments=[])
    comments = NPDComment.query.filter_by(project_id=pid)                   .order_by(NPDComment.created_at.desc()).all()
    return jsonify(comments=[{
        'id':       c.id,
        'message':  c.comment,
        'user':     c.user.full_name if c.user else 'Unknown',
        'initials': (c.user.full_name[:2]).upper() if c.user and c.user.full_name else '??',
        'time':     c.created_at.strftime('%d %b, %I:%M %p'),
        'mine':     c.user_id == current_user.id,
    } for c in comments])

@rd.route('/discussion/send', methods=['POST'])
@login_required
def discussion_send():
    from models.npd import NPDComment, NPDProject
    pid     = request.form.get('project_id', type=int)
    message = request.form.get('message', '').strip()
    if not pid or not message:
        return jsonify(success=False, error='Missing data'), 400
    proj = NPDProject.query.filter_by(id=pid, is_deleted=False).first_or_404()
    comment = NPDComment(
        project_id  = pid,
        user_id     = current_user.id,
        comment     = message,
        is_internal = False,
    )
    db.session.add(comment)
    db.session.commit()
    return jsonify(
        success  = True,
        id       = comment.id,
        message  = comment.comment,
        user     = current_user.full_name,
        initials = (current_user.full_name[:2]).upper() if current_user.full_name else 'ME',
        time     = comment.created_at.strftime('%d %b, %I:%M %p'),
        mine     = True,
    )


# ══════════════════════════════════════════════════════════════
# SETTINGS
# ══════════════════════════════════════════════════════════════

@rd.route('/settings')
@login_required
def settings():
    return render_template('rd/settings.html',
        active_page='rd_settings',
    )


# ══════════════════════════════════════════════════════════════
# API ENDPOINTS (AJAX)
# ══════════════════════════════════════════════════════════════

@rd.route('/api/projects')
@login_required
def api_projects():
    from models.npd import NPDProject
    projects = NPDProject.query.filter_by(is_deleted=False)\
                   .order_by(NPDProject.created_at.desc()).all()
    return jsonify([{
        'id':           p.id,
        'code':         p.code,
        'name':         p.product_name,
        'type':         p.project_type,
        'status':       p.status,
        'status_label': p.status_label,
        'status_color': p.status_color,
        'client':       p.client_company or p.client_name or '—',
        'sc':           p.sc_user.full_name if p.sc_user else '—',
        'rd':           p.rd_user.full_name if p.rd_user else '—',
        'age':          p.project_age,
    } for p in projects])


@rd.route('/api/stats')
@login_required
def api_stats():
    from models.npd import NPDProject, NPDFormulation
    return jsonify({
        'active_projects': NPDProject.query.filter(
            NPDProject.is_deleted == False,
            NPDProject.status.notin_(['complete', 'cancelled'])
        ).count(),
        'total_trials': NPDFormulation.query.count(),
        'completed': NPDProject.query.filter_by(is_deleted=False, status='complete').count(),
        'npd_count': NPDProject.query.filter_by(is_deleted=False, project_type='npd').count(),
        'epd_count': NPDProject.query.filter_by(is_deleted=False, project_type='existing').count(),
    })


@rd.route('/trials/<int:tid>/edit', methods=['GET','POST'])
@login_required
def edit_trial(tid):
    from models.npd import NPDFormulation, NPDProject, NPDActivityLog
    trial = NPDFormulation.query.get_or_404(tid)

    if request.method == 'POST':
        trial.formulation_name = request.form.get('formulation_name', trial.formulation_name)
        trial.formulation_desc = request.form.get('parameters', trial.formulation_desc)
        trial.rd_notes         = request.form.get('observations', trial.rd_notes)
        exec_id = request.form.get('exec_id')
        if exec_id:
            trial.rd_person = int(exec_id)
        proj_id = request.form.get('project_id')
        if proj_id:
            trial.project_id = int(proj_id)

        result = request.form.get('result', '')
        if result == 'pass':
            trial.client_status = 'approved'
            trial.status = 'client_approved'
        elif result == 'fail':
            trial.client_status = 'rejected'
            trial.status = 'client_rejected'
        else:
            trial.client_status = 'pending'
            trial.status = 'pending'

        db.session.add(NPDActivityLog(
            project_id = trial.project_id,
            user_id    = current_user.id,
            action     = f"R&D Trial #{trial.iteration} updated by {current_user.full_name}",
            created_at = datetime.now(),
        ))
        db.session.commit()
        flash(f'Trial #{trial.iteration} updated!', 'success')
        return redirect(url_for('rd.trials'))

    # GET: redirect to trials page (modal handles display)
    return redirect(url_for('rd.trials'))


# ══════════════════════════════════════════════════════════════
# ASSIGN R&D PERSON TO PROJECT (AJAX)
# ══════════════════════════════════════════════════════════════

@rd.route('/projects/<int:pid>/assign', methods=['POST'])
@login_required
def assign_project(pid):
    from models.npd import NPDProject, NPDActivityLog
    proj    = NPDProject.query.get_or_404(pid)
    rd_id   = request.form.get('rd_id') or None
    sc_id   = request.form.get('sc_id') or None

    old_rd = proj.assigned_rd
    proj.assigned_rd  = int(rd_id)  if rd_id  else None
    proj.assigned_sc  = int(sc_id)  if sc_id  else proj.assigned_sc
    proj.updated_by   = current_user.id

    rd_name = User.query.get(int(rd_id)).full_name if rd_id else 'Unassigned'
    db.session.add(NPDActivityLog(
        project_id = proj.id,
        user_id    = current_user.id,
        action     = f"R&D assigned: {rd_name} — by {current_user.full_name}",
        created_at = datetime.now(),
    ))
    db.session.commit()
    return jsonify(success=True, rd_name=rd_name, proj_id=pid)


@rd.route('/projects/<int:pid>/assign-multi', methods=['POST'])
@login_required
def assign_multi(pid):
    """Assign multiple R&D executives with individual variant codes"""
    from models.npd import NPDProject, NPDActivityLog, RDSubAssignment
    proj = NPDProject.query.get_or_404(pid)

    # Expecting JSON: [{user_id, variant_code, notes}, ...]
    data = request.get_json(silent=True)
    if not data:
        # fallback form data (old format)
        rd_ids = request.form.getlist('rd_ids')
        data = [{'user_id': uid, 'variant_code': '', 'notes': ''} for uid in rd_ids]

    if not data:
        return jsonify(success=False, error='Select at least one R&D person')

    names = []
    assigned_user_ids = []

    for item in data:
        # item can be dict (JSON) or string (old form fallback)
        if isinstance(item, dict):
            uid          = str(item.get('user_id', '')).strip()
            variant_code = str(item.get('variant_code', '')).strip()
            notes        = str(item.get('notes', '')).strip()
        else:
            uid          = str(item).strip()
            variant_code = ''
            notes        = ''

        # Resolve user — handle u_<id>, emp_<id>, or plain digit
        user_obj = None
        try:
            if uid.startswith('u_'):
                user_obj = User.query.get(int(uid[2:]))
            elif uid.startswith('emp_'):
                from models.employee import Employee as _EmpA
                emp = _EmpA.query.get(int(uid[4:]))
                if emp and emp.user_id:
                    user_obj = User.query.get(emp.user_id)
            elif uid.isdigit():
                user_obj = User.query.get(int(uid))
        except Exception as _ue:
            pass

        if not user_obj:
            continue

        names.append(user_obj.full_name)
        assigned_user_ids.append(f'u_{user_obj.id}')

        # Upsert RDSubAssignment — one per (project, user)
        sub = RDSubAssignment.query.filter_by(
            project_id=proj.id, user_id=user_obj.id
        ).first()
        if sub:
            sub.variant_code = variant_code
            sub.notes        = notes
            sub.assigned_by  = current_user.id
            sub.assigned_at  = datetime.now()
            sub.is_active    = True
        else:
            sub = RDSubAssignment(
                project_id   = proj.id,
                user_id      = user_obj.id,
                variant_code = variant_code,
                notes        = notes,
                assigned_by  = current_user.id,
                assigned_at  = datetime.now(),
                status       = 'not_started',
                is_active    = True,
            )
            db.session.add(sub)

    # Update project level assigned_rd_members for backward compat
    proj.assigned_rd         = User.query.get(int(assigned_user_ids[0][2:])).id if assigned_user_ids else proj.assigned_rd
    proj.assigned_rd_members = ','.join(assigned_user_ids)
    proj.updated_by          = current_user.id

    db.session.add(NPDActivityLog(
        project_id = proj.id,
        user_id    = current_user.id,
        action     = f"R&D team assigned: {', '.join(names)} — by {current_user.full_name}",
        created_at = datetime.now(),
    ))
    # RD Project Log
    from models.npd import RDProjectLog
    db.session.add(RDProjectLog(
        project_id = proj.id,
        user_id    = current_user.id,
        event      = 'assigned',
        detail     = f"Members: {', '.join(names)} — by {current_user.full_name}",
        created_at = datetime.now(),
    ))
    db.session.commit()

    return jsonify(
        success      = True,
        proj_id      = pid,
        rd_names     = names,
        sc_name      = proj.sc_user.full_name if proj.sc_user else '—',
        status       = proj.status_label,
        status_color = proj.status_color,
        code         = proj.code,
        name         = proj.product_name,
        type         = proj.project_type,
        client       = proj.client_company or proj.client_name or '—',
        age          = proj.project_age,
    )

# ══════════════════════════════════════════════════════════════
# PARAMETER MASTER
# ══════════════════════════════════════════════════════════════

@rd.route('/param-master')
@login_required
def param_master():
    try:
        from models.npd import RDTestParameter
        params = RDTestParameter.query.order_by(RDTestParameter.sort_order, RDTestParameter.id).all()
    except Exception:
        params = []
    return render_template('rd/param_master.html', active_page='rd_param_master', params=params)

@rd.route('/api/params')
@login_required
def api_params():
    from flask import jsonify
    try:
        from models.npd import RDTestParameter
        params = RDTestParameter.query.filter_by(is_active=True)\
                     .order_by(RDTestParameter.sort_order, RDTestParameter.id).all()
        return jsonify({'params': [{'name': p.name, 'unit': p.unit or '', 'default_val': p.default_val or ''} for p in params]})
    except Exception:
        return jsonify({'params': []})


@rd.route('/param-master/add', methods=['POST'])
@login_required
def param_master_add():
    from models.npd import RDTestParameter
    data = request.get_json()
    name = (data.get('name') or '').strip()
    if not name:
        return jsonify(success=False, error='Name is required')
    existing = RDTestParameter.query.filter(
        db.func.lower(RDTestParameter.name) == name.lower()
    ).first()
    if existing:
        return jsonify(success=False, error=f'Parameter already exists')
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


@rd.route('/param-master/<int:pid>/update', methods=['POST'])
@login_required
def param_master_update(pid):
    from models.npd import RDTestParameter
    param = RDTestParameter.query.get_or_404(pid)
    data  = request.get_json()
    field = data.get('field')
    value = (data.get('value') or '').strip()
    if field not in {'name', 'default_val', 'unit'}:
        return jsonify(success=False, error='Invalid field')
    if field == 'name' and not value:
        return jsonify(success=False, error='Name cannot be empty')
    setattr(param, field, value)
    db.session.commit()
    return jsonify(success=True)


@rd.route('/param-master/<int:pid>/toggle', methods=['POST'])
@login_required
def param_master_toggle(pid):
    from models.npd import RDTestParameter
    param = RDTestParameter.query.get_or_404(pid)
    param.is_active = not param.is_active
    db.session.commit()
    return jsonify(success=True, is_active=param.is_active)


@rd.route('/param-master/<int:pid>/delete', methods=['POST'])
@login_required
def param_master_delete(pid):
    from models.npd import RDTestParameter
    param = RDTestParameter.query.get_or_404(pid)
    db.session.delete(param)
    db.session.commit()
    return jsonify(success=True)


@rd.route('/param-master/reorder', methods=['POST'])
@login_required
def param_master_reorder():
    from models.npd import RDTestParameter
    data  = request.get_json()
    for item in (data.get('order') or []):
        RDTestParameter.query.filter_by(id=item['id']).update({'sort_order': item['sort_order']})
    db.session.commit()
    return jsonify(success=True)

# ══════════════════════════════════════════════════════════════
# PROJECT DEFAULT PARAMETERS (Pre-define per project)
# ══════════════════════════════════════════════════════════════

@rd.route('/project-params/<int:pid>')
@login_required
def get_project_params(pid):
    """Get saved default parameter values for a project"""
    from models.npd import NPDProject
    proj = NPDProject.query.get_or_404(pid)
    # Load from project notes/json field or a dedicated column
    import json
    try:
        data = json.loads(proj.rd_param_defaults or '{}')
        params      = data.get('params', data) if isinstance(data.get('params'), dict) else data
        sample_name = data.get('sample_name', '')
        remark      = data.get('remark', '')
    except Exception:
        params, sample_name, remark = {}, '', ''
    return jsonify(success=True, params=params, sample_name=sample_name, remark=remark)


@rd.route('/project-params/<int:pid>/save', methods=['POST'])
@login_required
def save_project_params(pid):
    """Save default parameter values for a project"""
    from models.npd import NPDProject
    import json
    proj = NPDProject.query.get_or_404(pid)
    data = request.get_json()
    save_data = {
        'params':      data.get('params', {}),
        'sample_name': data.get('sample_name', ''),
        'remark':      data.get('remark', '')
    }
    proj.rd_param_defaults = json.dumps(save_data)
    db.session.commit()
    return jsonify(success=True)


# ══════════════════════════════════════════════════════
# Sample Ready — R&D sidebar se bhi accessible
# (NPD wali functionality same, sirf active_page alag)
# ══════════════════════════════════════════════════════
@rd.route('/sample-ready')
@login_required
def sample_ready():
    from models.npd import NPDProject, NPDFormulation
    from models.employee import Employee

    q    = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)

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

    proj_ids = [p.id for p in projects.items]
    formulations = []
    if proj_ids:
        formulations = NPDFormulation.query.filter(
            NPDFormulation.project_id.in_(proj_ids)
        ).order_by(NPDFormulation.iteration).all()
    form_map = {}
    for f in formulations:
        form_map.setdefault(f.project_id, []).append(f)

    perm  = get_perm('rd')

    all_rd_ids = set()
    for p in projects.items:
        if p.assigned_rd_members:
            for x in str(p.assigned_rd_members).split(','):
                x = x.strip()
                if x and x.isdigit():
                    all_rd_ids.add(int(x))

    emp_name_map = {}
    if all_rd_ids:
        emps = Employee.query.filter(
            Employee.id.in_(all_rd_ids),
            Employee.is_deleted == False
        ).all()
        for e in emps:
            emp_name_map[e.id] = e.full_name

    rd_members_map = {}
    for p in projects.items:
        names = []
        if p.rd_user and p.rd_user.full_name:
            names.append(p.rd_user.full_name)
        if p.assigned_rd_members:
            for x in str(p.assigned_rd_members).split(','):
                x = x.strip()
                if x and x.isdigit():
                    n = emp_name_map.get(int(x))
                    if n and n not in names:
                        names.append(n)
        rd_members_map[p.id] = names

    rd_all = Employee.query.filter(
        Employee.is_deleted == False,
        Employee.department.ilike('%r&d%')
    ).order_by(Employee.first_name).all()
    rd_all_names = [e.full_name for e in rd_all if e.full_name] if rd_all else sorted(set(emp_name_map.values()))

    users = User.query.filter_by(is_active=True).order_by(User.full_name).all()

    return render_template('npd/sample_ready.html',
        active_page='rd_sample_ready',
        projects=projects,
        q=q,
        form_map=form_map,
        perm=perm,
        users=users,
        rd_members_map=rd_members_map,
        rd_all_names=rd_all_names,
        total=projects.total,
    )


# ══════════════════════════════════════════════════════
# Sample History — R&D sidebar se bhi accessible
# ══════════════════════════════════════════════════════
@rd.route('/sample-history')
@login_required
def sample_history():
    from models.npd import NPDProject, OfficeDispatchToken, OfficeDispatchItem
    from models.employee import Employee
    from datetime import timedelta

    page              = request.args.get('page', 1, type=int)
    q                 = request.args.get('q', '').strip()
    from_date         = request.args.get('from_date', '').strip()
    to_date           = request.args.get('to_date', '').strip()
    submitted_by_list = [x.strip() for x in request.args.getlist('submitted_by') if x.strip()]
    handover_to_list  = [x.strip() for x in request.args.getlist('handover_to')  if x.strip()]

    query = OfficeDispatchToken.query

    if from_date:
        try:
            query = query.filter(OfficeDispatchToken.dispatched_at >= datetime.strptime(from_date, '%Y-%m-%d'))
        except: pass
    if to_date:
        try:
            query = query.filter(OfficeDispatchToken.dispatched_at < datetime.strptime(to_date, '%Y-%m-%d') + timedelta(days=1))
        except: pass

    if q or submitted_by_list or handover_to_list:
        query = query.join(OfficeDispatchItem, OfficeDispatchItem.token_id == OfficeDispatchToken.id)
        if q:
            query = query.join(NPDProject, NPDProject.id == OfficeDispatchItem.project_id) \
                         .filter(NPDProject.product_name.ilike(f'%{q}%'))
        if submitted_by_list:
            query = query.filter(OfficeDispatchItem.submitted_by.in_(submitted_by_list))
        if handover_to_list:
            query = query.filter(OfficeDispatchItem.handover_to.in_(handover_to_list))
        query = query.distinct()

    tokens = query.order_by(OfficeDispatchToken.dispatched_at.desc()).paginate(page=page, per_page=25)

    rd_employees = Employee.query.filter(
        Employee.is_deleted == False,
        Employee.department.ilike('%r&d%')
    ).order_by(Employee.first_name).all()
    rd_names = [e.full_name for e in rd_employees if e.full_name]

    handover_emps = Employee.query.filter(
        Employee.is_deleted == False,
        db.or_(
            Employee.department == None,
            Employee.department == '',
            ~Employee.department.ilike('%r&d%')
        )
    ).order_by(Employee.first_name).all()
    handover_names = [e.full_name for e in handover_emps if e.full_name]

    return render_template('npd/sample_history.html',
        active_page='rd_sample_history',
        tokens=tokens,
        q=q, from_date=from_date, to_date=to_date,
        submitted_by_list=submitted_by_list,
        handover_to_list=handover_to_list,
        rd_names=rd_names,
        handover_names=handover_names,
    )


# ══════════════════════════════════════════════════════════════
# RD PROJECT LOG — project-wise activity (AJAX)
# ══════════════════════════════════════════════════════════════
@rd.route('/projects/<int:pid>/logs')
@login_required
def project_logs(pid):
    from models.npd import RDProjectLog, NPDProject, RDSubAssignment
    proj = NPDProject.query.get_or_404(pid)

    # Activity logs
    logs = RDProjectLog.query.filter_by(project_id=pid)                             .order_by(RDProjectLog.created_at.asc()).all()
    result = []
    for l in logs:
        result.append({
            'id'        : l.id,
            'event'     : l.event,
            'detail'    : l.detail or '',
            'user'      : l.user.full_name if l.user else 'System',
            'created_at': l.created_at.strftime('%d-%m-%Y %H:%M') if l.created_at else '',
        })

    # Per-executive sub-assignment summary
    subs = RDSubAssignment.query.filter_by(project_id=pid, is_active=True).all()
    members = []
    for s in subs:
        def fmt_sec(sec):
            if not sec: return '—'
            h = sec // 3600; m = (sec % 3600) // 60; sc = sec % 60
            return f'{h:02d}:{m:02d}:{sc:02d}'
        members.append({
            'name'        : s.executive.full_name if s.executive else '—',
            'variant_code': s.variant_code or '—',
            'status'      : s.status,
            'started_at'  : s.started_at.strftime('%d-%m-%Y %H:%M') if s.started_at else '—',
            'finished_at' : s.finished_at.strftime('%d-%m-%Y %H:%M') if s.finished_at else '—',
            'duration'    : fmt_sec(s.total_seconds),
        })

    return jsonify(
        success   = True,
        logs      = result,
        members   = members,
        proj_code = proj.code,
        proj_name = proj.product_name,
    )


# ══════════════════════════════════════════════════════════════
# RD SUB ASSIGNMENT — Executive Start / End (independent timer)
# ══════════════════════════════════════════════════════════════

@rd.route('/projects/<int:pid>/my-assignment')
@login_required
def my_assignment(pid):
    """Get current user's sub-assignment for this project"""
    from models.npd import RDSubAssignment
    sub = RDSubAssignment.query.filter_by(
        project_id=pid, user_id=current_user.id, is_active=True
    ).first()
    if not sub:
        return jsonify(success=False, error='No assignment found')
    return jsonify(
        success      = True,
        id           = sub.id,
        variant_code = sub.variant_code or '',
        notes        = sub.notes or '',
        status       = sub.status,
        started_at   = sub.started_at.strftime('%d-%m-%Y %I:%M %p') if sub.started_at else None,
        finished_at  = sub.finished_at.strftime('%d-%m-%Y %I:%M %p') if sub.finished_at else None,
        total_seconds= sub.total_seconds or 0,
    )


@rd.route('/projects/<int:pid>/sub-start', methods=['POST'])
@login_required
def sub_start(pid):
    """Executive starts their own timer — project status → in_progress"""
    from models.npd import RDSubAssignment, RDProjectLog, NPDProject, NPDActivityLog
    sub = RDSubAssignment.query.filter_by(
        project_id=pid, user_id=current_user.id, is_active=True
    ).first()
    if not sub:
        return jsonify(success=False, error='You are not assigned to this project')
    if sub.status == 'in_progress':
        return jsonify(success=False, error='Already started')

    sub.started_at = datetime.now()
    sub.status     = 'in_progress'

    # Project status → in_progress (if not already)
    proj = NPDProject.query.get(pid)
    if proj and proj.status != 'in_progress':
        proj.status     = 'in_progress'
        proj.started_at = proj.started_at or datetime.now()
        db.session.add(NPDActivityLog(
            project_id = pid,
            user_id    = current_user.id,
            action     = f"Project started by {current_user.full_name}",
            created_at = datetime.now(),
        ))

    db.session.add(RDProjectLog(
        project_id = pid,
        user_id    = current_user.id,
        event      = 'started',
        detail     = f"Started by {current_user.full_name}" + (f" | Variant: {sub.variant_code}" if sub.variant_code else ""),
        created_at = datetime.now(),
    ))
    db.session.commit()
    return jsonify(
        success    = True,
        started_at = sub.started_at.strftime('%d-%m-%Y %I:%M %p'),
        status     = sub.status,
    )


@rd.route('/projects/<int:pid>/sub-end', methods=['POST'])
@login_required
def sub_end(pid):
    """Executive ends their own timer — if all done, project → sample_ready"""
    from models.npd import RDSubAssignment, RDProjectLog, NPDProject, NPDActivityLog
    sub = RDSubAssignment.query.filter_by(
        project_id=pid, user_id=current_user.id, is_active=True
    ).first()
    if not sub:
        return jsonify(success=False, error='You are not assigned to this project')
    if sub.status != 'in_progress':
        return jsonify(success=False, error='Not started yet')

    sub.finished_at   = datetime.now()
    sub.status        = 'finished'
    if sub.started_at:
        sub.total_seconds = int((sub.finished_at - sub.started_at).total_seconds())

    dur_str = f"{sub.total_seconds//3600:02d}:{(sub.total_seconds%3600)//60:02d}:{sub.total_seconds%60:02d}"
    db.session.add(RDProjectLog(
        project_id = pid,
        user_id    = current_user.id,
        event      = 'finished',
        detail     = f"Finished by {current_user.full_name}" + (f" | Variant: {sub.variant_code}" if sub.variant_code else "") + f" | Duration: {dur_str}",
        created_at = datetime.now(),
    ))

    # Check if ALL active sub-assignments are finished
    db.session.flush()
    all_subs = RDSubAssignment.query.filter_by(project_id=pid, is_active=True).all()
    all_done = all(s.status == 'finished' for s in all_subs)

    proj = NPDProject.query.get(pid)
    if proj:
        if all_done:
            # All executives done → project sample_ready
            proj.status      = 'sample_ready'
            proj.finished_at = datetime.now()
            if proj.started_at:
                proj.total_duration_seconds = int((proj.finished_at - proj.started_at).total_seconds())
            db.session.add(NPDActivityLog(
                project_id = pid,
                user_id    = current_user.id,
                action     = f"Project completed — all R&D work done. Status → Sample Ready",
                created_at = datetime.now(),
            ))
            db.session.add(RDProjectLog(
                project_id = pid,
                user_id    = current_user.id,
                event      = 'sample_ready',
                detail     = f"All executives finished. Project → Sample Ready",
                created_at = datetime.now(),
            ))
        else:
            # Some still working — log individual completion
            db.session.add(NPDActivityLog(
                project_id = pid,
                user_id    = current_user.id,
                action     = f"{current_user.full_name} finished work (Variant: {sub.variant_code or '—'}). Other members still working.",
                created_at = datetime.now(),
            ))

    db.session.commit()
    return jsonify(
        success       = True,
        finished_at   = sub.finished_at.strftime('%d-%m-%Y %I:%M %p'),
        status        = sub.status,
        total_seconds = sub.total_seconds,
        all_done      = all_done,
        proj_status   = proj.status if proj else '',
    )
