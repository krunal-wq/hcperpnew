"""
models/hr_rules.py — Comprehensive HRMS Rules Engine

Tables:
  hr_shifts              — Shift master (Morning/Evening/Night/General)
  hr_locations           — Location master (Office/Factory/WFH)
  hr_late_rules          — Late Coming Rules (Location+Shift wise)
  hr_early_going_rules   — Early Going Rules
  hr_leave_policies      — Leave Policy master
  hr_leave_types         — Leave types per policy
  hr_lop_rules           — Loss of Pay rules
  hr_overtime_rules      — Overtime rules
  hr_compoff_rules       — Comp Off rules
  hr_absent_rules        — Absent penalty rules
"""
from datetime import datetime
from .base import db


# ═══════════════════════════════════════════════════════
# SHIFT MASTER
# ═══════════════════════════════════════════════════════
class HRShift(db.Model):
    """Shift timings master."""
    __tablename__ = 'hr_shifts'

    id            = db.Column(db.Integer, primary_key=True)
    name          = db.Column(db.String(100), nullable=False)        # Morning, Evening, General
    code          = db.Column(db.String(20), nullable=False, unique=True)  # MORN, EVE, GEN
    shift_start   = db.Column(db.String(5), nullable=False)          # HH:MM
    shift_end     = db.Column(db.String(5), nullable=False)          # HH:MM
    late_after    = db.Column(db.String(5))                          # HH:MM
    half_day_after= db.Column(db.String(5))
    absent_after  = db.Column(db.String(5))
    early_go_before= db.Column(db.String(5))                        # before shift_end
    min_hours_full= db.Column(db.Numeric(4,2), default=8.00)
    min_hours_half= db.Column(db.Numeric(4,2), default=4.00)
    break_minutes = db.Column(db.Integer, default=60)               # Lunch break
    weekly_off    = db.Column(db.String(50), default='Sunday')       # Sunday / Saturday,Sunday
    color         = db.Column(db.String(10), default='#2563eb')
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.now)
    created_by    = db.Column(db.Integer)
    updated_at    = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __repr__(self):
        return f'<HRShift {self.name} {self.shift_start}-{self.shift_end}>'


# ═══════════════════════════════════════════════════════
# LOCATION MASTER
# ═══════════════════════════════════════════════════════
class HRLocation(db.Model):
    """Company locations/branches."""
    __tablename__ = 'hr_locations'

    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100), nullable=False, unique=True)  # HCP OFFICE, FACTORY
    code       = db.Column(db.String(20), nullable=False, unique=True)   # OFFICE, FACT
    address    = db.Column(db.Text)
    city       = db.Column(db.String(100))
    state      = db.Column(db.String(100))
    is_active  = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    created_by = db.Column(db.Integer)

    def __repr__(self):
        return f'<HRLocation {self.name}>'


# ═══════════════════════════════════════════════════════
# LATE COMING RULE (Location + Shift wise)
# ═══════════════════════════════════════════════════════
class HRLateRule(db.Model):
    """
    Late coming rules — location + shift + employee_type combination.
    Har combination ka alag rule ho sakta hai.
    """
    __tablename__ = 'hr_late_rules'

    id              = db.Column(db.Integer, primary_key=True)
    # Scope
    location_id     = db.Column(db.Integer, db.ForeignKey('hr_locations.id'))
    shift_id        = db.Column(db.Integer, db.ForeignKey('hr_shifts.id'))
    employee_type   = db.Column(db.String(100))           # NULL = applies to all types
    # Rule
    grace_minutes   = db.Column(db.Integer, default=0)   # Grace period in minutes
    late_after      = db.Column(db.String(5))             # HH:MM override (else use shift)
    half_day_after  = db.Column(db.String(5))
    absent_after    = db.Column(db.String(5))
    # Monthly free lates (no penalty)
    free_lates_per_month = db.Column(db.Integer, default=0)
    # Auto deduct
    auto_deduct_lop = db.Column(db.Boolean, default=False)  # Auto LOP lagao
    is_active       = db.Column(db.Boolean, default=True)
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.now)
    created_by      = db.Column(db.Integer)
    updated_at      = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    location    = db.relationship('HRLocation', lazy='joined')
    shift       = db.relationship('HRShift',    lazy='joined')
    penalties   = db.relationship('HRLatePenaltySlab', backref='late_rule',
                                  cascade='all, delete-orphan',
                                  order_by='HRLatePenaltySlab.sort_order')

    def __repr__(self):
        return f'<HRLateRule loc={self.location_id} shift={self.shift_id}>'


