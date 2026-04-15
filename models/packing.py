"""
models/packing.py
─────────────────
Packing Sample Receipt Log — SQLAlchemy model
"""

from datetime import datetime, date
from .base import db


class PackingEntry(db.Model):
    __tablename__ = 'packing_entries'

    id                 = db.Column(db.Integer,       primary_key=True, autoincrement=True)
    entry_date         = db.Column(db.Date,          nullable=False, default=date.today)
    brand              = db.Column(db.String(150),   nullable=False)
    product_name       = db.Column(db.String(300),   nullable=False)
    batch_no           = db.Column(db.String(50),    default='')
    mfg_date           = db.Column(db.String(20),    default='')
    exp_date           = db.Column(db.String(20),    default='')
    sku_size           = db.Column(db.String(100),   default='')
    packaging_material = db.Column(db.String(100),   default='')
    quantity           = db.Column(db.Integer,       default=0)
    samples_sent_by    = db.Column(db.String(150),   default='')
    mrp                = db.Column(db.Numeric(10, 2),nullable=True)
    received_by        = db.Column(db.String(150),   default='')
    status             = db.Column(db.String(50),    default='Pending')
    received_date      = db.Column(db.Date,          nullable=True)
    testing_status     = db.Column(db.String(50),    default='Pending')
    remark             = db.Column(db.Text,          nullable=True)
    created_by         = db.Column(db.String(100),   default='')
    created_at         = db.Column(db.DateTime,      default=datetime.utcnow)
    updated_at         = db.Column(db.DateTime,      default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id':                 self.id,
            'entry_date':         self.entry_date.isoformat()  if self.entry_date   else None,
            'brand':              self.brand              or '',
            'product_name':       self.product_name       or '',
            'batch_no':           self.batch_no           or '',
            'mfg_date':           self.mfg_date           or '',
            'exp_date':           self.exp_date           or '',
            'sku_size':           self.sku_size           or '',
            'packaging_material': self.packaging_material or '',
            'quantity':           self.quantity           or 0,
            'samples_sent_by':    self.samples_sent_by    or '',
            'mrp':                float(self.mrp) if self.mrp is not None else None,
            'received_by':        self.received_by        or '',
            'status':             self.status             or 'Pending',
            'received_date':      self.received_date.isoformat() if self.received_date else None,
            'testing_status':     self.testing_status     or 'Pending',
            'remark':             self.remark             or '',
            'created_by':         self.created_by         or '',
            'created_at':         self.created_at.isoformat() if self.created_at else None,
        }
