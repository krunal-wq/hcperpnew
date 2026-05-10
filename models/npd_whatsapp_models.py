"""
models/npd_daily_report.py  (UPDATED — append these two classes to existing file)
────────────────────────────────────────────────────────────────
Add to the END of the existing models/npd_daily_report.py file.
These two new models handle WhatsApp configuration and send logs.
"""

# ─────────────────────────────────────────────────────────────
# 5. WhatsApp Config  (singleton — one row)
# ─────────────────────────────────────────────────────────────

class NPDWhatsAppConfig(db.Model):
    """
    Admin-managed WhatsApp API configuration.
    Single-row table (id=1 always). Managed from Admin Config UI.

    Supports two providers:
      - 'ultramsg'  — Instance ID + Token (easiest, free trial)
      - 'twilio'    — Account SID + Auth Token + From Number
    """
    __tablename__ = 'npd_whatsapp_config'

    id                  = db.Column(db.Integer, primary_key=True)

    # ── Provider ──────────────────────────────────────────────
    provider            = db.Column(db.String(30), default='ultramsg')
    is_enabled          = db.Column(db.Boolean,    default=False)

    # ── UltraMsg credentials ──────────────────────────────────
    instance_id         = db.Column(db.String(100), nullable=True)   # e.g. 'instance12345'
    api_token           = db.Column(db.String(200), nullable=True)

    # ── Twilio credentials ────────────────────────────────────
    twilio_account_sid  = db.Column(db.String(50),  nullable=True)
    twilio_auth_token   = db.Column(db.String(50),  nullable=True)
    twilio_from_number  = db.Column(db.String(30),  nullable=True)   # 'whatsapp:+14155238886'

    # ── Sending rules ─────────────────────────────────────────
    country_code        = db.Column(db.String(10),  default='+91')
    send_time           = db.Column(db.String(8),   default='21:00')  # HH:MM IST
    send_to_manager     = db.Column(db.Boolean,     default=True)
    send_to_employees   = db.Column(db.Boolean,     default=True)
    # JSON array of extra manager numbers: ['+919876543210', ...]
    manager_numbers     = db.Column(db.Text,        nullable=True)

    updated_at          = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    updated_by          = db.Column(db.Integer, nullable=True)

    def __repr__(self):
        return f'<NPDWhatsAppConfig provider={self.provider} enabled={self.is_enabled}>'


# ─────────────────────────────────────────────────────────────
# 6. WhatsApp Send Log
# ─────────────────────────────────────────────────────────────

class NPDWhatsAppSendLog(db.Model):
    """
    Audit trail of every WhatsApp message send attempt.
    One row per recipient per day.

    message_type: 'personal_report' | 'manager_summary' | 'test'
    status:       'sent' | 'failed' | 'skipped'
    """
    __tablename__ = 'npd_whatsapp_send_logs'

    id              = db.Column(db.Integer, primary_key=True)
    send_date       = db.Column(db.Date,   nullable=False, index=True)
    recipient_type  = db.Column(db.String(20), default='employee')
    recipient_name  = db.Column(db.String(150))
    mobile_number   = db.Column(db.String(25))
    user_id         = db.Column(db.Integer, nullable=True)
    message_type    = db.Column(db.String(30), default='personal_report')
    status          = db.Column(db.String(20), default='pending')
    error_message   = db.Column(db.String(500), nullable=True)
    message_id      = db.Column(db.String(100), nullable=True)   # Provider's message ID
    triggered_by    = db.Column(db.Integer, nullable=True)       # user_id who triggered
    created_at      = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<NPDWhatsAppSendLog {self.recipient_name} {self.status}>'
