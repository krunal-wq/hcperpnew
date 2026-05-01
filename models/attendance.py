"""
models/attendance.py — Attendance Models

Tables:
  raw_punch_logs  — Device se har punch aata hai (multiple per day per employee)
  attendance      — Daily summary: first punch_in + last punch_out
"""
from datetime import datetime
from .base import db


class RawPunchLog(db.Model):
    """
    Device se jo bhi punch aata hai seedha yahan store hota hai.
    Ek employee ek din mein multiple baar punch kar sakta hai.
    Table: raw_punch_logs
    """
    __tablename__ = 'raw_punch_logs'

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_code       = db.Column(db.String(100), nullable=False, index=True)
    log_date            = db.Column(db.DateTime, nullable=False, index=True)
    serial_number       = db.Column(db.String(100))
    punch_direction     = db.Column(db.String(20))           # IN / OUT
    temperature         = db.Column(db.Numeric(5, 2), default=0.00)
    temperature_state   = db.Column(db.String(50))
    synced_at           = db.Column(db.DateTime, default=datetime.now)

    def __repr__(self):
        return f'<RawPunchLog {self.employee_code} @ {self.log_date}>'


class Attendance(db.Model):
    """
    Daily attendance summary per employee.
    raw_punch_logs se calculate hota hai:
      punch_in  = us din ka PEHLA punch
      punch_out = us din ka AAKHRI punch
    Table: attendance
    """
    __tablename__ = 'attendance'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_code   = db.Column(db.String(100), nullable=False, index=True)
    attendance_date = db.Column(db.Date, nullable=False, index=True)
    punch_in        = db.Column(db.DateTime)
    punch_out       = db.Column(db.DateTime)
    in_device       = db.Column(db.String(100))
    out_device      = db.Column(db.String(100))
    total_hours     = db.Column(db.Numeric(5, 2))
    status          = db.Column(
                        db.Enum('Present', 'Absent', 'Half Day', 'Holiday', 'MIS-PUNCH', 'WOP'),
                        nullable=False, default='Present'
                      )
    # WOP = Week Off Present — employee ne weekly off ke din punch kiya hai.
    # Worker types ke liye Tuesday week off, HCP OFFICE ke liye Sunday.
    created_at      = db.Column(db.DateTime, default=datetime.now)
    updated_at      = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    employee = db.relationship(
        'Employee',
        primaryjoin="foreign(Attendance.employee_code) == Employee.employee_code",
        lazy='joined', uselist=False
    )

    @property
    def working_hours_display(self):
        if self.total_hours is None:
            return '—'
        h = int(self.total_hours)
        m = int((float(self.total_hours) - h) * 60)
        return f"{h}h {m}m"

    @property
    def punch_in_str(self):
        return self.punch_in.strftime('%I:%M %p') if self.punch_in else '—'

    @property
    def punch_out_str(self):
        return self.punch_out.strftime('%I:%M %p') if self.punch_out else 'Not Out'

    def __repr__(self):
        return f'<Attendance {self.employee_code} {self.attendance_date} {self.status}>'


class HolidayMaster(db.Model):
    """
    Company holidays — Diwali, Holi, etc.
    Table: holiday_master
    """
    __tablename__ = 'holiday_master'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    title       = db.Column(db.String(200), nullable=False)
    holiday_date= db.Column(db.Date, nullable=False, unique=True, index=True)
    holiday_type= db.Column(db.String(50), default='National')
    # National / Optional / Restricted / Weekly Off
    description = db.Column(db.String(300))
    is_active   = db.Column(db.Boolean, default=True)
    created_at  = db.Column(db.DateTime, default=datetime.now)
    created_by  = db.Column(db.Integer)

    def __repr__(self):
        return f'<Holiday {self.title} {self.holiday_date}>'


class LateShiftRule(db.Model):
    """
    Employee Type wise late coming time define karo.
    e.g. HCP OFFICE = 10:46 se late
         HCP FACTORY STAFF = 09:15 se late
    Table: late_shift_rules
    """
    __tablename__ = 'late_shift_rules'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_type   = db.Column(db.String(100), nullable=False, unique=True)
    # Shift timing
    shift_start     = db.Column(db.String(5), default='09:00')   # HH:MM
    late_after      = db.Column(db.String(5), nullable=False)     # HH:MM — is time ke baad late
    # e.g. HCP OFFICE = 10:46
    half_day_after  = db.Column(db.String(5), nullable=True)      # HH:MM — is time ke baad half day
    absent_after    = db.Column(db.String(5), nullable=True)      # HH:MM — is time ke baad absent
    shift_end       = db.Column(db.String(5), default='18:00')    # HH:MM
    min_hours_full  = db.Column(db.Numeric(4,2), default=8.00)    # Full day ke liye min hours
    min_hours_half  = db.Column(db.Numeric(4,2), default=4.00)    # Half day ke liye min hours
    is_active       = db.Column(db.Boolean, default=True)
    created_at      = db.Column(db.DateTime, default=datetime.now)
    created_by      = db.Column(db.Integer)
    updated_at      = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    # Relationship to penalty rules
    penalty_rules   = db.relationship('LatePenaltyRule', backref='shift_rule',
                                       lazy=True, cascade='all, delete-orphan',
                                       order_by='LatePenaltyRule.from_count')

    def late_after_dt(self, d):
        """Date + late_after time ka datetime object."""
        h, m = map(int, self.late_after.split(':'))
        return datetime(d.year, d.month, d.day, h, m, 0)

    def __repr__(self):
        return f'<LateShiftRule {self.employee_type} late_after={self.late_after}>'


