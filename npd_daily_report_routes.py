"""
npd_daily_report_routes.py
──────────────────────────
NPD Daily Work Report Dashboard — Blueprint

URLs (all under /npd prefix, registered on the existing `npd` blueprint):
  GET  /npd/daily-report                  → Dashboard page
  GET  /npd/api/daily-dashboard           → Dashboard summary JSON
  GET  /npd/api/employee-performance      → Employee performance JSON
  GET  /npd/api/daily-report-data         → Specific date report JSON
  POST /npd/api/generate-daily-report     → Trigger/refresh report generation
  GET  /npd/api/whatsapp-message          → Pre-formatted WhatsApp text
  POST /npd/api/time-ping                 → Client heartbeat for time tracking
  POST /npd/api/track-activity            → Manual activity hook (called from existing routes)

Auto-tracking:
  register_activity_hooks(app) installs SQLAlchemy after_insert listeners on:
    - NPDActivityLog  → NPDWorkActivityLog (enriched copy)
    - MilestoneLog    → NPDWorkActivityLog (milestone updates)
    - NPDComment      → NPDWorkActivityLog (comment events)

Call register_activity_hooks(app) once from index.py after db.init_app(app).
"""

import json
from datetime import datetime, date, timedelta
from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user
from sqlalchemy import func, and_, or_, desc

# ── Blueprint (separate from the existing `npd` blueprint) ──
npd_report_bp = Blueprint('npd_report', __name__, url_prefix='/npd')


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

SESSION_TIMEOUT_MINUTES = 30   # auto-close inactive tracking sessions


def _get_models():
    """Lazy import to avoid circular dependency at module load time."""
    from models import db, User, NPDProject, NPDActivityLog, MilestoneLog, NPDComment
    from models.npd_daily_report import (
        NPDWorkActivityLog, NPDTaskTimeTracking,
        NPDEmployeeProductivity, NPDDailyReport,
    )
    try:
        from models.employee import Employee
    except Exception:
        Employee = None
    return (db, User, NPDProject, NPDActivityLog, MilestoneLog, NPDComment,
            NPDWorkActivityLog, NPDTaskTimeTracking, NPDEmployeeProductivity, NPDDailyReport, Employee)


def _classify_action(action_text: str) -> str:
    """Map raw action string → action_type category."""
    t = (action_text or '').lower()
    if 'created'  in t and 'project' in t: return 'task_created'
    if 'created'  in t:                    return 'task_created'
    if 'complete' in t or 'finished' in t: return 'task_completed'
    if 'status'   in t or 'changed'  in t: return 'status_changed'
    if 'milestone' in t:                   return 'milestone_updated'
    if 'comment'  in t or 'note'     in t: return 'comment_added'
    if 'formulat' in t:                    return 'formulation_added'
    if 'artwork'  in t:                    return 'artwork_uploaded'
    if 'packing'  in t:                    return 'packing_updated'
    if 'closed'   in t or 'cancel'   in t: return 'project_closed'
    if 'deleted'  in t:                    return 'project_deleted'
    return 'task_updated'


def _upsert_productivity(db, NPDEmployeeProductivity, user_id, emp_id, for_date, action_type):
    """Create or update NPDEmployeeProductivity for user+date."""
    row = NPDEmployeeProductivity.query.filter_by(
        user_id=user_id, report_date=for_date
    ).first()
    if not row:
        row = NPDEmployeeProductivity(
            user_id=user_id, employee_id=emp_id, report_date=for_date
        )
        db.session.add(row)

    row.total_actions = (row.total_actions or 0) + 1

    if action_type == 'task_created':
        row.tasks_created = (row.tasks_created or 0) + 1
    elif action_type == 'task_completed':
        row.tasks_completed = (row.tasks_completed or 0) + 1
    elif action_type == 'milestone_updated':
        row.milestones_updated = (row.milestones_updated or 0) + 1
    elif action_type == 'comment_added':
        row.comments_added = (row.comments_added or 0) + 1
    elif action_type == 'status_changed':
        row.status_changes = (row.status_changes or 0) + 1
    else:
        row.tasks_updated = (row.tasks_updated or 0) + 1

    row.recalculate_score()
    return row


