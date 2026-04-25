"""
client_dispatch_routes.py — Send Approved Samples to Client
============================================================
Blueprint:  client_dispatch  at  /client-dispatch

Workflow:
  1. After Office approval (approval_status='approved' on
     OfficeDispatchItem), items become eligible for client dispatch.
  2. Operator selects a project from the list, picks one or more
     approved items via checkboxes, fills tracking details, hits
     "Send to Client".
  3. System:
     - Creates a ClientDispatch row (token, tracking)
     - Stamps each selected item with client_dispatch_id +
       sent_to_client_at
     - Updates project.status = 'sent_to_client'
     - Sends email (if address provided) using Gmail-like SMTP
     - Returns a wa.me URL the user can click to open WhatsApp with
       the pre-filled message (browser opens contact picker)

Endpoints:
  GET  /client-dispatch/                        Main list page
  GET  /client-dispatch/api/projects            List of projects with
                                                pending approved items
  GET  /client-dispatch/api/project/<pid>/items List of approved items
                                                (eligible to dispatch)
  POST /client-dispatch/api/send                Dispatch selected items
  GET  /client-dispatch/history                 Dispatch history page
  GET  /client-dispatch/api/history             JSON list of dispatches
"""

from datetime import datetime
from flask import (Blueprint, render_template, request, jsonify,
                   current_app, url_for)
from flask_login import login_required, current_user

from models import db, User
from models.npd import (NPDProject, OfficeDispatchItem,
                        ClientDispatch, NPDActivityLog, RDProjectLog)


client_dispatch_bp = Blueprint(
    'client_dispatch',
    __name__,
    url_prefix='/client-dispatch'
)


# ═══════════════════════════════════════════════════════════════════
# Helpers
# ═══════════════════════════════════════════════════════════════════

def _gen_token_no():
    """Generate next CDT-XXXX token number."""
    last = ClientDispatch.query.order_by(ClientDispatch.id.desc()).first()
    nxt = (last.id + 1) if last else 1
    return f'CDT-{nxt:04d}'


def _build_email_subject_and_body(project, items, courier_name, tracking_no, extra_notes):
    """
    Build email subject + HTML body using the editable Mail Master
    template (`code='sample_dispatch'`). Admin can customize via
    /mail/master without touching code.

    Falls back to a hardcoded body if the template isn't found / DB
    error — system still works during initial setup.
    """
    sender_name = (
        current_user.full_name if current_user.is_authenticated else 'Administrator'
    )
    try:
        from mail_routes import (
            _get_or_create_sample_dispatch_template,
            _render_sample_dispatch_vars,
        )
        t = _get_or_create_sample_dispatch_template()
        subject = _render_sample_dispatch_vars(
            t.subject, project, items, courier_name, tracking_no,
            extra_notes, sender_name,
        )
        body = _render_sample_dispatch_vars(
            t.body, project, items, courier_name, tracking_no,
            extra_notes, sender_name,
        )
        return subject, body
    except Exception as _ex:
        import traceback; traceback.print_exc()
        # Fallback — minimal hardcoded body so dispatch still works
        return (
            f"Sample Dispatch Details – {project.code}",
            _build_email_body_fallback(project, items, courier_name,
                                        tracking_no, extra_notes),
        )


def _build_email_body_fallback(project, items, courier_name, tracking_no, extra_notes):
    """Hardcoded HTML — used only if mail template lookup fails."""
    sample_lines_html = ''
    for it in items:
        code = it.sample_code or '—'
        product = project.product_name or ''
        sample_lines_html += (
            f'<li style="margin:4px 0;">{code} – {product}</li>'
        )

    if tracking_no and courier_name:
        tracking_line = f'{tracking_no} ({courier_name})'
    elif tracking_no:
        tracking_line = tracking_no
    elif courier_name:
        tracking_line = courier_name
    else:
        tracking_line = '—'

    notes_block = ''
    if extra_notes:
        notes_block = (
            f'<p style="margin:14px 0 0;color:#374151;">'
            f'<strong>Note:</strong> {extra_notes}</p>'
        )

    client_name = (
        project.client_name or project.client_company or 'Sir/Madam'
    )

    return f"""
<html><body style="font-family:Arial,sans-serif;font-size:14px;color:#333;line-height:1.6;">
<p>Dear <strong>{client_name}</strong>,</p>
<p>Greetings from HCP Wellness.</p>
<p>We have dispatched the samples for the above-mentioned project.
Please find the tracking details below:</p>
<p style="margin:14px 0;">
  <strong>Tracking Details:</strong> {tracking_line}
</p>
<p>We request you to kindly acknowledge receipt of the samples upon
delivery and share your feedback at the earliest to help us proceed
further.</p>
<p>Looking forward to your response.</p>
<ul style="margin:14px 0;padding-left:24px;">
  {sample_lines_html}
</ul>
{notes_block}
<p style="margin-top:24px;color:#6b7280;font-size:12px;">
— HCP Wellness Pvt. Ltd.
</p>
</body></html>
""".strip()


