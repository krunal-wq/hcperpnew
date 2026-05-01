"""
attendance_routes.py — Attendance API + Dashboard

API:
  POST /api/receive_logs          ← PHP push_to_live() yahan data bhejta hai

Routes:
  GET  /hr/attendance/            ← Dashboard
  GET  /hr/attendance/logs        ← Raw punch logs table
  GET  /hr/attendance/report      ← Monthly attendance report
"""
import json
from decimal import Decimal
from datetime import datetime, date, timedelta
from flask import Blueprint, request, jsonify, render_template, abort, flash, redirect, url_for
from flask_login import login_required, current_user
from models import db, Employee
from models.attendance import RawPunchLog, Attendance
from permissions import get_sub_perm

attendance_bp = Blueprint('attendance', __name__)


# ─────────────────────────────────────────────────────────────────
# Helper: gate decorator-style for sub-perm + admin bypass
# ─────────────────────────────────────────────────────────────────
def _require_sub_perm(module, key, redirect_to='attendance.attendance_dashboard'):
    """
    Returns True if access allowed. If denied, calls flash() and returns False.
    Caller should: `if not _require_sub_perm(...): return redirect(...)`
    Admin role bypasses all checks.
    """
    if not current_user.is_authenticated:
        return False
    if current_user.role == 'admin':
        return True
    return bool(get_sub_perm(module, key))

# ── Auth key — PHP push_to_live() mein jo Authorization header hai ──
PUSH_API_KEY = "HCP_PUSH_2024"

# ── Shift timing ──
SHIFT_START = (9, 0)    # 9:00 AM
SHIFT_END   = (18, 0)   # 6:00 PM
HALF_DAY_HOURS = 4.0    # 4 ghante se kam = Half Day


# ══════════════════════════════════════════════════════════════
# HELPER: Device API response fields parse karo
# ══════════════════════════════════════════════════════════════
def _get_field(entry, *keys):
    """
    Multiple possible key names try karo (case-insensitive).
    Device APIs har vendor ka alag JSON shape use karta hai —
    isiliye CamelCase, snake_case, lowercase sab try hoti hain.
    """
    if not isinstance(entry, dict):
        return None
    # First: exact match (fast path)
    for k in keys:
        v = entry.get(k)
        if v is not None and str(v).strip() != '':
            return str(v).strip()
    # Fallback: case-insensitive match
    lower_map = {str(k).lower(): k for k in entry.keys()}
    for k in keys:
        actual = lower_map.get(str(k).lower())
        if actual is not None:
            v = entry.get(actual)
            if v is not None and str(v).strip() != '':
                return str(v).strip()
    return None


def _parse_datetime(val):
    """
    Bahut saare formats try karo. Device APIs alag-alag format mein
    dates bhejti hain — Z-suffix UTC, milliseconds, ISO with offset, etc.
    """
    if not val:
        return None
    s = str(val).strip()
    # Strip 'Z' (UTC marker) and milliseconds for parsing
    if s.endswith('Z'):
        s = s[:-1]
    if '.' in s and 'T' in s:
        # e.g. 2026-04-30T08:55:00.123 → strip ms
        try:
            dot = s.index('.')
            tplus = s.find('+', dot)
            tminus = s.find('-', dot)
            cut = min([x for x in [tplus, tminus, len(s)] if x > 0])
            s = s[:dot] + s[cut:] if cut < len(s) else s[:dot]
        except Exception:
            pass

    formats = (
        '%Y-%m-%d %H:%M:%S',
        '%Y-%m-%dT%H:%M:%S',
        '%Y-%m-%dT%H:%M:%S%z',
        '%d/%m/%Y %H:%M:%S',
        '%m/%d/%Y %H:%M:%S',
        '%Y-%m-%d %H:%M',
        '%d-%m-%Y %H:%M:%S',
        '%d-%m-%Y %H:%M',
        '%Y/%m/%d %H:%M:%S',
        '%d.%m.%Y %H:%M:%S',
    )
    for fmt in formats:
        try:
            return datetime.strptime(s, fmt)
        except Exception:
            continue

    # Last try: epoch millis or seconds
    try:
        n = float(s)
        if n > 1e12:   # milliseconds
            return datetime.fromtimestamp(n / 1000.0)
        if n > 1e9:    # seconds
            return datetime.fromtimestamp(n)
    except Exception:
        pass
    return None


def _get_punch_direction(entry):
    """IN ya OUT detect karo device log se."""
    val = _get_field(entry, 'Direction', 'PunchType', 'punch_type',
                     'Type', 'type', 'punch_direction')
    if val:
        v = val.upper()
        if v in ('IN', '0', 'CHECKIN', 'CHECK IN', 'ENTRY', 'E'):
            return 'IN'
        if v in ('OUT', '1', 'CHECKOUT', 'CHECK OUT', 'EXIT', 'X'):
            return 'OUT'
    return 'IN'   # default IN


# ══════════════════════════════════════════════════════════════
# CORE: attendance table update karo (first IN + last OUT)
# ══════════════════════════════════════════════════════════════
def _update_attendance(employee_code, log_date_only):
    """
    raw_punch_logs se us employee ka us din ka
    PEHLA punch = punch_in
    AAKHRI punch = punch_out
    calculate karke attendance table mein save karo.
    """
    # Us din ke saare punches sorted by time
    punches = RawPunchLog.query.filter(
        RawPunchLog.employee_code == employee_code,
        db.func.date(RawPunchLog.log_date) == log_date_only
    ).order_by(RawPunchLog.log_date.asc()).all()

    if not punches:
        return

    first_punch = punches[0]
    last_punch  = punches[-1]

    punch_in    = first_punch.log_date
    in_device   = first_punch.serial_number

    # punch_out sirf tab jab ek se zyada punch ho
    punch_out   = last_punch.log_date  if len(punches) > 1 else None
    out_device  = last_punch.serial_number if len(punches) > 1 else None

    # Total hours calculate karo
    total_hours = None
    if punch_in and punch_out and punch_out > punch_in:
        diff_minutes = (punch_out - punch_in).total_seconds() / 3600
        total_hours  = round(diff_minutes, 2)

    # Status determine karo
    if punch_out is None:
        status = 'MIS-PUNCH'   # Sirf ek hi punch hai — in ya out pata nahi
    elif total_hours is not None and total_hours < HALF_DAY_HOURS:
        status = 'Half Day'
    else:
        status = 'Present'

    # Attendance record upsert karo
    att = Attendance.query.filter_by(
        employee_code=employee_code,
        attendance_date=log_date_only
    ).first()

    # Employee link — try employee_id first, then employee_code
    from models import Employee as _Emp
    emp_obj = _Emp.query.filter_by(employee_id=employee_code).first()
    if not emp_obj:
        emp_obj = _Emp.query.filter_by(employee_code=employee_code).first()

    if not att:
        att = Attendance(
            employee_code=employee_code,
            attendance_date=log_date_only
        )
        db.session.add(att)

    att.punch_in    = punch_in
    att.punch_out   = punch_out
    att.in_device   = in_device
    att.out_device  = out_device
    att.total_hours = total_hours
    att.status      = status
    att.updated_at  = datetime.now()