def _resolve_employee_id(user_id):
    """Get employee_id for a user_id, returns None if not found."""
    try:
        from models.employee import Employee
        emp = Employee.query.filter_by(user_id=user_id, is_deleted=False).first()
        return emp.id if emp else None
    except Exception:
        return None


# ─────────────────────────────────────────────────────────────
# SQLAlchemy Event Hooks  (auto-tracking engine)
# ─────────────────────────────────────────────────────────────

def register_activity_hooks(app):
    """
    Install SQLAlchemy after_insert listeners.
    Call once from index.py:
        from npd_daily_report_routes import register_activity_hooks
        register_activity_hooks(app)
    """
    from sqlalchemy import event
    from models.npd import NPDActivityLog, MilestoneLog, NPDComment

    @event.listens_for(NPDActivityLog, 'after_insert')
    def _on_npd_activity_log(mapper, connection, target):
        """Mirror every NPDActivityLog write → NPDWorkActivityLog."""
        try:
            with app.app_context():
                from models import db
                from models.npd_daily_report import NPDWorkActivityLog, NPDEmployeeProductivity
                uid       = target.user_id
                pid       = target.project_id
                action    = target.action or ''
                atype     = _classify_action(action)
                today     = date.today()
                emp_id    = _resolve_employee_id(uid) if uid else None

                log = NPDWorkActivityLog(
                    project_id=pid, user_id=uid, employee_id=emp_id,
                    action_type=atype, action_detail=action[:590],
                    activity_date=today,
                )
                db.session.add(log)

                if uid:
                    _upsert_productivity(db, NPDEmployeeProductivity, uid, emp_id, today, atype)

                db.session.flush()
        except Exception as e:
            current_app.logger.warning(f'[NPD Daily Report] activity hook error: {e}')

    @event.listens_for(MilestoneLog, 'after_insert')
    def _on_milestone_log(mapper, connection, target):
        """Track milestone updates."""
        try:
            with app.app_context():
                from models import db
                from models.npd import MilestoneMaster
                from models.npd_daily_report import NPDWorkActivityLog, NPDEmployeeProductivity
                ms   = MilestoneMaster.query.get(target.milestone_id)
                if not ms:
                    return
                uid  = target.created_by
                today = date.today()
                emp_id = _resolve_employee_id(uid) if uid else None

                log = NPDWorkActivityLog(
                    project_id=ms.project_id, user_id=uid, employee_id=emp_id,
                    action_type='milestone_updated',
                    action_detail=f'Milestone "{ms.title}" → {target.action}'[:590],
                    old_status=target.old_status, new_status=target.new_status,
                    milestone_id=target.milestone_id,
                    activity_date=today,
                )
                db.session.add(log)
                if uid:
                    _upsert_productivity(db, NPDEmployeeProductivity, uid, emp_id, today, 'milestone_updated')
                db.session.flush()
        except Exception as e:
            current_app.logger.warning(f'[NPD Daily Report] milestone hook error: {e}')

    @event.listens_for(NPDComment, 'after_insert')
    def _on_comment(mapper, connection, target):
        """Track comment additions."""
        try:
            with app.app_context():
                from models import db
                from models.npd_daily_report import NPDWorkActivityLog, NPDEmployeeProductivity
                uid  = target.user_id
                today = date.today()
                emp_id = _resolve_employee_id(uid) if uid else None

                log = NPDWorkActivityLog(
                    project_id=target.project_id, user_id=uid, employee_id=emp_id,
                    action_type='comment_added',
                    action_detail=f'Comment added: {(target.comment or "")[:100]}'[:590],
                    activity_date=today,
                )
                db.session.add(log)
                if uid:
                    _upsert_productivity(db, NPDEmployeeProductivity, uid, emp_id, today, 'comment_added')
                db.session.flush()
        except Exception as e:
            current_app.logger.warning(f'[NPD Daily Report] comment hook error: {e}')