def _build_email_body(project, items, courier_name, tracking_no, extra_notes):
    """Backward-compat wrapper — returns body HTML only."""
    _, body = _build_email_subject_and_body(
        project, items, courier_name, tracking_no, extra_notes
    )
    return body


def _build_whatsapp_text(project, items, tracking_no, courier_name):
    """Render the dispatch WhatsApp message — exact spec format."""
    client_name = (
        project.client_name or project.client_company or 'Sir/Madam'
    )

    # Tracking line — clear format: "Courier: <name>, Tracking: <no.>"
    parts = []
    if courier_name:
        parts.append(f'*Courier:* {courier_name}')
    if tracking_no:
        parts.append(f'*Tracking No.:* {tracking_no}')
    if not parts:
        tracking_block = '*Tracking Details:* —'
    else:
        tracking_block = '\n'.join(parts)

    sample_lines = '\n'.join(
        f'• {(it.sample_code or "—")} – {project.product_name or ""}'
        for it in items
    )

    return (
        f'Dear {client_name},\n\n'
        f'Greetings from HCP Wellness.\n\n'
        f'We have dispatched the samples for the above-mentioned project. '
        f'Please find the tracking details below:\n\n'
        f'{tracking_block}\n\n'
        f'We request you to kindly acknowledge receipt of the samples upon '
        f'delivery and share your feedback at the earliest to help us '
        f'proceed further.\n'
        f'Looking forward to your response.\n\n'
        f'{sample_lines}\n\n'
        f'— HCP Wellness'
    )


def _send_email(to_email, subject, html_body):
    """Send email via app's SMTP config. Returns (ok: bool, error: str)."""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    cfg = current_app.config
    if not cfg.get('MAIL_SERVER') or not cfg.get('MAIL_PORT'):
        return False, 'Mail server not configured.'

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = (
            'HCP Wellness Pvt. Ltd. '
            f'<{cfg.get("MAIL_USERNAME","info@hcpwellness.in")}>'
        )
        msg['To']      = to_email
        msg['Reply-To']= cfg.get('MAIL_USERNAME', 'info@hcpwellness.in')
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        server = smtplib.SMTP(cfg['MAIL_SERVER'], cfg['MAIL_PORT'], timeout=20)
        server.ehlo()
        if cfg.get('MAIL_USE_TLS'):
            server.starttls()
        if cfg.get('MAIL_USERNAME') and cfg.get('MAIL_PASSWORD'):
            server.login(cfg['MAIL_USERNAME'], cfg['MAIL_PASSWORD'])
        server.sendmail(msg['From'], [to_email], msg.as_string())
        server.quit()
        return True, ''
    except Exception as e:
        import traceback; traceback.print_exc()
        return False, str(e)


# ═══════════════════════════════════════════════════════════════════
# Pages
# ═══════════════════════════════════════════════════════════════════

@client_dispatch_bp.route('/')
@login_required
def index():
    """Main page — list of projects with approved items pending client dispatch."""
    return render_template('client_dispatch/index.html')


@client_dispatch_bp.route('/history')
@login_required
def history():
    """Past dispatches log."""
    return render_template('client_dispatch/history.html')


# ═══════════════════════════════════════════════════════════════════
# API: Projects with pending approved items
# ═══════════════════════════════════════════════════════════════════

