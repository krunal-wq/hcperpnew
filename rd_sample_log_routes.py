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
from sqlalchemy import or_, text

from models import db, User
from models.npd import (NPDProject, RDSubAssignment,
                        OfficeDispatchToken, OfficeDispatchItem)
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


def _user_bucket(role_or_user) -> str:
    """Return one of: 'full' | 'project' | 'employee'.

    Accepts either a role string (legacy) or a User object.
    Manager = User.role in FULL_ACCESS_ROLES. No designation magic.
    """
    # Get role string from either input type
    if isinstance(role_or_user, str) or role_or_user is None:
        r = (role_or_user or '').lower()
    else:
        r = (getattr(role_or_user, 'role', '') or '').lower()

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
    if _user_bucket(user) == 'full':
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

    bucket = _user_bucket(current_user)
    accessible_pids = get_accessible_project_ids(current_user)

    # ── Build the sample-log query ──
    # Exclude 'sent_to_office' rows — they live in the separate listing page
    q = RDSubAssignment.query.filter(
        RDSubAssignment.is_active == True,
        RDSubAssignment.status != 'sent_to_office'
    )

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
    # Also excludes 'sent_to_office' — mirrors main query
    summary_q = RDSubAssignment.query.filter(
        RDSubAssignment.is_active == True,
        RDSubAssignment.status != 'sent_to_office'
    )
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
    bucket = _user_bucket(current_user)
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

    bucket = _user_bucket(current_user)
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


# ════════════════════════════════════════════════════════════════════
#  SAMPLE CODE PERSISTENCE — added for Print Sticker workflow
# ════════════════════════════════════════════════════════════════════
#  Endpoints:
#    POST  /rd/sample-log/api/generate-codes       → auto-fill blanks (no save)
#    POST  /rd/sample-log/api/save-sample-codes    → validate + persist before print
#
#  Storage: RDSubAssignment.sample_code  (VARCHAR 500, comma-separated)
#  Uniqueness: checked case-insensitively across every stored code globally.
# ════════════════════════════════════════════════════════════════════


def _parse_codes(raw):
    """Split a comma-separated code string into a clean, ordered list."""
    if not raw:
        return []
    return [c.strip() for c in raw.split(',') if c.strip()]


def _all_existing_codes(exclude_row_id=None):
    """
    Return every sample_code currently stored in rd_sub_assignments,
    flattened across comma-separated values, upper-cased for comparison.
    Optionally exclude a single row id (so a row's own codes don't
    count as duplicates when re-saving it).
    """
    q = db.session.query(RDSubAssignment.id, RDSubAssignment.sample_code).filter(
        RDSubAssignment.sample_code.isnot(None),
        RDSubAssignment.sample_code != ''
    )
    out = set()
    for row_id, raw in q.all():
        if exclude_row_id is not None and row_id == exclude_row_id:
            continue
        for c in _parse_codes(raw):
            out.add(c.upper())
    return out


def _generate_unique_code(prefix, variant, taken):
    """
    Build a unique sample code from prefix + variant.
    Falls back to numbered suffix (-1, -2, ...) on collision.
    Mutates `taken` so repeated calls in the same batch don't collide
    with each other.
    """
    prefix  = (prefix  or 'SMP').upper().strip().replace(' ', '')
    variant = (variant or '').upper().strip().replace(' ', '')
    base    = '{}/{}'.format(prefix, variant) if variant else prefix

    code = base
    i = 1
    while code.upper() in taken:
        code = '{}-{}'.format(base, i)
        i += 1

    taken.add(code.upper())
    return code


# ─────────────────────────────────────────────────────────────────────
# 1. GENERATE CODES — auto-fill blank sample codes in modal (no save)
# ─────────────────────────────────────────────────────────────────────

