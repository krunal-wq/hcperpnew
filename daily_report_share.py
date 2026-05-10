"""
daily_report_share.py  (v4 — Comments Fixed)
─────────────────────────────────────────────
index.py mein:
    from daily_report_share import daily_report_bp
    app.register_blueprint(daily_report_bp)

Visit: http://127.0.0.1:5000/daily-report/
"""

import json, urllib.parse
from datetime import datetime, date
from collections import defaultdict
from flask import Blueprint, request, jsonify, Response
from flask_login import login_required

daily_report_bp = Blueprint('daily_report', __name__, url_prefix='/daily-report')

MOD = {
    'leads':               ('📋', 'CRM — Leads'),
    'leads_reminder':       ('📌', 'CRM — Reminders'),
    'clients':             ('🏢', 'CRM — Clients'),
    'quotations':          ('💼', 'CRM — Quotations'),
    'sample_orders':       ('📦', 'CRM — Sample Orders'),
    'quotations':          ('💼', 'CRM — Quotations'),
    'raw_material_sample': ('🧫', 'Raw Material Samples'),
    'approvals':           ('✅', 'Approvals'),
    'employees':           ('👥', 'HR — Employees'),
    'npd_project':         ('🧪', 'NPD — Projects'),
    'npd_milestone':       ('🎯', 'NPD — Milestones'),
    'npd_comment':         ('💬', 'NPD — Comments'),
    'packing':             ('🏭', 'Packing'),
}
ACT = {
    'INSERT':'Created','CREATE':'Created','UPDATE':'Updated','EDIT':'Updated',
    'DELETE':'Deleted','STATUS':'Status changed','KANBAN':'Status changed',
    'NOTE':'Note added','REMINDER':'Reminder set','FOLLOW_UP':'Follow-up added',
    'IMPORT':'Imported','DISPATCH':'Dispatched','RECEIVE':'Received',
    'CANCEL':'Cancelled','FINALIZE_SUPPLIER':'Supplier finalized',
    'PLACE_ORDER':'Order placed','CLOSE':'Closed','APPROVE':'Approved','REJECT':'Rejected',
}
# Actions to completely ignore
SKIP = {'VIEW', 'EXPORT', 'LOGIN', 'LOGOUT', 'AUTH', 'DISCUSSION', 'REMINDER', 'NOTE', 'FOLLOW_UP'}

def _al(a):  return ACT.get((a or '').upper(), (a or '').replace('_', ' ').title())
def _sh(t, n=200): s = str(t or '').strip(); return s if len(s) <= n else s[:n] + '…'
def _tf(dt): return dt.strftime('%I:%M %p') if dt else ''
def _mm(m):  return MOD.get(m, ('📌', m.replace('_', ' ').title()))


def _lead_info(lead_id):
    """Fetch Lead record → return formatted label string."""
    if not lead_id:
        return ''
    try:
        from models import Lead
        l = Lead.query.get(int(lead_id))
        if not l:
            return f'Lead #{lead_id}'
        parts = [l.code or f'LD-{lead_id}', l.contact_name or '']
        if l.company_name:
            parts.append(l.company_name)
        return ' | '.join(p for p in parts if p)
    except Exception:
        return f'Lead #{lead_id}'


def _npd_info(proj_id):
    """Fetch NPDProject → return formatted label string."""
    if not proj_id:
        return f'Project #{proj_id}'
    try:
        from models.npd import NPDProject
        p = NPDProject.query.get(int(proj_id))
        if not p:
            return f'Project #{proj_id}'
        parts = [p.code or f'NPD-{proj_id}', f'"{_sh(p.product_name or "", 30)}"']
        client = p.client_name or p.client_company or ''
        if client:
            parts.append(f'Client: {client}')
        return ' | '.join(parts)
    except Exception:
        return f'Project #{proj_id}'


def _npd_action(txt):
    t = (txt or '').lower()
    if 'creat'   in t: return 'Created'
    if 'complet' in t: return 'Completed'
    if 'close'   in t: return 'Closed'
    if 'cancel'  in t: return 'Cancelled'
    if 'status'  in t or '→' in txt: return 'Status changed'
    if 'comment' in t: return 'Comment added'
    if 'formulat'in t: return 'Formulation added'
    if 'artwork' in t: return 'Artwork updated'
    if 'packing' in t: return 'Packing updated'
    if 'delet'   in t: return 'Deleted'
    return 'Updated'


# ─────────────────────────────────────────────────────────────
# Collect all activities for the day
# ─────────────────────────────────────────────────────────────

