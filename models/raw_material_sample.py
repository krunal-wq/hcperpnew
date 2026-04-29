"""
models/raw_material_sample.py
─────────────────────────────
Raw Material Sample Request module — used by NPD / R&D teams to
request sample raw materials from the Purchase department.

Workflow:
    request_created   → NPD / R&D creates request
    sent_to_purchase  → Auto on create (visible to Purchase dept)
    supplier_finalized→ Purchase team picks a supplier
    order_placed      → Purchase team places order with supplier
    order_dispatched  → Purchase team enters courier / tracking
    sample_received   → NPD / R&D confirms physical receipt

Two tables:
    raw_material_sample_requests  (one row per request)
    rms_activity_log              (audit trail of status changes)
"""

from datetime import datetime
from .base import db


# ── ALLOWED STATUS VALUES ────────────────────────────────────────────
RMS_STATUSES = (
    'request_created',
    'sent_to_purchase',
    'supplier_finalized',
    'order_placed',
    'order_dispatched',
    'sample_received',
    'cancelled',
)

RMS_STATUS_LABELS = {
    'request_created'   : 'Request Created',
    'sent_to_purchase'  : 'Sent to Purchase',
    'supplier_finalized': 'Supplier Finalized',
    'order_placed'      : 'Order Placed',
    'order_dispatched'  : 'Order Dispatched',
    'sample_received'   : 'Sample Received',
    'cancelled'         : 'Cancelled',
}

RMS_STATUS_COLORS = {
    'request_created'   : '#64748b',   # slate
    'sent_to_purchase'  : '#f59e0b',   # amber
    'supplier_finalized': '#8b5cf6',   # violet
    'order_placed'      : '#3b82f6',   # blue
    'order_dispatched'  : '#0ea5e9',   # cyan
    'sample_received'   : '#16a34a',   # green
    'cancelled'         : '#dc2626',   # red
}


