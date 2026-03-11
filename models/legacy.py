"""
models/legacy.py
────────────────
Legacy Customer models (backward compatibility).
Purani 'customers' table ke liye — delete mat karo,
Lead model ka customer_id FK yahan point karta hai.
"""

from datetime import datetime
from .base import db


class Customer(db.Model):
    __tablename__ = 'customers'

    id               = db.Column(db.Integer, primary_key=True)
    code             = db.Column(db.String(20), unique=True)
    company_name     = db.Column(db.String(200))
    contact_name     = db.Column(db.String(150), nullable=False)
    email            = db.Column(db.String(150))
    mobile           = db.Column(db.String(20))
    alternate_mobile = db.Column(db.String(20))
    gstin            = db.Column(db.String(20))
    customer_type    = db.Column(db.String(50), default='regular')
    status           = db.Column(db.String(20), default='active')
    notes            = db.Column(db.Text)
    city             = db.Column(db.String(100))
    state            = db.Column(db.String(100))
    created_by       = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow,
                                 onupdate=datetime.utcnow)

    addresses = db.relationship('CustomerAddress', backref='customer',
                                lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Customer {self.code} — {self.contact_name}>'


class CustomerAddress(db.Model):
    __tablename__ = 'customer_addresses'

    id           = db.Column(db.Integer, primary_key=True)
    customer_id  = db.Column(db.Integer, db.ForeignKey('customers.id'),
                             nullable=False)
    address_type = db.Column(db.String(20), nullable=False)  # billing / shipping
    label        = db.Column(db.String(100), default='')
    address      = db.Column(db.Text)
    city         = db.Column(db.String(100))
    state        = db.Column(db.String(100))
    pincode      = db.Column(db.String(10))
    is_primary   = db.Column(db.Boolean, default=False)
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<CustomerAddress {self.address_type} — {self.customer_id}>'