def collect(for_date, filter_uid=None):
    from models import db, AuditLog
    ts  = datetime.combine(for_date, datetime.min.time())
    te  = datetime.combine(for_date, datetime.max.time())
    out = []   # list of activity dicts

    # ── Helper to add entry ──────────────────────────────────
    def add(uid, mod, action, record, detail_lines, ts_val):
        if filter_uid and uid != filter_uid:
            return
        if not uid:
            return
        out.append({'uid': uid, 'mod': mod, 'action': action,
                    'record': record, 'detail': detail_lines, 'ts': ts_val})

    # ════════════════════════════════════════════════════════
    # 1. LEAD COMMENTS — read directly from lead_discussions
    #    (audit_logs only has "Comment added by X", NOT the text)
    # ════════════════════════════════════════════════════════
    try:
        from models import LeadDiscussion
        rows = (LeadDiscussion.query
                .filter(LeadDiscussion.created_at >= ts,
                        LeadDiscussion.created_at <= te)
                .order_by(LeadDiscussion.user_id,
                          LeadDiscussion.created_at)
                .all())
        for r in rows:
            comment_text = (r.comment or '').strip()
            add(
                uid          = r.user_id,
                mod          = 'leads',
                action       = 'Comment added',
                record       = _lead_info(r.lead_id),
                detail_lines = [f'💬 "{_sh(comment_text, 250)}"'] if comment_text else [],
                ts_val       = r.created_at,
            )
    except Exception as e:
        # Log to help debug
        import traceback
        print(f'[DailyReport] lead_discussions error: {e}')
        traceback.print_exc()


    # ════════════════════════════════════════════════════════
    # 1b. LEAD REMINDERS — created today
    # ════════════════════════════════════════════════════════
    try:
        from models import LeadReminder
        rows = (LeadReminder.query
                .filter(LeadReminder.created_at >= ts,
                        LeadReminder.created_at <= te)
                .order_by(LeadReminder.user_id, LeadReminder.created_at)
                .all())
        for r in rows:
            if not r.user_id:
                continue
            title       = (r.title or '').strip()
            description = (r.description or '').strip()
            remind_time = r.remind_at.strftime('%d %b %Y %I:%M %p') if r.remind_at else ''
            status      = '✅ Done' if r.is_done else '⏰ Pending'
            detail_lines = [f'📌 "{title}"  [{status}]  🗓 {remind_time}']
            add(r.user_id, 'leads', 'Reminder set', _lead_info(r.lead_id), detail_lines, r.created_at)
    except Exception as e:
        print(f'[DailyReport] lead_reminders error: {e}')

    # ════════════════════════════════════════════════════════
    # 1e. QUOTATIONS — created today (direct table read)
    # ════════════════════════════════════════════════════════
    try:
        from models import Quotation
        rows = (Quotation.query
                .filter(Quotation.created_at >= ts,
                        Quotation.created_at <= te,
                        Quotation.is_deleted == False)
                .all())
        for r in rows:
            if not r.created_by:
                continue
            lead   = _lead_info(r.lead_id)
            total  = f'₹{float(r.total_amount or 0):,.0f}' if r.total_amount else ''
            status = (r.status or '').title()
            detail = [f'📄 {r.quot_number}  |  {r.bill_company or lead}']
            if total:
                detail.append(f'   💰 Total: {total}  |  Status: {status}')
            if r.email_sent_at and ts <= r.email_sent_at <= te:
                detail.append(f'   📧 Emailed to: {r.email_sent_to or "client"}')
            add(r.created_by, 'quotations', 'Quotation created', lead, detail, r.created_at)
    except Exception as e:
        print(f'[DailyReport] quotations error: {e}')

    # ════════════════════════════════════════════════════════
    # 1f. SAMPLE ORDERS — created today (direct table read)
    # ════════════════════════════════════════════════════════
    try:
        from models import SampleOrder
        rows = (SampleOrder.query
                .filter(SampleOrder.created_at >= ts,
                        SampleOrder.created_at <= te,
                        SampleOrder.is_deleted == False)
                .all())
        for r in rows:
            if not r.created_by:
                continue
            lead   = _lead_info(r.lead_id)
            total  = f'₹{float(r.total_amount or 0):,.0f}' if r.total_amount else ''
            detail = [f'🧾 {r.order_number}  |  {r.bill_company or lead}']
            if total:
                detail.append(f'   💰 Total: {total}')
            if r.bill_email:
                detail.append(f'   📧 Email: {r.bill_email}')
            add(r.created_by, 'sample_orders', 'Sample Order created', lead, detail, r.created_at)
    except Exception as e:
        print(f'[DailyReport] sample_orders error: {e}')

    # ════════════════════════════════════════════════════════
    # 1d. LEAD ACTIVITY LOG — NPD conversion, status changes,
    #     quotation emails, follow-ups (excluding comments/reminders
    #     which come from direct tables above)
    # ════════════════════════════════════════════════════════
    try:
        from models import LeadActivityLog
        rows = (LeadActivityLog.query
                .filter(LeadActivityLog.created_at >= ts,
                        LeadActivityLog.created_at <= te)
                .order_by(LeadActivityLog.user_id, LeadActivityLog.created_at)
                .all())
        for r in rows:
            if not r.user_id:
                continue
            txt = (r.action or '').strip()
            tl  = txt.lower()

            # Skip entries handled by direct table reads
            if any(x in tl for x in [
                'comment', 'reminder set', 'personal note',
                'quotation generated', 'sample order generated',
            ]):
                continue

            # Determine action label and icon
            if 'converted to npd' in tl or 'converted to epd' in tl:
                action_label = '🚀 NPD/EPD Project Created'
                mod = 'npd_project'
            elif 'quotation' in tl and 'email' in tl:
                action_label = '📧 Quotation emailed'
                mod = 'quotations'
            elif 'status changed' in tl:
                action_label = '🔀 Status changed'
                mod = 'leads'
            elif 'new lead added' in tl:
                action_label = '🆕 Lead created'
                mod = 'leads'
            elif 'lead record updated' in tl or 'inline edit' in tl:
                action_label = '✏️ Lead updated'
                mod = 'leads'
            else:
                action_label = txt[:60]
                mod = 'leads'

            add(r.user_id, mod, action_label,
                _lead_info(r.lead_id),
                [txt[:200]] if txt else [],
                r.created_at)
    except Exception as e:
        print(f'[DailyReport] lead_activity_logs error: {e}')

    # ════════════════════════════════════════════════════════
    # 2. AUDIT LOGS — all other actions (skip DISCUSSION)
    # ════════════════════════════════════════════════════════
    try:
        rows = (AuditLog.query
                .filter(AuditLog.created_at >= ts,
                        AuditLog.created_at <= te)
                .order_by(AuditLog.user_id, AuditLog.created_at)
                .all())
        for r in rows:
            if not r.user_id:
                continue
            if (r.action or '').upper() in SKIP:
                continue   # DISCUSSION skipped — handled above
            # Skip modules handled via direct table reads (avoid duplicates)
            if mod in ('quotations', 'sample_orders'):
                continue

            mod    = r.module or 'other'
            record = r.record_label or ''
            detail = []

            # Parse detail JSON
            raw = ''
            try:
                d   = json.loads(r.detail or '{}')
                raw = d.get('summary', '')
                if not raw and 'changes' in d:
                    parts = []
                    for k, v in list(d['changes'].items())[:4]:
                        b = _sh(str(v.get('before', '') or ''), 25)
                        a = _sh(str(v.get('after',  '') or ''), 25)
                        if b != a:
                            parts.append(f'{k}: {b} → {a}')
                    raw = ' | '.join(parts)
            except Exception:
                raw = _sh(str(r.detail or ''), 80)

            # Enrich leads record label
            if mod == 'leads' and r.record_id:
                record = _lead_info(r.record_id)

            if raw:
                detail.append(raw)

            add(r.user_id, mod, _al(r.action), record, detail, r.created_at)
    except Exception as e:
        print(f'[DailyReport] audit_logs error: {e}')

    # ════════════════════════════════════════════════════════
    # 3. NPD ACTIVITY LOGS
    # ════════════════════════════════════════════════════════
    try:
        from models.npd import NPDActivityLog
        rows = (NPDActivityLog.query
                .filter(NPDActivityLog.created_at >= ts,
                        NPDActivityLog.created_at <= te)
                .order_by(NPDActivityLog.user_id,
                          NPDActivityLog.created_at)
                .all())
        for r in rows:
            t   = (r.action or '').lower()
            mod = ('npd_milestone' if 'milestone' in t else
                   'npd_comment'   if 'comment'   in t else 'npd_project')
            add(
                uid          = r.user_id,
                mod          = mod,
                action       = _npd_action(r.action),
                record       = _npd_info(r.project_id),
                detail_lines = [_sh(r.action, 80)] if r.action else [],
                ts_val       = r.created_at,
            )
    except Exception as e:
        print(f'[DailyReport] npd_activity error: {e}')

    # ════════════════════════════════════════════════════════
    # 4. NPD COMMENTS — full text from npd_comments table
    # ════════════════════════════════════════════════════════
    try:
        from models.npd import NPDComment
        rows = (NPDComment.query
                .filter(NPDComment.created_at >= ts,
                        NPDComment.created_at <= te)
                .order_by(NPDComment.user_id,
                          NPDComment.created_at)
                .all())
        for r in rows:
            comment_text = (r.comment or '').strip()
            add(
                uid          = r.user_id,
                mod          = 'npd_comment',
                action       = 'Comment added',
                record       = _npd_info(r.project_id),
                detail_lines = [f'💬 "{_sh(comment_text, 250)}"'] if comment_text else [],
                ts_val       = r.created_at,
            )
    except Exception as e:
        print(f'[DailyReport] npd_comments error: {e}')

    # ════════════════════════════════════════════════════════
    # 5. MILESTONE LOGS
    # ════════════════════════════════════════════════════════
    try:
        from models.npd import MilestoneLog, MilestoneMaster
        rows = (MilestoneLog.query
                .filter(MilestoneLog.created_at >= ts,
                        MilestoneLog.created_at <= te)
                .all())
        for r in rows:
            if not r.created_by:
                continue
            ms = MilestoneMaster.query.get(r.milestone_id)
            if not ms:
                continue
            detail = []
            if r.old_status and r.new_status:
                detail.append(f'Status: {r.old_status} → {r.new_status}')
            elif r.action:
                detail.append(_sh(r.action, 80))
            if r.note:
                detail.append(f'Note: "{_sh(r.note, 120)}"')

            proj_label = _npd_info(ms.project_id)
            record     = f'{_sh(ms.title, 35)} | {proj_label}'
            add(r.created_by, 'npd_milestone', 'Updated', record, detail, r.created_at)
    except Exception as e:
        print(f'[DailyReport] milestone_logs error: {e}')

    return out


