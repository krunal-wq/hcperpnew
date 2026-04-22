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

    # ── Document Numbers ────────────────────────────────────────────────
    aadhaar_no       = db.Column(db.String(14))    # XXXX XXXX XXXX
    msme_no          = db.Column(db.String(25))    # UDYAM-XX-00-0000000
    trade_license_no = db.Column(db.String(50))
    bank_account_no  = db.Column(db.String(20))
    ifsc_code        = db.Column(db.String(11))

    # ── Document File Paths (stored in static/uploads/contractors/) ──
    aadhaar_file  = db.Column(db.String(255))
    pan_file      = db.Column(db.String(255))
    gst_file      = db.Column(db.String(255))
    msme_file     = db.Column(db.String(255))
    trade_file    = db.Column(db.String(255))
    bank_file     = db.Column(db.String(255))

    # ── Other / Extra Documents (JSON list) ────────────────────────
    # Format: [{"type": "ISO Certificate", "doc_no": "...", "file": "path/..."}, ...]
    other_docs    = db.Column(db.Text)  # JSON string

    # Relationship
    employees = db.relationship('Employee', backref='contractor_rel', lazy=True,
                                foreign_keys='Employee.contractor_id')

    def __repr__(self):
        return f'<Contractor {self.company_name}>'


class Employee(db.Model):
    __tablename__ = 'employees'

    id              = db.Column(db.Integer, primary_key=True)
    employee_code   = db.Column(db.String(50), unique=True, nullable=True)
    employee_id     = db.Column(db.String(50), unique=True, nullable=True)  # Biometric/Device ID
    qr_code_base64  = db.Column(db.Text(16777215))   # MEDIUMTEXT — base64 QR image

    # Basic Info
    first_name      = db.Column(db.String(100), nullable=False)
    middle_name     = db.Column(db.String(100), nullable=True)
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
    is_deleted      = db.Column(db.Boolean, default=False)
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
        parts = [self.first_name, self.middle_name or '', self.last_name]
        return ' '.join(p for p in parts if p).strip()

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


# ── Salary Config ─────────────────────────────────────────────────────────────

class SalaryConfig(db.Model):
    """Key-value store for salary calculation config (shared across all employees)."""
    __tablename__ = 'salary_config'
    id         = db.Column(db.Integer, primary_key=True)
    key        = db.Column(db.String(50), unique=True, nullable=False)
    value      = db.Column(db.String(100), nullable=False)
    updated_by = db.Column(db.String(100))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    _DEFAULTS = {
        'basic_pct':    '40',
        'hra_pct':      '50',
        'da_pct':       '10',
        'ta_fixed':     '1600',
        'med_fixed':    '1250',
        'pf_emp_pct':   '12',
        'pf_er_pct':    '12',
        'esic_emp_pct': '0.75',
        'esic_er_pct':  '3.25',
        'esic_limit':   '21000',
        'pt_fixed':     '200',

        # ─── HCP Salary Policy Rules (Phase 7) ──────────────────────
        'hcp_enabled':             '1',       # 1 = use HCP rules, 0 = use legacy CTC calc
        'hcp_high_gross_thresh':   '30000',   # Gross >= this uses "high" rules
        'hcp_esic_limit':          '21000',   # Gross <= this → ESIC applies (HO only)
        'hcp_low_basic_fixed':     '15000',   # Fixed Basic+DA when Gross < threshold
        'hcp_high_basic_pct':      '50',      # Basic % of Gross when Gross >= threshold
        'hcp_hra_pct_of_basic':    '40',      # HRA % of Basic+DA
        'hcp_conv_pct_of_basic':   '30',      # Conveyance % of Basic+DA
        'hcp_medical_fixed':       '1200',    # Medical fixed amount (high range)
        'hcp_pt_threshold':        '12000',   # Gross >= this → PT applies
        'hcp_pt_amount':           '200',     # PT amount when applicable
        'hcp_pf_emp_pct':          '12',      # PF Employee %
        'hcp_pf_er_pct':           '13',      # PF Employer % (incl admin + EDLI)
        'hcp_esic_emp_pct':        '0.75',    # ESIC Employee %
        'hcp_esic_er_pct':         '3.25',    # ESIC Employer %
        'hcp_bonus_pct':           '8.33',    # Bonus % of Gross
    }

    @classmethod
    def get_config(cls):
        rows = {r.key: r.value for r in cls.query.all()}
        result = {}
        for k, default in cls._DEFAULTS.items():
            try:
                result[k] = float(rows.get(k, default))
            except (ValueError, TypeError):
                result[k] = float(default)
        return result

    @classmethod
    def save_config(cls, data, updated_by='System'):
        for k, v in data.items():
            row = cls.query.filter_by(key=k).first()
            if row:
                row.value      = str(v)
                row.updated_by = updated_by
                row.updated_at = datetime.utcnow()
            else:
                db.session.add(cls(key=k, value=str(v), updated_by=updated_by))
        db.session.commit()