class HRLatePenaltySlab(db.Model):
    """Penalty slabs for late coming rule."""
    __tablename__ = 'hr_late_penalty_slabs'

    id            = db.Column(db.Integer, primary_key=True)
    late_rule_id  = db.Column(db.Integer, db.ForeignKey('hr_late_rules.id'), nullable=False)
    time_from     = db.Column(db.String(5), nullable=False)   # Punch time from HH:MM
    time_to       = db.Column(db.String(5))                   # Punch time to HH:MM (NULL=no limit)
    from_count    = db.Column(db.Integer, default=1)          # Late count from
    to_count      = db.Column(db.Integer)                     # Late count to (NULL=no limit)
    penalty_amount= db.Column(db.Numeric(8,2), default=0)
    penalty_type  = db.Column(db.String(20), default='fixed') # fixed/per_day/half_day/full_day
    description   = db.Column(db.String(200))
    sort_order    = db.Column(db.Integer, default=0)
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.now)


# ═══════════════════════════════════════════════════════
# EARLY GOING RULE
# ═══════════════════════════════════════════════════════
class HREarlyGoingRule(db.Model):
    """Early leaving rules — location + shift wise."""
    __tablename__ = 'hr_early_going_rules'

    id              = db.Column(db.Integer, primary_key=True)
    location_id     = db.Column(db.Integer, db.ForeignKey('hr_locations.id'))
    shift_id        = db.Column(db.Integer, db.ForeignKey('hr_shifts.id'))
    employee_type   = db.Column(db.String(100))
    name            = db.Column(db.String(150), nullable=False)
    # Rules
    grace_minutes   = db.Column(db.Integer, default=0)        # Grace before shift end
    half_day_before = db.Column(db.String(5))                 # HH:MM — before this = half day
    absent_before   = db.Column(db.String(5))                 # HH:MM — before this = absent
    free_early_per_month = db.Column(db.Integer, default=0)
    # Penalty slab
    penalty_per_early= db.Column(db.Numeric(8,2), default=0)  # Per early go penalty
    penalty_type    = db.Column(db.String(20), default='fixed')
    auto_deduct_lop = db.Column(db.Boolean, default=False)
    is_active       = db.Column(db.Boolean, default=True)
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.now)
    created_by      = db.Column(db.Integer)
    updated_at      = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    location = db.relationship('HRLocation', lazy='joined')
    shift    = db.relationship('HRShift',    lazy='joined')

    def __repr__(self):
        return f'<HREarlyGoingRule {self.name}>'


# ═══════════════════════════════════════════════════════
# OVERTIME RULE
# ═══════════════════════════════════════════════════════
class HROvertimeRule(db.Model):
    """Overtime calculation rules — location + shift wise."""
    __tablename__ = 'hr_overtime_rules'

    id              = db.Column(db.Integer, primary_key=True)
    location_id     = db.Column(db.Integer, db.ForeignKey('hr_locations.id'))
    shift_id        = db.Column(db.Integer, db.ForeignKey('hr_shifts.id'))
    employee_type   = db.Column(db.String(100))
    name            = db.Column(db.String(150), nullable=False)
    # OT starts after
    ot_after_minutes= db.Column(db.Integer, default=30)       # shift_end + X min = OT start
    min_ot_minutes  = db.Column(db.Integer, default=60)       # Minimum OT minutes to count
    max_ot_hours_day= db.Column(db.Numeric(4,2), default=4)   # Max OT per day
    max_ot_hours_month= db.Column(db.Numeric(6,2), default=50) # Max OT per month
    # Rate
    ot_rate_type    = db.Column(db.String(20), default='1.5x') # 1x/1.5x/2x/fixed
    ot_fixed_rate   = db.Column(db.Numeric(8,2))               # If fixed rate
    # Weekend / Holiday OT rate
    weekend_ot_rate = db.Column(db.String(20), default='2x')
    holiday_ot_rate = db.Column(db.String(20), default='2x')
    # Comp off instead of pay
    give_compoff    = db.Column(db.Boolean, default=False)
    compoff_min_hours= db.Column(db.Numeric(4,2), default=4)
    is_active       = db.Column(db.Boolean, default=True)
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.now)
    created_by      = db.Column(db.Integer)
    updated_at      = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    location = db.relationship('HRLocation', lazy='joined')
    shift    = db.relationship('HRShift',    lazy='joined')

    def __repr__(self):
        return f'<HROvertimeRule {self.name}>'