# ══════════════════════════════════════════════════════════════
# API: POST /api/receive_logs
# PHP push_to_live() yahan call karta hai
# ══════════════════════════════════════════════════════════════
@attendance_bp.route('/api/receive_logs', methods=['POST'])
def receive_logs():
    import sys

    # ── DEBUG: log incoming request basics ──
    sys.stderr.write(f"\n========== RECEIVE_LOGS DEBUG ==========\n")
    sys.stderr.write(f"  From IP      : {request.remote_addr}\n")
    sys.stderr.write(f"  Auth header  : '{request.headers.get('Authorization', '<MISSING>')}'\n")
    sys.stderr.write(f"  Content-Type : '{request.headers.get('Content-Type', '<MISSING>')}'\n")
    sys.stderr.write(f"  Body bytes   : {len(request.get_data())}\n")
    sys.stderr.flush()

    # ── Auth check ──
    auth = request.headers.get('Authorization', '')
    if auth != PUSH_API_KEY:
        sys.stderr.write(f"  ❌ Auth FAILED — expected '{PUSH_API_KEY}'\n")
        sys.stderr.flush()
        return jsonify({'error': 'Unauthorized'}), 401
    sys.stderr.write(f"  ✅ Auth OK\n")
    sys.stderr.flush()

    # ── JSON parse ──
    try:
        data = request.get_json(force=True)
    except Exception as ex:
        sys.stderr.write(f"  ❌ JSON parse failed: {ex}\n")
        sys.stderr.flush()
        return jsonify({'error': 'Invalid JSON'}), 400

    if not data:
        return jsonify({'error': 'Empty payload'}), 400

    # ── List normalize karo ──
    if isinstance(data, dict):
        logs_list = (data.get('data') or data.get('logs') or
                     data.get('DeviceLogs') or data.get('Records') or
                     data.get('Result')   or data.get('result')  or
                     [data])
    elif isinstance(data, list):
        logs_list = data
    else:
        return jsonify({'error': 'Unexpected format'}), 400

    # ── DEBUG: dump first 2 entries' structure ──
    sys.stderr.write(f"  payload type : {type(data).__name__}\n")
    sys.stderr.write(f"  logs_list len: {len(logs_list)}\n")
    for i, entry in enumerate(logs_list[:2]):
        sys.stderr.write(f"  entry[{i}] type: {type(entry).__name__}\n")
        if isinstance(entry, dict):
            sys.stderr.write(f"  entry[{i}] keys: {list(entry.keys())}\n")
            sys.stderr.write(f"  entry[{i}] data: {entry}\n")
    sys.stderr.flush()

    inserted       = 0
    skipped        = 0
    skip_reasons   = {'no_emp': 0, 'no_dt': 0, 'duplicate': 0, 'other': 0}
    errors         = []
    to_update      = set()
    sample_skipped = None    # pehla skipped entry yaad rakhne ke liye

    # ── Extended key list — alag alag biometric brands ke saath compatible ──
    # eSSL, ZKTeco, Realtime, Matrix, Anviz, etc.
    EMP_CODE_KEYS = (
        'EmployeeCode', 'employee_code', 'Employee_Code',
        'CardNo', 'card_no', 'CardNumber',
        'UserID', 'UserId', 'userid', 'user_id', 'UserCode',
        'EmpCode', 'emp_code', 'EmpId', 'emp_id', 'EmployeeID',
        'PIN', 'pin', 'Pin', 'BadgeNumber', 'badge_number',
        'StaffCode', 'staff_code', 'StaffID',
    )
    LOG_DT_KEYS = (
        'LogTime', 'log_date', 'log_time', 'LogDate',
        'PunchTime', 'punch_time', 'punchTime',
        'DateTime', 'datetime', 'DateAndTime',
        'Time', 'time', 'Timestamp', 'timestamp',
        'AttendanceTime', 'attendance_time',
        'CheckTime', 'check_time', 'EventTime',
    )

    for entry in logs_list:
        try:
            if not isinstance(entry, dict):
                skipped += 1
                skip_reasons['other'] += 1
                if sample_skipped is None: sample_skipped = repr(entry)[:200]
                continue

            emp_code = _get_field(entry, *EMP_CODE_KEYS)
            log_dt   = _parse_datetime(_get_field(entry, *LOG_DT_KEYS))

            if not emp_code:
                skipped += 1
                skip_reasons['no_emp'] += 1
                if sample_skipped is None: sample_skipped = f"no emp_code → keys={list(entry.keys())}"
                continue
            if not log_dt:
                skipped += 1
                skip_reasons['no_dt'] += 1
                if sample_skipped is None:
                    raw_dt = _get_field(entry, *LOG_DT_KEYS)
                    sample_skipped = f"no log_dt (raw={raw_dt!r}) → keys={list(entry.keys())}"
                continue

            # Duplicate check
            exists = RawPunchLog.query.filter_by(
                employee_code=emp_code,
                log_date=log_dt
            ).first()
            if exists:
                skipped += 1
                skip_reasons['duplicate'] += 1
                continue

            punch = RawPunchLog(
                employee_code     = emp_code,
                log_date          = log_dt,
                serial_number     = _get_field(entry, 'SerialNumber', 'serial_number',
                                               'DeviceId', 'device_id', 'MachineNo',
                                               'TerminalId', 'terminal_id'),
                punch_direction   = _get_punch_direction(entry),
                temperature       = _get_field(entry, 'Temperature', 'temperature') or 0.00,
                temperature_state = _get_field(entry, 'TemperatureState', 'temperature_state'),
                synced_at         = datetime.now(),
            )
            db.session.add(punch)
            to_update.add((emp_code, log_dt.date()))
            inserted += 1

        except Exception as e:
            errors.append(str(e))
            skip_reasons['other'] += 1
            continue

    # ── DEBUG: summary print ──
    sys.stderr.write(f"  ─ SUMMARY ─\n")
    sys.stderr.write(f"  inserted     : {inserted}\n")
    sys.stderr.write(f"  skipped      : {skipped} → {skip_reasons}\n")
    if sample_skipped:
        sys.stderr.write(f"  first skip   : {sample_skipped}\n")
    if errors:
        sys.stderr.write(f"  errors       : {errors[:3]}\n")
    sys.stderr.flush()

    # ── Commit raw punches ──
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        sys.stderr.write(f"  ❌ DB commit failed: {e}\n")
        sys.stderr.flush()
        return jsonify({'error': f'DB error: {str(e)}'}), 500

    # ── attendance table update — SKIPPED in receive_logs ──
    # 7000+ entries pe loop chalane se gunicorn worker timeout ho jata hai.
    # Solution: HR admin /attendance_log/sync screen se "Run Summary Sync"
    # press kare — woh batch processing optimal hai aur progress dikhta hai.
    #
    # Agar real-time chahiye toh background queue (Celery/RQ) chahiye —
    # for now ye trade-off acceptable hai kyunki PHP cron 1 din mein 1-2
    # baar chalti hai aur sync 30 second mein ho jaata hai manually.
    sys.stderr.write(f"  ℹ️  Skipping inline _update_attendance() to avoid "
                     f"timeout — use /attendance_log/sync to recompute.\n")
    sys.stderr.flush()

    return jsonify({
        'status':       'ok',
        'inserted':     inserted,
        'skipped':      skipped,
        'skip_reasons': skip_reasons,
        'total':        len(logs_list),
        'errors':       errors[:5],
        'sample_skip':  sample_skipped,
        'note':         'Raw punches saved. Run /attendance_log/sync to update attendance table.',
    }), 200


