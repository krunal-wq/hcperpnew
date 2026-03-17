"""
models/client.py  —  ClientMaster, ClientAddress, ClientBrand
"""
from datetime import datetime
from .base import db


class ClientMaster(db.Model):
    __tablename__ = 'client_masters'

    id               = db.Column(db.Integer, primary_key=True)
    code             = db.Column(db.String(20), unique=True)
    company_name     = db.Column(db.String(200))
    contact_name     = db.Column(db.String(150), nullable=False)
    position         = db.Column(db.String(100))
    email            = db.Column(db.String(150))
    website          = db.Column(db.String(200))
    mobile           = db.Column(db.String(20))
    alternate_mobile = db.Column(db.String(20))
    gstin            = db.Column(db.String(20))
    status           = db.Column(db.String(20), default='active')

    # These columns already exist in DB — keeping them
    address          = db.Column(db.Text)
    city             = db.Column(db.String(100))
    state            = db.Column(db.String(100))
    country          = db.Column(db.String(100), default='India')
    zip_code         = db.Column(db.String(10))

    notes            = db.Column(db.Text)

    # Soft Delete
    is_deleted       = db.Column(db.Boolean, default=False, nullable=False,
                                 server_default='0')
    deleted_at       = db.Column(db.DateTime, nullable=True)

    created_by       = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at       = db.Column(db.DateTime, default=datetime.now)
    modified_by      = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    updated_at       = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    brands    = db.relationship('ClientBrand',   backref='client', lazy=True,
                                cascade='all, delete-orphan')
    addresses = db.relationship('ClientAddress', backref='client', lazy=True,
                                cascade='all, delete-orphan', order_by='ClientAddress.id')
    leads     = db.relationship('Lead', backref='client', lazy=True)

    def __repr__(self):
        return f'<ClientMaster {self.code} — {self.contact_name}>'


class ClientAddress(db.Model):
    __tablename__ = 'client_addresses'

    id          = db.Column(db.Integer, primary_key=True)
    client_id   = db.Column(db.Integer, db.ForeignKey('client_masters.id'), nullable=False)
    brand_index = db.Column(db.Integer, default=0)   # 0=brand1, 1=brand2, etc.
    title      = db.Column(db.String(100), nullable=False, default='Address')
    addr_type  = db.Column(db.String(20), default='billing')   # billing / shipping / both
    address    = db.Column(db.Text)
    city       = db.Column(db.String(100))
    state      = db.Column(db.String(100))
    country    = db.Column(db.String(100), default='India')
    zip_code   = db.Column(db.String(10))
    is_default = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ClientAddress {self.title} ({self.addr_type})>'


class ClientBrand(db.Model):
    __tablename__ = 'client_brands'

    id          = db.Column(db.Integer, primary_key=True)
    client_id   = db.Column(db.Integer, db.ForeignKey('client_masters.id'), nullable=False)
    brand_name  = db.Column(db.String(200), nullable=False)
    category    = db.Column(db.String(100))
    description = db.Column(db.Text)
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<ClientBrand {self.brand_name}>'