@rd_sample_log_bp.route('/api/generate-codes', methods=['POST'])
@login_required
def api_generate_codes():
    """
    Body: { "ids": [12, 13, 14] }
    Returns: { ok: true, generated: { "12": "CODE1", "13": "CODE2", ... } }

    Only rows WITHOUT an existing sample_code get a fresh one.
    Rows that already have a code are skipped.
    """
    data = request.get_json(silent=True) or {}
    ids  = [int(x) for x in (data.get('ids') or []) if str(x).isdigit()]
    if not ids:
        return jsonify({'ok': False, 'error': 'No row ids provided.'}), 400

    rows = RDSubAssignment.query.filter(RDSubAssignment.id.in_(ids)).all()
    if not rows:
        return jsonify({'ok': False, 'error': 'No matching rows found.'}), 404

    taken = _all_existing_codes()
    generated = {}

    for r in rows:
        # Skip rows that already have a code — don't clobber
        if r.sample_code and r.sample_code.strip():
            continue

        proj = r.project
        prefix = (proj.code if proj and proj.code else 'P{}'.format(r.project_id))
        variant = r.variant_code or ''
        code = _generate_unique_code(prefix, variant, taken)
        generated[str(r.id)] = code

    return jsonify({'ok': True, 'generated': generated})


# ─────────────────────────────────────────────────────────────────────
# 2. SAVE SAMPLE CODES — persist BEFORE print
# ─────────────────────────────────────────────────────────────────────

@rd_sample_log_bp.route('/api/save-sample-codes', methods=['POST'])
@login_required
def api_save_sample_codes():
    """
    Body:
        {
          "rows": [
            { "id": 12, "codes": "SMP001,SMP002" },
            { "id": 13, "codes": "SMP003"        }
          ]
        }

    Behaviour:
      - Validates every row has at least one non-empty code.
      - Checks for duplicates WITHIN the batch (case-insensitive).
      - Checks for duplicates AGAINST other rows in the DB.
      - If anything fails → nothing is saved, error returned.
      - Otherwise → each row's `sample_code` field is overwritten with
        its comma-separated string and committed atomically.

    Returns:
        { ok: true,  saved: <count>,  rows: [{id, codes}, ...] }
        { ok: false, error: "...", duplicates: [...] }   on failure
    """
    data = request.get_json(silent=True) or {}
    payload = data.get('rows') or []
    if not payload:
        return jsonify({'ok': False, 'error': 'No rows supplied.'}), 400

    # ── 1. Normalise & basic validation ──────────────────────────
    cleaned = []
    for item in payload:
        try:
            rid = int(item.get('id'))
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'Invalid row id in payload.'}), 400

        codes = _parse_codes(item.get('codes') or '')
        if not codes:
            return jsonify({
                'ok': False,
                'error': 'Row #{} has no sample code. Every row must have at least one.'.format(rid)
            }), 400

        cleaned.append({'id': rid, 'codes': codes})

    # ── 2. In-batch duplicate check (case-insensitive) ──────────
    seen_in_batch = {}   # upper-code → row_id
    batch_dups = []
    for r in cleaned:
        for c in r['codes']:
            key = c.upper()
            if key in seen_in_batch and seen_in_batch[key] != r['id']:
                batch_dups.append(c)
            else:
                seen_in_batch[key] = r['id']
    if batch_dups:
        return jsonify({
            'ok': False,
            'error': 'Duplicate sample code(s) inside the selection.',
            'duplicates': sorted(set(batch_dups)),
        }), 409

    # ── 3. Fetch existing rows & permission check ───────────────
    ids = [r['id'] for r in cleaned]
    rows_by_id = {
        r.id: r for r in RDSubAssignment.query.filter(RDSubAssignment.id.in_(ids)).all()
    }
    missing = [i for i in ids if i not in rows_by_id]
    if missing:
        return jsonify({
            'ok': False,
            'error': 'Row(s) not found: {}'.format(missing)
        }), 404

    # Access control — employees can only save their OWN rows
    bucket = _user_bucket(current_user)
    if bucket == 'employee':
        bad = [i for i, r in rows_by_id.items() if r.user_id != current_user.id]
        if bad:
            return jsonify({
                'ok': False,
                'error': 'Permission denied for row(s): {}'.format(bad)
            }), 403

    # ── 4. DB-wide duplicate check (exclude rows being edited) ──
    existing_codes = _all_existing_codes()
    own_codes_union = set()
    for rid in ids:
        row = rows_by_id[rid]
        for c in _parse_codes(row.sample_code):
            own_codes_union.add(c.upper())
    other_codes = existing_codes - own_codes_union

    db_dups = []
    for r in cleaned:
        for c in r['codes']:
            if c.upper() in other_codes:
                db_dups.append(c)
    if db_dups:
        return jsonify({
            'ok': False,
            'error': 'Sample code(s) already exist elsewhere in the system.',
            'duplicates': sorted(set(db_dups)),
        }), 409

    # ── 5. Persist ───────────────────────────────────────────────
    saved = []
    for r in cleaned:
        row = rows_by_id[r['id']]
        combined = ','.join(r['codes'])
        row.sample_code = combined
        saved.append({'id': r['id'], 'codes': combined})
    db.session.commit()

    return jsonify({'ok': True, 'saved': len(saved), 'rows': saved})