@client_dispatch_bp.route('/api/projects')
@login_required
def api_projects():
    """
    List of projects that have at least one OfficeDispatchItem with
    approval_status='approved' AND client_dispatch_id IS NULL (i.e.
    not yet sent to client).
    """
    # Subquery — distinct project_ids with pending approved items
    subq = db.session.query(
        OfficeDispatchItem.project_id,
        db.func.count(OfficeDispatchItem.id).label('pending_count'),
    ).filter(
        OfficeDispatchItem.approval_status == 'approved',
        OfficeDispatchItem.client_dispatch_id.is_(None),
    ).group_by(OfficeDispatchItem.project_id).subquery()

    rows = db.session.query(
        NPDProject, subq.c.pending_count
    ).join(subq, NPDProject.id == subq.c.project_id) \
     .filter(NPDProject.is_deleted == False) \
     .order_by(NPDProject.id.desc()).all()

    out = []
    for p, cnt in rows:
        out.append({
            'id'           : p.id,
            'code'         : p.code,
            'product_name' : p.product_name or '',
            'client_name'  : p.client_name or p.client_company or '',
            'client_email' : p.client_email or '',
            'client_phone' : p.client_phone or '',
            'status'       : p.status or '',
            'pending_count': int(cnt),
        })
    return jsonify(success=True, projects=out)


# ═══════════════════════════════════════════════════════════════════
# API: Approved items for a specific project
# ═══════════════════════════════════════════════════════════════════

@client_dispatch_bp.route('/api/project/<int:pid>/items')
@login_required
def api_project_items(pid):
    """All approved-but-not-yet-sent items for the given project."""
    proj = NPDProject.query.get_or_404(pid)
    items = OfficeDispatchItem.query.filter(
        OfficeDispatchItem.project_id == pid,
        OfficeDispatchItem.approval_status == 'approved',
        OfficeDispatchItem.client_dispatch_id.is_(None),
    ).order_by(OfficeDispatchItem.id.desc()).all()

    out = []
    for it in items:
        out.append({
            'id'         : it.id,
            'sample_code': it.sample_code or '',
            'submitted_by': it.submitted_by or '',
            'handover_to' : it.handover_to or '',
            'actioned_by' : (it.actioner.full_name if it.actioner else ''),
            'actioned_at' : (
                it.actioned_at.strftime('%d-%m-%Y %I:%M %p')
                if it.actioned_at else ''
            ),
        })
    return jsonify(
        success      = True,
        project = {
            'id'          : proj.id,
            'code'        : proj.code,
            'product_name': proj.product_name or '',
            'client_name' : proj.client_name or proj.client_company or '',
            'client_email': proj.client_email or '',
            'client_phone': proj.client_phone or '',
        },
        items = out,
    )


# ═══════════════════════════════════════════════════════════════════
# API: Send selected items to client
# ═══════════════════════════════════════════════════════════════════

