"""
models/user.py
──────────────
User authentication models:
  - User       → login, roles, password hashing
  - LoginLog   → login history tracking
"""

from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from .base import db


class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id             = db.Column(db.Integer, primary_key=True)
    username       = db.Column(db.String(100), unique=True, nullable=False)
    email          = db.Column(db.String(150), unique=True, nullable=False)
    password_hash  = db.Column(db.String(256), nullable=False)
    full_name      = db.Column(db.String(150))
    role           = db.Column(db.String(50), default='user')
    is_active      = db.Column(db.Boolean, default=True)
    created_at     = db.Column(db.DateTime, default=datetime.now)
    created_by     = db.Column(db.Integer, nullable=True)
    modified_by    = db.Column(db.Integer, nullable=True)
    updated_at     = db.Column(db.DateTime, nullable=True)
    last_login     = db.Column(db.DateTime)
    login_attempts = db.Column(db.Integer, default=0)
    locked_until   = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_locked(self):
        if self.locked_until and datetime.utcnow() < self.locked_until:
            return True
        return False

    def __repr__(self):
        return f'<User {self.username}>'


class LoginLog(db.Model):
    __tablename__ = 'login_logs'

    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'))
    username   = db.Column(db.String(100))
    ip_address = db.Column(db.String(50))
    status     = db.Column(db.String(20))   # success / failed / locked
    timestamp  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<LoginLog {self.username} {self.status}>'
