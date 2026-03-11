"""
models/employee.py — Employee & Contractor models
"""
from datetime import datetime
from .base import db


def _parse_date(val):
    """Parse date string to date object, return None if empty/invalid."""
    if not val:
        return None
    try:
        from datetime import date
        return date.fromisoformat(val)
    except Exception:
        return None


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
    marriage_anniversary = db.Column(db.Date)

    # Flags
    is_block        = db.Column(db.Boolean, default=False)
    is_late         = db.Column(db.Boolean, default=False)
    is_probation    = db.Column(db.Boolean, default=True)
    status          = db.Column(db.String(20), default='active') # active/inactive/terminated

    # Linked system user (optional)
    user_id         = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reports_to      = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=True)

    remark          = db.Column(db.Text)
    address         = db.Column(db.Text)
    city            = db.Column(db.String(100))
    state           = db.Column(db.String(100))
    country         = db.Column(db.String(100), default='India')
    zip_code        = db.Column(db.String(20))
    subordinates    = db.relationship('Employee',
                          foreign_keys='[Employee.reports_to]',
                          backref=db.backref('manager_emp', remote_side='[Employee.id]'),
                          lazy='dynamic')
    # Identity / KYC
    aadhar_number   = db.Column(db.String(20))
    pan_number      = db.Column(db.String(20))
    passport_number = db.Column(db.String(30))
    passport_expiry = db.Column(db.Date)
    driving_license = db.Column(db.String(30))
    dl_expiry       = db.Column(db.Date)
    uan_number      = db.Column(db.String(20))     # PF UAN
    esic_number     = db.Column(db.String(20))
    nationality     = db.Column(db.String(50), default='Indian')
    religion        = db.Column(db.String(50))
    caste           = db.Column(db.String(50))
    physically_handicapped = db.Column(db.Boolean, default=False)

    # Emergency Contact
    emergency_name      = db.Column(db.String(150))
    emergency_relation  = db.Column(db.String(50))
    emergency_phone     = db.Column(db.String(20))
    emergency_address   = db.Column(db.Text)

    # Bank Details
    bank_name           = db.Column(db.String(150))
    bank_account_number = db.Column(db.String(50))
    bank_ifsc           = db.Column(db.String(20))
    bank_branch         = db.Column(db.String(150))
    bank_account_type   = db.Column(db.String(30))  # Savings/Current
    bank_account_holder = db.Column(db.String(150))

    # Salary Structure
    salary_ctc          = db.Column(db.Numeric(12, 2))
    salary_basic        = db.Column(db.Numeric(12, 2))
    salary_hra          = db.Column(db.Numeric(12, 2))
    salary_da           = db.Column(db.Numeric(12, 2))
    salary_ta           = db.Column(db.Numeric(12, 2))
    salary_special_allow= db.Column(db.Numeric(12, 2))
    salary_medical_allow= db.Column(db.Numeric(12, 2))
    salary_pf_employee  = db.Column(db.Numeric(12, 2))
    salary_pf_employer  = db.Column(db.Numeric(12, 2))
    salary_esic_employee= db.Column(db.Numeric(12, 2))
    salary_esic_employer= db.Column(db.Numeric(12, 2))
    salary_professional_tax = db.Column(db.Numeric(12, 2))
    salary_tds          = db.Column(db.Numeric(12, 2))
    salary_net          = db.Column(db.Numeric(12, 2))
    salary_mode         = db.Column(db.String(30))   # Bank/Cash/Cheque
    salary_effective_date = db.Column(db.Date)
    pay_grade           = db.Column(db.String(50))

    # Work Details
    shift               = db.Column(db.String(50))
    work_hours_per_day  = db.Column(db.Numeric(4,1), default=8.0)
    weekly_off          = db.Column(db.String(50))    # Sunday / Saturday+Sunday
    notice_period_days  = db.Column(db.Integer, default=30)
    confirmation_date   = db.Column(db.Date)
    resignation_date    = db.Column(db.Date)
    last_working_date   = db.Column(db.Date)
    rehire_eligible     = db.Column(db.Boolean, default=True)

    # Education
    highest_qualification = db.Column(db.String(100))
    university          = db.Column(db.String(200))
    passing_year        = db.Column(db.Integer)
    specialization      = db.Column(db.String(100))

    # Previous Employment
    prev_company        = db.Column(db.String(200))
    prev_designation    = db.Column(db.String(100))
    prev_from_date      = db.Column(db.Date)
    prev_to_date        = db.Column(db.Date)
    prev_leaving_reason = db.Column(db.Text)
    total_experience_yrs= db.Column(db.Numeric(4,1))

    # Documents (JSON list of {name, type, filename, base64, uploaded_at})
    documents_json      = db.Column(db.Text(16777215))   # MEDIUMTEXT — base64 docs

    created_by      = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def __repr__(self):
        return f'<Employee {self.employee_code} {self.full_name}>'


class WishLog(db.Model):
    """Track who wished whom today — prevent duplicate notifications."""
    __tablename__ = 'wish_logs'
    id          = db.Column(db.Integer, primary_key=True)
    sender_id   = db.Column(db.Integer, db.ForeignKey('users.id'))   # who sent the wish
    target_emp_id = db.Column(db.Integer, db.ForeignKey('employees.id'))  # whose occasion
    wish_type   = db.Column(db.String(30))  # birthday / work_anniversary / marriage_anniversary
    wish_date   = db.Column(db.Date)        # date of occasion (today)
    wish_text   = db.Column(db.Text)        # actual wish message sent
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)

    sender   = db.relationship('User', foreign_keys=[sender_id])
    target   = db.relationship('Employee', foreign_keys=[target_emp_id])

    __table_args__ = (
        db.UniqueConstraint('sender_id','target_emp_id','wish_type','wish_date', name='uq_wish_once_per_day'),
    )