@client_dispatch_bp.route('/api/send', methods=['POST'])
@login_required
def api_send():
    """
    Body:
      {
        project_id   : int,
        item_ids     : [int, int, ...]  (must all be approved + unsent),
        courier_name : str,
        tracking_no  : str,
        notes        : str,
        to_email     : str  (override; defaults to project.client_email),
        send_email   : bool (default true if to_email present),
        send_whatsapp: bool (default true; returns wa_url)
      }
    """
    try:
        data        = request.get_json(silent=True) or {}
        pid         = int(data.get('project_id') or 0)
        item_ids    = data.get('item_ids') or []
        courier     = (data.get('courier_name') or '').strip()
        tracking    = (data.get('tracking_no')  or '').strip()
        notes       = (data.get('notes')        or '').strip()
        to_email    = (data.get('to_email')     or '').strip()
        send_email  = bool(data.get('send_email', True))
        send_wa     = bool(data.get('send_whatsapp', True))

        if not pid:
            return jsonify(success=False, error='project_id required'), 400
        if not item_ids:
            return jsonify(success=False, error='Select at least one sample'), 400
        if not courier:
            return jsonify(success=False,
                error='Courier name is required.'), 400
        if not tracking:
            return jsonify(success=False,
                error='Tracking number is required.'), 400

        proj = NPDProject.query.get(pid)
        if not proj:
            return jsonify(success=False, error='Project not found'), 404

        # Default email to project client_email
        if send_email and not to_email:
            to_email = (proj.client_email or '').strip()

        # Fetch + validate items
        items = OfficeDispatchItem.query.filter(
            OfficeDispatchItem.id.in_(item_ids),
            OfficeDispatchItem.project_id == pid,
        ).all()
        if len(items) != len(item_ids):
            return jsonify(success=False,
                error='Some items not found or belong to another project'), 400

        bad = [i.id for i in items
               if i.approval_status != 'approved' or i.client_dispatch_id]
        if bad:
            return jsonify(success=False,
                error=f'Items {bad} are not eligible (not approved or already sent)'), 400

        now = datetime.now()

        # Create dispatch token
        cd = ClientDispatch(
            token_no      = _gen_token_no(),
            project_id    = pid,
            courier_name  = courier or None,
            tracking_no   = tracking or None,
            extra_notes   = notes or None,
            email_sent_to = to_email if (send_email and to_email) else None,
            whatsapp_sent = bool(send_wa),
            dispatched_by = current_user.id,
            dispatched_at = now,
        )
        db.session.add(cd)
        db.session.flush()    # need cd.id

        # Stamp items
        for it in items:
            it.client_dispatch_id = cd.id
            it.sent_to_client_at  = now

        # Project status → sent_to_client
        proj.status = 'sent_to_client'

        # Audit logs
        sample_str = ', '.join(it.sample_code or '?' for it in items)
        db.session.add(NPDActivityLog(
            project_id = pid,
            user_id    = current_user.id,
            action     = (
                f"Sent to client: {len(items)} samples ({sample_str}) "
                f"| Token: {cd.token_no} "
                f"| Tracking: {tracking or '—'} "
                f"| Courier: {courier or '—'}"
            ),
            created_at = now,
        ))
        db.session.add(RDProjectLog(
            project_id = pid,
            user_id    = current_user.id,
            event      = 'sent_to_client',
            detail     = (
                f"Token {cd.token_no}: {len(items)} samples sent to client. "
                f"Tracking: {tracking or '—'}"
            ),
            created_at = now,
        ))

        # ── Send Email ──
        email_ok, email_err = True, ''
        if send_email and to_email:
            subject, html = _build_email_subject_and_body(
                proj, items, courier, tracking, notes
            )
            email_ok, email_err = _send_email(to_email, subject, html)
            if email_ok:
                cd.email_sent_at = datetime.now()
            else:
                # Keep dispatch saved even if email fails — admin can resend
                cd.email_sent_to = None

        # ── Build WhatsApp URL ──
        wa_url = ''
        if send_wa:
            wa_text = _build_whatsapp_text(proj, items, tracking, courier)
            phone   = (proj.client_phone or '').strip()
            # Normalise phone: digits only, prepend country code if missing
            digits = ''.join(c for c in phone if c.isdigit())
            if digits:
                if len(digits) == 10:        # bare Indian mobile
                    digits = '91' + digits
                wa_url = f'https://wa.me/{digits}?text='
            else:
                wa_url = 'https://wa.me/?text='     # contact picker
            from urllib.parse import quote
            wa_url += quote(wa_text)

        db.session.commit()

        return jsonify(
            success     = True,
            token_no    = cd.token_no,
            dispatched_at = now.strftime('%d-%m-%Y %I:%M %p'),
            email_ok    = email_ok,
            email_err   = email_err,
            wa_url      = wa_url,
        )

    except Exception as e:
        db.session.rollback()
        import traceback; traceback.print_exc()
        return jsonify(success=False, error=f'Server error: {e}'), 500


# ═══════════════════════════════════════════════════════════════════
# API: Build WhatsApp message + URL (preview / share — no save)
# ═══════════════════════════════════════════════════════════════════

@client_dispatch_bp.route('/api/build-whatsapp', methods=['POST'])
@login_required
def api_build_whatsapp():
    """
    Build the WhatsApp share URL + text for the given project + items.
    Does NOT persist anything — just renders the message. Useful for
    "📱 Send WhatsApp" button when user wants to share via WhatsApp Web
    (separate flow from email).

    Body:
      {
        project_id   : int,
        item_ids     : [int, ...],
        courier_name : str,
        tracking_no  : str,
      }
    """
    try:
        data        = request.get_json(silent=True) or {}
        pid         = int(data.get('project_id') or 0)
        item_ids    = data.get('item_ids') or []
        courier     = (data.get('courier_name') or '').strip()
        tracking    = (data.get('tracking_no')  or '').strip()

        if not pid or not item_ids:
            return jsonify(success=False,
                error='project_id and item_ids required'), 400

        proj = NPDProject.query.get(pid)
        if not proj:
            return jsonify(success=False, error='Project not found'), 404

        items = OfficeDispatchItem.query.filter(
            OfficeDispatchItem.id.in_(item_ids),
            OfficeDispatchItem.project_id == pid,
        ).all()
        if not items:
            return jsonify(success=False, error='No matching items'), 400

        text = _build_whatsapp_text(proj, items, tracking, courier)

        # Build wa.me URL — phone normalization
        from urllib.parse import quote
        phone = (proj.client_phone or '').strip()
        digits = ''.join(c for c in phone if c.isdigit())
        if digits:
            if len(digits) == 10:        # bare Indian mobile
                digits = '91' + digits
            wa_url      = f'https://wa.me/{digits}?text=' + quote(text)
            wa_web_url  = f'https://web.whatsapp.com/send?phone={digits}&text=' + quote(text)
        else:
            # Empty / invalid phone → contact picker mode
            wa_url      = 'https://wa.me/?text=' + quote(text)
            wa_web_url  = 'https://web.whatsapp.com/send?text=' + quote(text)

        return jsonify(
            success    = True,
            text       = text,
            wa_url     = wa_url,        # mobile / native
            wa_web_url = wa_web_url,    # WhatsApp Web (desktop)
            phone      = digits or '',
        )

    except Exception as e:
        import traceback; traceback.print_exc()
        return jsonify(success=False, error=f'Server error: {e}'), 500


