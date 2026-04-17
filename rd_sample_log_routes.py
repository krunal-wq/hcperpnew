"""
rd_sample_log_routes.py — R&D Sample Log Menu
============================================
Aggregated view of RDSubAssignment rows (sample logs) across ALL
projects the current user is allowed to see.

Access rules (matches the requirement sheet):

  1. Employee (role: 'user', 'employee')
       - Sees ONLY their own sample log rows
       - AND only on projects assigned to them

  2. Team Lead / NPD / R&D Executive (role: 'rd_executive', 'sales',
                                            'hr', 'lead', 'team_lead')
       - Sees ALL sample log rows for projects assigned to them
       - Cannot see projects not assigned to them

  3. NPD Manager / Admin / Manager / R&D Manager
       (role: 'admin', 'manager', 'npd_manager', 'rd_manager')
       - Full visibility across every project + every employee

Project assignment is derived from NPDProject fields:
  - assigned_rd            (single user id)
  - assigned_sc            (single user id)
  - npd_poc                (single user id)
  - created_by             (single user id)
  - assigned_members       (CSV of user ids)
  - assigned_rd_members    (CSV of user ids)
  - RDSubAssignment.user_id (user has a sub-assignment on the project)

Blueprint:  rd_sample_log  at  /rd/sample-log
"""

from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, jsonify
from flask_login import login_required, current_user
from sqlalchemy import or_

from models import db, User
from models.npd import NPDProject, RDSubAssignment
from permissions import get_perm


rd_sample_log_bp = Blueprint(
    'rd_sample_log',
    __name__,
    url_prefix='/rd/sample-log'
)


# ════════════════════════════════════════════════════════════════
#  Role buckets
# ════════════════════════════════════════════════════════════════

# Full visibility — all projects, all employees
FULL_ACCESS_ROLES = {'admin', 'manager', 'npd_manager', 'rd_manager'}

# Mid-tier — all rows on THEIR projects (Team Lead / NPD / R&D executive)
PROJECT_SCOPED_ROLES = {'rd_executive', 'sales', 'lead', 'team_lead', 'hr', 'npd'}

# Everyone else → employee bucket (own rows only, on own projects)


def _user_bucket(role: str) -> str:
    """Return one of: 'full' | 'project' | 'employee'."""
    r = (role or '').lower()
    if r in FULL_ACCESS_ROLES:
        return 'full'
    if r in PROJECT_SCOPED_ROLES:
        return 'project'
    return 'employee'


# ════════════════════════════════════════════════════════════════
#  Core helper — projects visible to a user
# ════════════════════════════════════════════════════════════════

def get_accessible_project_ids(user) -> list[int] | None:
    """
    Return a list of project IDs the given user may see.
    Returns None (meaning NO filter — see everything) for full-access roles.
    Returns [] if the user has no assignments (→ empty page).
    """
    if _user_bucket(user.role) == 'full':
        return None

    uid = user.id
    uid_str = str(uid)

    # Projects where the user is referenced anywhere
    projects = NPDProject.query.filter(
        NPDProject.is_deleted == False,
        or_(
            NPDProject.assigned_rd == uid,
            NPDProject.assigned_sc == uid,
            NPDProject.npd_poc == uid,
            NPDProject.created_by == uid,
            NPDProject.assigned_members.like(f'%{uid_str}%'),
            NPDProject.assigned_rd_members.like(f'%{uid_str}%'),
        )
    ).all()
    ids = {p.id for p in projects}

    # Also include any project where the user has an active sub-assignment
    sub_pids = db.session.query(RDSubAssignment.project_id).filter(
        RDSubAssignment.user_id == uid,
        RDSubAssignment.is_active == True
    ).distinct().all()
    ids.update(pid for (pid,) in sub_pids)

    return sorted(ids)


# ════════════════════════════════════════════════════════════════
#  MAIN LISTING PAGE
# ════════════════════════════════════════════════════════════════

