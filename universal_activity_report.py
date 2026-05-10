"""
universal_activity_report.py
─────────────────────────────
Universal Daily Work Report — reads from:

  1. audit_logs              → CRM (leads, clients, quotations, sample_orders),
                               HR (employees), Approvals, Raw Material, etc.
  2. npd_activity_logs       → NPD project actions
  3. milestone_logs          → NPD milestone updates
  4. npd_comments            → NPD comments

Groups everything by:
    User → Module Category → Records (with action + time)

Produces a WhatsApp-ready formatted message.
Blueprint routes registered on npd_report_bp.
"""

import json, urllib.parse
from datetime import datetime, date
from collections import defaultdict, OrderedDict
from flask import request, jsonify, render_template
from flask_login import login_required
from npd_daily_report_routes import npd_report_bp   # reuse existing blueprint


# ─────────────────────────────────────────────────────────────
# Module metadata — icon, label, display order
# ─────────────────────────────────────────────────────────────

MODULE_META = {
    # audit_logs module values → (icon, display_label, sort_priority)
    'leads':               ('📋', 'CRM — Leads',             1),
    'clients':             ('🏢', 'CRM — Clients',           2),
    'quotations':          ('💼', 'CRM — Quotations',        3),
    'sample_orders':       ('📦', 'CRM — Sample Orders',     4),
    'raw_material_sample': ('🧫', 'Raw Material Samples',    5),
    'approvals':           ('✅', 'Approvals',               6),
    'employees':           ('👥', 'HR — Employees',          7),
    'users':               ('🔑', 'User Management',         8),
    'mail':                ('📧', 'Mail',                    9),
    # NPD-specific (synthetic module names)
    'npd_project':         ('🧪', 'NPD — Projects',         10),
    'npd_milestone':       ('🎯', 'NPD — Milestones',       11),
    'npd_comment':         ('💬', 'NPD — Comments',         12),
    'npd_formulation':     ('⚗️',  'NPD — Formulation',     13),
    'npd_artwork':         ('🎨', 'NPD — Artwork',          14),
    'npd_packing':         ('📦', 'NPD — Packing',          15),
    'packing':             ('🏭', 'Packing',                16),
}

# Actions to SKIP (noise — not meaningful for a work report)
SKIP_ACTIONS = {'VIEW', 'EXPORT', 'LOGIN', 'LOGOUT', 'AUTH'}

# Human-readable action labels
ACTION_LABELS = {
    'INSERT':             'Created',
    'CREATE':             'Created',
    'UPDATE':             'Updated',
    'EDIT':               'Updated',
    'DELETE':             'Deleted',
    'STATUS':             'Status changed',
    'KANBAN':             'Status changed',
    'DISCUSSION':         'Comment added',
    'NOTE':               'Note added',
    'REMINDER':           'Reminder set',
    'FOLLOW_UP':          'Follow-up added',
    'IMPORT':             'Imported',
    'DISPATCH':           'Dispatched',
    'RECEIVE':            'Received',
    'CANCEL':             'Cancelled',
    'FINALIZE_SUPPLIER':  'Supplier finalized',
    'PLACE_ORDER':        'Order placed',
    'BULK_FINALIZE':      'Bulk finalized',
    'BULK_DISPATCH':      'Bulk dispatched',
    'BULK_RECEIVE':       'Bulk received',
    'BULK_CANCEL':        'Bulk cancelled',
    'BULK_DELETE':        'Bulk deleted',
    'CLOSE':              'Closed',
    'RESTORE':            'Restored',
    'APPROVE':            'Approved',
    'REJECT':             'Rejected',
    'RESET':              'Reset',
}


def _action_label(action: str) -> str:
    return ACTION_LABELS.get((action or '').upper(), action.replace('_', ' ').title())


def _short(text, n=55):
    if not text:
        return ''
    text = str(text).strip()
    return text if len(text) <= n else text[:n] + '…'


def _time_fmt(dt) -> str:
    return dt.strftime('%I:%M %p') if dt else ''


def _module_meta(module_key: str):
    return MODULE_META.get(module_key, ('📌', module_key.replace('_', ' ').title(), 99))


# ─────────────────────────────────────────────────────────────
# Data collectors — returns list of activity dicts
# ─────────────────────────────────────────────────────────────

