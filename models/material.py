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

    children    = db.relationship('MaterialGroup', backref=db.backref('parent', remote_side=[id]), lazy='dynamic')
    materials   = db.relationship('Material', backref='group', lazy='dynamic')

    def to_dict(self):
        return {
            'id': self.id, 'group_name': self.group_name,
            'parent_id': self.parent_id,
            'description': self.description or '',
        }


class Material(db.Model):
    __tablename__ = 'materials'

    id                  = db.Column(db.Integer,       primary_key=True, autoincrement=True)
    material_name       = db.Column(db.String(300),   nullable=False)
    aliases             = db.Column(db.Text,          default='')   # comma-separated
    description         = db.Column(db.Text,          nullable=True)
    uom                 = db.Column(db.String(30),    default='KG')

    # Classification
    material_type_id    = db.Column(db.Integer, db.ForeignKey('material_types.id'), nullable=True)
    group_id            = db.Column(db.Integer, db.ForeignKey('material_groups.id'), nullable=True)

    # SKU / Packing specific
    sku_sizes           = db.Column(db.Text,  default='')   # comma-separated e.g. "50GM,100GM,200ML"

    # Supplier
    supplier_name       = db.Column(db.String(300),   default='')
    supplier_code       = db.Column(db.String(100),   default='')

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
    type_of_supply      = db.Column(db.String(50),    default='Goods')

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
            'material_type_id': self.material_type_id,
            'material_type': self.material_type.type_name if self.material_type else '',
            'material_type_abbr': self.material_type.abbreviation if self.material_type else '',
            'material_type_color': self.material_type.color if self.material_type else '#6366f1',
            'has_sku': self.material_type.has_sku if self.material_type else False,
            'group_id': self.group_id,
            'group_name': self.group.group_name if self.group else '',
            'sku_sizes': self.sku_sizes or '',
            'supplier_name': self.supplier_name or '',
            'supplier_code': self.supplier_code or '',
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
            'type_of_supply': self.type_of_supply or 'Goods',
            'is_active': self.is_active,
            'created_by': self.created_by or '',
            'updated_by': self.updated_by or '',
            'updated_at': self.updated_at.isoformat() if self.updated_at else '',
        }