@rd_sample_log_bp.route('/')
@login_required
def index():
    """
    Unified R&D Sample Log view.

    Query-string filters (all optional):
      ?project_id=<int>      limit to one project (must be in accessible list)
      ?status=<str>          not_started | in_progress | finished
      ?member_id=<int>       limit to one member (full-access roles only)
      ?from=YYYY-MM-DD       started_at >=
      ?to=YYYY-MM-DD         started_at <=
    """
    # ── Permission gate — the menu itself must be viewable ──
    perm = get_perm('rd_sample_log')
    if perm is None or (perm and not getattr(perm, 'can_view', True)):
        # Fallback — admins bypass, everyone else gets a polite 403 page
        if current_user.role != 'admin':
            return render_template(
                'errors/403.html',
                message='You do not have access to R&D Sample Log.'
            ), 403

    bucket = _user_bucket(current_user.role)
    accessible_pids = get_accessible_project_ids(current_user)

    # ── Build the sample-log query ──
    q = RDSubAssignment.query.filter(RDSubAssignment.is_active == True)

    # Project scoping
    if accessible_pids is not None:
        if not accessible_pids:
            # No projects assigned → force empty result
            q = q.filter(RDSubAssignment.id == -1)
        else:
            q = q.filter(RDSubAssignment.project_id.in_(accessible_pids))

    # Employee bucket → own rows only
    if bucket == 'employee':
        q = q.filter(RDSubAssignment.user_id == current_user.id)

    # ── Optional UI filters ──
    f_project = request.args.get('project_id', type=int)
    f_status  = (request.args.get('status') or '').strip()
    f_member  = request.args.get('member_id', type=int)
    f_from    = (request.args.get('from') or '').strip()
    f_to      = (request.args.get('to') or '').strip()

    if f_project:
        # Security: confirm project is in accessible list (if scoped)
        if accessible_pids is None or f_project in accessible_pids:
            q = q.filter(RDSubAssignment.project_id == f_project)
        else:
            q = q.filter(RDSubAssignment.id == -1)  # force empty

    if f_status in ('not_started', 'in_progress', 'finished'):
        q = q.filter(RDSubAssignment.status == f_status)

    # member filter — only full-access & project-scoped roles may filter
    # by other members.  Employees can only ever see themselves anyway.
    if f_member and bucket != 'employee':
        q = q.filter(RDSubAssignment.user_id == f_member)

    if f_from:
        try:
            dt_from = datetime.strptime(f_from, '%Y-%m-%d')
            q = q.filter(RDSubAssignment.started_at >= dt_from)
        except ValueError:
            pass

    if f_to:
        try:
            dt_to = datetime.strptime(f_to, '%Y-%m-%d') + timedelta(days=1)
            q = q.filter(RDSubAssignment.started_at < dt_to)
        except ValueError:
            pass

    # MySQL-safe null-last ordering: NULL rows sort to the bottom.
    # (.nullslast() is Postgres-only — MySQL rejects 'NULLS LAST' syntax.)
    logs = q.order_by(
        (RDSubAssignment.started_at.is_(None)).asc(),   # False(0) before True(1) → non-null first
        RDSubAssignment.started_at.desc(),
        RDSubAssignment.assigned_at.desc()
    ).all()

    # ── Dropdown data ──
    # Projects the user can filter by
    if accessible_pids is None:
        projects = NPDProject.query.filter_by(is_deleted=False)\
            .order_by(NPDProject.code).all()
    else:
        projects = NPDProject.query.filter(
            NPDProject.is_deleted == False,
            NPDProject.id.in_(accessible_pids) if accessible_pids else NPDProject.id == -1
        ).order_by(NPDProject.code).all()

    # Members the user can filter by
    if bucket == 'employee':
        members = [current_user]
    else:
        # Distinct users who appear in the visible log rows
        visible_user_ids = {l.user_id for l in logs if l.user_id}
        members = User.query.filter(User.id.in_(visible_user_ids))\
                            .order_by(User.full_name).all() if visible_user_ids else []

    # ── Summary counts (based on already-scoped query, minus UI filters) ──
    summary_q = RDSubAssignment.query.filter(RDSubAssignment.is_active == True)
    if accessible_pids is not None:
        if not accessible_pids:
            summary_q = summary_q.filter(RDSubAssignment.id == -1)
        else:
            summary_q = summary_q.filter(RDSubAssignment.project_id.in_(accessible_pids))
    if bucket == 'employee':
        summary_q = summary_q.filter(RDSubAssignment.user_id == current_user.id)

    all_scoped = summary_q.all()
    summary = {
        'total':       len(all_scoped),
        'in_progress': sum(1 for s in all_scoped if s.status == 'in_progress'),
        'finished':    sum(1 for s in all_scoped if s.status == 'finished'),
        'not_started': sum(1 for s in all_scoped if s.status == 'not_started'),
    }

    return render_template(
        'rd/sample_log.html',
        active_page='rd_sample_log',
        logs=logs,
        projects=projects,
        members=members,
        summary=summary,
        bucket=bucket,
        filters={
            'project_id': f_project or '',
            'status':     f_status or '',
            'member_id':  f_member or '',
            'from':       f_from,
            'to':         f_to,
        },
    )


# ════════════════════════════════════════════════════════════════
#  JSON endpoint — for AJAX refresh / mobile / integrations
# ════════════════════════════════════════════════════════════════

