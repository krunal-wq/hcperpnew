"""
models/material.py
──────────────────
Material Master, Material Type Master, Material Group Master
"""
from datetime import datetime
from .base import db


class MaterialType(db.Model):
    __tablename__ = 'material_types'

    id           = db.Column(db.Integer,      primary_key=True, autoincrement=True)
    type_name    = db.Column(db.String(100),  nullable=False, unique=True)
    abbreviation = db.Column(db.String(10),   default='')
    description  = db.Column(db.Text,         nullable=True)
    color        = db.Column(db.String(20),   default='#6366f1')
    sort_order   = db.Column(db.Integer,      default=0)
    is_active    = db.Column(db.Boolean,      default=True)
    is_deleted   = db.Column(db.Boolean,      default=False)
    deleted_at   = db.Column(db.DateTime,     nullable=True)
    created_at   = db.Column(db.DateTime,     default=datetime.utcnow)
    created_by   = db.Column(db.String(100),  default='')

    # Whether this type requires SKU size field
    has_sku      = db.Column(db.Boolean,      default=False)

    materials    = db.relationship('Material', backref='material_type', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id, 'type_name': self.type_name,
            'abbreviation': self.abbreviation or '',
            'description': self.description or '',
            'color': self.color or '#6366f1',
            'sort_order': self.sort_order or 0,
            'is_active': self.is_active,
            'is_deleted': getattr(self, 'is_deleted', False) or False,
            'has_sku': self.has_sku,
        }