# ════════════════════════════════════════════════════════════════════
#  SEND TO OFFICE WORKFLOW
# ════════════════════════════════════════════════════════════════════
#  Endpoints:
#    POST  /rd/sample-log/api/send-to-office
#         - Save sample codes for selected rows + mark status='sent_to_office'
#         - Stamps send_to_office_date and sent_to_office_by
#
#    POST  /rd/sample-log/api/revert/<id>
#         - Change status back to 'finished' (sample ready state)
#         - Clears send_to_office_date and sent_to_office_by
#
#    GET   /rd/sample-log/sent-to-office
#         - Separate listing screen for status='sent_to_office' rows
#         - Supports ?from=YYYY-MM-DD&to=YYYY-MM-DD date filters
# ════════════════════════════════════════════════════════════════════


def _apply_scope(q, user):
    """Re-usable project-scope filter — mirror of the logic in index()."""
    bucket = _user_bucket(user)
    accessible_pids = get_accessible_project_ids(user)
    if accessible_pids is not None:
        if not accessible_pids:
            return q.filter(RDSubAssignment.id == -1)
        q = q.filter(RDSubAssignment.project_id.in_(accessible_pids))
    if bucket == 'employee':
        q = q.filter(RDSubAssignment.user_id == user.id)
    return q


# ─────────────────────────────────────────────────────────────────────
# 1. SEND TO OFFICE — save codes + flip status
# ─────────────────────────────────────────────────────────────────────

