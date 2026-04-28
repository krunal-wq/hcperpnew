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


# ── Helper: get R&D department users only ──
def get_rd_users():
    """Return active Users whose linked Employee record belongs to the R&D
    (Research & Development) department — in any of its spelling variations
    (R&D, R & D, Research and Development, RND, etc.).
    Users without an Employee record, or whose Employee is in any other
    department, are excluded — even if they have the rd_executive /
    rd_manager / admin role."""
    from models.employee import Employee
    from models.rd_department import rd_department_filter, is_rd_department

    # SQL-level filter for efficiency — catches most variations
    rd_emps = Employee.query.filter(
        Employee.is_deleted == False,
        Employee.user_id.isnot(None),
        rd_department_filter(Employee),
    ).order_by(Employee.first_name).all()

    # Python-side strict check — SQL patterns can be loose (e.g. 'rd' might
    # match some edge cases), so we re-validate each row with the exact
    # normalizer logic
    rd_users = []
    seen = set()
    for emp in rd_emps:
        if not is_rd_department(emp.department):
            continue
        u = User.query.get(emp.user_id)
        if u and u.is_active and u.id not in seen:
            u._display_role = emp.designation or 'R&D Executive'
            rd_users.append(u)
            seen.add(u.id)

    rd_users.sort(key=lambda x: (x.full_name or '').lower())
    return rd_users


# ── Helper: set of allowed R&D user ids (for POST validation) ──
def get_rd_user_ids():
    return {u.id for u in get_rd_users()}


# ── Helper: check if a user is an R&D Manager ──
# Manager = User.role explicitly set to 'rd_manager' or 'admin'.
#
# Earlier versions ke ek iteration me designation-based fallback bhi
# tha ('Manager'/'Head' word in employee.designation), magar wo false
# positives deta tha (jaise koi user role='user' rakhta tha but
# designation 'Manager' hone se accidentally manager treat ho jata tha).
# Industry-standard explicit role check hi rakha hai — jis-jis ko R&D
# Manager banana hai, unka User.role MySQL me 'rd_manager' set karna
# zaruri hai (ek bar ka SQL kaam, deterministic).
def is_rd_manager_user(user=None):
    """True if `user` (default: current_user) should see ALL R&D projects.

    Manager = User.role in ('rd_manager', 'admin'). No magic guessing
    from designation — explicit role assignment only.
    """
    u = user or current_user
    if not u or not getattr(u, 'is_authenticated', False):
        return False
    return getattr(u, 'role', None) in ('rd_manager', 'admin')


# ══════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════