# ═══════════════════════════════════════════════════════
# LEAVE POLICY
# ═══════════════════════════════════════════════════════
class HRLeavePolicy(db.Model):
    """Leave policy master — location + employee_type wise."""
    __tablename__ = 'hr_leave_policies'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(150), nullable=False)
    location_id     = db.Column(db.Integer, db.ForeignKey('hr_locations.id'))
    employee_type   = db.Column(db.String(100))
    applicable_from = db.Column(db.Date)
    # Leave accumulation
    accrual_type    = db.Column(db.String(20), default='yearly') # yearly/monthly
    sandwich_rule   = db.Column(db.Boolean, default=True)        # Weekend between leaves count?
    carry_forward   = db.Column(db.Boolean, default=True)
    max_carry_forward= db.Column(db.Integer, default=15)          # Max days carry forward
    encashment      = db.Column(db.Boolean, default=False)        # Leave encashment allowed?
    max_encashment  = db.Column(db.Integer, default=10)
    # Probation
    probation_leave_allowed= db.Column(db.Boolean, default=False)
    # Negative leave
    allow_negative_leave   = db.Column(db.Boolean, default=False)
    max_negative_days      = db.Column(db.Integer, default=0)
    is_active       = db.Column(db.Boolean, default=True)
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.now)
    created_by      = db.Column(db.Integer)
    updated_at      = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    location    = db.relationship('HRLocation', lazy='joined')
    leave_types = db.relationship('HRLeaveType', backref='policy',
                                  cascade='all, delete-orphan',
                                  order_by='HRLeaveType.sort_order')

    def __repr__(self):
        return f'<HRLeavePolicy {self.name}>'


class HRLeaveType(db.Model):
    """Individual leave types inside a policy."""
    __tablename__ = 'hr_leave_types'

    id            = db.Column(db.Integer, primary_key=True)
    policy_id     = db.Column(db.Integer, db.ForeignKey('hr_leave_policies.id'), nullable=False)
    name          = db.Column(db.String(100), nullable=False)  # Annual Leave, Sick Leave
    code          = db.Column(db.String(20), nullable=False)   # AL, SL, CL
    days_per_year = db.Column(db.Numeric(5,1), nullable=False)
    # Rules
    min_days      = db.Column(db.Numeric(3,1), default=0.5)    # Min leave duration
    max_days      = db.Column(db.Numeric(5,1))                  # Max continuous leave
    advance_notice_days = db.Column(db.Integer, default=0)      # Days advance notice required
    carry_forward = db.Column(db.Boolean, default=True)
    max_carry_forward = db.Column(db.Integer)
    encashable    = db.Column(db.Boolean, default=False)
    paid          = db.Column(db.Boolean, default=True)         # Paid / Unpaid
    gender        = db.Column(db.String(10))                    # NULL/Male/Female (e.g. maternity)
    color         = db.Column(db.String(10), default='#2563eb')
    icon          = db.Column(db.String(10), default='📅')
    sort_order    = db.Column(db.Integer, default=0)
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<HRLeaveType {self.code} {self.days_per_year}days>'