# ══════════════════════════════════════════════════════════════
# DASHBOARD: GET /hr/attendance/
# ══════════════════════════════════════════════════════════════
@attendance_bp.route('/hr/attendance/')
@attendance_bp.route('/hr/attendance')
@login_required
def attendance_dashboard():
    today       = date.today()
    month_start = today.replace(day=1)

    # Today stats
    today_present  = Attendance.query.filter(
        Attendance.attendance_date == today,
        Attendance.status == 'Present'
    ).count()
    today_absent   = Attendance.query.filter(
        Attendance.attendance_date == today,
        Attendance.status == 'Absent'
    ).count()
    today_halfday  = Attendance.query.filter(
        Attendance.attendance_date == today,
        Attendance.status == 'Half Day'
    ).count()
    today_mispunch = Attendance.query.filter(
        Attendance.attendance_date == today,
        Attendance.status == 'MIS-PUNCH'
    ).count()
    today_holiday  = Attendance.query.filter(
        Attendance.attendance_date == today,
        Attendance.status == 'Holiday'
    ).count()

    total_employees = Employee.query.filter_by(status='active').count()

    # Last sync time
    last_raw  = RawPunchLog.query.order_by(RawPunchLog.synced_at.desc()).first()
    last_sync = last_raw.synced_at.strftime('%d %b %Y, %I:%M %p') if last_raw else 'No data yet'

    # Today list — all statuses (Present, Absent, Half Day, MIS-PUNCH, Holiday)
    today_list = db.session.query(Attendance).filter(
        Attendance.attendance_date == today
    ).order_by(
        db.case(
            (Attendance.status == 'Present',  1),
            (Attendance.status == 'Half Day', 2),
            (Attendance.status == 'MIS-PUNCH',3),
            (Attendance.status == 'Absent',   4),
            (Attendance.status == 'Holiday',  5),
            else_=6
        ),
        Attendance.punch_in
    ).limit(200).all()

    # Last 7 days trend — Present / Absent / Half Day
    trend_data = []
    for i in range(6, -1, -1):
        d = today - timedelta(days=i)
        stats = dict(
            db.session.query(Attendance.status, db.func.count(Attendance.id))
            .filter(Attendance.attendance_date == d)
            .group_by(Attendance.status).all()
        )
        trend_data.append({
            'date':     d.strftime('%d %b'),
            'present':  stats.get('Present', 0),
            'absent':   stats.get('Absent', 0),
            'half_day': stats.get('Half Day', 0),
        })

    # This month present count
    month_present = Attendance.query.filter(
        Attendance.attendance_date >= month_start,
        Attendance.attendance_date <= today,
        Attendance.status == 'Present'
    ).count()

    return render_template(
        'hr/attendance/dashboard.html',
        today           = today,
        today_present   = today_present,
        today_absent    = today_absent,
        today_halfday   = today_halfday,
        today_mispunch  = today_mispunch,
        today_holiday   = today_holiday,
        total_employees = total_employees,
        last_sync       = last_sync,
        today_list      = today_list,
        trend_data      = json.dumps(trend_data),
        month_present   = month_present,
        active_page     = 'hr_attendance',
    )


# ══════════════════════════════════════════════════════════════
# RAW LOGS PAGE: GET /hr/attendance/logs
# ══════════════════════════════════════════════════════════════
@attendance_bp.route('/hr/attendance/logs')
@login_required
def attendance_logs():
    page       = request.args.get('page', 1, type=int)
    emp_search = request.args.get('emp', '').strip()
    date_from  = request.args.get('from', '')
    date_to    = request.args.get('to', '')

    q = RawPunchLog.query

    if emp_search:
        q = q.filter(RawPunchLog.employee_code.ilike(f'%{emp_search}%'))
    if date_from:
        try:
            q = q.filter(db.func.date(RawPunchLog.log_date) >=
                         datetime.strptime(date_from, '%Y-%m-%d').date())
        except Exception:
            pass
    if date_to:
        try:
            q = q.filter(db.func.date(RawPunchLog.log_date) <=
                         datetime.strptime(date_to, '%Y-%m-%d').date())
        except Exception:
            pass

    pagination = q.order_by(RawPunchLog.log_date.desc()).paginate(
        page=page, per_page=50, error_out=False
    )

    return render_template(
        'hr/attendance/logs.html',
        logs        = pagination.items,
        pagination  = pagination,
        emp_search  = emp_search,
        date_from   = date_from,
        date_to     = date_to,
        active_page = 'hr_attendance',
    )


# ══════════════════════════════════════════════════════════════
# REPORT PAGE: GET /hr/attendance/report
# ══════════════════════════════════════════════════════════════
@attendance_bp.route('/hr/attendance/report')
@login_required
def attendance_report():
    month_str  = request.args.get('month', date.today().strftime('%Y-%m'))
    emp_search = request.args.get('emp', '').strip()
    page       = request.args.get('page', 1, type=int)

    try:
        month_start = datetime.strptime(month_str + '-01', '%Y-%m-%d').date()
    except Exception:
        month_start = date.today().replace(day=1)

    # Month end
    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)

    status_filter = request.args.get('status', '').strip()

    q = Attendance.query.filter(
        Attendance.attendance_date >= month_start,
        Attendance.attendance_date <= month_end
    )
    if emp_search:
        q = q.filter(Attendance.employee_code.ilike(f'%{emp_search}%'))
    if status_filter:
        q = q.filter(Attendance.status == status_filter)

    pagination = q.order_by(
        Attendance.attendance_date.desc(),
        Attendance.employee_code
    ).paginate(page=page, per_page=50, error_out=False)

    # Month summary stats
    month_stats = dict(
        db.session.query(Attendance.status, db.func.count(Attendance.id))
        .filter(
            Attendance.attendance_date >= month_start,
            Attendance.attendance_date <= month_end
        ).group_by(Attendance.status).all()
    )

    return render_template(
        'hr/attendance/report.html',
        records       = pagination.items,
        pagination    = pagination,
        month_str     = month_str,
        month_start   = month_start,
        month_end     = month_end,
        emp_search    = emp_search,
        status_filter = status_filter,
        month_stats   = month_stats,
        active_page   = 'hr_attendance',
    )


# ══════════════════════════════════════════════════════════════
# AJAX: GET /hr/attendance/api/daily-summary
# ══════════════════════════════════════════════════════════════
@attendance_bp.route('/hr/attendance/api/daily-summary')
@login_required
def api_daily_summary():
    month_str = request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        month_start = datetime.strptime(month_str + '-01', '%Y-%m-%d').date()
    except Exception:
        month_start = date.today().replace(day=1)

    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year + 1, month=1, day=1) - timedelta(days=1)
    else:
        month_end = month_start.replace(month=month_start.month + 1, day=1) - timedelta(days=1)

    rows = db.session.query(
        Attendance.attendance_date,
        db.func.count(db.case(
            (Attendance.status == 'Present', 1))).label('present'),
        db.func.count(db.case(
            (Attendance.status == 'Absent', 1))).label('absent'),
        db.func.count(db.case(
            (Attendance.status == 'Half Day', 1))).label('half_day'),
        db.func.count(db.case(
            (Attendance.status == 'MIS-PUNCH', 1))).label('mis_punch'),
    ).filter(
        Attendance.attendance_date >= month_start,
        Attendance.attendance_date <= month_end,
    ).group_by(Attendance.attendance_date).order_by(Attendance.attendance_date).all()

    return jsonify({'data': [
        {
            'date':      r.attendance_date.strftime('%d %b'),
            'present':   r.present,
            'absent':    r.absent,
            'half_day':  r.half_day,
            'mis_punch': r.mis_punch,
        } for r in rows
    ]})


