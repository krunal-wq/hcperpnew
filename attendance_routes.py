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
from flask import Blueprint, request, jsonify, render_template
from flask_login import login_required
from models import db, Employee
from models.attendance import RawPunchLog, Attendance

attendance_bp = Blueprint('attendance', __name__)

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
    """Multiple possible key names try karo."""
    for k in keys:
        v = entry.get(k)
        if v is not None and str(v).strip() != '':
            return str(v).strip()
    return None


def _parse_datetime(val):
    if not val:
        return None
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%dT%H:%M:%S',
                '%d/%m/%Y %H:%M:%S', '%Y-%m-%d %H:%M', '%d-%m-%Y %H:%M:%S'):
        try:
            return datetime.strptime(str(val).strip(), fmt)
        except Exception:
            continue
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
    # ── Auth check ──
    auth = request.headers.get('Authorization', '')
    if auth != PUSH_API_KEY:
        return jsonify({'error': 'Unauthorized'}), 401

    # ── JSON parse ──
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({'error': 'Invalid JSON'}), 400

    if not data:
        return jsonify({'error': 'Empty payload'}), 400

    # ── List normalize karo ──
    if isinstance(data, dict):
        logs_list = (data.get('data') or data.get('logs') or
                     data.get('DeviceLogs') or data.get('Records') or [data])
    elif isinstance(data, list):
        logs_list = data
    else:
        return jsonify({'error': 'Unexpected format'}), 400

    inserted       = 0
    skipped        = 0
    errors         = []
    to_update      = set()   # (employee_code, date) pairs

    for entry in logs_list:
        try:
            emp_code = _get_field(entry,
                'EmployeeCode', 'employee_code', 'CardNo', 'card_no',
                'UserID', 'UserId', 'EmpCode', 'emp_code'
            )
            log_dt = _parse_datetime(
                _get_field(entry,
                    'LogTime', 'log_date', 'PunchTime', 'DateTime',
                    'datetime', 'Time', 'Timestamp'
                )
            )

            if not emp_code or not log_dt:
                skipped += 1
                continue

            # Duplicate check — same employee, same second
            exists = RawPunchLog.query.filter_by(
                employee_code=emp_code,
                log_date=log_dt
            ).first()
            if exists:
                skipped += 1
                continue

            punch = RawPunchLog(
                employee_code     = emp_code,
                log_date          = log_dt,
                serial_number     = _get_field(entry, 'SerialNumber', 'serial_number',
                                               'DeviceId', 'device_id', 'MachineNo'),
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
            continue

    # ── Commit raw punches ──
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'DB error: {str(e)}'}), 500

    # ── attendance table update karo ──
    for (emp_code, att_date) in to_update:
        try:
            _update_attendance(emp_code, att_date)
        except Exception as e:
            errors.append(f'Attendance update {emp_code}: {e}')

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()

    return jsonify({
        'status':   'ok',
        'inserted': inserted,
        'skipped':  skipped,
        'total':    len(logs_list),
        'errors':   errors[:5],
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