# ─────────────────────────────────────────────────────────────────────
# Project Status Aggregator — central helper
# ─────────────────────────────────────────────────────────────────────
# Spec (multi-user assignment):
#
#   1. Sample Inprocess  : kisi bhi 1 user ne start kiya (and not all done)
#   2. Sample Ready      : SARE assigned users finish kar chuke
#   3. Sent to Office    : SARE finished rows ka status 'sent_to_office'
#   4. Approved By Office: SARE office_dispatch_items 'approved'
#   5. Rejected By Office: KOI bhi 1 office_dispatch_item 'rejected'
#
# Partial completion ke liye status forward NAHI badhta — strict aggregate.
#
# Terminal manual states (cancelled, on_hold, finish) — agar user ne
# manually set kiya, recompute touch nahi karta. Sirf workflow-driven
# status transitions handle karta hai.
def _recompute_project_status(pid, *, commit=False):
    """
    Re-derive `npd_project.status` from the underlying RDSubAssignment +
    OfficeDispatchItem state. Idempotent — safe to call multiple times.

    Returns the new status string (whatever was set, even if unchanged).
    """
    from models.npd import (NPDProject, RDSubAssignment,
                             OfficeDispatchItem, RDProjectLog)

    # Manually-set terminal states — never overwrite
    MANUAL_TERMINAL = {'cancelled', 'finish', 'finished', 'on_hold',
                       'sample_approved', 'sample_rejected',
                       'sent_to_client'}

    proj = NPDProject.query.get(pid)
    if not proj:
        return None
    if proj.status in MANUAL_TERMINAL:
        return proj.status

    subs = RDSubAssignment.query.filter_by(
        project_id=pid, is_active=True
    ).all()

    # Edge case — sub-assignments may have been deactivated by a reject
    # flow. In that case, derive status purely from office dispatch items
    # if any exist for this project.
    if not subs:
        items = OfficeDispatchItem.query.filter_by(project_id=pid).all()
        if items:
            statuses = [(i.approval_status or 'pending').lower() for i in items]
            if any(st == 'rejected' for st in statuses):
                _new = 'rejected_by_office'
            elif all(st == 'approved' for st in statuses):
                _new = 'approved_by_office'
            else:
                _new = 'sent_to_office'
            if _new != proj.status:
                proj.status = _new
        return proj.status   # don't infer further from sub-state

    sub_statuses = [(s.status or 'not_started').lower() for s in subs]

    # ── Aggregate decision tree ──
    new_status = None

    # Stage 4/5: ALL subs sent_to_office → check office dispatch items
    if all(st == 'sent_to_office' for st in sub_statuses):
        items = OfficeDispatchItem.query.filter_by(project_id=pid).all()
        if items:
            statuses = [(i.approval_status or 'pending').lower() for i in items]
            if any(st == 'rejected' for st in statuses):
                # Spec: ANY rejected → project rejected by office
                new_status = 'rejected_by_office'
            elif all(st == 'approved' for st in statuses):
                # Spec: ALL approved → project approved by office
                new_status = 'approved_by_office'
            else:
                # Some pending → still in office review queue
                new_status = 'sent_to_office'
        else:
            new_status = 'sent_to_office'

    # Stage 2/3: ALL finished or finished+sent_to_office mix → sample_ready
    # (Mixed = waiting for remaining members to dispatch — don't progress
    # to sent_to_office until ALL members have dispatched.)
    elif all(st in ('finished', 'sent_to_office') for st in sub_statuses):
        new_status = 'sample_ready'

    # Stage 1: ANY sub started/finished/sent → sample_inprocess
    elif any(st in ('in_progress', 'finished', 'sent_to_office')
             for st in sub_statuses):
        new_status = 'sample_inprocess'

    # Stage 0: All not_started
    else:
        new_status = 'not_started'

    if new_status and new_status != proj.status:
        old_status = proj.status
        proj.status = new_status
        if new_status == 'sample_ready' and not proj.finished_at:
            proj.finished_at = datetime.now()
            if proj.started_at:
                proj.total_duration_seconds = int(
                    (proj.finished_at - proj.started_at).total_seconds()
                )
        try:
            db.session.add(RDProjectLog(
                project_id = pid,
                user_id    = current_user.id if current_user.is_authenticated else None,
                event      = new_status,
                detail     = f"Auto: {old_status or 'none'} → {new_status} (aggregate of {len(subs)} R&D members)",
                created_at = datetime.now(),
            ))
        except Exception:
            pass

    if commit:
        db.session.commit()

    return proj.status


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
    is_rd_manager = is_rd_manager_user()
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

    # ─────────────────────────────────────────────────────────
    # Rejected Samples — visible to R&D Manager / Admin only.
    # Shows recently rejected OfficeDispatchItem rows with project
    # name, sample code, and rejection reason.
    # ─────────────────────────────────────────────────────────
    rejected_samples = []
    if is_rd_manager:
        from models.npd import OfficeDispatchItem
        q = OfficeDispatchItem.query.filter_by(approval_status='rejected') \
            .order_by(OfficeDispatchItem.actioned_at.desc()) \
            .limit(25).all()

        for it in q:
            proj = it.project
            rejected_samples.append({
                'item_id'     : it.id,
                'project_id'  : proj.id if proj else None,
                'project_no'  : (proj.code if proj else '—'),
                'project_name': (proj.product_name if proj else '—'),
                'client_name' : (proj.client_name if proj and proj.client_name else '—'),
                'sample_code' : it.sample_code or '—',
                'reason'      : it.reject_reason or '—',
                'actioned_by' : (it.actioner.full_name if it.actioner else '—'),
                'actioned_at' : (it.actioned_at.strftime('%d %b %Y, %I:%M %p')
                                 if it.actioned_at else '—'),
            })

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
        is_rd_manager=is_rd_manager,
        rejected_samples=rejected_samples,
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
    is_rd_manager = is_rd_manager_user()

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

    # ─────────────────────────────────────────────────────────
    # NON-MANAGER VISIBILITY
    # ─────────────────────────────────────────────────────────
    # Admin / R&D Manager → sees everything.
    # Everyone else → sees only projects where THEY are an assignee,
    # checked across ALL assignment systems we currently use:
    #   1. RDSubAssignment row referencing the user (multi-user system)
    #   2. Legacy single-user fields: assigned_rd / assigned_sc / npd_poc
    #   3. Legacy comma-separated tokens in assigned_rd_members /
    #      assigned_members (both u_<id> and pure-numeric emp-id forms)
    #
    # Previously this filter only ran on `closed`, and the template
    # filtered `allotted` using just `p.rd_user.id` — which missed
    # users assigned ONLY via RDSubAssignment (the modern path).
    # That's why R&D executives reported "I was assigned but I don't
    # see the project". Now we filter allotted + closed at the route
    # so the template sees a pre-filtered list and tab counts are
    # also correct.
    # ─────────────────────────────────────────────────────────
    if not is_rd_manager:
        uid = current_user.id

        # 1. RDSubAssignment lookup — single query covers both lists.
        relevant_pids = [p.id for p in (allotted + closed)]
        my_sub_pids = set()
        if relevant_pids:
            my_sub_pids = {
                s.project_id for s in RDSubAssignment.query.filter(
                    RDSubAssignment.user_id == uid,
                    RDSubAssignment.project_id.in_(relevant_pids),
                ).all()
            }

        # 2. Resolve current user's Employee.id for legacy numeric tokens.
        my_emp_id = None
        try:
            from models.employee import Employee as _EmpForCheck
            _emp = _EmpForCheck.query.filter_by(
                user_id=uid, is_deleted=False
            ).first()
            my_emp_id = _emp.id if _emp else None
        except Exception:
            my_emp_id = None

        def _user_in_member_str(member_str, user_id):
            if not member_str:
                return False
            for token in str(member_str).split(','):
                token = token.strip()
                if not token:
                    continue
                if token.startswith('u_'):
                    try:
                        if int(token[2:]) == user_id:
                            return True
                    except ValueError:
                        pass
            return False

        def _emp_id_in_member_str(member_str, emp_id):
            if not member_str or not emp_id:
                return False
            for token in str(member_str).split(','):
                token = token.strip()
                if token.isdigit() and int(token) == emp_id:
                    return True
            return False

        def _user_is_assigned(p):
            # Legacy single-user fields
            if p.assigned_rd == uid: return True
            if p.assigned_sc == uid: return True
            if p.npd_poc     == uid: return True
            # Modern multi-user system
            if p.id in my_sub_pids: return True
            # Legacy comma-separated token fields
            if _user_in_member_str(p.assigned_rd_members, uid): return True
            if _user_in_member_str(p.assigned_members,   uid):  return True
            if _emp_id_in_member_str(p.assigned_rd_members, my_emp_id): return True
            if _emp_id_in_member_str(p.assigned_members,   my_emp_id):  return True
            return False

        allotted = [p for p in allotted if _user_is_assigned(p)]
        closed   = [p for p in closed   if _user_is_assigned(p)]

    rd_sub = {
        'unalloted_npd': get_sub_perm('rd', 'unalloted_npd'),
        'alloted_npd':   get_sub_perm('rd', 'alloted_npd'),
        'closed_npd':    get_sub_perm('rd', 'closed_npd'),
        'assign':        get_sub_perm('rd', 'assign'),
    }
    # ── Build member list per project from RDSubAssignment (source of truth) ──
    # project_members = { project_id: [ {id, name, variant_code, status}, ... ] }
    from models.employee import Employee as _EmpM
    project_members = {}
    all_subs = RDSubAssignment.query.filter(
        RDSubAssignment.project_id.in_([p.id for p in projects]) if projects else False,
        RDSubAssignment.is_active == True,
    ).all() if projects else []

    _sub_user_ids = {s.user_id for s in all_subs if s.user_id}
    _sub_user_map = {u.id: u for u in User.query.filter(User.id.in_(_sub_user_ids)).all()} if _sub_user_ids else {}

    for s in all_subs:
        u = _sub_user_map.get(s.user_id)
        if not u:
            continue
        project_members.setdefault(s.project_id, []).append({
            'id'          : u.id,
            'name'        : u.full_name or u.username or '—',
            'variant_code': s.variant_code or '',
            'status'      : s.status or 'not_started',
        })

    # Sort each project's member list alphabetically by name
    for pid_key in project_members:
        project_members[pid_key].sort(key=lambda m: (m['name'] or '').lower())

    # ── Legacy emp_id → name map (kept for backward-compat with older rows) ──
    _legacy_emp_ids = set()
    _legacy_user_ids = set()
    for p in projects:
        if p.assigned_rd_members:
            for token in str(p.assigned_rd_members).split(','):
                token = token.strip()
                if token.startswith('u_'):
                    try: _legacy_user_ids.add(int(token[2:]))
                    except: pass
                elif token.isdigit():
                    _legacy_emp_ids.add(int(token))
    rd_emp_names = {}
    if _legacy_emp_ids:
        for e in _EmpM.query.filter(_EmpM.id.in_(_legacy_emp_ids), _EmpM.is_deleted==False).all():
            rd_emp_names[e.id] = e.full_name
    if _legacy_user_ids:
        for u in User.query.filter(User.id.in_(_legacy_user_ids)).all():
            rd_emp_names[f'u_{u.id}'] = u.full_name

    return render_template('rd/projects.html',
        active_page='rd_projects',
        projects=projects, q=q, cat=cat, status=status,
        users=users, unallotted=unallotted, allotted=allotted, closed=closed,
        is_rd_manager=is_rd_manager, perm=get_perm('rd'),
        rd_sub=rd_sub,
        rd_emp_names=rd_emp_names,
        project_members=project_members,
    )