# ─────────────────────────────────────────────────────────────
# Build WhatsApp message
# ─────────────────────────────────────────────────────────────

def build_message(for_date, filter_uid=None):
    from models import User

    acts = collect(for_date, filter_uid)
    if not acts:
        return (f'📋 *Daily Work Report — {for_date.strftime("%d %b %Y")}*\n\n'
                f'Aaj koi activity record nahi mili.\n_HCP ERP_')

    # Resolve user names
    uc = {}
    def gname(uid):
        if uid not in uc:
            try:
                u = User.query.get(uid)
                uc[uid] = u.full_name if u else f'User #{uid}'
            except Exception:
                uc[uid] = f'User #{uid}'
        return uc[uid]

    # Group by user
    by_user = defaultdict(list)
    for a in acts:
        by_user[a['uid']].append(a)

    sorted_users = sorted(by_user.keys(),
                          key=lambda u: len(by_user[u]), reverse=True)

    day_str   = for_date.strftime('%d %b.%Y')
    UNIT_MAP  = {
        'leads':               'Lead',
        'quotations':          'Quotation',
        'sample_orders':       'Sample Order',
        'npd_project':         'NPD Project',
        'npd_milestone':       'Milestone',
        'npd_comment':         'NPD Comment',
        'approvals':           'Approval',
        'employees':           'Employee',
        'clients':             'Client',
        'packing':             'Packing Entry',
        'raw_material_sample': 'RM Sample',
    }

    # ── PASS 1: build employee detail lines + collect mod_totals ──
    mod_totals  = defaultdict(int)
    detail_lines = []   # all employee detail lines

    for uid in sorted_users:
        uacts = by_user[uid]
        uname = gname(uid)



        by_mod = defaultdict(list)
        for a in uacts:
            by_mod[a['mod']].append(a)
            mod_totals[a['mod']] += 1

        for mod in sorted(by_mod.keys(), key=lambda m: _mm(m)[1]):
            icon, label = _mm(mod)
            macts = by_mod[mod]
            detail_lines.append(f'')
            detail_lines.append(f'▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬▬')
            detail_lines.append(f'{icon} *{label}*')
            detail_lines.append(f'')

            by_rec = defaultdict(list)
            for a in macts:
                by_rec[a['record']].append(a)

            for rec, ras in list(by_rec.items())[:10]:
                detail_lines.append(f'  📁 {rec}')

                # Group comments — show count only, not individual text
                comment_acts = [r for r in ras if 'comment' in r['action'].lower()]
                other_acts   = [r for r in ras if 'comment' not in r['action'].lower()]

                if comment_acts:
                    first_t = _tf(comment_acts[0]['ts'])
                    last_t  = _tf(comment_acts[-1]['ts'])
                    time_range = f'{first_t} – {last_t}' if first_t != last_t else first_t
                    detail_lines.append(f'     • 💬 {len(comment_acts)} Comment{"s" if len(comment_acts)>1 else ""} added  🕐 {time_range}')

                for ra in other_acts[:5]:
                    detail_lines.append(f'     • {ra["action"]}  🕐 {_tf(ra["ts"])}')
                    for dl in ra['detail'][:2]:
                        if dl.strip():
                            detail_lines.append(f'       {dl}')

        detail_lines.append('')

    # ── PASS 2: build summary (mod_totals now populated) ──
    summary_lines = [
        f'━━━━━━━━━━━━━━━━━━━━━━━━━━',
        f'📊 *Module-wise Summary*',
        f'┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄',
    ]
    for mod, _ in sorted(mod_totals.items(), key=lambda x: _mm(x[0])[1]):
        icon, label = _mm(mod)
        unique_recs = len(set(
            a['record'] for u in sorted_users
            for a in by_user[u] if a['mod'] == mod and a['record']
        ))
        unit   = UNIT_MAP.get(mod, 'Record')
        plural = f'{unit}s' if unique_recs != 1 else unit
        summary_lines.append(f'  {icon} {label}: *{unique_recs} {plural}*')
    summary_lines.append(f'━━━━━━━━━━━━━━━━━━━━━━━━━━')
    summary_lines.append('')

    # ── Final: employee header → summary → detail ──
    # Extract just the first line (👤 Name- Work Report) from each employee
    emp_headers = []
    for uid in sorted_users:
        uname = gname(uid)
        emp_headers.append(f'👤 *{uname}- Work Report - {day_str}*')
        emp_headers.append(f'━━━━━━━━━━━━━━━━━━━━━━━━━━')
        emp_headers.append('')

    lines = emp_headers + summary_lines + detail_lines
    lines += ['━━━━━━━━━━━━━━━━━━━━━━━━━━']
    return '\n'.join(lines)