@rd_sample_log_bp.route('/api/list')
@login_required
def api_list():
    """Return the same filtered list as JSON."""
    bucket = _user_bucket(current_user.role)
    accessible_pids = get_accessible_project_ids(current_user)

    q = RDSubAssignment.query.filter(RDSubAssignment.is_active == True)

    if accessible_pids is not None:
        if not accessible_pids:
            return jsonify({'ok': True, 'count': 0, 'rows': [], 'bucket': bucket})
        q = q.filter(RDSubAssignment.project_id.in_(accessible_pids))

    if bucket == 'employee':
        q = q.filter(RDSubAssignment.user_id == current_user.id)

    logs = q.order_by(
        (RDSubAssignment.started_at.is_(None)).asc(),
        RDSubAssignment.started_at.desc()
    ).all()

    rows = []
    for s in logs:
        proj = s.project
        exec_user = s.executive
        rows.append({
            'id':            s.id,
            'project_id':    s.project_id,
            'project_code':  proj.code if proj else None,
            'product_name':  proj.product_name if proj else None,
            'member_id':     s.user_id,
            'member_name':   exec_user.full_name if exec_user else None,
            'variant_code':  s.variant_code,
            'started_at':    s.started_at.strftime('%d-%m-%Y %H:%M') if s.started_at else None,
            'finished_at':   s.finished_at.strftime('%d-%m-%Y %H:%M') if s.finished_at else None,
            'duration_sec':  s.total_seconds or 0,
            'status':        s.status,
        })

    return jsonify({
        'ok': True,
        'count': len(rows),
        'rows': rows,
        'bucket': bucket,
    })


# ════════════════════════════════════════════════════════════════
#  DIAGNOSTIC endpoint — helps debug "why count is X?" issues
#  Open in browser:  /rd/sample-log/api/debug
#  Shows exactly what the current user's scope and counts are.
# ════════════════════════════════════════════════════════════════

@rd_sample_log_bp.route('/api/debug')
@login_required
def api_debug():
    """Return diagnostic info for the current user. ADMIN ONLY."""
    # Gate: only admin / manager can hit this endpoint
    if current_user.role not in ('admin', 'manager'):
        return jsonify({'ok': False, 'error': 'Admin access required'}), 403

    bucket = _user_bucket(current_user.role)
    accessible_pids = get_accessible_project_ids(current_user)

    # All projects where the user is referenced somewhere
    from models.npd import NPDProject, RDSubAssignment
    uid = current_user.id
    uid_str = str(uid)

    projects_detail = []
    if accessible_pids is None:
        # Full access — just count total, don't list all
        total = NPDProject.query.filter_by(is_deleted=False).count()
        projects_detail = [{'note': f'Full access — all {total} projects visible'}]
    else:
        for pid in accessible_pids:
            p = NPDProject.query.get(pid)
            if not p:
                continue
            # Why does this user see this project?
            reasons = []
            if p.assigned_rd == uid:             reasons.append('assigned_rd')
            if p.assigned_sc == uid:             reasons.append('assigned_sc')
            if p.npd_poc == uid:                 reasons.append('npd_poc')
            if p.created_by == uid:              reasons.append('created_by')
            if p.assigned_members and uid_str in (p.assigned_members or ''):
                reasons.append('assigned_members(CSV)')
            if p.assigned_rd_members and uid_str in (p.assigned_rd_members or ''):
                reasons.append('assigned_rd_members(CSV)')
            # Also check sub_assignments
            has_sub = RDSubAssignment.query.filter_by(
                project_id=pid, user_id=uid, is_active=True
            ).first()
            if has_sub:
                reasons.append('has_sub_assignment')

            # Count logs on this project
            all_logs_on_project = RDSubAssignment.query.filter_by(
                project_id=pid, is_active=True
            ).count()
            own_logs_on_project = RDSubAssignment.query.filter_by(
                project_id=pid, user_id=uid, is_active=True
            ).count()

            projects_detail.append({
                'project_id':   pid,
                'code':         p.code,
                'product':      p.product_name,
                'visible_because': reasons,
                'total_logs_on_project': all_logs_on_project,
                'my_logs_on_project':    own_logs_on_project,
            })

    # What the user actually sees in the summary
    q = RDSubAssignment.query.filter(RDSubAssignment.is_active == True)
    if accessible_pids is not None:
        if not accessible_pids:
            q = q.filter(RDSubAssignment.id == -1)
        else:
            q = q.filter(RDSubAssignment.project_id.in_(accessible_pids))
    if bucket == 'employee':
        q = q.filter(RDSubAssignment.user_id == uid)
    visible_count = q.count()

    return jsonify({
        'current_user': {
            'id':        current_user.id,
            'username':  current_user.username,
            'full_name': current_user.full_name,
            'role':      current_user.role,
        },
        'computed_bucket': bucket,
        'bucket_meaning': {
            'full':     'Sees ALL logs across all projects (admin/manager/npd_manager/rd_manager)',
            'project':  'Sees ALL logs on THEIR projects (rd_executive/sales/hr/lead)',
            'employee': 'Sees ONLY their OWN logs on their projects (user/other)',
        }.get(bucket),
        'accessible_project_ids': accessible_pids if accessible_pids is not None else 'ALL',
        'accessible_project_count': 'ALL' if accessible_pids is None else len(accessible_pids),
        'projects_detail': projects_detail,
        'visible_log_count': visible_count,
        'note': (
            'Compare visible_log_count with what the UI shows. '
            'If UI matches this number, behaviour is correct. '
            'If you expected a higher number, check projects_detail — '
            'either the project is not in your accessible list '
            '(assignment missing) or no RDSubAssignment rows exist on it.'
        ),
    })

