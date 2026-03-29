"""
seed_attendance.py — Dummy employees + attendance data seed karo
Saari situations cover hoti hain:
  Present, Absent, Half Day, Holiday, MIS-PUNCH, Late, Early Exit
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from index import app
from models import db, Employee
from models.attendance import RawPunchLog, Attendance
from datetime import datetime, date, timedelta
import random

DEPARTMENTS = ['Engineering', 'Sales', 'HR', 'Finance', 'Operations', 'Marketing']
DESIGNATIONS = {
    'Engineering': ['Software Engineer', 'Senior Developer', 'Tech Lead'],
    'Sales':       ['Sales Executive', 'Sales Manager', 'BDE'],
    'HR':          ['HR Executive', 'HR Manager', 'Recruiter'],
    'Finance':     ['Accountant', 'Finance Manager', 'Auditor'],
    'Operations':  ['Operations Executive', 'Team Lead', 'Manager'],
    'Marketing':   ['Marketing Executive', 'Content Writer', 'Brand Manager'],
}
DEVICES = ['BIO-001', 'BIO-002', 'BIO-003']

# 10 dummy employees
EMPLOYEES = [
    ('EMP001', '1001', 'Aarav',    'Shah',      'Engineering', 'Software Engineer', 'Full Time'),
    ('EMP002', '1002', 'Priya',    'Patel',     'Sales',       'Sales Manager',     'Full Time'),
    ('EMP003', '1003', 'Rohan',    'Mehta',     'HR',          'HR Executive',      'Full Time'),
    ('EMP004', '1004', 'Sneha',    'Desai',     'Finance',     'Accountant',        'Full Time'),
    ('EMP005', '1005', 'Vikram',   'Joshi',     'Operations',  'Operations Executive','Full Time'),
    ('EMP006', '1006', 'Kavya',    'Iyer',      'Marketing',   'Marketing Executive','Full Time'),
    ('EMP007', '1007', 'Arjun',    'Nair',      'Engineering', 'Tech Lead',         'Full Time'),
    ('EMP008', '1008', 'Divya',    'Reddy',     'Sales',       'Sales Executive',   'Part Time'),
    ('EMP009', '1009', 'Siddharth','Kumar',     'Finance',     'Finance Manager',   'Full Time'),
    ('EMP010', '1010', 'Ananya',   'Sharma',    'HR',          'HR Manager',        'Full Time'),
]

def seed():
    with app.app_context():
        print("\n🌱 Seeding dummy data...\n")

        # ── Step 1: Employees ──
        created_emps = []
        for emp_code, emp_id, fname, lname, dept, desig, etype in EMPLOYEES:
            existing = Employee.query.filter_by(employee_code=emp_code).first()
            if existing:
                print(f"   ⏭  Employee {emp_code} already exists")
                created_emps.append(existing)
                continue

            e = Employee(
                employee_code   = emp_code,
                employee_id     = emp_id,
                first_name      = fname,
                last_name       = lname,
                mobile          = f'98{random.randint(10000000,99999999)}',
                email           = f'{fname.lower()}.{lname.lower()}@hcp.com',
                gender          = random.choice(['Male', 'Female']),
                department      = dept,
                designation     = desig,
                employee_type   = etype,
                date_of_joining = date(2023, random.randint(1,12), random.randint(1,28)),
                status          = 'active',
                location        = 'Ahmedabad',
            )
            db.session.add(e)
            created_emps.append(e)
            print(f"   ✅ Employee {emp_code} — {fname} {lname} ({dept})")

        db.session.commit()
        print(f"\n   👥 {len(created_emps)} employees ready\n")

        # ── Step 2: Attendance — last 30 days ──
        today      = date.today()
        start_date = today - timedelta(days=29)

        # Clear existing seed data
        existing_att = Attendance.query.filter(
            Attendance.attendance_date >= start_date
        ).count()
        if existing_att > 200:
            # Force re-seed today's data
            from models.attendance import Attendance as Att
            today_count = Att.query.filter_by(attendance_date=today).count()
            if today_count > 0:
                print(f"   ⏭  Attendance already seeded ({existing_att} records, today: {today_count})")
                print("\n✅ Seed complete!\n")
                return
            print(f"   ℹ️  Past data exists but today missing — adding today's data...")

        att_count = 0
        punch_count = 0

        for emp_code, emp_id, fname, lname, dept, desig, etype in EMPLOYEES:
            current = start_date
            while current <= today:
                weekday = current.weekday()  # 0=Mon, 6=Sun

                # Sunday = Holiday for most, but 2-3 employees present (duty)
                if weekday == 6:
                    # Last 2 employees Sunday ko present rahenge (duty)
                    emp_index = EMPLOYEES.index((emp_code, emp_id, fname, lname, dept, desig, etype))
                    if emp_index >= 8:  # EMP009, EMP010 Sunday duty
                        pin  = datetime(current.year, current.month, current.day, 9, random.randint(0,20))
                        pout = datetime(current.year, current.month, current.day, 14, random.randint(0,30))
                        dev  = random.choice(DEVICES)
                        _add_raw_punches(emp_code, emp_id, [pin, pout], dev, current)
                        _add_attendance(emp_code, current, 'Half Day', pin, pout, dev, dev,
                                        round((pout-pin).seconds/3600, 2))
                    else:
                        _add_attendance(emp_code, current, 'Holiday', None, None, None, None, None)
                    att_count += 1
                    current += timedelta(days=1)
                    continue

                # Saturday = Half Day (only morning shift)
                if weekday == 5:
                    pin  = datetime(current.year, current.month, current.day, 9, random.randint(0,15))
                    pout = datetime(current.year, current.month, current.day, 13, random.randint(0,30))
                    dev  = random.choice(DEVICES)
                    _add_raw_punches(emp_code, emp_id, [pin, pout], dev, current)
                    _add_attendance(emp_code, current, 'Half Day', pin, pout, dev, dev,
                                    round((pout-pin).seconds/3600, 2))
                    att_count += 1
                    punch_count += 2
                    current += timedelta(days=1)
                    continue

                # Weekdays — random situation
                rand = random.random()

                if rand < 0.05:
                    # ABSENT (5%)
                    _add_attendance(emp_code, current, 'Absent', None, None, None, None, None)
                    att_count += 1

                elif rand < 0.10:
                    # MIS-PUNCH — only one punch (10%)
                    punch_time = datetime(current.year, current.month, current.day,
                                          random.randint(8,10), random.randint(0,59))
                    dev = random.choice(DEVICES)
                    _add_raw_punches(emp_code, emp_id, [punch_time], dev, current)
                    _add_attendance(emp_code, current, 'MIS-PUNCH', punch_time, None, dev, None, None)
                    att_count += 1
                    punch_count += 1

                elif rand < 0.18:
                    # HALF DAY (8%)
                    pin  = datetime(current.year, current.month, current.day, 9, random.randint(0,20))
                    pout = datetime(current.year, current.month, current.day, 13, random.randint(0,30))
                    dev  = random.choice(DEVICES)
                    _add_raw_punches(emp_code, emp_id, [pin, pout], dev, current)
                    _add_attendance(emp_code, current, 'Half Day', pin, pout, dev, dev,
                                    round((pout-pin).seconds/3600, 2))
                    att_count += 1
                    punch_count += 2

                elif rand < 0.30:
                    # LATE — came after 9:15 (12%)
                    late_min = random.randint(16, 90)
                    pin  = datetime(current.year, current.month, current.day, 9,  15 + late_min % 45)
                    pout = datetime(current.year, current.month, current.day, 18, random.randint(0,30))
                    dev  = random.choice(DEVICES)
                    # Multiple punches during day
                    mid_punches = _random_mid_punches(current, pin, pout)
                    all_punches = [pin] + mid_punches + [pout]
                    _add_raw_punches(emp_code, emp_id, all_punches, dev, current)
                    _add_attendance(emp_code, current, 'Present', pin, pout, dev, dev,
                                    round((pout-pin).seconds/3600, 2))
                    att_count += 1
                    punch_count += len(all_punches)

                else:
                    # PRESENT — normal (65%)
                    in_min  = random.randint(0, 14)   # 9:00–9:14
                    out_min = random.randint(0, 45)
                    pin  = datetime(current.year, current.month, current.day, 9,  in_min)
                    pout = datetime(current.year, current.month, current.day, 18, out_min)
                    dev  = random.choice(DEVICES)
                    mid_punches = _random_mid_punches(current, pin, pout)
                    all_punches = [pin] + mid_punches + [pout]
                    _add_raw_punches(emp_code, emp_id, all_punches, dev, current)
                    _add_attendance(emp_code, current, 'Present', pin, pout, dev, dev,
                                    round((pout-pin).seconds/3600, 2))
                    att_count += 1
                    punch_count += len(all_punches)

                current += timedelta(days=1)

        db.session.commit()
        print(f"   ✅ {att_count} attendance records added")
        print(f"   ✅ {punch_count} raw punch logs added")
        print(f"\n✅ Seed complete! Ab /hr/attendance visit karo.\n")


def _random_mid_punches(d, pin, pout):
    """Lunch break aur random mid-day punches generate karo."""
    punches = []
    # Lunch out ~1:00 PM
    lunch_out = datetime(d.year, d.month, d.day, 13, random.randint(0, 15))
    lunch_in  = datetime(d.year, d.month, d.day, 14, random.randint(0, 15))
    if lunch_out > pin and lunch_in < pout:
        punches += [lunch_out, lunch_in]
    return punches


def _add_raw_punches(emp_code, emp_id, punch_times, device, log_date):
    for i, pt in enumerate(punch_times):
        # Avoid duplicate
        exists = RawPunchLog.query.filter_by(
            employee_code=emp_id,  # device uses employee_id
            log_date=pt
        ).first()
        if exists:
            continue
        direction = 'IN' if i % 2 == 0 else 'OUT'
        rp = RawPunchLog(
            employee_code   = emp_id,   # device sends employee_id
            log_date        = pt,
            serial_number   = device,
            punch_direction = direction,
            temperature     = round(random.uniform(36.1, 37.2), 1),
            temperature_state = 'Normal',
            synced_at       = datetime.now(),
        )
        db.session.add(rp)


def _add_attendance(emp_code, att_date, status, pin, pout, in_dev, out_dev, total_hrs):
    exists = Attendance.query.filter_by(
        employee_code=emp_code,
        attendance_date=att_date
    ).first()
    if exists:
        return
    a = Attendance(
        employee_code   = emp_code,
        attendance_date = att_date,
        punch_in        = pin,
        punch_out       = pout,
        in_device       = in_dev,
        out_device      = out_dev,
        total_hours     = total_hrs,
        status          = status,
    )
    db.session.add(a)


if __name__ == '__main__':
    seed()