class RawMaterialSampleRequest(db.Model):
    """
    Master row for one raw-material sample request.
    Lifecycle is controlled via the `status` field.
    """
    __tablename__ = 'raw_material_sample_requests'

    id              = db.Column(db.Integer,     primary_key=True, autoincrement=True)
    request_no      = db.Column(db.String(20),  unique=True, nullable=False)   # RMS-0001

    # ── REQUEST PART (filled by NPD / R&D) ───────────────────────────
    material_name   = db.Column(db.String(300), nullable=False)
    inci_name       = db.Column(db.String(300), default='')
    quantity        = db.Column(db.String(60),  default='')   # e.g. "500 GM"
    purpose_remarks = db.Column(db.Text,        default='')   # purpose / R&D remarks
    application     = db.Column(db.String(200), default='')   # e.g. Skin Care, Hair Care
    suggested_supplier = db.Column(db.String(300), default='')  # optional hint to purchase
    required_by_date= db.Column(db.Date,        nullable=True)

    requested_by      = db.Column(db.Integer,    db.ForeignKey('users.id'), nullable=False)

    # ── PURCHASE PART (filled by Purchase team) ──────────────────────
    actual_supplier  = db.Column(db.String(300), default='')
    supplier_contact = db.Column(db.String(200), default='')   # phone / email of supplier
    rate_per_kg      = db.Column(db.Numeric(12, 2), default=0)
    moq              = db.Column(db.String(60),  default='')
    lead_time        = db.Column(db.String(60),  default='')

    # When supplier finalised
    supplier_finalized_at = db.Column(db.DateTime, nullable=True)
    supplier_finalized_by = db.Column(db.Integer,  db.ForeignKey('users.id'), nullable=True)

    # When order placed
    order_no       = db.Column(db.String(60),  default='')
    order_placed_at= db.Column(db.DateTime,    nullable=True)
    order_placed_by= db.Column(db.Integer,     db.ForeignKey('users.id'), nullable=True)

    # ── DISPATCH PART (filled by Purchase team after supplier ships) ─
    courier_name    = db.Column(db.String(200), default='')
    tracking_no     = db.Column(db.String(120), default='')
    dispatch_date   = db.Column(db.Date,        nullable=True)
    dispatch_remarks= db.Column(db.Text,        default='')
    dispatched_at   = db.Column(db.DateTime,    nullable=True)
    dispatched_by   = db.Column(db.Integer,     db.ForeignKey('users.id'), nullable=True)

    # ── RECEIPT PART (filled by NPD / R&D when material arrives) ─────
    received_qty    = db.Column(db.String(60),  default='')
    received_date   = db.Column(db.Date,        nullable=True)
    batch_no        = db.Column(db.String(120), default='')
    receipt_remarks = db.Column(db.Text,        default='')
    received_at     = db.Column(db.DateTime,    nullable=True)
    received_by     = db.Column(db.Integer,     db.ForeignKey('users.id'), nullable=True)

    # ── STATUS & META ────────────────────────────────────────────────
    status          = db.Column(db.String(30),  default='request_created', nullable=False)

    is_deleted      = db.Column(db.Boolean,     default=False)
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── RELATIONSHIPS ────────────────────────────────────────────────
    requester      = db.relationship('User', foreign_keys=[requested_by])
    finalizer      = db.relationship('User', foreign_keys=[supplier_finalized_by])
    placer         = db.relationship('User', foreign_keys=[order_placed_by])
    dispatcher     = db.relationship('User', foreign_keys=[dispatched_by])
    receiver       = db.relationship('User', foreign_keys=[received_by])

    activity_logs  = db.relationship(
        'RMSActivityLog',
        backref='request',
        lazy='dynamic',
        cascade='all, delete-orphan',
        order_by='RMSActivityLog.created_at.desc()'
    )

    # ── HELPERS ──────────────────────────────────────────────────────
    @property
    def status_label(self):
        return RMS_STATUS_LABELS.get(self.status, self.status)

    @property
    def status_color(self):
        return RMS_STATUS_COLORS.get(self.status, '#64748b')

    def to_dict(self, include_logs=False):
        out = {
            'id'                : self.id,
            'request_no'        : self.request_no,
            'material_name'     : self.material_name or '',
            'inci_name'         : self.inci_name or '',
            'quantity'          : self.quantity or '',
            'purpose_remarks'   : self.purpose_remarks or '',
            'application'       : self.application or '',
            'suggested_supplier': self.suggested_supplier or '',
            'required_by_date'  : self.required_by_date.isoformat() if self.required_by_date else '',

            'requested_by'      : self.requested_by,
            'requester_name'    : (self.requester.full_name or self.requester.username) if self.requester else '',

            'actual_supplier'   : self.actual_supplier or '',
            'supplier_contact'  : self.supplier_contact or '',
            'rate_per_kg'       : float(self.rate_per_kg or 0),
            'moq'               : self.moq or '',
            'lead_time'         : self.lead_time or '',
            'supplier_finalized_at': self.supplier_finalized_at.strftime('%Y-%m-%d %H:%M') if self.supplier_finalized_at else '',
            'finalizer_name'    : (self.finalizer.full_name or self.finalizer.username) if self.finalizer else '',

            'order_no'          : self.order_no or '',
            'order_placed_at'   : self.order_placed_at.strftime('%Y-%m-%d %H:%M') if self.order_placed_at else '',
            'placer_name'       : (self.placer.full_name or self.placer.username) if self.placer else '',

            'courier_name'      : self.courier_name or '',
            'tracking_no'       : self.tracking_no or '',
            'dispatch_date'     : self.dispatch_date.isoformat() if self.dispatch_date else '',
            'dispatch_remarks'  : self.dispatch_remarks or '',
            'dispatched_at'     : self.dispatched_at.strftime('%Y-%m-%d %H:%M') if self.dispatched_at else '',
            'dispatcher_name'   : (self.dispatcher.full_name or self.dispatcher.username) if self.dispatcher else '',

            'received_qty'      : self.received_qty or '',
            'received_date'     : self.received_date.isoformat() if self.received_date else '',
            'batch_no'          : self.batch_no or '',
            'receipt_remarks'   : self.receipt_remarks or '',
            'received_at'       : self.received_at.strftime('%Y-%m-%d %H:%M') if self.received_at else '',
            'receiver_name'     : (self.receiver.full_name or self.receiver.username) if self.receiver else '',

            'status'            : self.status,
            'status_label'      : self.status_label,
            'status_color'      : self.status_color,

            'created_at'        : self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
            'updated_at'        : self.updated_at.strftime('%Y-%m-%d %H:%M') if self.updated_at else '',
        }
        if include_logs:
            out['activity_logs'] = [l.to_dict() for l in self.activity_logs]
        return out