class LatePenaltyRule(db.Model):
    """
    Late count basis pe penalty rules.
    Ek shift rule ke multiple penalty slabs ho sakte hain.

    Example:
      from_count=3, to_count=3,  time_from=10:46, time_to=10:59, amount=120
      from_count=4, to_count=9,  time_from=10:46, time_to=10:59, amount=250
      from_count=1, to_count=999,time_from=11:00, time_to=None,  amount=259

    Table: late_penalty_rules
    """
    __tablename__ = 'late_penalty_rules'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    shift_rule_id   = db.Column(db.Integer, db.ForeignKey('late_shift_rules.id'),
                                nullable=False, index=True)

    # Time band — punch_in ka time kis range mein hai
    time_from       = db.Column(db.String(5), nullable=False)   # HH:MM e.g. 10:46
    time_to         = db.Column(db.String(5), nullable=True)    # HH:MM e.g. 10:59 (NULL = no upper limit)

    # Late count band — is mahine mein kitni baar late aaya
    from_count      = db.Column(db.Integer, nullable=False, default=1)   # e.g. 3
    to_count        = db.Column(db.Integer, nullable=True)               # e.g. 3 (NULL = no upper limit)

    # Penalty
    penalty_amount  = db.Column(db.Numeric(8,2), nullable=False, default=0)
    penalty_type    = db.Column(db.String(20), default='fixed')
    # fixed = fixed amount | per_day = per late day multiply

    description     = db.Column(db.String(200))   # Rule ka description
    is_active       = db.Column(db.Boolean, default=True)
    sort_order      = db.Column(db.Integer, default=0)
    created_at      = db.Column(db.DateTime, default=datetime.now)
    created_by      = db.Column(db.Integer)

    def time_from_dt(self, d):
        h, m = map(int, self.time_from.split(':'))
        return datetime(d.year, d.month, d.day, h, m, 0)

    def time_to_dt(self, d):
        if not self.time_to: return None
        h, m = map(int, self.time_to.split(':'))
        return datetime(d.year, d.month, d.day, h, m, 59)

    def count_range_label(self):
        if self.to_count is None:
            return f'{self.from_count}+ baar'
        if self.from_count == self.to_count:
            return f'Exactly {self.from_count} baar'
        return f'{self.from_count} – {self.to_count} baar'

    def time_range_label(self):
        if self.time_to:
            return f'{self.time_from} – {self.time_to}'
        return f'{self.time_from} ya baad mein'

    def __repr__(self):
        return f'<LatePenaltyRule shift={self.shift_rule_id} {self.time_from}-{self.time_to} count={self.from_count}-{self.to_count} amt={self.penalty_amount}>'


class EarlyComingRule(db.Model):
    """
    Employee Type wise early coming rules.
    Shift se pehle aane wale employees ke liye tracking + reward rules.
    e.g. HCP OFFICE = 09:00 shift, 08:30 se pehle aaye = early coming
    Table: early_coming_rules
    """
    __tablename__ = 'early_coming_rules'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    employee_type   = db.Column(db.String(100), nullable=False, unique=True)
    shift_start     = db.Column(db.String(5), default='09:00')    # HH:MM
    early_before    = db.Column(db.String(5), nullable=False)      # HH:MM — is se pehle aaye = early
    # e.g. 08:45 — 08:45 se pehle aana = early coming
    min_early_minutes = db.Column(db.Integer, default=15)          # Minimum minutes early to count
    # Reward
    reward_type     = db.Column(db.String(20), default='none')     # none / points / amount / compoff
    reward_amount   = db.Column(db.Numeric(8,2), default=0)        # Reward per early day
    reward_points   = db.Column(db.Integer, default=0)             # Points per early day
    # Count thresholds
    min_per_month   = db.Column(db.Integer, default=0)             # Monthly min early days to get reward
    # Tracking only (no reward)
    track_only      = db.Column(db.Boolean, default=True)          # Sirf track karo, reward mat do
    is_active       = db.Column(db.Boolean, default=True)
    notes           = db.Column(db.Text)
    created_at      = db.Column(db.DateTime, default=datetime.now)
    created_by      = db.Column(db.Integer)
    updated_at      = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def early_before_dt(self, d):
        """Date + early_before time ka datetime object."""
        h, m = map(int, self.early_before.split(':'))
        return datetime(d.year, d.month, d.day, h, m, 0)

    def __repr__(self):
        return f'<EarlyComingRule {self.employee_type} early_before={self.early_before}>'