# ══════════════════════════════════════════════════════════════
# R&D TRIALS (Formulations)
# ══════════════════════════════════════════════════════════════

@rd.route('/trials')
@login_required
def trials():
    from models.npd import NPDProject, RDSubAssignment, RDTrialLog
    q          = request.args.get('q', '').strip()
    project_id = request.args.get('project_id', type=int)

    is_admin = is_rd_manager_user()

    # ─────────────────────────────────────────────────────────
    #  Resolve which project IDs THIS user is assigned to.
    #  Used to scope the "My Projects" left panel — without this,
    #  an executive who's assigned via RDSubAssignment (modern
    #  multi-user) but not the legacy `assigned_rd` field sees
    #  nothing on this page even though they have samples to log
    #  trials against.
    # ─────────────────────────────────────────────────────────
    if is_admin:
        my_assigned_pids = None   # sentinel: see all
    else:
        legacy_pids = {
            p.id for p in NPDProject.query.filter(
                NPDProject.is_deleted == False,
                NPDProject.assigned_rd == current_user.id,
            ).all()
        }
        sub_pids = {
            s.project_id for s in RDSubAssignment.query.filter_by(
                user_id=current_user.id
            ).all()
        }
        my_assigned_pids = legacy_pids | sub_pids

    # ─────────────────────────────────────────────────────────
    #  Trial query — uses the new dedicated rd_trial_logs table.
    #  NPDFormulation is no longer touched here; that table belongs
    #  to the legacy NPD sample-dispatch / client-review workflow.
    # ─────────────────────────────────────────────────────────
    query = RDTrialLog.query
    if project_id:
        query = query.filter(RDTrialLog.project_id == project_id)
    if q:
        # Search across sample code, parameters JSON, and observations.
        query = query.filter(db.or_(
            RDTrialLog.sample_code.ilike(f'%{q}%'),
            RDTrialLog.parameters_json.ilike(f'%{q}%'),
            RDTrialLog.observations.ilike(f'%{q}%'),
        ))

    # Executive sees only their own trials. Admin/manager sees all.
    # We don't filter by project here — the project-level filter is
    # the user's left-panel selection driving project_id above.
    if not is_admin:
        query = query.filter(RDTrialLog.rd_user_id == current_user.id)

    trials = query.order_by(RDTrialLog.created_at.desc()).all()
    users  = get_rd_users()

    # ── All active projects for modal dropdown ──
    all_projects = NPDProject.query.filter(
        NPDProject.is_deleted == False,
        NPDProject.status.notin_(['complete', 'cancelled'])
    ).order_by(NPDProject.created_at.desc()).all()

    # ── project_filter for banner (when coming from projects page) ──
    project_filter = NPDProject.query.get(project_id) if project_id else None

    # ── Grid 1: my_projects (left panel) ──
    active_q = NPDProject.query.filter(
        NPDProject.is_deleted == False,
        NPDProject.status.notin_(['complete', 'cancelled'])
    )
    if is_admin:
        my_projects = active_q.order_by(NPDProject.created_at.desc()).all()
    else:
        if my_assigned_pids:
            my_projects = active_q.filter(
                NPDProject.id.in_(list(my_assigned_pids))
            ).order_by(NPDProject.created_at.desc()).all()
        else:
            my_projects = []

    # ── test_params for parameter table in modal ──
    try:
        from models.npd import RDTestParameter
        test_params = RDTestParameter.query.filter_by(is_active=True)\
                          .order_by(RDTestParameter.sort_order).all()
    except Exception:
        test_params = []

    # ── User's sample codes per project ──
    # Each user-on-project assignment in RDSubAssignment may carry
    # one or more comma-separated sample codes assigned by the
    # manager (e.g. "SMP001,SMP002"). The trial-log modal uses these
    # to populate the Sample Code dropdown.
    user_sample_codes = {}
    if not is_admin:
        my_subs = RDSubAssignment.query.filter_by(
            user_id=current_user.id, is_active=True
        ).all()
        for s in my_subs:
            codes = [c.strip() for c in (s.sample_code or '').split(',') if c.strip()]
            if codes:
                existing = user_sample_codes.get(s.project_id, [])
                merged = list(dict.fromkeys(existing + codes))
                user_sample_codes[s.project_id] = merged

    return render_template('rd/trials.html',
        active_page='rd_trials',
        trials=trials, q=q, result='',
        users=users, all_projects=all_projects,
        my_projects=my_projects,
        project_filter=project_filter,
        test_params=test_params,
        user_sample_codes=user_sample_codes,
    )