# ─────────────────────────────────────────────────────────────
# Debug endpoint — check terminal for errors
# ─────────────────────────────────────────────────────────────

@daily_report_bp.route('/debug')
@login_required
def debug():
    """Visit /daily-report/debug to test comment fetching."""
    from models import db
    ts = datetime.combine(date.today(), datetime.min.time())
    te = datetime.combine(date.today(), datetime.max.time())
    result = {'status': 'ok', 'lead_comments': [], 'npd_comments': [], 'errors': []}

    try:
        from models import LeadDiscussion
        rows = LeadDiscussion.query.filter(
            LeadDiscussion.created_at >= ts,
            LeadDiscussion.created_at <= te
        ).all()
        result['lead_comments'] = [
            {'lead_id': r.lead_id, 'user_id': r.user_id,
             'comment': (r.comment or '')[:200], 'time': str(r.created_at)}
            for r in rows
        ]
    except Exception as e:
        result['errors'].append(f'lead_discussions: {e}')

    try:
        from models.npd import NPDComment
        rows = NPDComment.query.filter(
            NPDComment.created_at >= ts,
            NPDComment.created_at <= te
        ).all()
        result['npd_comments'] = [
            {'project_id': r.project_id, 'user_id': r.user_id,
             'comment': (r.comment or '')[:200], 'time': str(r.created_at)}
            for r in rows
        ]
    except Exception as e:
        result['errors'].append(f'npd_comments: {e}')

    return jsonify(result)