@rd_sample_log_bp.route('/api/send-to-office', methods=['POST'])
@login_required
def api_send_to_office():
    """
    Body:
        {
          "rows": [
            { "id": 12, "codes": "SMP001,SMP002" },
            { "id": 13, "codes": "SMP003"        }
          ]
        }

    Steps (atomic):
      1. Validate & save sample codes (reuses the same rules as
         api_save_sample_codes — empty/dup/permission).
      2. Flip status='sent_to_office' on every row.
      3. Stamp send_to_office_date + sent_to_office_by.
    """
    data = request.get_json(silent=True) or {}
    payload = data.get('rows') or []
    if not payload:
        return jsonify({'ok': False, 'error': 'No rows supplied.'}), 400

    # Normalise
    cleaned = []
    for item in payload:
        try:
            rid = int(item.get('id'))
        except (TypeError, ValueError):
            return jsonify({'ok': False, 'error': 'Invalid row id in payload.'}), 400

        codes = _parse_codes(item.get('codes') or '')
        if not codes:
            return jsonify({
                'ok': False,
                'error': 'Row #{} has no sample code. Every row must have at least one.'.format(rid)
            }), 400

        cleaned.append({'id': rid, 'codes': codes})

    # In-batch duplicate check
    seen_in_batch = {}
    batch_dups = []
    for r in cleaned:
        for c in r['codes']:
            key = c.upper()
            if key in seen_in_batch and seen_in_batch[key] != r['id']:
                batch_dups.append(c)
            else:
                seen_in_batch[key] = r['id']
    if batch_dups:
        return jsonify({
            'ok': False,
            'error': 'Duplicate sample code(s) inside the selection.',
            'duplicates': sorted(set(batch_dups)),
        }), 409

    # Fetch & permission
    ids = [r['id'] for r in cleaned]
    rows_by_id = {
        r.id: r for r in RDSubAssignment.query.filter(RDSubAssignment.id.in_(ids)).all()
    }
    missing = [i for i in ids if i not in rows_by_id]
    if missing:
        return jsonify({'ok': False, 'error': 'Row(s) not found: {}'.format(missing)}), 404

    bucket = _user_bucket(current_user)
    if bucket == 'employee':
        bad = [i for i, r in rows_by_id.items() if r.user_id != current_user.id]
        if bad:
            return jsonify({'ok': False, 'error': 'Permission denied for row(s): {}'.format(bad)}), 403

    # DB-wide duplicate check
    existing_codes = _all_existing_codes()
    own_codes_union = set()
    for rid in ids:
        row = rows_by_id[rid]
        for c in _parse_codes(row.sample_code):
            own_codes_union.add(c.upper())
    other_codes = existing_codes - own_codes_union

    db_dups = []
    for r in cleaned:
        for c in r['codes']:
            if c.upper() in other_codes:
                db_dups.append(c)
    if db_dups:
        return jsonify({
            'ok': False,
            'error': 'Sample code(s) already exist elsewhere in the system.',
            'duplicates': sorted(set(db_dups)),
        }), 409

    # Persist — save codes + flip status + stamp dispatch metadata
    # + create OfficeDispatchToken / OfficeDispatchItem entries so this
    #   dispatch shows up in the existing Sample History page.
    now = datetime.now()

    # Extract optional handover_to / submitted_by maps from payload
    # (sent by the A4 modal as {row_id: "..."} dicts)
    handover_map  = (data.get('handover_to')  or {})   # {"12": "Sneha Dagar", ...}
    submitted_map = (data.get('submitted_by') or {})   # {"12": "Aaquib", ...}

    # Reuse today's token if one already exists, else create a new one
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    today_end   = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    token = OfficeDispatchToken.query.filter(
        OfficeDispatchToken.dispatched_at >= today_start,
        OfficeDispatchToken.dispatched_at <= today_end
    ).order_by(OfficeDispatchToken.dispatched_at.desc()).first()
    if not token:
        last = OfficeDispatchToken.query.order_by(OfficeDispatchToken.id.desc()).first()
        next_num = (last.id + 1) if last else 1
        token = OfficeDispatchToken(
            token_no      = 'ODT-{:04d}'.format(next_num),
            dispatched_by = current_user.id,
            dispatched_at = now,
            notes         = 'R&D Sample Log dispatch'
        )
        db.session.add(token)
        db.session.flush()

    saved = []
    for r in cleaned:
        row = rows_by_id[r['id']]
        combined = ','.join(r['codes'])

        # 1. Update RDSubAssignment row
        row.sample_code         = combined
        row.status              = 'sent_to_office'
        row.send_to_office_date = now
        row.sent_to_office_by   = current_user.id

        # 2. Create OfficeDispatchItem so it appears in Sample History
        ht = (handover_map.get(str(r['id']))  or '').strip() or None
        sb = (submitted_map.get(str(r['id'])) or '').strip() or None
        # Fallback for submitted_by: the executive's name
        if not sb and row.executive:
            sb = row.executive.full_name or row.executive.username

        db.session.add(OfficeDispatchItem(
            token_id             = token.id,
            project_id           = row.project_id,
            sample_code          = combined,
            handover_to          = ht,
            submitted_by         = sb,
            rd_sub_assignment_id = row.id,
        ))

        saved.append({'id': r['id'], 'codes': combined})

    # Flush sub-assignment changes so the recompute sees them
    db.session.flush()

    # ─────────────────────────────────────────────────────────────
    # Aggregate project status after dispatch.
    # Per spec: "When all employees send their completed samples to
    # office → Status should change to Sent to Office".
    # `_recompute_project_status` checks if ALL active subs of each
    # affected project are now sent_to_office and updates accordingly.
    # ─────────────────────────────────────────────────────────────
    affected_pids = {row.project_id for row in rows_by_id.values()}
    try:
        from rd_routes import _recompute_project_status
        for _pid in affected_pids:
            _recompute_project_status(_pid)
    except Exception:
        import traceback; traceback.print_exc()

    db.session.commit()

    return jsonify({
        'ok': True,
        'saved': len(saved),
        'rows': saved,
        'token_no': token.token_no,
        'dispatched_at': now.strftime('%d-%m-%Y %H:%M'),
    })