# ══════════════════════════════════════════════════════════════
# MANUAL ATTENDANCE ENTRY & EDIT
# GET/POST /hr/attendance/manual
# GET/POST /hr/attendance/<int:id>/edit
# ══════════════════════════════════════════════════════════════
@attendance_bp.route('/hr/attendance/manual', methods=['GET', 'POST'])
@login_required
def attendance_manual():
    from flask_login import current_user
    if current_user.role not in ('admin', 'manager', 'hr'):
        from flask import abort; abort(403)

    employees = Employee.query.filter_by(status='active').order_by(Employee.first_name).all()
    msg = None

    if request.method == 'POST':
        emp_code    = request.form.get('employee_code', '').strip()
        att_date    = request.form.get('attendance_date', '').strip()
        punch_in_s  = request.form.get('punch_in', '').strip()
        punch_out_s = request.form.get('punch_out', '').strip()
        status      = request.form.get('status', 'Present')
        in_device   = request.form.get('in_device', 'MANUAL').strip()

        try:
            att_date_obj = datetime.strptime(att_date, '%Y-%m-%d').date()
            pin  = datetime.strptime(f"{att_date} {punch_in_s}",  '%Y-%m-%d %H:%M') if punch_in_s  else None
            pout = datetime.strptime(f"{att_date} {punch_out_s}", '%Y-%m-%d %H:%M') if punch_out_s else None

            total_hours = None
            if pin and pout and pout > pin:
                total_hours = round((pout - pin).total_seconds() / 3600, 2)

            # Auto status
            if status == 'auto':
                if not pin:                 status = 'Absent'
                elif not pout:              status = 'MIS-PUNCH'
                elif total_hours < 4:       status = 'Half Day'
                else:                       status = 'Present'

            existing = Attendance.query.filter_by(
                employee_code=emp_code, attendance_date=att_date_obj
            ).first()

            if existing:
                existing.punch_in    = pin
                existing.punch_out   = pout
                existing.in_device   = in_device
                existing.out_device  = in_device if pout else None
                existing.total_hours = total_hours
                existing.status      = status
                existing.updated_at  = datetime.now()
                msg = ('success', f'Attendance updated for {emp_code} on {att_date}')
            else:
                att = Attendance(
                    employee_code=emp_code, attendance_date=att_date_obj,
                    punch_in=pin, punch_out=pout,
                    in_device=in_device, out_device=in_device if pout else None,
                    total_hours=total_hours, status=status,
                )
                db.session.add(att)
                msg = ('success', f'Attendance added for {emp_code} on {att_date}')

            db.session.commit()

            # Raw punch log bhi add karo
            if pin:
                if not RawPunchLog.query.filter_by(employee_code=emp_code, log_date=pin).first():
                    db.session.add(RawPunchLog(
                        employee_code=emp_code, log_date=pin,
                        serial_number='MANUAL', punch_direction='IN', synced_at=datetime.now()
                    ))
            if pout:
                if not RawPunchLog.query.filter_by(employee_code=emp_code, log_date=pout).first():
                    db.session.add(RawPunchLog(
                        employee_code=emp_code, log_date=pout,
                        serial_number='MANUAL', punch_direction='OUT', synced_at=datetime.now()
                    ))
            db.session.commit()

        except Exception as e:
            db.session.rollback()
            msg = ('error', f'Error: {str(e)}')

    # Recent entries
    recent = Attendance.query.order_by(
        Attendance.updated_at.desc()
    ).limit(20).all()

    return render_template('hr/attendance/manual.html',
        employees=employees, msg=msg, recent=recent,
        today=date.today().strftime('%Y-%m-%d'),
        active_page='att_manual'
    )


@attendance_bp.route('/hr/attendance/<int:att_id>/edit', methods=['GET', 'POST'])
@login_required
def attendance_edit(att_id):
    from flask_login import current_user
    if current_user.role not in ('admin', 'manager', 'hr'):
        from flask import abort; abort(403)

    att       = Attendance.query.get_or_404(att_id)
    employees = Employee.query.filter_by(status='active').order_by(Employee.first_name).all()
    msg       = None

    if request.method == 'POST':
        try:
            att_date    = request.form.get('attendance_date', '')
            punch_in_s  = request.form.get('punch_in', '').strip()
            punch_out_s = request.form.get('punch_out', '').strip()
            status      = request.form.get('status', att.status)

            att.attendance_date = datetime.strptime(att_date, '%Y-%m-%d').date()
            att.punch_in   = datetime.strptime(f"{att_date} {punch_in_s}",  '%Y-%m-%d %H:%M') if punch_in_s  else None
            att.punch_out  = datetime.strptime(f"{att_date} {punch_out_s}", '%Y-%m-%d %H:%M') if punch_out_s else None
            att.in_device  = request.form.get('in_device', att.in_device or 'MANUAL')
            att.status     = status
            att.updated_at = datetime.now()

            if att.punch_in and att.punch_out and att.punch_out > att.punch_in:
                att.total_hours = round((att.punch_out - att.punch_in).total_seconds() / 3600, 2)
            else:
                att.total_hours = None

            db.session.commit()
            msg = ('success', 'Attendance updated successfully!')
        except Exception as e:
            db.session.rollback()
            msg = ('error', str(e))

    return render_template('hr/attendance/edit.html',
        att=att, employees=employees, msg=msg,
        active_page='my_attendance'
    )


# ══════════════════════════════════════════════════════════════
# LATE COMERS & ABSENT REPORT
# GET /hr/attendance/late-absent
# ══════════════════════════════════════════════════════════════
@attendance_bp.route('/hr/attendance/late-absent')
@login_required
def attendance_late_absent():
    report_date = request.args.get('date', date.today().strftime('%Y-%m-%d'))
    report_type = request.args.get('type', 'late')  # late / absent / mispunch
    dept_filter = request.args.get('dept', '')

    try:
        filter_date = datetime.strptime(report_date, '%Y-%m-%d').date()
    except Exception:
        filter_date = date.today()

    SHIFT_START_H, SHIFT_START_M = 9, 0
    GRACE_MINUTES = 15

    # Late comers — punch_in after 9:15
    if report_type == 'late':
        shift_start = datetime(filter_date.year, filter_date.month, filter_date.day,
                               SHIFT_START_H, SHIFT_START_M + GRACE_MINUTES)
        records = Attendance.query.filter(
            Attendance.attendance_date == filter_date,
            Attendance.punch_in != None,
            Attendance.punch_in > shift_start,
            Attendance.status.in_(['Present', 'Half Day'])
        ).order_by(Attendance.punch_in.asc()).all()

        # Late minutes calculate
        for rec in records:
            if rec.punch_in:
                base = datetime(filter_date.year, filter_date.month, filter_date.day,
                                SHIFT_START_H, SHIFT_START_M)
                rec._late_min = max(0, int((rec.punch_in - base).total_seconds() / 60))
            else:
                rec._late_min = 0

    elif report_type == 'absent':
        records = Attendance.query.filter(
            Attendance.attendance_date == filter_date,
            Attendance.status == 'Absent'
        ).order_by(Attendance.employee_code).all()
        for rec in records:
            rec._late_min = 0

    else:  # mispunch
        records = Attendance.query.filter(
            Attendance.attendance_date == filter_date,
            Attendance.status == 'MIS-PUNCH'
        ).order_by(Attendance.punch_in.asc()).all()
        for rec in records:
            rec._late_min = 0

    # Dept filter
    if dept_filter:
        records = [r for r in records if r.employee and r.employee.department == dept_filter]

    # All departments for filter dropdown
    departments = db.session.query(Employee.department).filter(
        Employee.department != None, Employee.status == 'active'
    ).distinct().order_by(Employee.department).all()
    departments = [d[0] for d in departments]

    # Summary counts for the date
    summary = dict(
        db.session.query(Attendance.status, db.func.count(Attendance.id))
        .filter(Attendance.attendance_date == filter_date)
        .group_by(Attendance.status).all()
    )
    # Late count
    shift_start_dt = datetime(filter_date.year, filter_date.month, filter_date.day,
                               SHIFT_START_H, SHIFT_START_M + GRACE_MINUTES)
    late_count = Attendance.query.filter(
        Attendance.attendance_date == filter_date,
        Attendance.punch_in > shift_start_dt,
        Attendance.status.in_(['Present', 'Half Day'])
    ).count()

    return render_template('hr/attendance/late_absent.html',
        records=records, report_date=report_date, report_type=report_type,
        filter_date=filter_date, dept_filter=dept_filter,
        departments=departments, summary=summary, late_count=late_count,
        active_page='att_late'
    )


