"""
npd_wa_web_report.py
─────────────────────
WhatsApp Web Share — Detailed NPD Activity Report

Koi API nahi, koi credentials nahi.
Seedha existing npd_activity_logs + milestone_logs + npd_comments se
data padhke ek detailed formatted message banata hai.

Button click → WhatsApp Web opens with ready message.

URL: /npd/api/wa-detail-report?date=YYYY-MM-DD
"""

from datetime import datetime, date
from collections import defaultdict
from flask import request, jsonify
from flask_login import login_required, current_user
from npd_daily_report_routes import npd_report_bp   # reuse existing blueprint


# ─────────────────────────────────────────────────────────────
# Action text → (module_label, icon) classifier
# ─────────────────────────────────────────────────────────────

def _classify_log(action_text: str):
    """Returns (module_label, icon, clean_action) from raw action string."""
    t = (action_text or '').lower()

    if 'milestone' in t:
        return ('Milestones', '🎯', action_text)
    if 'comment' in t or 'note' in t:
        return ('Comments', '💬', action_text)
    if 'formulat' in t:
        return ('Formulation', '🧪', action_text)
    if 'artwork' in t:
        return ('Artwork', '🎨', action_text)
    if 'packing' in t:
        return ('Packing Material', '📦', action_text)
    if 'status' in t or 'changed' in t or '→' in action_text:
        return ('Project Status', '🔀', action_text)
    if 'created' in t and 'project' in t:
        return ('Project', '🆕', action_text)
    if 'complete' in t or 'finished' in t or 'closed' in t:
        return ('Project', '✅', action_text)
    if 'sample' in t:
        return ('Sample', '🧫', action_text)
    if 'dispatch' in t:
        return ('Dispatch', '📤', action_text)
    if 'deleted' in t:
        return ('Project', '🗑️', action_text)
    return ('Project', '🔄', action_text)


def _time_fmt(dt):
    if not dt:
        return ''
    return dt.strftime('%I:%M %p')   # e.g. 02:30 PM


def _short(text, n=60):
    if not text:
        return ''
    text = str(text).strip()
    return text if len(text) <= n else text[:n] + '…'


# ─────────────────────────────────────────────────────────────
# Core message builder
# ─────────────────────────────────────────────────────────────

