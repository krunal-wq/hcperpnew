"""
models/employee.py — Employee & Contractor models
"""
from datetime import datetime
from .base import db


class Contractor(db.Model):
    """Contractor master — matches provided DB schema"""
    __tablename__ = 'contractors'

    id             = db.Column(db.BigInteger, primary_key=True)
    company_name   = db.Column(db.String(255), nullable=False)
    supply         = db.Column(db.String(100))
    pancard        = db.Column(db.String(50))
    gstno          = db.Column(db.String(50))
    remarks        = db.Column(db.Text)
    contract_id    = db.Column(db.String(50), nullable=False)
    contact_person = db.Column(db.String(255), nullable=False)
    contact_no     = db.Column(db.String(30))
    email_address  = db.Column(db.String(100))
    address        = db.Column(db.Text)
    is_deleted     = db.Column(db.Integer, default=0)
    status         = db.Column(db.Integer, default=1)   # 1=active, 0=inactive
    created_by     = db.Column(db.String(255))
    created_date   = db.Column(db.DateTime, default=datetime.now)
    modified_by    = db.Column(db.String(255))
    modified_date  = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationship
    employees = db.relationship('Employee', backref='contractor_rel', lazy=True,
                                foreign_keys='Employee.contractor_id')

    def __repr__(self):
        return f'<Contractor {self.company_name}>'


class Employee(db.Model):
    __tablename__ = 'employees'

    id              = db.Column(db.Integer, primary_key=True)
    employee_code   = db.Column(db.String(50), unique=True, nullable=True)
    qr_code_base64  = db.Column(db.Text(16777215))   # MEDIUMTEXT — base64 QR image

    # Basic Info
    first_name      = db.Column(db.String(100), nullable=False)
    last_name       = db.Column(db.String(100), nullable=False)
    mobile          = db.Column(db.String(20), nullable=False)
    email           = db.Column(db.String(150))
    gender          = db.Column(db.String(10))
    profile_photo   = db.Column(db.Text(16777215))   # MEDIUMTEXT — base64 photo

    # Social
    linkedin        = db.Column(db.String(200))
    facebook        = db.Column(db.String(200))

    # Professional
    department      = db.Column(db.String(100))
    designation     = db.Column(db.String(100))
    employee_type   = db.Column(db.String(50))    # Full Time/Part Time/Contract/Intern
    date_of_joining = db.Column(db.Date)
    location        = db.Column(db.String(100))

    # Contractor link
    is_contractor   = db.Column(db.Boolean, default=False)
    contractor_id   = db.Column(db.BigInteger, db.ForeignKey('contractors.id'), nullable=True)

    # Personal
    date_of_birth   = db.Column(db.Date)
    blood_group     = db.Column(db.String(10))
    marital_status  = db.Column(db.String(20))    # Single/Married/Divorced/Widowed

    # Flags
    is_block        = db.Column(db.Boolean, default=False)
    is_late         = db.Column(db.Boolean, default=False)
    is_probation    = db.Column(db.Boolean, default=True)
    status          = db.Column(db.String(20), default='active') # active/inactive/terminated

    # Linked system user (optional)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)

    remark          = db.Column(db.Text)
    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self):
        return f'<Employee {self.employee_code} {self.full_name}>'