# ══════════════════════════════════════════════════════════════
# HOLIDAY MASTER
# GET/POST /hr/attendance/holidays
# POST /hr/attendance/holidays/<int:id>/delete
# ══════════════════════════════════════════════════════════════
@attendance_bp.route('/hr/attendance/holidays', methods=['GET', 'POST'])
@login_required
def holiday_master():
    from flask_login import current_user
    from models.attendance import HolidayMaster
    if current_user.role not in ('admin', 'manager', 'hr'):
        from flask import abort; abort(403)

    msg = None
    if request.method == 'POST':
        title        = request.form.get('title', '').strip()
        holiday_date = request.form.get('holiday_date', '').strip()
        holiday_type = request.form.get('holiday_type', 'National')
        description  = request.form.get('description', '').strip()

        if not title or not holiday_date:
            msg = ('error', 'Title aur Date required hai.')
        else:
            try:
                hdate = datetime.strptime(holiday_date, '%Y-%m-%d').date()
                existing = HolidayMaster.query.filter_by(holiday_date=hdate).first()
                if existing:
                    msg = ('error', f'{holiday_date} pe pehle se holiday hai: {existing.title}')
                else:
                    h = HolidayMaster(
                        title=title, holiday_date=hdate,
                        holiday_type=holiday_type, description=description,
                        created_by=current_user.id
                    )
                    db.session.add(h)
                    db.session.commit()
                    msg = ('success', f'Holiday "{title}" added!')
            except Exception as e:
                db.session.rollback()
                msg = ('error', str(e))

    year  = request.args.get('year', date.today().year, type=int)
    holidays = HolidayMaster.query.filter(
        db.extract('year', HolidayMaster.holiday_date) == year
    ).order_by(HolidayMaster.holiday_date).all()

    return render_template('hr/attendance/holidays.html',
        holidays=holidays, msg=msg, year=year,
        today=date.today().strftime('%Y-%m-%d'),
        active_page='att_holidays'
    )


@attendance_bp.route('/hr/attendance/holidays/<int:hid>/delete', methods=['POST'])
@login_required
def holiday_delete(hid):
    from flask_login import current_user
    from models.attendance import HolidayMaster
    if current_user.role not in ('admin',):
        from flask import abort; abort(403)
    h = HolidayMaster.query.get_or_404(hid)
    db.session.delete(h)
    db.session.commit()
    from flask import redirect, url_for
    return redirect(url_for('attendance.holiday_master'))


# ══════════════════════════════════════════════════════════════
# EMPLOYEE — MY ATTENDANCE
# GET /hr/attendance/my
# ══════════════════════════════════════════════════════════════
@attendance_bp.route('/hr/attendance/my')
@login_required
def my_attendance():
    from flask_login import current_user
    from flask import abort

    # Employee dhundo current user ke liye
    emp = Employee.query.filter_by(user_id=current_user.id).first()
    if not emp:
        # role admin/hr ho toh redirect to dashboard
        if current_user.role in ('admin', 'manager', 'hr'):
            from flask import redirect, url_for
            return redirect(url_for('attendance.attendance_dashboard'))
        abort(404)

    month_str = request.args.get('month', date.today().strftime('%Y-%m'))
    try:
        month_start = datetime.strptime(month_str + '-01', '%Y-%m-%d').date()
    except Exception:
        month_start = date.today().replace(day=1)

    if month_start.month == 12:
        month_end = month_start.replace(year=month_start.year+1, month=1, day=1) - timedelta(days=1)
    else:
        month_end = month_start.replace(month=month_start.month+1, day=1) - timedelta(days=1)

    # Us mahine ki saari attendance
    records = Attendance.query.filter(
        Attendance.employee_code == emp.employee_code,
        Attendance.attendance_date >= month_start,
        Attendance.attendance_date <= month_end
    ).order_by(Attendance.attendance_date.asc()).all()

    # Month summary
    att_map = {r.attendance_date: r for r in records}
    summary = {'Present':0,'Absent':0,'Half Day':0,'MIS-PUNCH':0,'Holiday':0}
    for r in records:
        summary[r.status] = summary.get(r.status, 0) + 1

    # Today's punches
    today_punches = RawPunchLog.query.filter(
        RawPunchLog.employee_code == (emp.employee_id or emp.employee_code),
        db.func.date(RawPunchLog.log_date) == date.today()
    ).order_by(RawPunchLog.log_date.asc()).all()

    # Calendar data — har din ka status
    calendar_days = []
    current_day = month_start
    while current_day <= month_end:
        rec = att_map.get(current_day)
        calendar_days.append({
            'date':    current_day,
            'weekday': current_day.weekday(),
            'status':  rec.status if rec else ('Future' if current_day > date.today() else 'No Data'),
            'punch_in':  rec.punch_in.strftime('%I:%M %p')  if rec and rec.punch_in  else None,
            'punch_out': rec.punch_out.strftime('%I:%M %p') if rec and rec.punch_out else None,
            'hours':     rec.working_hours_display          if rec else None,
        })
        current_day += timedelta(days=1)

    return render_template('hr/attendance/my_attendance.html',
        emp=emp, month_str=month_str,
        month_start=month_start, month_end=month_end,
        records=records, calendar_days=calendar_days,
        summary=summary, today_punches=today_punches,
        today=date.today(),
        active_page='hr_attendance'
    )


# ════════════════════════════════════════════════════════════════════════
# ATTENDANCE LOG SYNC SCREEN — /attendance_log/sync
# ────────────────────────────────────────────────────────────────────────
# PHP CodeIgniter ke `sync_all_summary_to_attendance()` aur
# `push_to_python()` ka Flask equivalent.
# Source-of-truth Flask schema mein RawPunchLog hai (PHP wala
# tbl_attendance_summary). Attendance table same hi hai.
# ════════════════════════════════════════════════════════════════════════

# ── Local biometric device API config ────────────────────────────────
# PHP code ke hisab se hardcoded; future me settings master me jaane chahiye.
DEVICE_API_URL    = "http://192.168.2.2:82/api/v2/WebAPI/GetDeviceLogs"
DEVICE_API_KEY    = "242511032625"
PUSH_LIVE_URL     = "https://hcperp.in/api/receive_logs"
PUSH_LIVE_KEY     = "HCP_PUSH_2024"

# ── Default employees (9001 & 9002) — admin / management staff jo
# device pe punch nahi karte par hamesha Present count hone chahiye.
DEFAULT_EMPLOYEES = {
    '9001': {'type': 'HCP OFFICE', 'in': '10:30:00', 'out': '19:00:00', 'hours': 8.50},
    '9002': {'type': 'HCP OFFICE', 'in': '10:30:00', 'out': '19:00:00', 'hours': 8.50},
}