# ─────────────────────────────────────────────────────────────
# Report Generation Logic
# ─────────────────────────────────────────────────────────────

def _build_report_for_date(for_date: date):
    """
    Build (or rebuild) NPDDailyReport for `for_date`.
    Returns the NPDDailyReport object (NOT committed yet — caller must commit).
    """
    (db, User, NPDProject, NPDActivityLog, MilestoneLog, NPDComment,
     NPDWorkActivityLog, NPDTaskTimeTracking, NPDEmployeeProductivity,
     NPDDailyReport, Employee) = _get_models()

    today_start = datetime.combine(for_date, datetime.min.time())
    today_end   = datetime.combine(for_date, datetime.max.time())

    # ── Projects active today (has at least one activity log today) ──
    active_proj_ids = (
        db.session.query(NPDWorkActivityLog.project_id)
        .filter(NPDWorkActivityLog.activity_date == for_date)
        .distinct()
        .all()
    )
    active_proj_ids = [r[0] for r in active_proj_ids]

    total_tasks_worked = len(active_proj_ids)

    # ── Completed today (project status changed to 'complete' today) ──
    completed_today = NPDProject.query.filter(
        NPDProject.is_deleted == False,
        NPDProject.completed_at >= today_start,
        NPDProject.completed_at <= today_end,
    ).count()

    # ── Pending (all non-deleted, non-completed projects) ──
    pending_tasks = NPDProject.query.filter(
        NPDProject.is_deleted == False,
        ~NPDProject.status.in_(['complete', 'cancelled', 'closed']),
    ).count()

    # ── New projects created today ──
    new_today = NPDProject.query.filter(
        NPDProject.is_deleted == False,
        NPDProject.created_at >= today_start,
        NPDProject.created_at <= today_end,
    ).count()

    # ── Late tasks: target_sample_date < today and still pending ──
    late_tasks = NPDProject.query.filter(
        NPDProject.is_deleted == False,
        NPDProject.target_sample_date < for_date,
        ~NPDProject.status.in_(['complete', 'cancelled', 'closed']),
    ).count()

    # ── Active employees today ──
    active_emp_rows = (
        db.session.query(NPDWorkActivityLog.user_id)
        .filter(NPDWorkActivityLog.activity_date == for_date,
                NPDWorkActivityLog.user_id != None)
        .distinct()
        .all()
    )
    active_employees = len(active_emp_rows)
    active_uids = [r[0] for r in active_emp_rows]

    # ── Total time (from time tracking) ──
    tt_agg = db.session.query(
        func.sum(NPDTaskTimeTracking.duration_seconds)
    ).filter(NPDTaskTimeTracking.activity_date == for_date).scalar() or 0

    # ── Employee summaries ──
    prod_rows = NPDEmployeeProductivity.query.filter_by(report_date=for_date).all()
    employee_summary = []
    for p in prod_rows:
        u = User.query.get(p.user_id)
        if not u:
            continue
        employee_summary.append({
            'user_id':   p.user_id,
            'name':      u.full_name or u.username,
            'created':   p.tasks_created or 0,
            'completed': p.tasks_completed or 0,
            'updated':   p.tasks_updated or 0,
            'milestones':p.milestones_updated or 0,
            'comments':  p.comments_added or 0,
            'time_label':p.total_time_label,
            'time_secs': p.total_time_seconds or 0,
            'score':     p.productivity_score or 0,
        })
    employee_summary.sort(key=lambda x: x['score'], reverse=True)

    top_emp = employee_summary[0] if employee_summary else None

    # ── Recently updated projects ──
    recent_logs = (
        NPDWorkActivityLog.query
        .filter(NPDWorkActivityLog.activity_date == for_date)
        .order_by(desc(NPDWorkActivityLog.created_at))
        .limit(15)
        .all()
    )
    seen_proj = set()
    recently_updated = []
    for l in recent_logs:
        if l.project_id in seen_proj:
            continue
        seen_proj.add(l.project_id)
        proj = NPDProject.query.get(l.project_id)
        if not proj:
            continue
        user = User.query.get(l.user_id) if l.user_id else None
        recently_updated.append({
            'project_code': proj.code or f'P-{proj.id}',
            'product_name': proj.product_name or '—',
            'status':       proj.status_label,
            'status_color': proj.status_color,
            'updated_by':   user.full_name if user else '—',
            'action':       l.action_detail[:80],
            'updated_at':   l.created_at.strftime('%H:%M'),
        })

    # ── Hourly activity distribution (for chart) ──
    hourly = (
        db.session.query(
            func.hour(NPDWorkActivityLog.created_at).label('hr'),
            func.count(NPDWorkActivityLog.id).label('cnt'),
        )
        .filter(NPDWorkActivityLog.activity_date == for_date)
        .group_by('hr')
        .all()
    )
    hourly_data = {str(row.hr): row.cnt for row in hourly}

    # ── Action type breakdown ──
    action_counts = (
        db.session.query(
            NPDWorkActivityLog.action_type,
            func.count(NPDWorkActivityLog.id).label('cnt'),
        )
        .filter(NPDWorkActivityLog.activity_date == for_date)
        .group_by(NPDWorkActivityLog.action_type)
        .all()
    )
    action_breakdown = {row.action_type: row.cnt for row in action_counts}

    report_data = {
        'total_tasks_worked': total_tasks_worked,
        'completed_tasks':    completed_today,
        'pending_tasks':      pending_tasks,
        'late_tasks':         late_tasks,
        'new_tasks_today':    new_today,
        'active_employees':   active_employees,
        'top_employee':       top_emp,
        'employee_summary':   employee_summary,
        'recently_updated':   recently_updated,
        'hourly_activity':    hourly_data,
        'action_breakdown':   action_breakdown,
        'total_time_label':   _secs_to_label(tt_agg),
    }

    # ── Upsert NPDDailyReport ──
    existing = NPDDailyReport.query.filter_by(report_date=for_date).first()
    if not existing:
        existing = NPDDailyReport(report_date=for_date)
        db.session.add(existing)

    existing.total_tasks_worked = total_tasks_worked
    existing.completed_tasks    = completed_today
    existing.pending_tasks      = pending_tasks
    existing.late_tasks         = late_tasks
    existing.new_tasks_today    = new_today
    existing.active_employees   = active_employees
    existing.total_time_seconds = tt_agg
    existing.report_data        = json.dumps(report_data, ensure_ascii=False, default=str)
    existing.generated_at       = datetime.now()

    return existing, report_data


