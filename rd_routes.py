"""
rd_routes.py — R&D NPD Management System
Blueprint: rd at /rd
"""

from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime, date
from models import db, User

rd = Blueprint('rd', __name__, url_prefix='/rd')


# ── Helper: get all RD users (employees assigned to R&D) ──
def get_rd_users():
    """Return only R&D department users (rd_executive + rd_manager)"""
    return User.query.filter(
        User.is_active == True,
        User.role.in_(['rd_executive', 'rd_manager', 'admin'])
    ).order_by(User.full_name).all()


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

    return render_template('rd/dashboard.html',
        active_page='rd_dashboard',
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

    unallotted = [p for p in projects if not p.assigned_rd or p.assigned_rd not in rd_exec_ids]
    allotted   = [p for p in projects if p.assigned_rd and p.assigned_rd in rd_exec_ids]

    return render_template('rd/projects.html',
        active_page='rd_projects',
        projects=projects, q=q, cat=cat, status=status,
        users=users, unallotted=unallotted, allotted=allotted,
        is_rd_manager=is_rd_manager,
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
    from models.npd import NPDProject
    projects = NPDProject.query.filter(
        NPDProject.is_deleted == False,
        NPDProject.status.notin_(['complete', 'cancelled'])
    ).order_by(NPDProject.created_at.desc()).all()

    return render_template('rd/discussion.html',
        active_page='rd_discussion',
        projects=projects,
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
    """Assign multiple R&D persons — saves primary as assigned_rd, others in notes"""
    from models.npd import NPDProject, NPDActivityLog
    proj = NPDProject.query.get_or_404(pid)

    rd_ids = request.form.getlist('rd_ids')  # list of user ids
    sc_id  = request.form.get('sc_id') or None

    if not rd_ids:
        return jsonify(success=False, error='Select at least one R&D person')

    # Primary R&D = first selected
    proj.assigned_rd = int(rd_ids[0])
    if sc_id:
        proj.assigned_sc = int(sc_id)
    proj.updated_by = current_user.id

    names = []
    for uid in rd_ids:
        u = User.query.get(int(uid))
        if u: names.append(u.full_name)

    db.session.add(NPDActivityLog(
        project_id = proj.id,
        user_id    = current_user.id,
        action     = f"R&D team assigned: {', '.join(names)} — by {current_user.full_name}",
        created_at = datetime.now(),
    ))
    db.session.commit()

    # Return updated project info
    return jsonify(
        success    = True,
        proj_id    = pid,
        rd_names   = names,
        sc_name    = proj.sc_user.full_name if proj.sc_user else '—',
        status     = proj.status_label,
        status_color = proj.status_color,
        code       = proj.code,
        name       = proj.product_name,
        type       = proj.project_type,
        client     = proj.client_company or proj.client_name or '—',
        age        = proj.project_age,
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