@rd.route('/trials/add', methods=['POST'])
@login_required
def add_trial():
    """Log a new R&D trial against a project.

    Writes to the new `rd_trial_logs` table (RDTrialLog model),
    not the legacy npd_formulations table. The form fields the
    template sends are:
      - project_id          (required) — npd_projects.id
      - formulation_name    — sample code from the manager's
                              RDSubAssignment.sample_code list
      - exec_id             — rd_user_id (defaults to current user
                              when the modal is opened from a project
                              card; admin can override)
      - parameters          — JSON string of [{parameter, result}, ...]
      - observations        — CKEditor HTML notes
    """
    from models.npd import NPDProject, NPDActivityLog, RDTrialLog
    project_id = request.form.get('project_id')
    if not project_id:
        flash('Project is required', 'error')
        return redirect(url_for('rd.trials'))

    proj = NPDProject.query.get_or_404(int(project_id))

    # Resolve the rd_user_id and take a name snapshot.
    # `exec_id` is a hidden form field set client-side to the
    # logged-in user's id when the modal opens from a project card,
    # OR the value chosen from the dropdown when opened from the
    # global "+ Log Trial" button. Bad/missing values fall back to
    # the current user since whoever clicked Log Trial logged in.
    raw_exec_id = request.form.get('exec_id')
    rd_user_id  = None
    rd_user_name = None
    if raw_exec_id:
        try:
            rd_user_id = int(raw_exec_id)
        except (TypeError, ValueError):
            rd_user_id = None
    if not rd_user_id:
        rd_user_id = current_user.id

    _u = User.query.get(rd_user_id)
    rd_user_name = _u.full_name if _u else current_user.full_name

    sample_code = (request.form.get('formulation_name') or '').strip()
    if not sample_code:
        flash('Sample code is required', 'error')
        return redirect(url_for('rd.trials'))

    log = RDTrialLog(
        project_id      = proj.id,
        sample_code     = sample_code,
        rd_user_id      = rd_user_id,
        rd_user_name    = rd_user_name,
        parameters_json = request.form.get('parameters', '') or None,
        observations    = request.form.get('observations', '') or None,
        created_at      = datetime.now(),
        updated_at      = datetime.now(),
    )
    db.session.add(log)

    db.session.add(NPDActivityLog(
        project_id = proj.id,
        user_id    = current_user.id,
        action     = f"R&D Trial logged: {sample_code} by {rd_user_name or current_user.full_name}",
        created_at = datetime.now(),
    ))
    db.session.commit()
    flash(f'Trial logged successfully for sample {sample_code}', 'success')
    return redirect(url_for('rd.trials'))


