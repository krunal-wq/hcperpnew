"""
npd_whatsapp_routes.py
───────────────────────
WhatsApp Admin Config + Manual Send Trigger routes.

URLs (add to existing npd_report_bp or register separately):
  GET  /npd/whatsapp-config          → Config admin page (embedded in dashboard)
  GET  /npd/api/whatsapp-config      → Get current config JSON
  POST /npd/api/whatsapp-config      → Save config
  POST /npd/api/whatsapp-test        → Send test message
  POST /npd/api/send-whatsapp-now    → Manual "Send Now" trigger
  GET  /npd/api/whatsapp-send-logs   → Send history
"""

import json
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required, current_user

# Uses the same blueprint as the dashboard
from npd_daily_report_routes import npd_report_bp


# ─────────────────────────────────────────────────────────────
# GET / SAVE CONFIG
# ─────────────────────────────────────────────────────────────

@npd_report_bp.route('/api/whatsapp-config', methods=['GET'])
@login_required
def api_get_whatsapp_config():
    """Return current WhatsApp config (tokens masked)."""
    from models import db
    from models.npd_daily_report import NPDWhatsAppConfig

    row = NPDWhatsAppConfig.query.first()
    if not row:
        return jsonify({'ok': True, 'config': {
            'provider': 'ultramsg', 'is_enabled': False,
            'instance_id': '', 'api_token': '',
            'country_code': '+91', 'send_time': '21:00',
            'send_to_manager': True, 'send_to_employees': True,
            'manager_numbers': [],
        }})

    return jsonify({'ok': True, 'config': {
        'provider':           row.provider or 'ultramsg',
        'is_enabled':         bool(row.is_enabled),
        'instance_id':        row.instance_id or '',
        'api_token':          _mask(row.api_token),
        'twilio_account_sid': _mask(row.twilio_account_sid),
        'twilio_auth_token':  _mask(row.twilio_auth_token),
        'twilio_from_number': row.twilio_from_number or '',
        'country_code':       row.country_code or '+91',
        'send_time':          row.send_time or '21:00',
        'send_to_manager':    bool(row.send_to_manager),
        'send_to_employees':  bool(row.send_to_employees),
        'manager_numbers':    json.loads(row.manager_numbers or '[]'),
    }})


@npd_report_bp.route('/api/whatsapp-config', methods=['POST'])
@login_required
def api_save_whatsapp_config():
    """Save WhatsApp config. Non-empty masked values ('••••') are preserved."""
    from models import db
    from models.npd_daily_report import NPDWhatsAppConfig

    data = request.get_json(silent=True) or {}

    row = NPDWhatsAppConfig.query.first()
    if not row:
        row = NPDWhatsAppConfig(id=1)
        db.session.add(row)

    row.provider         = data.get('provider', 'ultramsg')
    row.is_enabled       = bool(data.get('is_enabled', False))
    row.country_code     = data.get('country_code', '+91')
    row.send_time        = data.get('send_time', '21:00')
    row.send_to_manager  = bool(data.get('send_to_manager', True))
    row.send_to_employees= bool(data.get('send_to_employees', True))
    row.updated_by       = current_user.id

    mgr_nums = data.get('manager_numbers', [])
    if isinstance(mgr_nums, str):
        mgr_nums = [n.strip() for n in mgr_nums.split(',') if n.strip()]
    row.manager_numbers = json.dumps(mgr_nums)

    # Only overwrite tokens if user sent a real (unmasked) value
    def _update_secret(field_name, new_val, old_val):
        if new_val and '•' not in new_val:
            return new_val
        return old_val   # keep existing

    row.instance_id         = _update_secret('instance_id',        data.get('instance_id', ''),        row.instance_id)
    row.api_token           = _update_secret('api_token',          data.get('api_token', ''),          row.api_token)
    row.twilio_account_sid  = _update_secret('twilio_account_sid', data.get('twilio_account_sid', ''), row.twilio_account_sid)
    row.twilio_auth_token   = _update_secret('twilio_auth_token',  data.get('twilio_auth_token', ''),  row.twilio_auth_token)
    row.twilio_from_number  = data.get('twilio_from_number', row.twilio_from_number or '')

    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'ok': False, 'error': str(e)}), 500

    # Reschedule APScheduler if send_time changed
    try:
        from flask import current_app
        sched = getattr(current_app, '_npd_wa_scheduler', None)
        if sched:
            from npd_whatsapp_auto import reschedule_whatsapp_job
            reschedule_whatsapp_job(sched, row.send_time)
    except Exception:
        pass

    return jsonify({'ok': True, 'message': 'Config saved successfully!'})


# ─────────────────────────────────────────────────────────────
# TEST CONNECTION
# ─────────────────────────────────────────────────────────────