# ─────────────────────────────────────────────────────────────
# APIs
# ─────────────────────────────────────────────────────────────

@daily_report_bp.route('/api')
@login_required
def api_data():
    d   = request.args.get('date', date.today().isoformat())
    uid = request.args.get('user_id', '')
    try:
        fd = datetime.strptime(d, '%Y-%m-%d').date()
    except Exception:
        fd = date.today()
    fuid = int(uid) if uid.isdigit() else None
    msg  = build_message(fd, fuid)
    wa   = 'https://web.whatsapp.com/send?text=' + urllib.parse.quote(msg)
    return jsonify(ok=True, message=msg, wa_url=wa,
                   chars=len(msg), date=fd.strftime('%d %b %Y'))


@daily_report_bp.route('/api/users')
@login_required
def api_users():
    d = request.args.get('date', date.today().isoformat())
    try:
        fd = datetime.strptime(d, '%Y-%m-%d').date()
    except Exception:
        fd = date.today()
    acts = collect(fd)
    from models import User
    seen  = set()
    users = []
    for a in acts:
        if a['uid'] not in seen:
            seen.add(a['uid'])
            try:
                u = User.query.get(a['uid'])
                if u:
                    users.append({'id': a['uid'], 'name': u.full_name or u.username})
            except Exception:
                pass
    users.sort(key=lambda x: x['name'])
    return jsonify(ok=True, users=users)