@rd.route('/trials/<int:tid>/result', methods=['POST'])
@login_required
def update_trial_result(tid):
    """Legacy endpoint — no longer applicable to RDTrialLog rows.

    Trial pass/fail used to be tracked on `npd_formulations.client_status`,
    but the new dedicated `rd_trial_logs` table doesn't carry workflow
    state — it's a record of what was tested, nothing more. Keep the
    route alive so any old client code that hits it gets a meaningful
    response instead of a 404 / 500.
    """
    return jsonify(success=True,
                   note='Trial result tracking is no longer maintained '
                        'on this endpoint.')


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
            NPDFormulation.client_status == 'rejected'
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
            NPDFormulation.client_status == 'rejected'
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
    """Update an existing R&D trial entry.

    Operates on the new `rd_trial_logs` table. Visibility check —
    non-admin users can only edit their own trials, never someone
    else's; this matches the listing where they only see their own.
    """
    from models.npd import NPDActivityLog, RDTrialLog
    trial = RDTrialLog.query.get_or_404(tid)

    # Non-admin: can only edit own trials
    if not is_rd_manager_user() and trial.rd_user_id != current_user.id:
        flash('You can only edit your own trial entries', 'error')
        return redirect(url_for('rd.trials'))

    if request.method == 'POST':
        sample_code = (request.form.get('formulation_name') or '').strip()
        if sample_code:
            trial.sample_code = sample_code
        params = request.form.get('parameters')
        if params is not None:
            trial.parameters_json = params or None
        observations = request.form.get('observations')
        if observations is not None:
            trial.observations = observations or None

        # Allow the executive to be reassigned (admin / manager only —
        # non-admin can't reach this branch since we'd have rejected
        # them above on rd_user_id mismatch).
        exec_id = request.form.get('exec_id')
        if exec_id:
            try:
                new_uid = int(exec_id)
                trial.rd_user_id = new_uid
                _u = User.query.get(new_uid)
                trial.rd_user_name = _u.full_name if _u else None
            except (TypeError, ValueError):
                pass

        proj_id = request.form.get('project_id')
        if proj_id:
            try:
                trial.project_id = int(proj_id)
            except (TypeError, ValueError):
                pass

        trial.updated_at = datetime.now()

        db.session.add(NPDActivityLog(
            project_id = trial.project_id,
            user_id    = current_user.id,
            action     = f"R&D Trial updated: {trial.sample_code} by {current_user.full_name}",
            created_at = datetime.now(),
        ))
        db.session.commit()
        flash(f'Trial {trial.sample_code} updated', 'success')
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

    # Guard: only R&D Manager / Admin can (re)assign projects.
    # Non-manager users may have stumbled onto this endpoint via dev
    # tools — block them at the server side regardless of UI hiding.
    if not is_rd_manager_user():
        return jsonify(success=False,
            error='Only R&D Manager can assign or reassign projects.'), 403

    proj    = NPDProject.query.get_or_404(pid)
    rd_id   = request.form.get('rd_id') or None
    sc_id   = request.form.get('sc_id') or None

    # Guard: only users in the R&D department may be assigned
    if rd_id:
        try:
            if int(rd_id) not in get_rd_user_ids():
                return jsonify(success=False,
                    error='Selected user is not in the R&D department.'), 400
        except (TypeError, ValueError):
            return jsonify(success=False, error='Invalid R&D user id.'), 400

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

    # Guard: only R&D Manager / Admin can (re)assign projects.
    if not is_rd_manager_user():
        return jsonify(success=False,
            error='Only R&D Manager can assign or reassign projects.'), 403

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
    assigned_user_ids_int = set()   # raw int ids — for deactivation diff
    allowed_rd_ids = get_rd_user_ids()
    rejected = []

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

        # Guard: only R&D department users may be assigned
        if user_obj.id not in allowed_rd_ids:
            rejected.append(user_obj.full_name or user_obj.username)
            continue

        names.append(user_obj.full_name)
        assigned_user_ids.append(f'u_{user_obj.id}')
        assigned_user_ids_int.add(user_obj.id)

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

    if not assigned_user_ids:
        msg = 'No valid R&D department users selected.'
        if rejected:
            msg += ' Rejected (not in R&D): ' + ', '.join(rejected)
        return jsonify(success=False, error=msg), 400

    # Update project level assigned_rd_members for backward compat
    proj.assigned_rd         = User.query.get(int(assigned_user_ids[0][2:])).id if assigned_user_ids else proj.assigned_rd
    proj.assigned_rd_members = ','.join(assigned_user_ids)
    proj.updated_by          = current_user.id

    # ─────────────────────────────────────────────────────────────
    # Deactivate stale assignments — un-checked users hatao.
    # Bug fix: pehle code sirf upsert karta tha; un-checked users
    # is_active=True hi pade rehte the aur UI me dikhte rehte the.
    # Ab har un-active assignment ko soft-delete (is_active=False)
    # kar dete hain — audit trail preserve hota hai, UI clean.
    # ─────────────────────────────────────────────────────────────
    removed_names = []
    stale_subs = RDSubAssignment.query.filter(
        RDSubAssignment.project_id == proj.id,
        RDSubAssignment.is_active  == True,
        ~RDSubAssignment.user_id.in_(assigned_user_ids_int),
    ).all()
    for s in stale_subs:
        s.is_active = False
        removed_user = User.query.get(s.user_id)
        if removed_user:
            removed_names.append(removed_user.full_name or removed_user.username)
    # ─────────────────────────────────────────────────────────────

    db.session.add(NPDActivityLog(
        project_id = proj.id,
        user_id    = current_user.id,
        action     = (
            f"R&D team assigned: {', '.join(names)}"
            + (f" — Removed: {', '.join(removed_names)}" if removed_names else "")
            + f" — by {current_user.full_name}"
        ),
        created_at = datetime.now(),
    ))
    # RD Project Log
    from models.npd import RDProjectLog
    db.session.add(RDProjectLog(
        project_id = proj.id,
        user_id    = current_user.id,
        event      = 'assigned',
        detail     = (
            f"Members: {', '.join(names)}"
            + (f" — Removed: {', '.join(removed_names)}" if removed_names else "")
            + f" — by {current_user.full_name}"
        ),
        created_at = datetime.now(),
    ))
    db.session.commit()

    return jsonify(
        success      = True,
        proj_id      = pid,
        rd_names     = names,
        rejected     = rejected,
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

    # ─────────────────────────────────────────────────────────────
    # Role-based log visibility
    #   • rd_manager / admin  → sare users ke logs
    #   • Other roles         → sirf apne logs (user_id = current_user.id)
    #                            + 'System' events (user_id = NULL) — taaki
    #                            milestone changes / auto-events bhi dikhe
    # ─────────────────────────────────────────────────────────────
    log_q = RDProjectLog.query.filter_by(project_id=pid)
    if not is_rd_manager_user():
        log_q = log_q.filter(
            db.or_(
                RDProjectLog.user_id == current_user.id,
                RDProjectLog.user_id.is_(None),
            )
        )
    logs = log_q.order_by(RDProjectLog.created_at.asc()).all()
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
    # Same role rule — non-managers ko sirf apni summary row dikhao
    sub_q = RDSubAssignment.query.filter_by(project_id=pid, is_active=True)
    if not is_rd_manager_user():
        sub_q = sub_q.filter(RDSubAssignment.user_id == current_user.id)
    subs = sub_q.all()
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
        success         = True,
        logs            = result,
        members         = members,
        proj_code       = proj.code,
        proj_name       = proj.product_name,
        is_manager_view = is_rd_manager_user(),
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
    """Executive starts their own timer — project status auto-derived."""
    from models.npd import RDSubAssignment, RDProjectLog, NPDProject
    sub = RDSubAssignment.query.filter_by(
        project_id=pid, user_id=current_user.id, is_active=True
    ).first()
    if not sub:
        return jsonify(success=False, error='You are not assigned to this project')
    if sub.status == 'in_progress':
        return jsonify(success=False, error='Already started')

    sub.started_at = datetime.now()
    sub.status     = 'in_progress'

    # Stamp project.started_at on first start (any user)
    proj = NPDProject.query.get(pid)
    if proj and not proj.started_at:
        proj.started_at = datetime.now()

    db.session.add(RDProjectLog(
        project_id = pid,
        user_id    = current_user.id,
        event      = 'started',
        detail     = f"Started by {current_user.full_name}" + (f" | Variant: {sub.variant_code}" if sub.variant_code else ""),
        created_at = datetime.now(),
    ))

    # Flush so recompute sees the new sub state, then derive project status
    db.session.flush()
    _recompute_project_status(pid)

    db.session.commit()
    return jsonify(
        success    = True,
        started_at = sub.started_at.strftime('%d-%m-%Y %I:%M %p'),
        status     = sub.status,
    )


@rd.route('/projects/<int:pid>/sub-end', methods=['POST'])
@login_required
def sub_end(pid):
    """Executive ends their own timer — project status auto-derived."""
    from models.npd import RDSubAssignment, RDProjectLog, NPDProject
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

    # Flush so recompute sees new state, then derive aggregate project status
    db.session.flush()
    _recompute_project_status(pid)

    db.session.commit()

    # ── Compute response payload ──
    # Frontend uses `success` to call location.reload() — anything that
    # raises a NameError here returns 500 and the page never refreshes,
    # which is exactly the bug users were hitting: clicking END seemed
    # to do nothing until they manually reloaded. Previously `all_done`
    # and `proj` were referenced without being defined; resolve them
    # explicitly here so the response is always well-formed.
    proj = NPDProject.query.get(pid)
    # all_done = every active sub-assignment for this project is finished
    open_subs = RDSubAssignment.query.filter(
        RDSubAssignment.project_id == pid,
        RDSubAssignment.is_active == True,
        RDSubAssignment.status != 'finished',
    ).count()
    all_done = (open_subs == 0)

    return jsonify(
        success       = True,
        finished_at   = sub.finished_at.strftime('%d-%m-%Y %I:%M %p'),
        status        = sub.status,
        total_seconds = sub.total_seconds,
        all_done      = all_done,
        proj_status   = proj.status if proj else '',
    )