# ═══════════════════════════════════════════════════════════════════
# API: Send Email for an EXISTING dispatch (from history page)
# ═══════════════════════════════════════════════════════════════════

@client_dispatch_bp.route('/api/<int:cid>/send-email', methods=['POST'])
@login_required
def api_send_email_existing(cid):
    """Trigger email for an already-saved dispatch.

    Used by the History page's 📧 Send Email button. Email body is
    rendered from the editable Mail Master template (`sample_dispatch`).
    """
    try:
        cd = ClientDispatch.query.get(cid)
        if not cd:
            return jsonify(success=False, error='Dispatch not found'), 404

        proj = cd.project
        if not proj:
            return jsonify(success=False, error='Project not found'), 404

        # Optional override email from request
        data     = request.get_json(silent=True) or {}
        to_email = (data.get('to_email') or '').strip() or \
                   (cd.email_sent_to or proj.client_email or '').strip()

        if not to_email:
            return jsonify(success=False,
                error='No email address available for this client'), 400

        items = list(cd.items)
        if not items:
            return jsonify(success=False,
                error='No items linked to this dispatch'), 400

        subject, html = _build_email_subject_and_body(
            proj, items, cd.courier_name or '', cd.tracking_no or '',
            cd.extra_notes or ''
        )
        ok, err = _send_email(to_email, subject, html)
        if not ok:
            return jsonify(success=False, error=err or 'Email send failed'), 500

        cd.email_sent_to = to_email
        cd.email_sent_at = datetime.now()
        db.session.add(NPDActivityLog(
            project_id = proj.id,
            user_id    = current_user.id,
            action     = f"Email sent to {to_email} for dispatch {cd.token_no} by {current_user.full_name}",
            created_at = datetime.now(),
        ))
        db.session.commit()

        return jsonify(
            success     = True,
            email_sent_to = to_email,
            email_sent_at = cd.email_sent_at.strftime('%d-%m-%Y %I:%M %p'),
        )
    except Exception as e:
        db.session.rollback()
        import traceback; traceback.print_exc()
        return jsonify(success=False, error=f'Server error: {e}'), 500


# ═══════════════════════════════════════════════════════════════════
# API: Build WhatsApp URL for an EXISTING dispatch (from history page)
# ═══════════════════════════════════════════════════════════════════

@client_dispatch_bp.route('/api/<int:cid>/whatsapp-url')
@login_required
def api_whatsapp_url_existing(cid):
    """Return WhatsApp Web URL pre-filled for an existing dispatch."""
    try:
        cd = ClientDispatch.query.get(cid)
        if not cd:
            return jsonify(success=False, error='Dispatch not found'), 404

        proj = cd.project
        items = list(cd.items)
        if not proj or not items:
            return jsonify(success=False, error='Missing project/items'), 400

        text = _build_whatsapp_text(
            proj, items, cd.tracking_no or '', cd.courier_name or ''
        )

        from urllib.parse import quote
        phone = (proj.client_phone or '').strip()
        digits = ''.join(c for c in phone if c.isdigit())
        if digits:
            if len(digits) == 10:
                digits = '91' + digits
            wa_url     = f'https://wa.me/{digits}?text=' + quote(text)
            wa_web_url = f'https://web.whatsapp.com/send?phone={digits}&text=' + quote(text)
        else:
            wa_url     = 'https://wa.me/?text=' + quote(text)
            wa_web_url = 'https://web.whatsapp.com/send?text=' + quote(text)

        # Mark whatsapp_sent flag on first request (best-effort)
        if not cd.whatsapp_sent:
            cd.whatsapp_sent = True
            db.session.add(NPDActivityLog(
                project_id = proj.id,
                user_id    = current_user.id,
                action     = f"WhatsApp opened for dispatch {cd.token_no} by {current_user.full_name}",
                created_at = datetime.now(),
            ))
            db.session.commit()

        return jsonify(
            success    = True,
            text       = text,
            wa_url     = wa_url,
            wa_web_url = wa_web_url,
            phone      = digits or '',
        )
    except Exception as e:
        db.session.rollback()
        import traceback; traceback.print_exc()
        return jsonify(success=False, error=f'Server error: {e}'), 500


