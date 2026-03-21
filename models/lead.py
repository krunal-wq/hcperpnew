"""
models/lead.py
──────────────
Lead CRM models:
  - Lead             → main lead record
  - LeadDiscussion   → comments / discussion board
  - LeadAttachment   → files uploaded to lead / discussion
  - LeadReminder     → follow-up reminders
  - LeadNote         → private personal notes per user
  - LeadActivityLog  → auto activity timeline
"""

from datetime import datetime
from .base import db


class Lead(db.Model):
    __tablename__ = 'leads'

    id               = db.Column(db.Integer, primary_key=True)
    code             = db.Column(db.String(30), unique=True, nullable=True)  # e.g. LD001

    # ── Existing DB columns (matching your original database) ──
    title            = db.Column(db.String(200))
    contact_name     = db.Column(db.String(150), nullable=False)
    company_name     = db.Column(db.String(200))
    email            = db.Column(db.String(150))
    website          = db.Column(db.String(200))
    phone            = db.Column(db.String(20))
    alternate_mobile = db.Column(db.String(20))
    source           = db.Column(db.String(100))
    status           = db.Column(db.String(30), default='open')   # open/in_process/close/cancel
    lead_type        = db.Column(db.String(20), default='Quality')  # Quality / Non-Quality
    priority         = db.Column(db.String(20), default='medium') # low/medium/high
    expected_value   = db.Column(db.Numeric(12, 2))
    assigned_to      = db.Column(db.Integer, db.ForeignKey('users.id'))
    follow_up_date   = db.Column(db.Date)
    notes            = db.Column(db.Text)
    lost_reason      = db.Column(db.String(200))
    customer_id      = db.Column(db.Integer, db.ForeignKey('customers.id'))

    # ── New columns (added via migration) ──
    position         = db.Column(db.String(100))
    address          = db.Column(db.Text)
    city             = db.Column(db.String(100))
    state            = db.Column(db.String(100))
    country          = db.Column(db.String(100), default='India')
    zip_code         = db.Column(db.String(10))
    average_cost     = db.Column(db.Numeric(12, 2), default=0)

    # Requirement Info
    product_name     = db.Column(db.String(200))
    category         = db.Column(db.String(100))
    product_range    = db.Column(db.String(100))
    order_quantity   = db.Column(db.String(100))
    requirement_spec = db.Column(db.Text)
    tags             = db.Column(db.String(300))
    remark           = db.Column(db.Text)

    # Tracking
    last_contact     = db.Column(db.DateTime)
    team_members     = db.Column(db.Text)  # comma-separated user IDs

    # Client Master link
    client_id        = db.Column(db.Integer, db.ForeignKey('client_masters.id'))
    client_attachment = db.Column(db.String(300))

    # Soft Delete
    is_deleted       = db.Column(db.Boolean, default=False, nullable=False,
                                 server_default='0')
    deleted_at       = db.Column(db.DateTime, nullable=True)

    # Close tracking
    closed_at        = db.Column(db.DateTime, nullable=True)

    # Audit
    created_by       = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at       = db.Column(db.DateTime, default=datetime.now)
    modified_by      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_at       = db.Column(db.DateTime, default=datetime.now,
                                 onupdate=datetime.utcnow)

    # Relationships
    discussions   = db.relationship('LeadDiscussion',  backref='lead', lazy=True,
                                    cascade='all, delete-orphan',
                                    order_by='LeadDiscussion.created_at.desc()')
    reminders     = db.relationship('LeadReminder',    backref='lead', lazy=True,
                                    cascade='all, delete-orphan',
                                    order_by='LeadReminder.remind_at')
    notes_list    = db.relationship('LeadNote',        backref='lead', lazy=True,
                                    cascade='all, delete-orphan')
    activity_logs = db.relationship('LeadActivityLog', backref='lead', lazy=True,
                                    cascade='all, delete-orphan',
                                    order_by='LeadActivityLog.created_at.desc()')
    attachments   = db.relationship('LeadAttachment',  backref='lead', lazy=True,
                                    cascade='all, delete-orphan')

    # ── Backward-compat properties (templates mein l.name etc. kaam karte hain) ──
    @property
    def name(self):
        return self.contact_name or ''

    @property
    def mobile(self):
        return self.phone or ''

    @property
    def company(self):
        return self.company_name or ''

    @property
    def lead_age(self):
        """Days from created_at to closed_at (if closed/cancelled) or today."""
        if not self.created_at:
            return 0
        # Use date comparison to avoid timezone issues
        created_date = self.created_at.date() if hasattr(self.created_at, 'date') else self.created_at
        if self.status in ('close', 'cancel') and self.closed_at:
            end_date = self.closed_at.date() if hasattr(self.closed_at, 'date') else self.closed_at
        else:
            end_date = datetime.now().date()
        return max(0, (end_date - created_date).days)

    # ── Team helpers ──
    def get_team_member_ids(self):
        if self.team_members:
            try:
                return [int(x) for x in self.team_members.split(',') if x.strip()]
            except Exception:
                return []
        return []

    def get_team_member_objects(self):
        from .user import User
        ids = self.get_team_member_ids()
        if ids:
            return User.query.filter(User.id.in_(ids)).all()
        return []

    def __repr__(self):
        return f'<Lead {self.code} — {self.contact_name}>'