def _secs_to_label(seconds):
    h, rem = divmod(int(seconds or 0), 3600)
    m = rem // 60
    return f'{h}h {m}m' if h else f'{m}m'


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@npd_report_bp.route('/daily-report')
@login_required
def daily_report_dashboard():
    """Main dashboard page."""
    return render_template(
        'npd/daily_report/dashboard.html',
        _pg='npd_daily_report',
        _mod='npd',
    )


@npd_report_bp.route('/api/daily-dashboard')
@login_required
def api_daily_dashboard():
    """
    Returns aggregated data for today (or ?date=YYYY-MM-DD).
    Automatically regenerates if no report exists for today.
    """
    (db, User, NPDProject, _, _, _,
     NPDWorkActivityLog, NPDTaskTimeTracking, NPDEmployeeProductivity,
     NPDDailyReport, Employee) = _get_models()

    date_str = request.args.get('date', '')
    try:
        for_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        for_date = date.today()

    # Ensure a report exists for today
    report = NPDDailyReport.query.filter_by(report_date=for_date).first()
    if not report or (for_date == date.today()):
        # Always refresh today's report on each dashboard load
        try:
            report, report_data = _build_report_for_date(for_date)
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'[NPD Daily Report] build error: {e}')
            report_data = {}
    else:
        try:
            report_data = json.loads(report.report_data or '{}')
        except Exception:
            report_data = {}

    return jsonify({
        'ok': True,
        'date': for_date.strftime('%d %b %Y'),
        'date_iso': for_date.isoformat(),
        'report': {
            'total_tasks_worked': report.total_tasks_worked if report else 0,
            'completed_tasks':    report.completed_tasks    if report else 0,
            'pending_tasks':      report.pending_tasks      if report else 0,
            'late_tasks':         report.late_tasks         if report else 0,
            'new_tasks_today':    report.new_tasks_today    if report else 0,
            'active_employees':   report.active_employees   if report else 0,
            'total_time_label':   report.total_time_label   if report else '0m',
            **report_data,
        }
    })