# ─────────────────────────────────────────────────────────────────────
# 2. REVERT — sent_to_office → finished (sample ready)
# ─────────────────────────────────────────────────────────────────────

@rd_sample_log_bp.route('/api/revert/<int:row_id>', methods=['POST'])
@login_required
def api_revert(row_id):
    """
    Revert a single row from 'sent_to_office' back to 'finished'.
    Clears send_to_office_date and sent_to_office_by.
    Keeps the saved sample_code intact (don't throw it away on revert).
    """
    row = RDSubAssignment.query.get(row_id)
    if not row:
        return jsonify({'ok': False, 'error': 'Row not found.'}), 404

    # Permission check
    bucket = _user_bucket(current_user)
    if bucket == 'employee' and row.user_id != current_user.id:
        return jsonify({'ok': False, 'error': 'Permission denied.'}), 403

    # Project-scope check for non-admin roles
    accessible_pids = get_accessible_project_ids(current_user)
    if accessible_pids is not None and row.project_id not in accessible_pids:
        return jsonify({'ok': False, 'error': 'Permission denied for this project.'}), 403

    if row.status != 'sent_to_office':
        return jsonify({
            'ok': False,
            'error': 'Only sent-to-office rows can be reverted. Current status: {}'.format(row.status)
        }), 400

    row.status              = 'finished'
    row.send_to_office_date = None
    row.sent_to_office_by   = None

    # Also remove the linked OfficeDispatchItem(s) so Sample History
    # stays consistent. If the token ends up with no items, drop it too.
    linked_items = OfficeDispatchItem.query.filter_by(rd_sub_assignment_id=row.id).all()
    affected_tokens = {it.token_id for it in linked_items}
    for it in linked_items:
        db.session.delete(it)
    db.session.flush()
    for tid in affected_tokens:
        remaining = OfficeDispatchItem.query.filter_by(token_id=tid).count()
        if remaining == 0:
            tok = OfficeDispatchToken.query.get(tid)
            if tok:
                db.session.delete(tok)

    db.session.flush()

    # Re-aggregate project status — when this row reverts, project may go
    # back from 'sent_to_office' / 'approved_by_office' / 'rejected_by_office'
    # to 'sample_ready' (since not all subs are dispatched anymore).
    try:
        from rd_routes import _recompute_project_status
        _recompute_project_status(row.project_id)
    except Exception:
        import traceback; traceback.print_exc()

    db.session.commit()

    return jsonify({'ok': True, 'row_id': row_id, 'new_status': 'finished'})


# ─────────────────────────────────────────────────────────────────────
# 3. SENT-TO-OFFICE LISTING — redirect to existing NPD Sample History
# ─────────────────────────────────────────────────────────────────────
# The dispatch data is stored as OfficeDispatchToken/OfficeDispatchItem,
# which the existing `/npd/sample-history` page already renders. So we
# just redirect there instead of duplicating the UI.

@rd_sample_log_bp.route('/sent-to-office')
@login_required
def sent_to_office():
    from flask import redirect, url_for
    f_from = (request.args.get('from') or '').strip()
    f_to   = (request.args.get('to')   or '').strip()
    params = {}
    if f_from: params['from_date'] = f_from
    if f_to:   params['to_date']   = f_to
    return redirect(url_for('rd.sample_history', **params))