def _collect_audit_logs(today_start, today_end):
    """Read audit_logs for the day — covers ALL modules."""
    from models import db, AuditLog, User

    rows = (AuditLog.query
            .filter(AuditLog.created_at >= today_start,
                    AuditLog.created_at <= today_end)
            .order_by(AuditLog.user_id, AuditLog.created_at)
            .all())

    activities = []
    for log in rows:
        if not log.user_id:
            continue
        action_up = (log.action or '').upper()
        if action_up in SKIP_ACTIONS:
            continue

        # Extract detail summary from JSON or plain text
        detail_txt = ''
        if log.detail:
            try:
                d = json.loads(log.detail)
                detail_txt = d.get('summary', '')
                if not detail_txt and 'changes' in d:
                    chgs = d['changes']
                    parts = []
                    for k, v in list(chgs.items())[:3]:
                        parts.append(f'{k}: {_short(str(v.get("before","")),20)} → {_short(str(v.get("after","")),20)}')
                    detail_txt = ' | '.join(parts)
            except Exception:
                detail_txt = _short(str(log.detail), 60)

        activities.append({
            'user_id':      log.user_id,
            'username':     log.username or '',
            'module':       log.module or 'other',
            'action_key':   action_up,
            'action_label': _action_label(action_up),
            'record_label': _short(log.record_label or '', 50),
            'detail':       _short(detail_txt, 60),
            'ts':           log.created_at,
        })
    return activities


def _collect_npd_logs(today_start, today_end):
    """Read NPD-specific logs — projects, milestones, comments, formulations."""
    from models.npd import (NPDActivityLog, NPDProject,
                             MilestoneLog, MilestoneMaster,
                             NPDComment, NPDFormulation, NPDArtwork)

    activities = []

    # ── NPD Activity Logs ────────────────────────────────────
    for log in (NPDActivityLog.query
                .filter(NPDActivityLog.created_at >= today_start,
                        NPDActivityLog.created_at <= today_end)
                .all()):
        if not log.user_id:
            continue
        proj = NPDProject.query.get(log.project_id)
        code = proj.code if proj else f'P-{log.project_id}'
        name = _short(proj.product_name, 30) if proj else '—'
        action_txt = log.action or ''

        # Determine module from action text
        t = action_txt.lower()
        if 'formulat' in t:
            mod = 'npd_formulation'
        elif 'artwork' in t:
            mod = 'npd_artwork'
        elif 'packing' in t:
            mod = 'npd_packing'
        else:
            mod = 'npd_project'

        activities.append({
            'user_id':      log.user_id,
            'username':     '',
            'module':       mod,
            'action_key':   'NPD',
            'action_label': _action_label_npd(action_txt),
            'record_label': f'{code} — "{name}"',
            'detail':       _short(action_txt, 60),
            'ts':           log.created_at,
        })

    # ── Milestone Logs ───────────────────────────────────────
    for ml in (MilestoneLog.query
               .filter(MilestoneLog.created_at >= today_start,
                       MilestoneLog.created_at <= today_end)
               .all()):
        uid = ml.created_by
        if not uid:
            continue
        ms   = MilestoneMaster.query.get(ml.milestone_id)
        if not ms:
            continue
        proj = NPDProject.query.get(ms.project_id)
        code = proj.code if proj else f'P-{ms.project_id}'
        label = f'{_short(ms.title,35)} ({code})'
        status_txt = ''
        if ml.old_status and ml.new_status:
            status_txt = f'{ml.old_status} → {ml.new_status}'
        elif ml.action:
            status_txt = _short(ml.action, 55)

        activities.append({
            'user_id':      uid,
            'username':     '',
            'module':       'npd_milestone',
            'action_key':   'MILESTONE',
            'action_label': 'Updated',
            'record_label': label,
            'detail':       status_txt,
            'ts':           ml.created_at,
        })

    # ── NPD Comments ─────────────────────────────────────────
    for cmt in (NPDComment.query
                .filter(NPDComment.created_at >= today_start,
                        NPDComment.created_at <= today_end)
                .all()):
        uid = cmt.user_id
        if not uid:
            continue
        proj = NPDProject.query.get(cmt.project_id)
        code = proj.code if proj else f'P-{cmt.project_id}'
        name = _short(proj.product_name, 25) if proj else '—'
        activities.append({
            'user_id':      uid,
            'username':     '',
            'module':       'npd_comment',
            'action_key':   'COMMENT',
            'action_label': 'Comment added',
            'record_label': f'{code} — "{name}"',
            'detail':       _short(cmt.comment, 50),
            'ts':           cmt.created_at,
        })

    return activities