@npd_report_bp.route('/api/employee-performance')
@login_required
def api_employee_performance():
    """Employee-wise performance for a given date range."""
    (db, User, _, _, _, _,
     NPDWorkActivityLog, NPDTaskTimeTracking, NPDEmployeeProductivity,
     NPDDailyReport, Employee) = _get_models()

    date_str = request.args.get('date', '')
    try:
        for_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        for_date = date.today()

    rows = NPDEmployeeProductivity.query.filter_by(report_date=for_date).all()
    result = []
    for p in rows:
        u = User.query.get(p.user_id)
        if not u:
            continue

        # Per-action breakdown for this user
        action_rows = (
            db.session.query(
                NPDWorkActivityLog.action_type,
                func.count(NPDWorkActivityLog.id).label('cnt'),
            )
            .filter(
                NPDWorkActivityLog.user_id == p.user_id,
                NPDWorkActivityLog.activity_date == for_date,
            )
            .group_by(NPDWorkActivityLog.action_type)
            .all()
        )
        breakdown = {r.action_type: r.cnt for r in action_rows}

        result.append({
            'user_id':         p.user_id,
            'name':            u.full_name or u.username,
            'tasks_created':   p.tasks_created or 0,
            'tasks_completed': p.tasks_completed or 0,
            'tasks_updated':   p.tasks_updated or 0,
            'milestones':      p.milestones_updated or 0,
            'comments':        p.comments_added or 0,
            'total_actions':   p.total_actions or 0,
            'time_label':      p.total_time_label,
            'time_seconds':    p.total_time_seconds or 0,
            'score':           p.productivity_score or 0,
            'active_sessions': p.active_sessions or 0,
            'breakdown':       breakdown,
        })

    result.sort(key=lambda x: x['score'], reverse=True)
    return jsonify({'ok': True, 'date': for_date.isoformat(), 'employees': result})


@npd_report_bp.route('/api/daily-report-data')
@login_required
def api_daily_report_data():
    """Retrieve stored daily report for a specific date."""
    (db, User, _, _, _, _,
     _, _, _, NPDDailyReport, _) = _get_models()

    date_str = request.args.get('date', date.today().isoformat())
    try:
        for_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'ok': False, 'error': 'Invalid date format'}), 400

    report = NPDDailyReport.query.filter_by(report_date=for_date).first()
    if not report:
        return jsonify({'ok': False, 'error': 'No report for this date'}), 404

    try:
        data = json.loads(report.report_data or '{}')
    except Exception:
        data = {}

    return jsonify({
        'ok': True,
        'date': for_date.strftime('%d %b %Y'),
        'report': data,
        'generated_at': report.generated_at.strftime('%d %b %Y %H:%M') if report.generated_at else '',
    })


@npd_report_bp.route('/api/generate-daily-report', methods=['POST'])
@login_required
def api_generate_daily_report():
    """
    Trigger (re)generation of daily report.
    POST body (JSON): {"date": "YYYY-MM-DD"}   (optional — defaults to today)
    Also usable as a cron endpoint (skip auth with ?auto=1 from localhost).
    """
    (db, User, _, _, _, _,
     _, _, _, NPDDailyReport, _) = _get_models()

    data = request.get_json(silent=True) or {}
    date_str = data.get('date', date.today().isoformat())
    try:
        for_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'ok': False, 'error': 'Invalid date'}), 400

    try:
        report, report_data = _build_report_for_date(for_date)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

    return jsonify({
        'ok': True,
        'message': f'Report generated for {for_date}',
        'summary': {
            'total_tasks_worked': report.total_tasks_worked,
            'completed_tasks':    report.completed_tasks,
            'pending_tasks':      report.pending_tasks,
            'active_employees':   report.active_employees,
        }
    })