# ════════════════════════════════════════════════════════════════════
#  DIAGNOSE & ACTIVATE — recovery utilities
# ════════════════════════════════════════════════════════════════════
#  These endpoints help when the Sample Log page shows zero rows
#  even though you know records should exist. Typical causes:
#
#    1. The records are for a different user (bucket=employee scope)
#    2. The records belong to projects you're not assigned to
#    3. The records are sent_to_office (filtered out of main view)
#    4. The records have is_active=0 (soft-deleted)
#
#  Usage:
#    • /rd/sample-log/api/diagnose  (GET, no args)
#        → returns counts + samples explaining exactly what's visible/hidden
#
#    • /rd/sample-log/api/activate?scope=all   (POST, admin-only)
#        → reactivates ALL rd_sub_assignments:
#           is_active = TRUE
#           status    = 'finished' (if currently 'sent_to_office')
#           clears send_to_office_date / sent_to_office_by
#        → also deletes orphan OfficeDispatchItems linked to them
#
#    • /rd/sample-log/api/activate?scope=mine  (POST)
#        → same, but only for the current user's rows
# ════════════════════════════════════════════════════════════════════


@rd_sample_log_bp.route('/api/diagnose')
@login_required
def api_diagnose():
    """
    Returns a JSON report explaining why rows don't appear in the
    sample log. No permission gate so every user can self-diagnose.
    """
    uid    = current_user.id
    bucket = _user_bucket(current_user)
    accessible_pids = get_accessible_project_ids(current_user)

    # Raw totals (no scoping)
    total_rows             = RDSubAssignment.query.count()
    active_rows            = RDSubAssignment.query.filter_by(is_active=True).count()
    inactive_rows          = total_rows - active_rows
    sent_to_office_rows    = RDSubAssignment.query.filter_by(status='sent_to_office').count()
    mine_rows              = RDSubAssignment.query.filter_by(user_id=uid).count()
    mine_active            = RDSubAssignment.query.filter_by(user_id=uid, is_active=True).count()
    mine_sent              = RDSubAssignment.query.filter_by(user_id=uid, status='sent_to_office').count()

    # Per-status breakdown (all rows)
    status_breakdown = {}
    for status, in db.session.query(RDSubAssignment.status).distinct().all():
        cnt = RDSubAssignment.query.filter_by(status=status).count()
        status_breakdown[status or 'NULL'] = cnt

    # What the sample-log page WOULD show for this user
    vq = RDSubAssignment.query.filter(
        RDSubAssignment.is_active == True,
        RDSubAssignment.status != 'sent_to_office'
    )
    if accessible_pids is not None:
        if not accessible_pids:
            vq = vq.filter(RDSubAssignment.id == -1)
        else:
            vq = vq.filter(RDSubAssignment.project_id.in_(accessible_pids))
    if bucket == 'employee':
        vq = vq.filter(RDSubAssignment.user_id == uid)
    visible_count = vq.count()

    # Why might rows be hidden?  Per-project tally
    per_project = []
    all_pids = [pid for (pid,) in db.session.query(RDSubAssignment.project_id).distinct().all()]
    for pid in all_pids:
        p = NPDProject.query.get(pid)
        cnt_total  = RDSubAssignment.query.filter_by(project_id=pid).count()
        cnt_active = RDSubAssignment.query.filter_by(project_id=pid, is_active=True).count()
        cnt_mine   = RDSubAssignment.query.filter_by(project_id=pid, user_id=uid).count()
        in_scope   = (accessible_pids is None) or (pid in (accessible_pids or []))
        per_project.append({
            'project_id':    pid,
            'project_code':  p.code if p else None,
            'product_name':  (p.product_name[:50] if p and p.product_name else None),
            'total_rows':    cnt_total,
            'active_rows':   cnt_active,
            'mine_rows':     cnt_mine,
            'visible_to_you': bool(in_scope and (bucket != 'employee' or cnt_mine > 0)),
        })

    return jsonify({
        'current_user': {
            'id':       uid,
            'username': current_user.username,
            'role':     current_user.role,
            'bucket':   bucket,
        },
        'accessible_project_count': 'ALL' if accessible_pids is None else len(accessible_pids or []),
        'raw_totals': {
            'total_rd_sub_assignments': total_rows,
            'active_rows':              active_rows,
            'inactive_rows':            inactive_rows,
            'sent_to_office_rows':      sent_to_office_rows,
        },
        'status_breakdown':      status_breakdown,
        'my_rows': {
            'total':          mine_rows,
            'active':         mine_active,
            'sent_to_office': mine_sent,
        },
        'sample_log_visible_count': visible_count,
        'per_project_breakdown':    per_project,
        'hint': (
            'If raw_totals.total_rd_sub_assignments > 0 but sample_log_visible_count = 0, '
            'one of these is true: '
            '(a) your rows are all sent_to_office — check /rd/sample-history; '
            '(b) your rows have is_active=0 — run POST /api/activate to fix; '
            '(c) the projects are not assigned to you — ask admin; '
            '(d) you are in employee bucket and rows belong to other users.'
        ),
    })