# ── Week-off rule: HCP OFFICE = Sunday off; baki sab = Tuesday off ──
def _is_week_off(emp_type, dt):
    """dt ko us emp_type ka weekly off hai ya nahi."""
    # Python's weekday(): Monday=0..Sunday=6
    # PHP DAYOFWEEK: Sunday=1, Monday=2, ..., Saturday=7
    wd = dt.weekday()
    if (emp_type or '').upper() == 'HCP OFFICE':
        return wd == 6   # Sunday
    return wd == 1       # Tuesday


def _classify_status(emp_type, att_date, punch_in, punch_out):
    """
    Sync ka core classification logic — PHP CASE expression ka direct port.
    Order matters:
      1. WOP    = Weekly off pe valid in+out (>0 mins, valid range)
      2. Present= valid in+out, hours >= 7
      3. Half Day= valid in+out, hours >= 6 (lekin <7)
      4. Absent = valid in+out lekin hours <6
      5. MIS-PUNCH = sirf in ya sirf out, ya in==out
    """
    has_in  = punch_in  is not None
    has_out = punch_out is not None

    # MIS-PUNCH cases
    if has_in and not has_out:                  return 'MIS-PUNCH'
    if not has_in and has_out:                  return 'MIS-PUNCH'
    if has_in and has_out and punch_in == punch_out: return 'MIS-PUNCH'

    if has_in and has_out and punch_out > punch_in:
        hours = (punch_out - punch_in).total_seconds() / 3600.0
        if _is_week_off(emp_type, att_date):
            return 'WOP'
        if hours >= 7.0:  return 'Present'
        if hours >= 6.0:  return 'Half Day'
        return 'Absent'
    return 'MIS-PUNCH'


def _sync_one_date(target_date):
    """
    Ek din ke liye saare employees ka attendance recompute karo.
    Returns: {inserted: int, updated: int, skipped_woff: int}

    OPTIMIZED: Pehle har employee per 4 queries chalti thi (employee lookup,
    in_device, out_device, existing attendance). Total ~1000 queries per date.
    Ab sab bulk-fetch ho jata hai — total 4 queries per date, regardless of
    employee count. ~250x faster.
    """
    inserted = 0
    updated  = 0
    skipped  = 0

    # ── Step 1: Us din ke saare punches ek hi query me lao ──
    all_punches = RawPunchLog.query.filter(
        db.func.date(RawPunchLog.log_date) == target_date
    ).order_by(RawPunchLog.employee_code, RawPunchLog.log_date.asc()).all()

    if not all_punches:
        # No punches at all — sirf default employees handle karo niche
        emp_groups = {}
    else:
        # Group by employee_code in Python (no DB roundtrip)
        emp_groups = {}
        for p in all_punches:
            emp_groups.setdefault(p.employee_code, []).append(p)

    emp_codes_with_punches = list(emp_groups.keys())

    # ── Step 2: Saare employees ek hi query me lao ──
    # employee_code ya employee_id dono se match
    emp_map = {}
    if emp_codes_with_punches:
        emp_rows = Employee.query.filter(
            db.or_(
                Employee.employee_code.in_(emp_codes_with_punches),
                Employee.employee_id.in_(emp_codes_with_punches),
            )
        ).all()
        for e in emp_rows:
            if e.employee_code: emp_map[e.employee_code] = e
            if e.employee_id:   emp_map[e.employee_id]   = e

    # ── Step 3: Us date ke saare existing attendance records lao ──
    all_codes = list(emp_codes_with_punches) + list(DEFAULT_EMPLOYEES.keys())
    existing_atts = {}
    if all_codes:
        att_rows = Attendance.query.filter(
            Attendance.attendance_date == target_date,
            Attendance.employee_code.in_(all_codes),
        ).all()
        for a in att_rows:
            existing_atts[a.employee_code] = a

    # ── Step 4: Process each employee with punches ──
    for emp_code, punches in emp_groups.items():
        first_punch = punches[0]   # already sorted by log_date asc
        last_punch  = punches[-1]

        first_in = first_punch.log_date
        in_dev   = first_punch.serial_number

        actual_out = None
        out_dev    = None
        if last_punch.log_date != first_in:
            actual_out = last_punch.log_date
            out_dev    = last_punch.serial_number

        emp = emp_map.get(emp_code)
        emp_type = (emp.employee_type if emp else '') or ''

        status = _classify_status(emp_type, target_date, first_in, actual_out)
        total_hours = None
        if first_in and actual_out and actual_out > first_in:
            total_hours = round((actual_out - first_in).total_seconds() / 3600.0, 2)

        att = existing_atts.get(emp_code)
        if att is None:
            att = Attendance(employee_code=emp_code, attendance_date=target_date)
            db.session.add(att)
            inserted += 1
        else:
            updated += 1

        att.punch_in    = first_in
        att.punch_out   = actual_out
        att.in_device   = in_dev
        att.out_device  = out_dev
        att.total_hours = total_hours
        att.status      = status
        att.updated_at  = datetime.now()

    # ── Step 5: Default employees (9001/9002) — existing_atts dict use karo ──
    for emp_code, conf in DEFAULT_EMPLOYEES.items():
        if _is_week_off(conf['type'], target_date):
            skipped += 1
            continue

        in_time  = datetime.strptime(f"{target_date} {conf['in']}",  "%Y-%m-%d %H:%M:%S")
        out_time = datetime.strptime(f"{target_date} {conf['out']}", "%Y-%m-%d %H:%M:%S")

        existing = existing_atts.get(emp_code)

        # Create-or-fix logic — PHP code ke same triggers
        needs_default = False
        if existing is None:
            needs_default = True
        elif existing.status in ('MIS-PUNCH', 'Absent'):
            needs_default = True
        elif (existing.punch_out is None
              or (existing.punch_in and existing.punch_out
                  and existing.punch_out <= existing.punch_in)
              or (existing.punch_in and existing.punch_out
                  and (existing.punch_out - existing.punch_in).total_seconds() < 3600)):
            needs_default = True

        if needs_default:
            if existing is None:
                existing = Attendance(employee_code=emp_code, attendance_date=target_date)
                db.session.add(existing)
                inserted += 1
            else:
                updated += 1
            existing.punch_in    = in_time
            existing.punch_out   = out_time
            existing.in_device   = 'DEFAULT'
            existing.out_device  = 'DEFAULT'
            existing.total_hours = conf['hours']
            existing.status      = 'Present'
            existing.updated_at  = datetime.now()

    return {'inserted': inserted, 'updated': updated, 'skipped_woff': skipped}


# ── Sync UI Screen ────────────────────────────────────────────────────
@attendance_bp.route('/attendance_log/sync', methods=['GET'])
@login_required
def attendance_log_sync_view():
    if not _require_sub_perm('hr', 'att_sync'):
        flash('Access denied: Sync Data permission nahi hai.', 'error')
        return redirect(url_for('attendance.attendance_dashboard'))
    today = date.today()
    return render_template(
        'hr/attendance/sync.html',
        today_str=today.strftime('%Y-%m-%d'),
        active_page='att_sync',
    )