def build_detail_message(for_date: date) -> str:
    """
    Reads npd_activity_logs, milestone_logs, npd_comments for the given date.
    Returns a WhatsApp-ready formatted string with full per-employee detail.

    Format:
    ━━━━━━━━━━━━━━━━━━━━━
    📋 NPD Daily Report — 09 May 2026

    👤 Rahul Sharma
    ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄
    🔀 Project Status
       • NPD-001 "Face Wash" → In Progress → Completed 🕐 2:30 PM
    🎯 Milestones
       • Artwork Approval (NPD-001) → Pending → Approved 🕐 3:45 PM
    💬 Comments
       • NPD-002 "Hair Serum" — comment added 🕐 4:00 PM
    ━━━━━━━━━━━━━━━━━━━━━
    """
    from models import db, User
    from models.npd import (NPDActivityLog, NPDProject,
                            MilestoneLog, MilestoneMaster,
                            NPDComment, NPDFormulation, NPDArtwork)

    today_start = datetime.combine(for_date, datetime.min.time())
    today_end   = datetime.combine(for_date, datetime.max.time())

    # ── 1. Pull all activity logs for today ──────────────────
    logs = (NPDActivityLog.query
            .filter(NPDActivityLog.created_at >= today_start,
                    NPDActivityLog.created_at <= today_end)
            .order_by(NPDActivityLog.user_id, NPDActivityLog.created_at)
            .all())

    ms_logs = (MilestoneLog.query
               .filter(MilestoneLog.created_at >= today_start,
                       MilestoneLog.created_at <= today_end)
               .order_by(MilestoneLog.created_by, MilestoneLog.created_at)
               .all())

    comments = (NPDComment.query
                .filter(NPDComment.created_at >= today_start,
                        NPDComment.created_at <= today_end)
                .order_by(NPDComment.user_id, NPDComment.created_at)
                .all())

    # ── 2. Group by user ────────────────────────────────────
    # Structure: user_id → list of (module, icon, record_label, action_detail, time)
    user_activities = defaultdict(list)

    # Project activity logs
    for log in logs:
        if not log.user_id:
            continue
        proj = NPDProject.query.get(log.project_id)
        code = proj.code if proj else f'P-{log.project_id}'
        name = _short(proj.product_name, 30) if proj else '—'
        record_label = f'{code} "{name}"'
        module, icon, action = _classify_log(log.action)
        user_activities[log.user_id].append((module, icon, record_label, action, log.created_at))

    # Milestone logs
    for ml in ms_logs:
        uid = ml.created_by
        if not uid:
            continue
        ms = MilestoneMaster.query.get(ml.milestone_id)
        if not ms:
            continue
        proj = NPDProject.query.get(ms.project_id) if ms else None
        code = proj.code if proj else f'P-{ms.project_id}'
        ms_title = _short(ms.title, 35)
        record_label = f'{ms_title} ({code})'
        old_s = ml.old_status or ''
        new_s = ml.new_status or ''
        status_part = f'{old_s} → {new_s}' if old_s and new_s else (ml.action or '')
        user_activities[uid].append(('Milestones', '🎯', record_label, status_part, ml.created_at))

    # Comments
    for cmt in comments:
        uid = cmt.user_id
        if not uid:
            continue
        proj = NPDProject.query.get(cmt.project_id)
        code = proj.code if proj else f'P-{cmt.project_id}'
        name = _short(proj.product_name, 25) if proj else '—'
        record_label = f'{code} "{name}"'
        cmt_preview = _short(cmt.comment, 40)
        user_activities[uid].append(('Comments', '💬', record_label, cmt_preview, cmt.created_at))

    if not user_activities:
        return (f'📋 *NPD Daily Report — {for_date.strftime("%d %b %Y")}*\n\n'
                f'Aaj koi activity record nahi hui.\n\n'
                f'_HCP ERP — NPD Module_')

    # ── 3. Build formatted message ───────────────────────────
    lines = [
        f'📋 *NPD Daily Report — {for_date.strftime("%d %b %Y")}*',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '',
    ]

    total_actions  = 0
    user_summaries = []   # For footer: [(name, count)]

    for uid, activities in sorted(user_activities.items()):
        user = User.query.get(uid)
        uname = user.full_name if user else f'User #{uid}'

        # Group activities by module within this user
        by_module = defaultdict(list)
        for (module, icon, record, action, ts) in activities:
            by_module[(module, icon)].append((record, action, ts))

        lines.append(f'👤 *{uname}*')
        lines.append('┄' * 22)

        for (module, icon), items in by_module.items():
            lines.append(f'{icon} _{module}_')
            for (record, action, ts) in items[:10]:   # max 10 per module
                time_str = _time_fmt(ts)
                action_clean = _short(action, 55)
                lines.append(f'   • {record}')
                if action_clean:
                    lines.append(f'     ↳ {action_clean}  🕐 {time_str}')
                else:
                    lines.append(f'     🕐 {time_str}')

        lines.append('')
        total_actions += len(activities)
        user_summaries.append((uname, len(activities)))

    # Footer summary
    lines.append('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    lines.append(f'📊 *Total Actions Today: {total_actions}*')
    lines.append(f'👥 *Active Members: {len(user_activities)}*')

    if user_summaries:
        top = max(user_summaries, key=lambda x: x[1])
        lines.append(f'🏆 *Most Active: {top[0]} ({top[1]} actions)*')

    lines.append('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    lines.append('_HCP ERP — NPD Module_')

    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────
# API Route
# ─────────────────────────────────────────────────────────────

@npd_report_bp.route('/api/wa-detail-report')
@login_required
def api_wa_detail_report():
    """
    Returns formatted WhatsApp message + direct wa.me URL.
    GET ?date=YYYY-MM-DD  (default: today)

    Response:
    {
      "ok": true,
      "message": "full formatted text...",
      "wa_url": "https://wa.me/?text=...",
      "char_count": 1234,
      "date": "09 May 2026"
    }
    """
    date_str = request.args.get('date', '')
    try:
        for_date = datetime.strptime(date_str, '%Y-%m-%d').date() if date_str else date.today()
    except ValueError:
        for_date = date.today()

    message = build_detail_message(for_date)

    import urllib.parse
    wa_url = 'https://web.whatsapp.com/send?text=' + urllib.parse.quote(message)

    return jsonify({
        'ok':         True,
        'message':    message,
        'wa_url':     wa_url,
        'char_count': len(message),
        'date':       for_date.strftime('%d %b %Y'),
    })
