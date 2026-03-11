"""
models/permission.py — Role-based Permission System
"""
from datetime import datetime
from .base import db


class Module(db.Model):
    """System modules (CRM, HR, Masters, etc.)"""
    __tablename__ = 'modules'

    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False, unique=True)
    label       = db.Column(db.String(100))          # Display name
    icon        = db.Column(db.String(20))
    url_prefix  = db.Column(db.String(100))          # e.g. /crm, /hr
    parent_id   = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=True)
    sort_order  = db.Column(db.Integer, default=0)
    is_active   = db.Column(db.Boolean, default=True)

    children    = db.relationship('Module', backref=db.backref('parent', remote_side=[id]), lazy=True)
    permissions = db.relationship('RolePermission', backref='module', lazy=True,
                                  cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Module {self.name}>'


class RolePermission(db.Model):
    """Permission matrix: role × module × actions"""
    __tablename__ = 'role_permissions'

    id          = db.Column(db.Integer, primary_key=True)
    role        = db.Column(db.String(50), nullable=False)   # admin/manager/user/hr
    module_id   = db.Column(db.Integer, db.ForeignKey('modules.id'), nullable=False)

    can_view    = db.Column(db.Boolean, default=False)
    can_add     = db.Column(db.Boolean, default=False)
    can_edit    = db.Column(db.Boolean, default=False)
    can_delete  = db.Column(db.Boolean, default=False)
    can_export  = db.Column(db.Boolean, default=False)

    # Field-level permissions (JSON list of allowed field names)
    visible_fields = db.Column(db.Text)   # JSON: ["name","mobile","email",...]

    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('role', 'module_id', name='uq_role_module'),)

    def get_visible_fields(self):
        import json
        if self.visible_fields:
            try:
                return json.loads(self.visible_fields)
            except Exception:
                return []
        return []

    def set_visible_fields(self, fields_list):
        import json
        self.visible_fields = json.dumps(fields_list)

    def __repr__(self):
        return f'<RolePermission {self.role}/{self.module_id}>'


class UserGridConfig(db.Model):
    """Per-user grid column customization"""
    __tablename__ = 'user_grid_configs'

    id          = db.Column(db.Integer, primary_key=True)
    user_id     = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    module_name = db.Column(db.String(100), nullable=False)
    columns     = db.Column(db.Text)     # JSON list of visible column keys in order
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (db.UniqueConstraint('user_id', 'module_name', name='uq_user_module_grid'),)

    def get_columns(self):
        import json
        if self.columns:
            try:
                return json.loads(self.columns)
            except Exception:
                return []
        return []

    def set_columns(self, cols):
        import json
        self.columns = json.dumps(cols)
