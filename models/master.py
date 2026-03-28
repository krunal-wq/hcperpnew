"""
models/master.py — Lead Master tables
  LeadStatus, LeadSource, LeadCategory, ProductRange
"""
from datetime import datetime
from .base import db

class NPDStatus(db.Model):
    __tablename__ = 'npd_statuses'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False, unique=True)
    slug       = db.Column(db.String(60),  nullable=False, unique=True)   # e.g. 'sample_inprocess'
    color      = db.Column(db.String(20),  default='#6b7280')
    icon       = db.Column(db.String(10),  default='🔵')
    sort_order = db.Column(db.Integer,     default=0)
    is_active  = db.Column(db.Boolean,     default=True)
    created_at = db.Column(db.DateTime,    default=datetime.now)
    created_by = db.Column(db.Integer,     nullable=True)
    modified_by= db.Column(db.Integer,     nullable=True)
    modified_at= db.Column(db.DateTime,    nullable=True)
    def __repr__(self): return f'<NPDStatus {self.name}>'


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


# ──────────────────────────────────────
# Category Master
# ──────────────────────────────────────
class CategoryMaster(db.Model):
    __tablename__ = 'category_masters'
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(150), nullable=False, unique=True)
    status      = db.Column(db.Boolean, default=True)
    is_deleted  = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.now)
    created_by  = db.Column(db.Integer, nullable=True)
    modified_at = db.Column(db.DateTime, nullable=True)
    modified_by = db.Column(db.Integer, nullable=True)
    def __repr__(self): return f'<CategoryMaster {self.name}>'


# ──────────────────────────────────────
# UOM Master
# ──────────────────────────────────────
class UOMMaster(db.Model):
    __tablename__ = 'uom_masters'
    id          = db.Column(db.Integer, primary_key=True)
    code        = db.Column(db.String(30), nullable=False, unique=True)
    name        = db.Column(db.String(100), nullable=False)
    status      = db.Column(db.Boolean, default=True)
    is_deleted  = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.now)
    created_by  = db.Column(db.Integer, nullable=True)
    modified_at = db.Column(db.DateTime, nullable=True)
    modified_by = db.Column(db.Integer, nullable=True)
    def __repr__(self): return f'<UOMMaster {self.code}>'


# ──────────────────────────────────────
# HSN Code Master
# ──────────────────────────────────────
class HSNCode(db.Model):
    __tablename__ = 'hsn_codes'
    id          = db.Column(db.Integer, primary_key=True)
    hsn_code    = db.Column(db.String(20), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    gst_rate    = db.Column(db.Numeric(5,2), default=0)   # e.g. 18.00
    cgst        = db.Column(db.Numeric(5,2), default=0)   # half of gst
    sgst        = db.Column(db.Numeric(5,2), default=0)   # half of gst
    igst        = db.Column(db.Numeric(5,2), default=0)   # full gst for inter-state
    cess        = db.Column(db.Numeric(5,2), default=0)
    status      = db.Column(db.Boolean, default=True)
    is_deleted  = db.Column(db.Boolean, default=False)
    created_at  = db.Column(db.DateTime, default=datetime.now)
    created_by  = db.Column(db.Integer, nullable=True)
    modified_at = db.Column(db.DateTime, nullable=True)
    modified_by = db.Column(db.Integer, nullable=True)
    def __repr__(self): return f'<HSNCode {self.hsn_code}>'


class MilestoneStatus(db.Model):
    __tablename__ = 'milestone_statuses'
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False, unique=True)
    slug       = db.Column(db.String(60),  nullable=False, unique=True)
    color      = db.Column(db.String(20),  default='#6b7280')
    icon       = db.Column(db.String(10),  default='🔵')
    sort_order = db.Column(db.Integer,     default=0)
    is_active  = db.Column(db.Boolean,     default=True)
    created_at = db.Column(db.DateTime,    default=datetime.now)
    created_by = db.Column(db.Integer,     nullable=True)
    modified_by= db.Column(db.Integer,     nullable=True)
    modified_at= db.Column(db.DateTime,    nullable=True)
    def __repr__(self): return f'<MilestoneStatus {self.name}>'