def _action_label_npd(action_text: str) -> str:
    t = (action_text or '').lower()
    if 'created'  in t: return 'Created'
    if 'complete' in t: return 'Completed'
    if 'closed'   in t: return 'Closed'
    if 'status'   in t or '→' in action_text: return 'Status changed'
    if 'comment'  in t: return 'Comment added'
    if 'formulat' in t: return 'Formulation added'
    if 'artwork'  in t: return 'Artwork updated'
    if 'packing'  in t: return 'Packing updated'
    if 'deleted'  in t: return 'Deleted'
    if 'updated'  in t: return 'Updated'
    return 'Updated'


# ─────────────────────────────────────────────────────────────
# Message builder
# ─────────────────────────────────────────────────────────────

def build_universal_message(for_date: date, filter_user_id: int = None) -> str:
    """
    Build the full cross-module WhatsApp message for `for_date`.
    If filter_user_id is set, show only that user's activity.
    """
    from models import User

    today_start = datetime.combine(for_date, datetime.min.time())
    today_end   = datetime.combine(for_date, datetime.max.time())

    # Collect from all sources
    all_activities = _collect_audit_logs(today_start, today_end)
    all_activities += _collect_npd_logs(today_start, today_end)

    if not all_activities:
        return (f'📋 *Daily Work Report — {for_date.strftime("%d %b %Y")}*\n\n'
                f'Aaj koi activity record nahi hui.\n\n_HCP ERP_')

    # Enrich usernames from User table (for NPD logs which don't have username)
    user_cache = {}
    def get_username(uid):
        if uid not in user_cache:
            u = User.query.get(uid)
            user_cache[uid] = u.full_name if u else f'User #{uid}'
        return user_cache[uid]

    # Group: user_id → module → list of (record, action_label, detail, ts)
    user_data = defaultdict(lambda: defaultdict(list))
    user_action_count = defaultdict(int)

    for act in all_activities:
        uid = act['user_id']
        if filter_user_id and uid != filter_user_id:
            continue
        mod = act['module']
        user_data[uid][mod].append(act)
        user_action_count[uid] += 1

    if not user_data:
        return (f'📋 *Daily Work Report — {for_date.strftime("%d %b %Y")}*\n\n'
                f'Koi activity nahi mili.\n_HCP ERP_')

    # Sort users by action count (most active first)
    sorted_users = sorted(user_data.keys(),
                          key=lambda uid: user_action_count[uid], reverse=True)

    lines = [
        f'📋 *Daily Work Report — {for_date.strftime("%d %b %Y")}*',
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        f'👥 *{len(sorted_users)} members active | {len(all_activities)} total actions*',
        '',
    ]

    total_module_counts = defaultdict(int)

    for uid in sorted_users:
        uname = get_username(uid)
        mod_dict = user_data[uid]
        total_u = user_action_count[uid]

        lines.append(f'👤 *{uname}*  ({total_u} actions)')
        lines.append('┄' * 24)

        # Sort modules by priority
        sorted_mods = sorted(mod_dict.keys(),
                             key=lambda m: _module_meta(m)[2])

        for mod in sorted_mods:
            icon, mod_label, _ = _module_meta(mod)
            acts = mod_dict[mod]
            total_module_counts[mod] += len(acts)

            lines.append(f'{icon} _{mod_label}_ ({len(acts)})')

            # De-duplicate by record — if same record has multiple actions, show all
            seen = {}   # record_label → list of (action_label, detail, ts)
            for a in acts:
                rl = a['record_label'] or '—'
                if rl not in seen:
                    seen[rl] = []
                seen[rl].append(a)

            for record_label, record_acts in list(seen.items())[:8]:  # max 8 records per module
                lines.append(f'   • *{record_label}*')
                for a in record_acts[:3]:  # max 3 actions per record
                    parts = [a['action_label']]
                    if a['detail']:
                        parts.append(a['detail'])
                    action_str = ' — '.join(parts)
                    lines.append(f'     ↳ {_short(action_str, 65)}  🕐 {_time_fmt(a["ts"])}')

            if len(seen) > 8:
                lines.append(f'     … +{len(seen)-8} more records')

        lines.append('')

    # ── Footer summary ────────────────────────────────────────
    lines.append('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')

    # Module-wise totals
    if total_module_counts:
        lines.append('📊 *Module Wise Summary:*')
        for mod, cnt in sorted(total_module_counts.items(),
                               key=lambda x: _module_meta(x[0])[2]):
            icon, lbl, _ = _module_meta(mod)
            lines.append(f'   {icon} {lbl}: {cnt}')

    # Top performer
    if sorted_users:
        top_uid   = sorted_users[0]
        top_name  = get_username(top_uid)
        top_count = user_action_count[top_uid]
        lines.append(f'🏆 *Most Active: {top_name} ({top_count} actions)*')

    lines.append('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    lines.append('_HCP ERP — Daily Work Report_')

    return '\n'.join(lines)


def build_stats(for_date: date) -> dict:
    """Quick stats for the header chips."""
    from models import db, AuditLog
    from models.npd import NPDActivityLog

    today_start = datetime.combine(for_date, datetime.min.time())
    today_end   = datetime.combine(for_date, datetime.max.time())

    from sqlalchemy import func

    audit_stats = (db.session.query(
            AuditLog.module,
            func.count(AuditLog.id).label('cnt'),
            func.count(func.distinct(AuditLog.user_id)).label('users'),
        )
        .filter(AuditLog.created_at >= today_start,
                AuditLog.created_at <= today_end,
                ~AuditLog.action.in_(list(SKIP_ACTIONS)))
        .group_by(AuditLog.module)
        .all())

    npd_count = (NPDActivityLog.query
                 .filter(NPDActivityLog.created_at >= today_start,
                         NPDActivityLog.created_at <= today_end)
                 .count())

    total_actions = sum(r.cnt for r in audit_stats) + npd_count
    active_users  = len(set(
        uid for r in (db.session.query(AuditLog.user_id)
                      .filter(AuditLog.created_at >= today_start,
                              AuditLog.created_at <= today_end,
                              AuditLog.user_id != None)
                      .distinct().all()) for uid in [r[0]]
    ))

    modules_active = [r.module for r in audit_stats] + (['npd'] if npd_count else [])

    return {
        'total_actions': total_actions,
        'active_users':  active_users,
        'modules_active': list(set(modules_active)),
        'module_breakdown': [
            {'module': r.module, 'label': _module_meta(r.module)[1],
             'icon': _module_meta(r.module)[0], 'count': r.cnt}
            for r in sorted(audit_stats, key=lambda r: _module_meta(r.module)[2])
        ] + ([{'module': 'npd', 'label': 'NPD — Projects',
               'icon': '🧪', 'count': npd_count}] if npd_count else []),
    }


# ─────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────

@npd_report_bp.route('/universal-report')
@login_required
def universal_report_page():
    """Universal cross-module WhatsApp share page."""
    return render_template('daily_report/universal_share.html',
                           _pg='universal_report', _mod='npd')


@npd_report_bp.route('/api/universal-report')
@login_required
def api_universal_report():
    """
    GET /npd/api/universal-report?date=YYYY-MM-DD&user_id=N
    Returns formatted message + wa.me URL.
    """
    date_str = request.args.get('date', '')
    uid_str  = request.args.get('user_id', '')

    try:
        for_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        for_date = date.today()

    filter_uid = int(uid_str) if uid_str.isdigit() else None

    message  = build_universal_message(for_date, filter_user_id=filter_uid)
    wa_url   = 'https://web.whatsapp.com/send?text=' + urllib.parse.quote(message)
    stats    = build_stats(for_date)

    return jsonify({
        'ok':         True,
        'message':    message,
        'wa_url':     wa_url,
        'char_count': len(message),
        'date':       for_date.strftime('%d %b %Y'),
        'stats':      stats,
    })


@npd_report_bp.route('/api/universal-users')
@login_required
def api_universal_users():
    """Users who have activity on the given date (for the filter dropdown)."""
    from models import db, AuditLog, User
    from models.npd import NPDActivityLog

    date_str = request.args.get('date', date.today().isoformat())
    try:
        for_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        for_date = date.today()

    today_start = datetime.combine(for_date, datetime.min.time())
    today_end   = datetime.combine(for_date, datetime.max.time())

    from sqlalchemy import func

    audit_uids = {r[0] for r in
        db.session.query(AuditLog.user_id)
        .filter(AuditLog.created_at >= today_start,
                AuditLog.created_at <= today_end,
                AuditLog.user_id != None)
        .distinct().all()}

    npd_uids = {r[0] for r in
        db.session.query(NPDActivityLog.user_id)
        .filter(NPDActivityLog.created_at >= today_start,
                NPDActivityLog.created_at <= today_end,
                NPDActivityLog.user_id != None)
        .distinct().all()}

    all_uids = audit_uids | npd_uids
    users = []
    for uid in all_uids:
        u = User.query.get(uid)
        if u:
            users.append({'id': uid, 'name': u.full_name or u.username})

    users.sort(key=lambda x: x['name'])
    return jsonify({'ok': True, 'users': users})