# ═══════════════════════════════════════════════════════
# LOSS OF PAY (LOP) RULE
# ═══════════════════════════════════════════════════════
class HRLOPRule(db.Model):
    """Loss of Pay rules — location + employee_type wise."""
    __tablename__ = 'hr_lop_rules'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(150), nullable=False)
    location_id     = db.Column(db.Integer, db.ForeignKey('hr_locations.id'))
    employee_type   = db.Column(db.String(100))
    # Calculation
    lop_basis       = db.Column(db.String(20), default='working_days')  # working_days/calendar_days
    paid_days_basis = db.Column(db.String(20), default='actual')        # actual/30/26
    # What triggers LOP
    absent_triggers_lop  = db.Column(db.Boolean, default=True)
    late_triggers_lop    = db.Column(db.Boolean, default=False)
    late_lop_after_count = db.Column(db.Integer, default=3)  # After X lates = 0.5 day LOP
    lop_per_late_count   = db.Column(db.Integer, default=3)  # Every X lates = 0.5 LOP
    # Half day LOP
    half_day_lop_after_count = db.Column(db.Integer, default=3)
    # Salary calculation
    daily_rate_formula = db.Column(db.String(50), default='basic_gross/working_days')
    include_allowances = db.Column(db.Boolean, default=True)
    is_active       = db.Column(db.Boolean, default=True)
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.now)
    created_by      = db.Column(db.Integer)
    updated_at      = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    location = db.relationship('HRLocation', lazy='joined')

    def __repr__(self):
        return f'<HRLOPRule {self.name}>'


# ═══════════════════════════════════════════════════════
# ABSENT PENALTY RULE
# ═══════════════════════════════════════════════════════
class HRAbsentRule(db.Model):
    """Absent penalty rules beyond LOP."""
    __tablename__ = 'hr_absent_rules'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(150), nullable=False)
    location_id     = db.Column(db.Integer, db.ForeignKey('hr_locations.id'))
    employee_type   = db.Column(db.String(100))
    # Trigger
    absent_days_from    = db.Column(db.Integer, default=1)    # From X absent days per month
    absent_days_to      = db.Column(db.Integer)               # To X days (NULL = no limit)
    # Penalty
    penalty_per_day     = db.Column(db.Numeric(8,2), default=0)
    penalty_type        = db.Column(db.String(20), default='fixed')  # fixed/percent_basic
    # Consecutive absent
    consecutive_absent_days = db.Column(db.Integer, default=3)  # X consecutive = warning
    auto_terminate_days     = db.Column(db.Integer)              # X days = auto terminate
    notify_hr           = db.Column(db.Boolean, default=True)
    is_active           = db.Column(db.Boolean, default=True)
    notes               = db.Column(db.Text)
    created_at          = db.Column(db.DateTime, default=datetime.now)
    created_by          = db.Column(db.Integer)
    updated_at          = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    location = db.relationship('HRLocation', lazy='joined')

    def __repr__(self):
        return f'<HRAbsentRule {self.name}>'


# ═══════════════════════════════════════════════════════
# COMP OFF RULE
# ═══════════════════════════════════════════════════════
class HRCompOffRule(db.Model):
    """Compensatory Off rules."""
    __tablename__ = 'hr_compoff_rules'

    id              = db.Column(db.Integer, primary_key=True)
    name            = db.Column(db.String(150), nullable=False)
    location_id     = db.Column(db.Integer, db.ForeignKey('hr_locations.id'))
    employee_type   = db.Column(db.String(100))
    # Eligibility
    min_hours_worked = db.Column(db.Numeric(4,2), default=4)  # Min hours worked on holiday for comp off
    comp_off_days   = db.Column(db.Numeric(3,1), default=1)   # Days awarded
    # Work on
    applicable_on_sunday  = db.Column(db.Boolean, default=True)
    applicable_on_holiday = db.Column(db.Boolean, default=True)
    applicable_on_saturday= db.Column(db.Boolean, default=True)
    # Validity
    comp_off_validity_days= db.Column(db.Integer, default=30)  # Must use within X days
    # Approval
    needs_approval  = db.Column(db.Boolean, default=True)
    max_comp_off_balance = db.Column(db.Numeric(4,1), default=6)  # Max balance allowed
    is_active       = db.Column(db.Boolean, default=True)
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.now)
    created_by      = db.Column(db.Integer)
    updated_at      = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    location = db.relationship('HRLocation', lazy='joined')

    def __repr__(self):
        return f'<HRCompOffRule {self.name}>'