@npd_report_bp.route('/api/whatsapp-message')
@login_required
def api_whatsapp_message():
    """
    Returns pre-formatted WhatsApp message text for today's report.
    GET ?date=YYYY-MM-DD  (optional)
    """
    (db, User, _, _, _, _,
     _, _, NPDEmployeeProductivity, NPDDailyReport, _) = _get_models()

    date_str = request.args.get('date', date.today().isoformat())
    try:
        for_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        for_date = date.today()

    report = NPDDailyReport.query.filter_by(report_date=for_date).first()
    if not report:
        # Auto-generate on demand
        try:
            report, _ = _build_report_for_date(for_date)
            db.session.commit()
        except Exception:
            db.session.rollback()
            return jsonify({'ok': False, 'error': 'Could not generate report'}), 500

    try:
        rd = json.loads(report.report_data or '{}')
    except Exception:
        rd = {}

    emp_lines = []
    for emp in rd.get('employee_summary', [])[:10]:
        c  = emp.get('completed', 0)
        u  = emp.get('updated', 0)
        nm = emp.get('name', 'Unknown')
        if c > 0:
            emp_lines.append(f'  ✅ {nm} → {c} completed')
        elif u > 0:
            emp_lines.append(f'  🔄 {nm} → {u} updated')
        else:
            emp_lines.append(f'  📌 {nm} → active')

    top = rd.get('top_employee') or {}
    top_line = ''
    if top:
        top_line = (f'\n🏆 *Top Performer:* {top.get("name","—")} '
                    f'(score: {top.get("score",0):.0f})')

    late_line = f'\n⚠️ *Late Tasks:* {report.late_tasks}' if report.late_tasks else ''

    msg = (
        f'📋 *NPD Daily Report — {for_date.strftime("%d %b %Y")}*\n'
        f'━━━━━━━━━━━━━━━━━━━━━\n'
        f'📊 Total Worked:  *{report.total_tasks_worked}*\n'
        f'✅ Completed:     *{report.completed_tasks}*\n'
        f'⏳ Pending:       *{report.pending_tasks}*\n'
        f'🆕 New Today:     *{report.new_tasks_today}*\n'
        f'👥 Active Team:   *{report.active_employees}*\n'
        f'⏱️ Total Time:    *{report.total_time_label}*'
        f'{late_line}\n'
        f'━━━━━━━━━━━━━━━━━━━━━\n'
        f'👤 *Team Activity:*\n' +
        '\n'.join(emp_lines or ['  (No activity recorded)']) +
        top_line + '\n'
        f'━━━━━━━━━━━━━━━━━━━━━\n'
        f'_Generated by HCP ERP — NPD Module_'
    )

    return jsonify({'ok': True, 'message': msg, 'date': for_date.isoformat()})


