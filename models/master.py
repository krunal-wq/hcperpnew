"""
models/master.py — Lead Master tables
  LeadStatus, LeadSource, LeadCategory, ProductRange
"""
from datetime import datetime
from .base import db

class LeadStatus(db.Model):
    __tablename__ = 'lead_statuses'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False, unique=True)
    color      = db.Column(db.String(20), default='#6b7280')   # hex color
    icon       = db.Column(db.String(10), default='🔵')
    sort_order = db.Column(db.Integer, default=0)
    is_active  = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.now)
    created_by  = db.Column(db.Integer, nullable=True)
    modified_by = db.Column(db.Integer, nullable=True)
    modified_at = db.Column(db.DateTime, nullable=True)
    def __repr__(self): return f'<LeadStatus {self.name}>'

class LeadSource(db.Model):
    __tablename__ = 'lead_sources'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False, unique=True)
    icon       = db.Column(db.String(10), default='📌')
    sort_order = db.Column(db.Integer, default=0)
    is_active  = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.now)
    created_by  = db.Column(db.Integer, nullable=True)
    modified_by = db.Column(db.Integer, nullable=True)
    modified_at = db.Column(db.DateTime, nullable=True)
    def __repr__(self): return f'<LeadSource {self.name}>'

class LeadCategory(db.Model):
    __tablename__ = 'lead_categories'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False, unique=True)
    icon       = db.Column(db.String(10), default='🏷️')
    sort_order = db.Column(db.Integer, default=0)
    is_active  = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.now)
    created_by  = db.Column(db.Integer, nullable=True)
    modified_by = db.Column(db.Integer, nullable=True)
    modified_at = db.Column(db.DateTime, nullable=True)
    def __repr__(self): return f'<LeadCategory {self.name}>'

class ProductRange(db.Model):
    __tablename__ = 'product_ranges'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False, unique=True)
    icon       = db.Column(db.String(10), default='📦')
    sort_order = db.Column(db.Integer, default=0)
    is_active  = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.now)
    created_by  = db.Column(db.Integer, nullable=True)
    modified_by = db.Column(db.Integer, nullable=True)
    modified_at = db.Column(db.DateTime, nullable=True)
    def __repr__(self): return f'<ProductRange {self.name}>'