@npd_report_bp.route('/api/whatsapp-test', methods=['POST'])
@login_required
def api_whatsapp_test():
    """
    Send a test WhatsApp message to verify credentials.
    POST JSON: {"test_number": "+919876543210"}
    """
    data = request.get_json(silent=True) or {}
    test_num = data.get('test_number', '').strip()
    if not test_num:
        return jsonify({'ok': False, 'error': 'test_number is required'}), 400

    from whatsapp_sender import WhatsAppConfig, test_connection
    cfg = WhatsAppConfig.from_db()
    if not cfg.instance_id and not cfg.account_sid:
        return jsonify({'ok': False, 'error': 'No credentials configured yet. Save config first.'}), 400

    # Temporarily enable for test
    cfg.enabled = True
    result = test_connection(cfg, test_num)
    return jsonify(result)


# ─────────────────────────────────────────────────────────────
# MANUAL "SEND NOW" TRIGGER
# ─────────────────────────────────────────────────────────────

@npd_report_bp.route('/api/send-whatsapp-now', methods=['POST'])
@login_required
def api_send_whatsapp_now():
    """
    Manually trigger the daily WhatsApp send (for testing or ad-hoc sends).
    POST JSON: {"date": "YYYY-MM-DD"}   (optional — defaults to today)
    """
    from flask import current_app
    data     = request.get_json(silent=True) or {}
    date_str = data.get('date', date.today().isoformat())

    try:
        for_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        return jsonify({'ok': False, 'error': 'Invalid date'}), 400

    from npd_whatsapp_auto import send_daily_reports
    try:
        result = send_daily_reports(
            app        = current_app._get_current_object(),
            for_date   = for_date,
            triggered_by = current_user.id,
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'ok': False, 'error': str(e)}), 500


# ─────────────────────────────────────────────────────────────
# SEND LOGS
# ─────────────────────────────────────────────────────────────

@npd_report_bp.route('/api/whatsapp-send-logs')
@login_required
def api_whatsapp_send_logs():
    """
    Retrieve send log for a date.
    GET ?date=YYYY-MM-DD&days=7
    """
    from models.npd_daily_report import NPDWhatsAppSendLog

    days     = int(request.args.get('days', 7))
    date_str = request.args.get('date', '')
    try:
        if date_str:
            for_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            logs = NPDWhatsAppSendLog.query.filter_by(send_date=for_date).order_by(NPDWhatsAppSendLog.created_at.desc()).all()
        else:
            since = date.today() - timedelta(days=days)
            logs  = NPDWhatsAppSendLog.query.filter(
                NPDWhatsAppSendLog.send_date >= since
            ).order_by(NPDWhatsAppSendLog.created_at.desc()).limit(100).all()
    except Exception:
        logs = []

    items = [{
        'date':      l.send_date.isoformat() if l.send_date else '',
        'name':      l.recipient_name or '—',
        'type':      l.recipient_type or '—',
        'number':    l.mobile_number or '—',
        'msg_type':  l.message_type or '—',
        'status':    l.status or '—',
        'error':     l.error_message or '',
        'time':      l.created_at.strftime('%H:%M') if l.created_at else '',
    } for l in logs]

    sent_count   = sum(1 for i in items if i['status'] == 'sent')
    failed_count = sum(1 for i in items if i['status'] == 'failed')

    return jsonify({
        'ok': True,
        'logs': items,
        'summary': {'sent': sent_count, 'failed': failed_count, 'total': len(items)},
    })


# ─────────────────────────────────────────────────────────────
# EMPLOYEE NUMBERS PREVIEW
# ─────────────────────────────────────────────────────────────

@npd_report_bp.route('/api/whatsapp-recipients')
@login_required
def api_whatsapp_recipients():
    """
    Preview who will receive messages (from employee records).
    Used by the Admin Config UI to show the recipient list.
    """
    from models import db
    from models.employee import Employee

    npd_emps = Employee.query.filter(
        Employee.is_deleted == False,
        Employee.status == 'active',
        db.or_(
            Employee.department.ilike('%npd%'),
            Employee.department.ilike('%management%'),
            Employee.department.ilike('%r&d%'),
            Employee.department.ilike('%rd%'),
        )
    ).order_by(Employee.first_name).all()

    recipients = []
    for e in npd_emps:
        recipients.append({
            'name':       f'{e.first_name} {e.last_name}'.strip(),
            'department': e.department or '—',
            'mobile':     e.mobile or '—',
            'has_user':   bool(e.user_id),
            'has_mobile': bool(e.mobile),
        })

    return jsonify({'ok': True, 'recipients': recipients, 'total': len(recipients)})


# ─────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────

def _mask(s: str) -> str:
    """Mask a secret: show first 4 chars + bullets."""
    if not s:
        return ''
    if len(s) <= 6:
        return '••••••'
    return s[:4] + '•' * (len(s) - 4)