# ── Sync POST endpoint — date range process karta hai ────────────────
@attendance_bp.route('/attendance_log/sync/run', methods=['POST'])
@login_required
def attendance_log_sync_run():
    if not _require_sub_perm('hr', 'att_sync'):
        return jsonify(success=False, error='Access denied: Sync permission nahi hai.'), 403
    from_date = request.form.get('from_date') or date.today().isoformat()
    to_date   = request.form.get('to_date')   or from_date

    def _parse_flex(s):
        """YYYY-MM-DD, DD-MM-YYYY, DD/MM/YYYY, MM/DD/YYYY — sab try karo."""
        s = (s or '').strip()
        for fmt in ('%Y-%m-%d', '%d-%m-%Y', '%d/%m/%Y', '%m/%d/%Y',
                    '%Y/%m/%d', '%d.%m.%Y'):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
        return None

    d_from = _parse_flex(from_date)
    d_to   = _parse_flex(to_date)
    if not d_from or not d_to:
        return jsonify(
            success=False,
            error=f'Invalid date format. Got from={from_date!r}, to={to_date!r}. '
                  f'Use YYYY-MM-DD ya DD-MM-YYYY.'
        ), 400

    if d_to < d_from:
        return jsonify(success=False, error='To Date, From Date se chhoti nahi ho sakti.'), 400

    # Safety cap — bahut bada range accidently na chale
    days_count = (d_to - d_from).days + 1
    if days_count > 90:
        return jsonify(success=False, error=f'Max 90 din ek baar me. Tumne {days_count} din maange.'), 400

    log_lines    = []
    grand_ins    = 0
    grand_upds   = 0
    grand_skipw  = 0

    cur = d_from
    while cur <= d_to:
        try:
            res = _sync_one_date(cur)
            # Commit per-date — memory clear, progress safe even if next date crashes
            db.session.commit()
            grand_ins   += res['inserted']
            grand_upds  += res['updated']
            grand_skipw += res['skipped_woff']
            log_lines.append(
                f"[{cur.isoformat()}] inserted={res['inserted']}  "
                f"updated={res['updated']}  weekoff_skipped={res['skipped_woff']}"
            )
        except Exception as ex:
            db.session.rollback()
            log_lines.append(f"[{cur.isoformat()}] ❌ ERROR: {ex}")
        cur += timedelta(days=1)

    log_lines.append("")
    log_lines.append(f"✅ DONE — {days_count} day(s) processed")
    log_lines.append(f"   Total inserted : {grand_ins}")
    log_lines.append(f"   Total updated  : {grand_upds}")
    log_lines.append(f"   Weekly off skip: {grand_skipw}")

    return jsonify(
        success  = True,
        from_date= d_from.isoformat(),
        to_date  = d_to.isoformat(),
        inserted = grand_ins,
        updated  = grand_upds,
        skipped  = grand_skipw,
        log      = log_lines,
    )


# ── Fetch-from-device API (manual trigger) ────────────────────────────
# PHP `push_to_python()` ka Flask equivalent. Yeh local LAN biometric
# device API ko call karta hai aur logs ko seedha RawPunchLog me bhar
# deta hai (PHP wala "push to live server" step skip — kyunki yahin
# server hai). Agar future me 2 servers chalane hon, to PUSH_LIVE_URL
# par forward karne ka switch turn on kar sakte hain.
@attendance_bp.route('/attendance_log/fetch_device', methods=['POST'])
@login_required
def attendance_log_fetch_device():
    import urllib.request, urllib.error, urllib.parse

    from_date = request.form.get('from_date') or date.today().replace(day=1).isoformat()
    to_date   = request.form.get('to_date')   or date.today().isoformat()
    forward   = request.form.get('forward_to_live') in ('1', 'true', 'on', 'yes')

    qs  = urllib.parse.urlencode({
        'APIKey'  : DEVICE_API_KEY,
        'FromDate': from_date,
        'ToDate'  : to_date,
    })
    url = f"{DEVICE_API_URL}?{qs}"

    log_lines = [f"→ GET {url}"]

    # 1. Fetch from device
    try:
        req = urllib.request.Request(url, headers={'User-Agent': 'HCP-ERP-Sync/1.0'})
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode('utf-8', errors='replace')
        log_lines.append(f"← HTTP {resp.status}, {len(raw)} bytes")
        try:
            payload = json.loads(raw)
        except Exception:
            return jsonify(success=False, error='Device API ne valid JSON nahi diya',
                           log=log_lines), 502
    except urllib.error.URLError as ex:
        log_lines.append(f"❌ Device API reachable nahi: {ex}")
        return jsonify(success=False, error=f'Device API connect nahi hua: {ex}',
                       log=log_lines), 502
    except Exception as ex:
        log_lines.append(f"❌ Unexpected error: {ex}")
        return jsonify(success=False, error=f'Fetch failed: {ex}', log=log_lines), 500

    if not payload:
        return jsonify(success=False, error='Device se empty data', log=log_lines), 200

    # 2. Forward to live server (optional, mirrors PHP push_to_python)
    if forward:
        try:
            push_data = json.dumps(payload).encode('utf-8')
            push_req  = urllib.request.Request(
                PUSH_LIVE_URL,
                data=push_data,
                headers={
                    'Content-Type' : 'application/json',
                    'Authorization': PUSH_LIVE_KEY,
                },
                method='POST',
            )
            with urllib.request.urlopen(push_req, timeout=60) as push_resp:
                push_body = push_resp.read().decode('utf-8', errors='replace')
            log_lines.append(f"→ Pushed to live server: HTTP {push_resp.status}")
            log_lines.append(f"  ↳ {push_body[:200]}")
            return jsonify(success=True, mode='forwarded',
                           live_response=push_body, log=log_lines)
        except Exception as ex:
            log_lines.append(f"❌ Forward to live failed: {ex}")
            return jsonify(success=False, error=f'Forward failed: {ex}',
                           log=log_lines), 502

    # 3. Local-mode: store directly into RawPunchLog
    if isinstance(payload, dict):
        logs_list = (payload.get('data') or payload.get('logs') or
                     payload.get('DeviceLogs') or payload.get('Records') or [payload])
    elif isinstance(payload, list):
        logs_list = payload
    else:
        return jsonify(success=False, error='Unexpected payload shape', log=log_lines), 502

    inserted = 0; skipped = 0; errors = []
    for entry in logs_list:
        try:
            emp_code = _get_field(entry,
                'EmployeeCode', 'employee_code', 'CardNo', 'card_no',
                'UserID', 'UserId', 'EmpCode', 'emp_code')
            log_dt = _parse_datetime(_get_field(entry,
                'LogTime', 'log_date', 'PunchTime', 'DateTime', 'datetime', 'Time'))
            if not emp_code or not log_dt:
                skipped += 1; continue

            if RawPunchLog.query.filter_by(employee_code=emp_code, log_date=log_dt).first():
                skipped += 1; continue

            db.session.add(RawPunchLog(
                employee_code=emp_code, log_date=log_dt,
                serial_number=_get_field(entry, 'SerialNumber', 'serial_number',
                                         'DeviceId', 'MachineNo'),
                punch_direction=_get_punch_direction(entry),
                temperature=_get_field(entry, 'Temperature') or 0.00,
                temperature_state=_get_field(entry, 'TemperatureState'),
                synced_at=datetime.now(),
            ))
            inserted += 1
        except Exception as ex:
            errors.append(str(ex))

    try:
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        return jsonify(success=False, error=f'DB error: {ex}', log=log_lines), 500

    log_lines.append(f"✅ Inserted: {inserted}, Skipped (dup): {skipped}, "
                     f"Errors: {len(errors)}")
    return jsonify(success=True, mode='local',
                   inserted=inserted, skipped=skipped,
                   total=len(logs_list), errors=errors[:5], log=log_lines)