class RMSActivityLog(db.Model):
    """
    Append-only audit trail for a sample request. Each status change
    or significant edit records who did what, when.
    """
    __tablename__ = 'rms_activity_log'

    id          = db.Column(db.Integer,     primary_key=True, autoincrement=True)
    request_id  = db.Column(db.Integer,     db.ForeignKey('raw_material_sample_requests.id'),
                            nullable=False, index=True)
    user_id     = db.Column(db.Integer,     db.ForeignKey('users.id'), nullable=True)
    username    = db.Column(db.String(120), default='')
    action      = db.Column(db.String(80),  default='')   # e.g. 'CREATE', 'STATUS_CHANGE'
    from_status = db.Column(db.String(30),  default='')
    to_status   = db.Column(db.String(30),  default='')
    note        = db.Column(db.Text,        default='')
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)

    user = db.relationship('User')

    def to_dict(self):
        return {
            'id'         : self.id,
            'user_id'    : self.user_id,
            'username'   : self.username or (self.user.username if self.user else ''),
            'full_name'  : (self.user.full_name or self.user.username) if self.user else (self.username or ''),
            'action'     : self.action or '',
            'from_status': self.from_status or '',
            'to_status'  : self.to_status or '',
            'from_label' : RMS_STATUS_LABELS.get(self.from_status, self.from_status or ''),
            'to_label'   : RMS_STATUS_LABELS.get(self.to_status, self.to_status or ''),
            'note'       : self.note or '',
            'created_at' : self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }


# ── Notification queue (optional — used by routes) ──────────────────
class RMSNotification(db.Model):
    """
    Tiny in-app notification queue. Routes push rows here on status
    changes; the bell icon / dashboard reads them.
    Rendering UI is optional — just reading the rows is enough for
    the requirement "notify on status change".
    """
    __tablename__ = 'rms_notifications'

    id         = db.Column(db.Integer,     primary_key=True, autoincrement=True)
    request_id = db.Column(db.Integer,     db.ForeignKey('raw_material_sample_requests.id'),
                           nullable=False, index=True)
    user_id    = db.Column(db.Integer,     db.ForeignKey('users.id'), nullable=False, index=True)
    title      = db.Column(db.String(200), default='')
    body       = db.Column(db.Text,        default='')
    is_read    = db.Column(db.Boolean,     default=False, index=True)
    created_at = db.Column(db.DateTime,    default=datetime.utcnow)

    request = db.relationship('RawMaterialSampleRequest')
    user    = db.relationship('User')

    def to_dict(self):
        return {
            'id'        : self.id,
            'request_id': self.request_id,
            'user_id'   : self.user_id,
            'title'     : self.title or '',
            'body'      : self.body or '',
            'is_read'   : bool(self.is_read),
            'created_at': self.created_at.strftime('%Y-%m-%d %H:%M') if self.created_at else '',
        }


# ════════════════════════════════════════════════════════════════════
# Daily Reminder Acknowledgement
# ════════════════════════════════════════════════════════════════════
# One row per (user, day). Used to ensure the "Pending Materials"
# reminder popup appears at most once per day per user.

class RMSDailyAck(db.Model):
    __tablename__ = 'rms_daily_ack'

    id            = db.Column(db.Integer,  primary_key=True, autoincrement=True)
    user_id       = db.Column(db.Integer,  db.ForeignKey('users.id'),
                              nullable=False, index=True)
    ack_date      = db.Column(db.Date,     nullable=False, index=True)
    pending_count = db.Column(db.Integer,  default=0)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'ack_date', name='uq_rms_ack_user_date'),
    )

    user = db.relationship('User')
