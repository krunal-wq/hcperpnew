from models import db
from datetime import datetime


class Supplier(db.Model):
    __tablename__ = 'suppliers'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    supplier_code   = db.Column(db.String(50),  default='', nullable=True)
    supplier_name   = db.Column(db.String(300),  nullable=False)
    supplier_type   = db.Column(db.String(20),   default='RM')  # RM, PM, or RM,PM (comma-sep)

    # Contact
    contact_person  = db.Column(db.String(200),  default='')
    phone           = db.Column(db.String(30),   default='')
    email           = db.Column(db.String(200),  default='')
    email_list      = db.Column(db.Text,         nullable=True)  # comma-separated additional emails
    company_name    = db.Column(db.String(300),  default='')

    # Addresses (JSON array of {type, address, city, state, pincode, country})
    addresses       = db.Column(db.Text,         nullable=True)  # JSON
    # Keep legacy fields for compatibility
    address         = db.Column(db.Text,         nullable=True)
    billing_state   = db.Column(db.String(100),  default='')
    billing_city    = db.Column(db.String(100),  default='')
    billing_pincode = db.Column(db.String(20),   default='')
    billing_country = db.Column(db.String(100),  default='India')
    shipping_address= db.Column(db.Text,         nullable=True)
    shipping_state  = db.Column(db.String(100),  default='')
    shipping_city   = db.Column(db.String(100),  default='')
    shipping_pincode= db.Column(db.String(20),   default='')
    shipping_country= db.Column(db.String(100),  default='India')

    # Business
    gst_number      = db.Column(db.String(20),   default='')
    pan_number      = db.Column(db.String(20),   default='')

    # Payment
    payment_type    = db.Column(db.String(50),   default='')
    payment_terms   = db.Column(db.Text,         nullable=True)
    credit_days     = db.Column(db.Integer,      default=30)
    credit_limit    = db.Column(db.Numeric(14,2),default=0)
    currency        = db.Column(db.String(10),   default='INR')
    lead_time_days  = db.Column(db.Integer,      default=7)

    # Banking
    bank_name       = db.Column(db.String(200),  default='')
    account_number  = db.Column(db.String(50),   default='')
    ifsc_code       = db.Column(db.String(20),   default='')
    branch_address  = db.Column(db.Text,         nullable=True)

    # Other
    rating          = db.Column(db.String(20),   default='')
    remarks         = db.Column(db.Text,         nullable=True)

    # Status
    is_active       = db.Column(db.Boolean,      default=True)
    is_deleted      = db.Column(db.Boolean,      default=False)
    deleted_at      = db.Column(db.DateTime,     nullable=True)
    created_at      = db.Column(db.DateTime,     default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime,     default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id':               self.id,
            'supplier_code':    self.supplier_code or '',
            'supplier_name':    self.supplier_name or '',
            'supplier_type':    self.supplier_type or 'RM',
            'contact_person':   self.contact_person or '',
            'phone':            self.phone or '',
            'email':            self.email or '',
            'email_list':       self.email_list or '',
            'company_name':     self.company_name or '',
            'addresses':        self.addresses or '[]',
            'address':          self.address or '',
            'billing_state':    self.billing_state or '',
            'billing_city':     self.billing_city or '',
            'billing_pincode':  self.billing_pincode or '',
            'billing_country':  self.billing_country or 'India',
            'shipping_address': self.shipping_address or '',
            'shipping_state':   self.shipping_state or '',
            'shipping_city':    self.shipping_city or '',
            'shipping_pincode': self.shipping_pincode or '',
            'shipping_country': self.shipping_country or 'India',
            'gst_number':       self.gst_number or '',
            'pan_number':       self.pan_number or '',
            'payment_type':     self.payment_type or '',
            'payment_terms':    self.payment_terms or '',
            'credit_days':      self.credit_days or 30,
            'credit_limit':     float(self.credit_limit or 0),
            'currency':         self.currency or 'INR',
            'lead_time_days':   self.lead_time_days or 7,
            'bank_name':        self.bank_name or '',
            'account_number':   self.account_number or '',
            'ifsc_code':        self.ifsc_code or '',
            'branch_address':   self.branch_address or '',
            'rating':           self.rating or '',
            'remarks':          self.remarks or '',
            'is_active':        self.is_active,
            'is_deleted':       self.is_deleted or False,
        }