# ──────────────────────────────────────
# Lead Discussion (Comment Board)
# ──────────────────────────────────────

class LeadDiscussion(db.Model):
    __tablename__ = 'lead_discussions'

    id         = db.Column(db.Integer, primary_key=True)
    lead_id    = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    comment    = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user        = db.relationship('User', backref='lead_discussions', lazy=True)
    attachments = db.relationship('LeadAttachment', backref='discussion', lazy=True,
                                  primaryjoin='LeadAttachment.discussion_id == LeadDiscussion.id',
                                  cascade='all, delete-orphan')

    def __repr__(self):
        return f'<LeadDiscussion lead={self.lead_id}>'


# ──────────────────────────────────────
# Lead Attachment (Files)
# ──────────────────────────────────────

class LeadAttachment(db.Model):
    __tablename__ = 'lead_attachments'

    id            = db.Column(db.Integer, primary_key=True)
    lead_id       = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    discussion_id = db.Column(db.Integer, db.ForeignKey('lead_discussions.id'))
    file_name     = db.Column(db.String(300), nullable=False)
    file_path     = db.Column(db.String(500), nullable=False)
    file_size     = db.Column(db.Integer)
    file_type     = db.Column(db.String(100))
    uploaded_by   = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    uploader = db.relationship('User', backref='lead_attachments', lazy=True)

    def __repr__(self):
        return f'<LeadAttachment {self.file_name}>'


# ──────────────────────────────────────
# Lead Reminder (Follow-up)
# ──────────────────────────────────────

class LeadReminder(db.Model):
    __tablename__ = 'lead_reminders'

    id          = db.Column(db.Integer, primary_key=True)
    lead_id     = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title       = db.Column(db.String(300), nullable=False)
    description = db.Column(db.Text)
    remind_at   = db.Column(db.DateTime, nullable=False)
    is_done     = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='lead_reminders', lazy=True)

    def __repr__(self):
        return f'<LeadReminder {self.title} @ {self.remind_at}>'


# ──────────────────────────────────────
# Lead Personal Note (Private per user)
# ──────────────────────────────────────

class LeadNote(db.Model):
    __tablename__ = 'lead_notes'

    id         = db.Column(db.Integer, primary_key=True)
    lead_id    = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    note       = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    user = db.relationship('User', backref='lead_notes', lazy=True)

    def __repr__(self):
        return f'<LeadNote lead={self.lead_id} user={self.user_id}>'


# ──────────────────────────────────────
# Lead Activity Log (Auto Timeline)
# ──────────────────────────────────────