class MaterialGroup(db.Model):
    __tablename__ = 'material_groups'

    id          = db.Column(db.Integer,     primary_key=True, autoincrement=True)
    group_name  = db.Column(db.String(150), nullable=False)
    parent_id   = db.Column(db.Integer,     db.ForeignKey('material_groups.id'), nullable=True)
    description = db.Column(db.Text,        nullable=True)
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by  = db.Column(db.String(100), default='')
    is_deleted  = db.Column(db.Boolean,     default=False)
    deleted_at  = db.Column(db.DateTime,    nullable=True)

    children    = db.relationship('MaterialGroup', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    materials   = db.relationship('Material', backref='group', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id, 'group_name': self.group_name,
            'parent_id': self.parent_id,
            'description': self.description or '',
            'is_deleted': getattr(self,'is_deleted',False) or False,
            'deleted_at': self.deleted_at.isoformat() if getattr(self,'deleted_at',None) else None,
        }


class Material(db.Model):
    __tablename__ = 'materials'

    id                  = db.Column(db.Integer,       primary_key=True, autoincrement=True)
    material_name       = db.Column(db.String(300),   nullable=False)
    aliases             = db.Column(db.Text,          default='')   # comma-separated
    description         = db.Column(db.Text,          nullable=True)
    uom                 = db.Column(db.String(30),    default='KG')

    # Item code (RM-001, PM-001 etc.)
    code                = db.Column(db.String(100),   default='', nullable=True)

    # INCI Name (RM only)
    inci_name           = db.Column(db.String(300),   default='', nullable=True)

    # Brand & Category (PM/FG)
    brand               = db.Column(db.String(200),   default='', nullable=True)
    category            = db.Column(db.String(200),   default='', nullable=True)

    # Per box qty (FG only)
    per_box_qty         = db.Column(db.Integer,       default=0)

    # PM Material Type (PM only: HM = Hard Material, CM = Carton Material)
    pm_material_type    = db.Column(db.String(20),    default='', nullable=True)
    pm_attribute        = db.Column(db.String(300),   default='', nullable=True)  # comma-sep: Bottle,Tube,Box
    corrugation_ply     = db.Column(db.String(20),    default='', nullable=True)  # 3 Ply/5 Ply/7 Ply
    dim_length          = db.Column(db.Numeric(10,2), nullable=True)  # mm
    dim_width           = db.Column(db.Numeric(10,2), nullable=True)  # mm
    dim_height          = db.Column(db.Numeric(10,2), nullable=True)  # mm (Corrugation only)
    pm_client_type      = db.Column(db.String(10),    default='', nullable=True)  # HM or CM

    # Classification
    material_type_id    = db.Column(db.Integer, db.ForeignKey('material_types.id'), nullable=True)
    group_id            = db.Column(db.Integer, db.ForeignKey('material_groups.id'), nullable=True)

    # SKU / Packing specific
    sku_sizes           = db.Column(db.Text,  default='')   # comma-separated e.g. "50GM,100GM,200ML"

    # Supplier

    # Stock / Procurement
    opening_balance     = db.Column(db.Numeric(14,3), default=0)
    msl                 = db.Column(db.Numeric(14,3), default=0)    # Min Stock Level
    lead_time_days      = db.Column(db.Integer,       default=0)
    std_pack_size       = db.Column(db.Numeric(14,3), default=0)
    last_purchase_rate  = db.Column(db.Numeric(12,2), default=0)
    ordered_qty         = db.Column(db.Numeric(14,3), default=0)
    buffer_qty          = db.Column(db.Numeric(14,3), default=0)

    # GST / Statutory
    hsn_code            = db.Column(db.String(20),    default='')
    gst_rate            = db.Column(db.Numeric(5,2),  default=0)
    taxability          = db.Column(db.String(50),    default='Taxable')

    # Soft Delete
    is_deleted          = db.Column(db.Boolean,       default=False)
    deleted_at          = db.Column(db.DateTime,      nullable=True)

    # Product Image (PM/FG)
    image_data          = db.Column(db.Text,          nullable=True)  # base64 data URL

    # Meta
    is_active           = db.Column(db.Boolean,       default=True)
    created_by          = db.Column(db.String(100),   default='')
    updated_by          = db.Column(db.String(100),   default='')
    created_at          = db.Column(db.DateTime,      default=datetime.utcnow)
    updated_at          = db.Column(db.DateTime,      default=datetime.utcnow, onupdate=datetime.utcnow)

    def alias_list(self):
        return [a.strip() for a in (self.aliases or '').split(',') if a.strip()]

    def sku_list(self):
        return [s.strip() for s in (self.sku_sizes or '').split(',') if s.strip()]

    def to_dict(self):
        return {
            'id': self.id,
            'material_name': self.material_name,
            'aliases': self.aliases or '',
            'description': self.description or '',
            'uom': self.uom or 'KG',
            'code': self.code or '',
            'inci_name': self.inci_name or '',
            'brand': self.brand or '',
            'category': self.category or '',
            'per_box_qty': self.per_box_qty or 0,
            'pm_material_type': self.pm_material_type or '',
            'pm_attribute':     self.pm_attribute or '',
            'corrugation_ply':  self.corrugation_ply or '',
            'pm_client_type':   self.pm_client_type or '',
            'dim_length':       float(self.dim_length) if self.dim_length else None,
            'dim_width':        float(self.dim_width) if self.dim_width else None,
            'dim_height':       float(self.dim_height) if self.dim_height else None,
            'material_type_id': self.material_type_id,
            'material_type': self.material_type.type_name if self.material_type else '',
            'material_type_abbr': self.material_type.abbreviation if self.material_type else '',
            'material_type_color': self.material_type.color if self.material_type else '#6366f1',
            'has_sku': self.material_type.has_sku if self.material_type else False,
            'group_id': self.group_id,
            'group_name': self.group.group_name if self.group else '',
            'sku_sizes': self.sku_sizes or '',
            'opening_balance': float(self.opening_balance or 0),
            'msl': float(self.msl or 0),
            'lead_time_days': self.lead_time_days or 0,
            'std_pack_size': float(self.std_pack_size or 0),
            'last_purchase_rate': float(self.last_purchase_rate or 0),
            'ordered_qty': float(self.ordered_qty or 0),
            'buffer_qty': float(self.buffer_qty or 0),
            'hsn_code': self.hsn_code or '',
            'gst_rate': float(self.gst_rate or 0),
            'taxability': self.taxability or 'Taxable',
            'is_active': self.is_active,
            'is_deleted': getattr(self, 'is_deleted', False) or False,
            'image_data': self.image_data or '',
            'created_by': self.created_by or '',
            'updated_by': self.updated_by or '',
            'updated_at': self.updated_at.isoformat() if self.updated_at else '',
        }

class ItemCategory(db.Model):
    __tablename__ = 'item_categories'

    id            = db.Column(db.Integer,      primary_key=True, autoincrement=True)
    category_name = db.Column(db.String(150),  nullable=False, unique=True)
    description   = db.Column(db.Text,         nullable=True)
    is_active     = db.Column(db.Boolean,      default=True)
    created_at    = db.Column(db.DateTime,     default=datetime.utcnow)
    updated_at    = db.Column(db.DateTime,     default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by    = db.Column(db.String(100),  default='')
    is_deleted    = db.Column(db.Boolean,      default=False)
    deleted_at    = db.Column(db.DateTime,     nullable=True)

    def to_dict(self):
        return {
            'id':            self.id,
            'category_name': self.category_name,
            'description':   self.description or '',
            'is_active':     self.is_active,
            'is_deleted':    getattr(self,'is_deleted',False) or False,
            'deleted_at':    self.deleted_at.isoformat() if getattr(self,'deleted_at',None) else None,
        }