# ═══════════════════════════════════════════════════════════════════
# API: Dispatch history (past sends)
# ═══════════════════════════════════════════════════════════════════
@client_dispatch_bp.route('/api/history')
@login_required
def api_history():
    """List past client dispatches, newest first."""
    rows = ClientDispatch.query.order_by(
        ClientDispatch.dispatched_at.desc()
    ).limit(200).all()
    out = []
    for r in rows:
        out.append({
            'id'            : r.id,
            'token_no'      : r.token_no,
            'project_code'  : r.project.code if r.project else '',
            'product_name'  : r.project.product_name if r.project else '',
            'client_name'   : (r.project.client_name or r.project.client_company)
                              if r.project else '',
            'client_email'  : (r.project.client_email or '') if r.project else '',
            'client_phone'  : (r.project.client_phone or '') if r.project else '',
            'courier_name'  : r.courier_name or '',
            'tracking_no'   : r.tracking_no or '',
            'item_count'    : len(r.items),
            'sample_codes'  : ', '.join(it.sample_code or '?' for it in r.items),
            'email_sent_to' : r.email_sent_to or '',
            'email_sent_at' : (r.email_sent_at.strftime('%d-%m-%Y %I:%M %p')
                               if r.email_sent_at else ''),
            'whatsapp_sent' : bool(r.whatsapp_sent),
            'dispatched_by' : r.dispatcher.full_name if r.dispatcher else '',
            'dispatched_at' : r.dispatched_at.strftime('%d-%m-%Y %I:%M %p'),
        })
    return jsonify(success=True, dispatches=out)


# ═══════════════════════════════════════════════════════════════════
# API: Revert a client dispatch (undo "Send to Client")
# ═══════════════════════════════════════════════════════════════════

@client_dispatch_bp.route('/api/<int:cid>/revert', methods=['POST'])
@login_required
def api_revert(cid):
    """
    Undo a client dispatch:
      - Clear client_dispatch_id + sent_to_client_at on each linked item
      - Delete the ClientDispatch row itself (token disappears)
      - Recompute project status — usually goes back to 'approved_by_office'

    Note: email already sent to client cannot be "unsent" — but the
    operator can re-send if needed. Audit log is preserved.
    """
    try:
        cd = ClientDispatch.query.get(cid)
        if not cd:
            return jsonify(success=False, error='Dispatch not found'), 404

        pid = cd.project_id
        token = cd.token_no
        item_count = len(cd.items)
        sample_codes = ', '.join(it.sample_code or '?' for it in cd.items)

        # Unstamp items
        for it in cd.items:
            it.client_dispatch_id = None
            it.sent_to_client_at  = None

        # Delete dispatch row
        db.session.delete(cd)
        db.session.flush()

        # Audit log
        db.session.add(NPDActivityLog(
            project_id = pid,
            user_id    = current_user.id,
            action     = (
                f"Client dispatch REVERTED: token {token} ({item_count} samples) "
                f"by {current_user.full_name}. Samples: {sample_codes}"
            ),
            created_at = datetime.now(),
        ))
        db.session.add(RDProjectLog(
            project_id = pid,
            user_id    = current_user.id,
            event      = 'dispatch_reverted',
            detail     = f"Client dispatch token {token} reverted. {item_count} samples returned to approved state.",
            created_at = datetime.now(),
        ))

        # Reset project status — was 'sent_to_client', go back to
        # 'approved_by_office' (since items are still approved, just not dispatched)
        from models.npd import NPDProject
        proj = NPDProject.query.get(pid)
        if proj and proj.status == 'sent_to_client':
            proj.status = 'approved_by_office'

        db.session.commit()
        return jsonify(
            success     = True,
            project_id  = pid,
            new_status  = 'approved_by_office',
            samples_returned = item_count,
        )

    except Exception as e:
        db.session.rollback()
        import traceback; traceback.print_exc()
        return jsonify(success=False, error=f'Server error: {e}'), 500