# ─────────────────────────────────────────────────────────────
# Self-contained HTML page
# ─────────────────────────────────────────────────────────────

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Daily Work Report</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',sans-serif;background:#f0f2f5;min-height:100vh;padding:1rem}
.w{max-width:860px;margin:0 auto}
.hdr{background:linear-gradient(135deg,#1e2d5e,#7c3aed 55%,#25d366);border-radius:16px;
     padding:1.2rem 1.5rem;color:#fff;margin-bottom:1rem;
     display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:.6rem}
.hdr h1{font-size:1.1rem;font-weight:800;margin-bottom:3px}
.hdr p{font-size:.74rem;opacity:.85}
.bar{background:#fff;border:1px solid #e2e8f0;border-radius:11px;
     padding:.6rem .9rem;display:flex;align-items:center;gap:.65rem;flex-wrap:wrap;margin-bottom:.85rem}
.bar label{font-size:.73rem;font-weight:700;color:#64748b}
.bar input,.bar select{font-size:.79rem;border:1px solid #e2e8f0;border-radius:7px;
     padding:.3rem .6rem;outline:none;background:#f8fafc;color:#1e293b}
.bar input:focus,.bar select:focus{border-color:#25d366}
.chips{display:grid;grid-template-columns:repeat(3,1fr);gap:.6rem;margin-bottom:.85rem}
.chip{background:#fff;border:1px solid #e2e8f0;border-radius:11px;padding:.65rem .8rem;text-align:center}
.chip-n{font-size:1.5rem;font-weight:900;color:#1e293b;line-height:1}
.chip-l{font-size:.67rem;color:#94a3b8;margin-top:3px}
.card{background:#fff;border:1px solid #e2e8f0;border-radius:14px;overflow:hidden;
      margin-bottom:.85rem;box-shadow:0 1px 4px rgba(0,0,0,.06)}
.card-hdr{display:flex;align-items:center;justify-content:space-between;
           padding:.65rem 1rem;border-bottom:1px solid #f1f5f9;background:#fafafa}
.card-ttl{font-size:.84rem;font-weight:700;color:#1e293b}
.bdg{background:#dcfce7;color:#16a34a;border-radius:20px;padding:2px 9px;font-size:.67rem;font-weight:700}
.wa-bg{background:#e5ddd5;padding:.8rem;max-height:520px;overflow-y:auto}
.bubble{background:#fff;border-radius:0 12px 12px 12px;box-shadow:0 1px 2px rgba(0,0,0,.15);
        padding:.85rem 1rem;font-size:.77rem;line-height:1.75;color:#111;
        white-space:pre-wrap;word-break:break-word}
.btns{display:flex;gap:.6rem;padding:.85rem 1rem;border-top:1px solid #f1f5f9;flex-wrap:wrap}
.bwa{flex:1;display:inline-flex;align-items:center;justify-content:center;gap:.5rem;
     background:#25d366;color:#fff;border:none;border-radius:9px;padding:.6rem 1.2rem;
     font-size:.84rem;font-weight:700;cursor:pointer;text-decoration:none}
.bwa:hover{background:#128c7e}
.bcp{display:inline-flex;align-items:center;gap:.4rem;background:#f1f5f9;
     color:#475569;border:1px solid #e2e8f0;border-radius:9px;
     padding:.55rem 1rem;font-size:.8rem;font-weight:600;cursor:pointer}
.bcp.ok{background:#dcfce7;color:#16a34a;border-color:#86efac}
.sk{background:linear-gradient(90deg,#f1f5f9 25%,#e2e8f0 50%,#f1f5f9 75%);
    background-size:200% 100%;animation:sk 1.2s infinite;border-radius:5px;display:block}
@keyframes sk{0%{background-position:200% 0}100%{background-position:-200% 0}}
/* WhatsApp rendered */
.wh{font-weight:800;font-size:.85rem;display:block;margin:.55rem 0 .1rem;color:#111}
.wd{border-top:1px solid #ccc;margin:.35rem 0}
.wm{font-weight:700;font-size:.79rem;color:#374151;display:block;margin:.4rem 0 .05rem}
.wr{font-size:.78rem;font-weight:600;color:#1e293b;display:block;padding-left:.5rem}
.wa{font-size:.73rem;color:#059669;display:block;padding-left:1rem;font-weight:600}
.wc{font-size:.73rem;color:#1d4ed8;display:block;padding-left:1.8rem;font-style:italic;
    background:#eff6ff;border-left:3px solid #93c5fd;margin:.1rem 0 .1rem 1.5rem;
    padding:.2rem .5rem;border-radius:0 6px 6px 0}
.ws{font-weight:600;font-size:.78rem;color:#1e293b;display:block;margin:.1rem 0}
</style>
</head>
<body><div class="w">

<div class="hdr">
  <div>
    <h1>📋 Daily Work Report — Share</h1>
    <p>Sab teams, sab modules, actual comments — ek WhatsApp message</p>
  </div>
  <a href="/" style="background:rgba(255,255,255,.15);color:#fff;border:1px solid rgba(255,255,255,.3);
     border-radius:8px;padding:.38rem .8rem;font-size:.77rem;font-weight:600;text-decoration:none">
    ← Dashboard
  </a>
</div>

<div class="bar">
  <label>📅 Date:</label>
  <input type="date" id="fD" onchange="load()">
  <label>👤 Member:</label>
  <select id="fU" onchange="load()"><option value="">All Members</option></select>
  <span style="flex:1"></span>
  <span id="dlbl" style="font-size:.77rem;font-weight:700;color:#7c3aed"></span>
  <a href="/daily-report/debug" target="_blank"
     style="font-size:.7rem;color:#94a3b8;text-decoration:none">🔍 Debug</a>
</div>

<div class="chips" id="chips">
  <div class="chip"><span class="sk" style="width:40px;height:22px;margin:.1rem auto .3rem"></span><div class="chip-l">Members</div></div>
  <div class="chip"><span class="sk" style="width:40px;height:22px;margin:.1rem auto .3rem"></span><div class="chip-l">Actions</div></div>
  <div class="chip"><span class="sk" style="width:50px;height:22px;margin:.1rem auto .3rem"></span><div class="chip-l">Generated</div></div>
</div>

<div class="card">
  <div class="card-hdr">
    <div class="card-ttl">💬 Message Preview <span class="bdg">WhatsApp Ready</span></div>
    <span id="chars" style="font-size:.7rem;color:#94a3b8">—</span>
  </div>
  <div class="wa-bg">
    <div class="bubble" id="prev">
      <div style="display:flex;flex-direction:column;gap:7px">
        <span class="sk" style="width:65%;height:13px"></span>
        <span class="sk" style="width:45%;height:11px"></span>
        <span class="sk" style="width:80%;height:11px"></span>
        <span class="sk" style="width:70%;height:11px"></span>
        <span class="sk" style="width:55%;height:11px"></span>
        <span class="sk" style="width:85%;height:11px"></span>
      </div>
    </div>
  </div>
  <div class="btns">
    <a class="bwa" id="waBtn" href="#" target="_blank" rel="noopener">
      <svg viewBox="0 0 24 24" width="18" height="18" fill="currentColor">
        <path d="M17.472 14.382c-.297-.149-1.758-.867-2.03-.967-.273-.099-.471-.148-.67.15-.197.297-.767.966-.94 1.164-.173.199-.347.223-.644.075-.297-.15-1.255-.463-2.39-1.475-.883-.788-1.48-1.761-1.653-2.059-.173-.297-.018-.458.13-.606.134-.133.298-.347.446-.52.149-.174.198-.298.298-.497.099-.198.05-.371-.025-.52-.075-.149-.669-1.612-.916-2.207-.242-.579-.487-.5-.669-.51-.173-.008-.371-.01-.57-.01-.198 0-.52.074-.792.372-.272.297-1.04 1.016-1.04 2.479 0 1.462 1.065 2.875 1.213 3.074.149.198 2.096 3.2 5.077 4.487.709.306 1.262.489 1.694.625.712.227 1.36.195 1.871.118.571-.085 1.758-.719 2.006-1.413.248-.694.248-1.289.173-1.413-.074-.124-.272-.198-.57-.347m-5.421 7.403h-.004a9.87 9.87 0 01-5.031-1.378l-.361-.214-3.741.982.998-3.648-.235-.374a9.86 9.86 0 01-1.51-5.26c.001-5.45 4.436-9.884 9.888-9.884 2.64 0 5.122 1.03 6.988 2.898a9.825 9.825 0 012.893 6.994c-.003 5.45-4.437 9.884-9.885 9.884m8.413-18.297A11.815 11.815 0 0012.05 0C5.495 0 .16 5.335.157 11.892c0 2.096.547 4.142 1.588 5.945L.057 24l6.305-1.654a11.882 11.882 0 005.683 1.448h.005c6.554 0 11.89-5.335 11.893-11.893a11.821 11.821 0 00-3.48-8.413Z"/>
      </svg>
      Open WhatsApp Web & Send
    </a>
    <button class="bcp" id="cpBtn" onclick="copy()">📋 Copy Message</button>
  </div>
</div>

</div>
<script>
let _msg = '';
window.onload = () => {
  document.getElementById('fD').value = new Date().toISOString().split('T')[0];
  load();
};

function load() {
  const d = document.getElementById('fD').value;
  const u = document.getElementById('fU').value;
  if (!d) return;
  document.getElementById('prev').innerHTML = sk(8);
  document.getElementById('chars').textContent = '—';
  document.getElementById('dlbl').textContent  = '⏳';

  fetch('/daily-report/api/users?date=' + d)
    .then(r => r.json()).then(data => {
      if (!data.ok) return;
      const s = document.getElementById('fU'), cur = s.value;
      s.innerHTML = '<option value="">All Members</option>' +
        data.users.map(u =>
          `<option value="${u.id}"${String(u.id)===cur?' selected':''}>${E(u.name)}</option>`
        ).join('');
    }).catch(() => {});

  fetch('/daily-report/api?date=' + d + (u ? '&user_id=' + u : ''))
    .then(r => r.json()).then(data => {
      if (!data.ok) {
        document.getElementById('prev').innerHTML =
          '<span style="color:#dc2626">Error — check terminal for details</span>';
        return;
      }
      _msg = data.message;
      document.getElementById('prev').innerHTML  = render(data.message);
      document.getElementById('waBtn').href      = data.wa_url;
      document.getElementById('chars').textContent = data.chars.toLocaleString() + ' chars';
      document.getElementById('dlbl').textContent  = data.date;

      const ml = (data.message.match(/^👤/gm) || []).length;
      const al = data.message.match(/👥 (\d+) members.*?(\d+) total/m);
      document.getElementById('chips').innerHTML = `
        <div class="chip"><div class="chip-n">${ml}</div><div class="chip-l">Members Active</div></div>
        <div class="chip"><div class="chip-n">${al ? al[2] : 0}</div><div class="chip-l">Total Actions</div></div>
        <div class="chip"><div class="chip-n">${new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'})}</div><div class="chip-l">Generated</div></div>`;
    }).catch(() => {
      document.getElementById('prev').innerHTML =
        '<span style="color:#dc2626">Network error — server chal raha hai? Terminal check karo.</span>';
    });
}

function render(txt) {
  return txt.split('\n').map(line => {
    line = line
      .replace(/\*([^*\n]+)\*/g, '<strong>$1</strong>')
      .replace(/_([^_\n]+)_/g,   '<em style="color:#555">$1</em>');
    const t = line.trim();
    if (/^━+$/.test(t) || /^─+$/.test(t)) return '<span class="wd"></span>';
    if (/^👤/.test(t))   return `<span class="wh">${t}</span>`;
    if (/^[📋🏢💼📦🧫✅👥🧪🎯💬🏭📧📌]/.test(t)) return `<span class="wm">${t}</span>`;
    if (t.startsWith('  •'))  return `<span class="wr">${t}</span>`;
    if (t.startsWith('    ↳')) return `<span class="wa">${t}</span>`;
    // Comment lines (💬) — highlighted blue
    if (t.startsWith('       💬')) return `<span class="wc">${t.replace('       ','')}</span>`;
    if (t.startsWith('       '))  return `<span style="display:block;font-size:.71rem;color:#6b7280;padding-left:2rem">${t}</span>`;
    if (/^[📊🏆]/.test(t)) return `<span class="ws">${t}</span>`;
    if (!t) return '<span style="display:block;height:.2rem"></span>';
    return `<span style="display:block;font-size:.78rem;color:#374151">${t}</span>`;
  }).join('');
}

function copy() {
  if (!_msg) return;
  const b = document.getElementById('cpBtn');
  navigator.clipboard && navigator.clipboard.writeText(_msg).then(() => {
    b.classList.add('ok'); b.textContent = '✅ Copied!';
    setTimeout(() => { b.classList.remove('ok'); b.textContent = '📋 Copy Message'; }, 2500);
  });
}

function sk(n) {
  const w = [55,80,65,90,70,45,85,60];
  return '<div style="display:flex;flex-direction:column;gap:7px">' +
    Array.from({length:n}, (_, i) =>
      `<span class="sk" style="width:${w[i%w.length]}%;height:12px"></span>`
    ).join('') + '</div>';
}
function E(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}
</script>
</body></html>"""

@daily_report_bp.route('/')
@login_required
def page():
    return Response(PAGE, mimetype='text/html')