class LeadActivityLog(db.Model):
    __tablename__ = 'lead_activity_logs'

    id         = db.Column(db.Integer, primary_key=True)
    lead_id    = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'))
    action     = db.Column(db.String(500), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', backref='lead_activity_logs', lazy=True)

    def __repr__(self):
        return f'<LeadActivityLog lead={self.lead_id} — {self.action[:30]}>'


# ──────────────────────────────────────
# Sample Order
# ──────────────────────────────────────

class SampleOrder(db.Model):
    __tablename__ = 'sample_orders'

    id           = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    lead_id      = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    order_date   = db.Column(db.Date, nullable=False)
    category     = db.Column(db.String(50), default='Sample Order')
    bill_company = db.Column(db.String(200))
    bill_address = db.Column(db.Text)
    bill_phone   = db.Column(db.String(20))
    bill_email   = db.Column(db.String(150))
    bill_gst     = db.Column(db.String(20))
    gst_pct      = db.Column(db.Numeric(5,2), default=18)
    sub_total    = db.Column(db.Numeric(12,2), default=0)
    gst_amount   = db.Column(db.Numeric(12,2), default=0)
    total_amount = db.Column(db.Numeric(12,2), default=0)
    items_json   = db.Column(db.Text)   # JSON list of items
    terms        = db.Column(db.Text)
    invoice_file = db.Column(db.String(300))   # uploaded invoice filename
    created_by   = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    # ── Soft Delete ──
    is_deleted   = db.Column(db.Boolean, default=False, nullable=False, server_default='0')
    deleted_at   = db.Column(db.DateTime, nullable=True)
    deleted_by   = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    lead    = db.relationship('Lead',  backref='sample_orders', lazy=True)
    creator = db.relationship('User',  backref='sample_orders', lazy=True,
                               foreign_keys=[created_by])

    def __repr__(self):
        return f'<SampleOrder {self.order_number}>'


# ──────────────────────────────────────
# Quotation
# ──────────────────────────────────────

class Quotation(db.Model):
    __tablename__ = 'quotations'

    id             = db.Column(db.Integer, primary_key=True)
    quot_number    = db.Column(db.String(50), unique=True, nullable=False)
    lead_id        = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    quot_date      = db.Column(db.Date, nullable=False)
    valid_until    = db.Column(db.Date)
    subject        = db.Column(db.String(300))
    bill_company   = db.Column(db.String(200))
    bill_address   = db.Column(db.Text)
    bill_phone     = db.Column(db.String(20))
    bill_email     = db.Column(db.String(150))
    bill_gst       = db.Column(db.String(20))
    gst_pct        = db.Column(db.Numeric(5,2), default=18)
    sub_total      = db.Column(db.Numeric(12,2), default=0)
    gst_amount     = db.Column(db.Numeric(12,2), default=0)
    total_amount   = db.Column(db.Numeric(12,2), default=0)
    items_json     = db.Column(db.Text)
    terms          = db.Column(db.Text)
    notes          = db.Column(db.Text)
    status         = db.Column(db.String(20), default='draft')  # draft / sent / accepted / rejected
    email_sent_at  = db.Column(db.DateTime)
    email_sent_to  = db.Column(db.String(150))
    created_by     = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    # ── Soft Delete ──
    is_deleted     = db.Column(db.Boolean, default=False, nullable=False, server_default='0')
    deleted_at     = db.Column(db.DateTime, nullable=True)
    deleted_by     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    lead    = db.relationship('Lead', backref='quotations', lazy=True)
    creator = db.relationship('User', backref='quotations', lazy=True,
                               foreign_keys=[created_by])

    def __repr__(self):
        return f'<Quotation {self.quot_number}>'


# ──────────────────────────────────────
# Email Template Master
# ──────────────────────────────────────

class EmailTemplate(db.Model):
    __tablename__ = 'email_templates'

    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(50), unique=True, nullable=False)  # e.g. 'npd_project'
    name        = db.Column(db.String(200), nullable=False)              # Display name
    subject     = db.Column(db.String(500), nullable=False)
    body        = db.Column(db.Text, nullable=False)
    from_email  = db.Column(db.String(150), default='info@hcpwellness.in')
    from_name   = db.Column(db.String(150), default='HCP Wellness Pvt. Ltd.')
    is_active   = db.Column(db.Boolean, default=True)
    updated_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    editor = db.relationship('User', backref='email_templates', lazy=True, foreign_keys=[updated_by])

    def __repr__(self):
        return f'<EmailTemplate {self.code}>'


# ──────────────────────────────────────
# Lead Contribution Tracking
# ──────────────────────────────────────

class LeadContribution(db.Model):
    __tablename__ = 'lead_contributions'

    id          = db.Column(db.Integer, primary_key=True)
    lead_id     = db.Column(db.Integer, db.ForeignKey('leads.id'), nullable=False)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    action_type = db.Column(db.String(30), nullable=False)
    # comment=1, status_change=2, close=5, cancel=2, follow_up=1, reminder=1
    points      = db.Column(db.Integer, default=0)
    note        = db.Column(db.String(200))
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    lead = db.relationship('Lead', backref='contributions', lazy=True)
    user = db.relationship('User', backref='lead_contributions_list', lazy=True)

    def __repr__(self):
        return f'<LeadContribution lead={self.lead_id} user={self.user_id} pts={self.points}>'


# ──────────────────────────────────────
# Contribution Points Config
# ──────────────────────────────────────

class ContributionConfig(db.Model):
    __tablename__ = 'contribution_config'

    id          = db.Column(db.Integer, primary_key=True)
    action_type = db.Column(db.String(30), unique=True, nullable=False)
    label       = db.Column(db.String(100), nullable=False)
    points      = db.Column(db.Integer, default=0)
    description = db.Column(db.String(200))
    updated_by  = db.Column(db.Integer, db.ForeignKey('users.id'))
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<ContributionConfig {self.action_type}={self.points}>'