@npd_report_bp.route('/api/time-ping', methods=['POST'])
@login_required
def api_time_ping():
    """
    Client heartbeat — called every 60s from project view pages.
    POST JSON: {"project_id": int, "action": "project_viewed"}

    Opens or extends a session record.  Sessions older than
    SESSION_TIMEOUT_MINUTES are auto-closed before creating a new one.
    """
    (db, User, NPDProject, _, _, _,
     _, NPDTaskTimeTracking, NPDEmployeeProductivity,
     _, Employee) = _get_models()

    data = request.get_json(silent=True) or {}
    pid  = data.get('project_id')
    if not pid:
        return jsonify({'ok': False, 'error': 'project_id required'}), 400

    uid   = current_user.id
    today = date.today()
    now   = datetime.now()
    emp_id = _resolve_employee_id(uid)

    # Close stale sessions
    cutoff = now - timedelta(minutes=SESSION_TIMEOUT_MINUTES)
    stale  = NPDTaskTimeTracking.query.filter(
        NPDTaskTimeTracking.user_id == uid,
        NPDTaskTimeTracking.project_id == pid,
        NPDTaskTimeTracking.session_end.is_(None),
        NPDTaskTimeTracking.session_start < cutoff,
    ).all()
    for s in stale:
        s.session_end   = s.session_start + timedelta(minutes=SESSION_TIMEOUT_MINUTES)
        s.duration_seconds = int((s.session_end - s.session_start).total_seconds())
        s.auto_closed   = True
        # Roll up to productivity
        p = NPDEmployeeProductivity.query.filter_by(
            user_id=uid, report_date=s.activity_date
        ).first()
        if p:
            p.total_time_seconds = (p.total_time_seconds or 0) + s.duration_seconds
            p.recalculate_score()

    # Find open session for today
    open_sess = NPDTaskTimeTracking.query.filter(
        NPDTaskTimeTracking.user_id == uid,
        NPDTaskTimeTracking.project_id == pid,
        NPDTaskTimeTracking.activity_date == today,
        NPDTaskTimeTracking.session_end.is_(None),
    ).first()

    if not open_sess:
        open_sess = NPDTaskTimeTracking(
            project_id=pid, user_id=uid, employee_id=emp_id,
            session_start=now, activity_date=today,
            action_type=data.get('action', 'project_viewed'),
        )
        db.session.add(open_sess)
        # Count active sessions
        prod = NPDEmployeeProductivity.query.filter_by(user_id=uid, report_date=today).first()
        if prod:
            prod.active_sessions = (prod.active_sessions or 0) + 1

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

    return jsonify({'ok': True, 'session_id': open_sess.id})


@npd_report_bp.route('/api/activity-feed')
@login_required
def api_activity_feed():
    """
    Real-time activity feed for the dashboard live ticker.
    GET ?date=YYYY-MM-DD&limit=20
    """
    (db, User, NPDProject, _, _, _,
     NPDWorkActivityLog, _, _, _, _) = _get_models()

    date_str = request.args.get('date', date.today().isoformat())
    limit    = min(int(request.args.get('limit', 20)), 50)
    try:
        for_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        for_date = date.today()

    logs = (
        NPDWorkActivityLog.query
        .filter(NPDWorkActivityLog.activity_date == for_date)
        .order_by(desc(NPDWorkActivityLog.created_at))
        .limit(limit)
        .all()
    )

    items = []
    for l in logs:
        user = User.query.get(l.user_id) if l.user_id else None
        proj = NPDProject.query.get(l.project_id)
        items.append({
            'id':         l.id,
            'user':       user.full_name if user else 'System',
            'action':     l.action_detail[:100],
            'action_type':l.action_type,
            'project':    proj.code if proj else f'P-{l.project_id}',
            'product':    proj.product_name[:40] if proj else '—',
            'time':       l.created_at.strftime('%H:%M'),
            'time_ago':   _time_ago(l.created_at),
        })

    return jsonify({'ok': True, 'feed': items})


@npd_report_bp.route('/api/productivity-trend')
@login_required
def api_productivity_trend():
    """
    7-day productivity trend for charts.
    Returns per-day totals for the past 7 days.
    """
    (db, User, NPDProject, _, _, _,
     NPDWorkActivityLog, _, NPDEmployeeProductivity, NPDDailyReport, _) = _get_models()

    days = int(request.args.get('days', 7))
    days = min(days, 30)

    today = date.today()
    result = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        rpt = NPDDailyReport.query.filter_by(report_date=d).first()
        result.append({
            'date':          d.isoformat(),
            'label':         d.strftime('%d %b'),
            'tasks_worked':  rpt.total_tasks_worked if rpt else 0,
            'completed':     rpt.completed_tasks    if rpt else 0,
            'active_emps':   rpt.active_employees   if rpt else 0,
        })

    return jsonify({'ok': True, 'trend': result})


def _time_ago(dt: datetime) -> str:
    diff = datetime.now() - dt
    secs = int(diff.total_seconds())
    if secs < 60:   return 'just now'
    if secs < 3600: return f'{secs // 60}m ago'
    if secs < 86400:return f'{secs // 3600}h ago'
    return dt.strftime('%d %b')
