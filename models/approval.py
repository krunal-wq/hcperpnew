"""
models/approval.py — Hierarchy & Approval Workflow
"""
from datetime import datetime
from .base import db


class ApprovalRequest(db.Model):
    """Generic approval request — any module can raise one"""
    __tablename__ = 'approval_requests'

    id           = db.Column(db.Integer, primary_key=True)
    module       = db.Column(db.String(50), nullable=False)   # leads / clients / employees / leave / etc.
    record_id    = db.Column(db.Integer, nullable=False)       # ID of the record needing approval
    record_label = db.Column(db.String(200))                   # Human-readable label e.g. "Lead: ABC Corp"
    action       = db.Column(db.String(50), default='approve') # approve / delete / edit / export

    requested_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    status       = db.Column(db.String(20), default='pending') # pending / approved / rejected
    approved_by  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    approved_at  = db.Column(db.DateTime, nullable=True)
    remarks      = db.Column(db.Text)                          # Approver's note
    requester_note = db.Column(db.Text)                        # Requester's note

    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    requester    = db.relationship('User', foreign_keys=[requested_by], backref='approval_requests_sent')
    approver     = db.relationship('User', foreign_keys=[approved_by],  backref='approval_requests_done')

    def __repr__(self):
        return f'<ApprovalRequest {self.module}/{self.record_id} {self.status}>'


class ApprovalLevel(db.Model):
    """Defines how many approval levels each module requires"""
    __tablename__ = 'approval_levels'

    id         = db.Column(db.Integer, primary_key=True)
    module     = db.Column(db.String(50), unique=True, nullable=False)
    label      = db.Column(db.String(100))          # Display name
    levels     = db.Column(db.Integer, default=1)   # 1-5 levels needed
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ApprovalLevel {self.module} x{self.levels}>'