# ── Salary Component ──────────────────────────────────────────────────────────

class SalaryComponent(db.Model):
    """Dynamic salary components — earnings, deductions, employer contributions."""
    __tablename__ = 'salary_components'

    id                 = db.Column(db.Integer, primary_key=True)
    name               = db.Column(db.String(100), nullable=False)
    code               = db.Column(db.String(50),  unique=True, nullable=False)
    component_type     = db.Column(db.String(30),  nullable=False)   # earning / deduction / employer_contrib
    calc_type          = db.Column(db.String(30),  nullable=False)   # pct_of_basic / pct_of_gross / pct_of_ctc / fixed / pct_of_basic_capped / balance
    value              = db.Column(db.Float,  default=0)
    cap_amount         = db.Column(db.Float,  nullable=True)
    apply_if_gross_lte = db.Column(db.Float,  nullable=True)
    sort_order         = db.Column(db.Integer, default=0)
    is_active          = db.Column(db.Boolean, default=True)
    is_system          = db.Column(db.Boolean, default=False)
    description        = db.Column(db.String(255))
    updated_by         = db.Column(db.String(100))
    updated_at         = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_at         = db.Column(db.DateTime, default=datetime.utcnow)

    @classmethod
    def get_all_active(cls):
        return cls.query.filter_by(is_active=True).order_by(
            cls.component_type, cls.sort_order
        ).all()

    def to_dict(self):
        return {
            'id':                 self.id,
            'name':               self.name,
            'code':               self.code,
            'component_type':     self.component_type,
            'calc_type':          self.calc_type,
            'value':              self.value,
            'cap_amount':         self.cap_amount,
            'apply_if_gross_lte': self.apply_if_gross_lte,
            'sort_order':         self.sort_order,
            'is_active':          self.is_active,
            'is_system':          self.is_system,
            'description':        self.description,
            'updated_by':         self.updated_by,
        }


class EmployeeTypeMaster(db.Model):
    """Employee Type Master — HCP OFFICE, HCP FACTORY STAFF, etc."""
    __tablename__ = 'employee_type_master'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name       = db.Column(db.String(100), nullable=False, unique=True)
    sort_order = db.Column(db.Integer, default=0)
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    created_by = db.Column(db.Integer, nullable=True)

    def __repr__(self): return f'<EmployeeTypeMaster {self.name}>'


class EmployeeLocationMaster(db.Model):
    """Employee Location/Branch Master — Office, Factory, etc."""
    __tablename__ = 'employee_location_master'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name       = db.Column(db.String(100), nullable=False, unique=True)
    sort_order = db.Column(db.Integer, default=0)
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    created_by = db.Column(db.Integer, nullable=True)

    def __repr__(self): return f'<EmployeeLocationMaster {self.name}>'


class DepartmentMaster(db.Model):
    """Department Master — Sales, HR, IT, etc."""
    __tablename__ = 'department_master'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name       = db.Column(db.String(100), nullable=False, unique=True)
    code       = db.Column(db.String(20))
    sort_order = db.Column(db.Integer, default=0)
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    created_by = db.Column(db.Integer, nullable=True)

    def __repr__(self): return f'<DepartmentMaster {self.name}>'


class DesignationMaster(db.Model):
    """Designation Master — Manager, Executive, etc."""
    __tablename__ = 'designation_master'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name       = db.Column(db.String(100), nullable=False, unique=True)
    department = db.Column(db.String(100))   # Optional: link to dept
    sort_order = db.Column(db.Integer, default=0)
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    created_by = db.Column(db.Integer, nullable=True)

    def __repr__(self): return f'<DesignationMaster {self.name}>'