@rd_sample_log_bp.route('/api/activate', methods=['POST'])
@login_required
def api_activate():
    """
    Bulk-restore RDSubAssignment rows so they appear on the sample-log page.

    Query params:
      ?scope=mine   (default) — only current user's rows
      ?scope=all              — every row (ADMIN / MANAGER only)

    What it does for each affected row:
      • is_active              → True
      • status                 → 'finished'        (only if currently 'sent_to_office')
      • send_to_office_date    → NULL
      • sent_to_office_by      → NULL

    Also deletes the linked OfficeDispatchItem(s) so Sample History
    stays consistent. Any token left with zero items is also deleted.
    """
    scope = (request.args.get('scope') or 'mine').lower()
    if scope == 'all':
        if _user_bucket(current_user) != 'full':
            return jsonify({
                'ok': False,
                'error': 'scope=all requires admin/manager role.'
            }), 403
        q = RDSubAssignment.query
    else:
        q = RDSubAssignment.query.filter_by(user_id=current_user.id)

    rows = q.all()
    if not rows:
        return jsonify({'ok': True, 'affected': 0, 'message': 'No rows to activate.'})

    stats = {
        'reactivated_is_active': 0,
        'reverted_from_sent':    0,
        'deleted_dispatch_items': 0,
        'deleted_empty_tokens':  0,
    }
    row_ids = [r.id for r in rows]

    # 1. Fix is_active + status flip
    for r in rows:
        if not r.is_active:
            r.is_active = True
            stats['reactivated_is_active'] += 1
        if r.status == 'sent_to_office':
            r.status              = 'finished'
            r.send_to_office_date = None
            r.sent_to_office_by   = None
            stats['reverted_from_sent'] += 1

    # 2. Cascade: remove linked dispatch items so Sample History is consistent
    linked_items = OfficeDispatchItem.query.filter(
        OfficeDispatchItem.rd_sub_assignment_id.in_(row_ids)
    ).all()
    affected_token_ids = {it.token_id for it in linked_items}
    for it in linked_items:
        db.session.delete(it)
        stats['deleted_dispatch_items'] += 1

    db.session.flush()

    # 3. Drop tokens left empty
    for tid in affected_token_ids:
        remaining = OfficeDispatchItem.query.filter_by(token_id=tid).count()
        if remaining == 0:
            tok = OfficeDispatchToken.query.get(tid)
            if tok:
                db.session.delete(tok)
                stats['deleted_empty_tokens'] += 1

    db.session.commit()

    return jsonify({
        'ok':       True,
        'affected': len(rows),
        'scope':    scope,
        'stats':    stats,
        'message':  'Done. Reload /rd/sample-log to see your rows.',
    })
