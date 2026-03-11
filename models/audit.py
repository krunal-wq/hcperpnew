"""
models/audit.py — Central Audit Log
Every INSERT / UPDATE / DELETE / VIEW action logged here.
"""
from datetime import datetime
from .base import db


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id           = db.Column(db.Integer, primary_key=True)
    # Who
    user_id      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    username     = db.Column(db.String(100))          # snapshot — survives user delete
    user_role    = db.Column(db.String(50))
    # What
    module       = db.Column(db.String(60))           # leads / clients / employees / etc
    action       = db.Column(db.String(30))           # INSERT UPDATE DELETE VIEW STATUS KANBAN NOTE DISCUSSION REMINDER FOLLOW_UP IMPORT EXPORT LOGIN LOGOUT
    record_id    = db.Column(db.Integer, nullable=True)
    record_label = db.Column(db.String(300))          # human readable — "LD-0032 / Rahul Yadav"
    # Detail
    detail       = db.Column(db.Text)                 # JSON or plain text diff
    ip_address   = db.Column(db.String(50))
    # When
    created_at   = db.Column(db.DateTime, default=datetime.now, index=True)

    user = db.relationship('User', backref='audit_logs', lazy=True)

    def __repr__(self):
        return f'<AuditLog {self.action} {self.module} #{self.record_id}>'