# ════════════════════════════════════════════════════════════════════════
# DAILY ATTENDANCE VIEW — /hr/attendance/daily
# Image 2 ka design — date picker, employee type filter, stat chips, table
# ════════════════════════════════════════════════════════════════════════
@attendance_bp.route('/hr/attendance/daily')
@login_required
def attendance_daily():
    if not _require_sub_perm('hr', 'att_daily'):
        flash('Access denied: Daily Attendance permission nahi hai.', 'error')
        return redirect(url_for('attendance.attendance_dashboard'))
    sel_date_str = request.args.get('date', date.today().isoformat())
    try:
        sel_date = datetime.strptime(sel_date_str, '%Y-%m-%d').date()
    except ValueError:
        sel_date = date.today()

    search_q = (request.args.get('q') or '').strip().lower()
    emp_type = (request.args.get('emp_type') or '').strip()

    # Sab active employees fetch karo + us din ka attendance
    emp_q = Employee.query.filter_by(status='active')
    if emp_type:
        emp_q = emp_q.filter(Employee.employee_type == emp_type)
    employees = emp_q.order_by(Employee.first_name).all()

    att_map = {a.employee_code: a for a in Attendance.query.filter_by(
        attendance_date=sel_date).all()}

    rows = []
    for emp in employees:
        # Match by employee_code OR employee_id
        att = att_map.get(emp.employee_code) or att_map.get(emp.employee_id)
        full_name = f"{emp.first_name or ''}{('_' + emp.last_name) if emp.last_name else ''}"
        if search_q:
            hay = ' '.join(filter(None, [emp.first_name, emp.last_name,
                                          emp.employee_code, emp.employee_id,
                                          emp.department or '',
                                          emp.designation or ''])).lower()
            if search_q not in hay:
                continue
        rows.append({
            'emp':         emp,
            'full_name':   full_name,
            'att':         att,
            'status':      att.status if att else 'Absent',
        })

    # Stats
    total       = len(rows)
    present_n   = sum(1 for r in rows if r['status'] == 'Present')
    halfday_n   = sum(1 for r in rows if r['status'] == 'Half Day')
    mispunch_n  = sum(1 for r in rows if r['status'] == 'MIS-PUNCH')
    absent_n    = sum(1 for r in rows if r['status'] == 'Absent')
    wop_n       = sum(1 for r in rows if r['status'] == 'WOP')

    # Distinct employee types for the filter dropdown
    type_rows = db.session.query(Employee.employee_type).filter(
        Employee.employee_type.isnot(None),
        Employee.employee_type != '',
        Employee.status == 'active',
    ).distinct().order_by(Employee.employee_type).all()
    emp_types = [t[0] for t in type_rows if t[0]]

    return render_template('hr/attendance/daily.html',
        rows=rows, sel_date=sel_date, search_q=search_q, emp_type=emp_type,
        emp_types=emp_types,
        stats=dict(total=total, present=present_n, halfday=halfday_n,
                   mispunch=mispunch_n, absent=absent_n, wop=wop_n),
        prev_date=(sel_date - timedelta(days=1)).isoformat(),
        next_date=(sel_date + timedelta(days=1)).isoformat(),
        today_str=date.today().isoformat(),
        active_page='att_daily',
    )


# ════════════════════════════════════════════════════════════════════════
# MONTHLY ATTENDANCE VIEW — /hr/attendance/monthly
# Image 3 ka design — year/month, per-employee day-wise grid
# ════════════════════════════════════════════════════════════════════════
@attendance_bp.route('/hr/attendance/monthly')
@login_required
def attendance_monthly():
    if not _require_sub_perm('hr', 'att_monthly'):
        flash('Access denied: Monthly Attendance permission nahi hai.', 'error')
        return redirect(url_for('attendance.attendance_dashboard'))
    import calendar as _cal
    today = date.today()
    try:
        year  = int(request.args.get('year',  today.year))
        month = int(request.args.get('month', today.month))
    except ValueError:
        year, month = today.year, today.month

    if not (1 <= month <= 12) or year < 2000 or year > 2100:
        year, month = today.year, today.month

    search_q = (request.args.get('q') or '').strip().lower()
    emp_type = (request.args.get('emp_type') or '').strip()

    days_in_month = _cal.monthrange(year, month)[1]
    month_start   = date(year, month, 1)
    month_end     = date(year, month, days_in_month)

    # Working days = month days minus weekly offs (Sundays for HCP OFFICE
    # logic could be per-employee; here we use a conservative "Mon-Sat = working")
    working_days = sum(1 for i in range(days_in_month)
                       if (month_start + timedelta(days=i)).weekday() != 6)

    emp_q = Employee.query.filter_by(status='active')
    if emp_type:
        emp_q = emp_q.filter(Employee.employee_type == emp_type)
    if search_q:
        like = f'%{search_q}%'
        emp_q = emp_q.filter(db.or_(
            Employee.first_name.ilike(like),
            Employee.last_name.ilike(like),
            Employee.employee_code.ilike(like),
            Employee.employee_id.ilike(like),
            Employee.department.ilike(like),
        ))
    employees = emp_q.order_by(Employee.first_name).all()

    # Bulk attendance fetch for the month
    att_records = Attendance.query.filter(
        Attendance.attendance_date >= month_start,
        Attendance.attendance_date <= month_end,
    ).all()
    # group by emp_code → {date: att}
    att_by_emp = {}
    for a in att_records:
        att_by_emp.setdefault(a.employee_code, {})[a.attendance_date] = a

    # Build per-employee rows
    emp_rows = []
    day_list = [date(year, month, d) for d in range(1, days_in_month + 1)]
    type_rows = db.session.query(Employee.employee_type).filter(
        Employee.employee_type.isnot(None), Employee.employee_type != '',
    ).distinct().order_by(Employee.employee_type).all()
    emp_types = [t[0] for t in type_rows if t[0]]

    for emp in employees:
        per_emp = att_by_emp.get(emp.employee_code) or att_by_emp.get(emp.employee_id) or {}
        days = []
        cnt = dict(P=0, HD=0, AB=0, MP=0, WO=0, WOP=0)
        for d in day_list:
            a = per_emp.get(d)
            wo = _is_week_off(emp.employee_type, d)
            if a is None:
                if wo: code = 'WO'
                else:  code = 'AB'
                in_t = out_t = ''
                tot = 0.0
            else:
                if a.status == 'Present':       code = 'P'
                elif a.status == 'Half Day':    code = 'HD'
                elif a.status == 'MIS-PUNCH':   code = 'MP'
                elif a.status == 'WOP':         code = 'WOP'
                elif a.status == 'Holiday':     code = 'WO'
                elif a.status == 'Absent':      code = 'WO' if wo else 'AB'
                else:                            code = 'AB'
                in_t  = a.punch_in.strftime('%H:%M')  if a.punch_in  else ''
                out_t = a.punch_out.strftime('%H:%M') if a.punch_out else ''
                tot   = float(a.total_hours or 0)
            cnt[code] = cnt.get(code, 0) + 1
            days.append(dict(date=d, in_t=in_t, out_t=out_t, tot=tot, code=code))
        emp_rows.append(dict(emp=emp, days=days, cnt=cnt))

    return render_template('hr/attendance/monthly.html',
        year=year, month=month, month_name=_cal.month_name[month],
        emp_rows=emp_rows, working_days=working_days,
        total_emps=len(employees), emp_types=emp_types,
        emp_type=emp_type, search_q=search_q,
        prev_year=(year if month > 1 else year - 1),
        prev_month=(month - 1 if month > 1 else 12),
        next_year=(year if month < 12 else year + 1),
        next_month=(month + 1 if month < 12 else 1),
        active_page='att_monthly',
    )
