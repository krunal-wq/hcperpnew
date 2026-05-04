"""
qr_scan_routes.py — v2.1 — DIAGNOSTIC VERSION
QR Code Scanner kiosk: punch register + employee display

Kya karta hai:
  • External USB/Bluetooth scanner ya mobile/system camera se QR scan
  • Code milte hi:
       1. RawPunchLog mein nayi entry insert (serial_number='QR_KIOSK')
       2. Attendance table update (first IN + last OUT logic)
       3. Employee ka photo, naam, code, time-in/out wapas bhejo
  • Cooldown: same employee 30 sec mein dobara scan kare to ignore
  • Auto IN/OUT detect: pehla scan = IN, doosra scan = OUT, aage ke
    scans punch_out ko latest update karte hain

Login NAHI chahiye — kiosk mode (entrance gate ke liye).

Routes:
  GET  /hr/attendance/qr-scan         ← kiosk page render
  POST /hr/attendance/qr-lookup       ← scan API: punch + return data
  GET  /hr/attendance/qr-version      ← debug: which version is running
"""
import json
import sys
from datetime import date, datetime

from flask import Blueprint, request, jsonify, render_template

from models import db, Employee
from models.attendance import Attendance, RawPunchLog


# ════════════════════════════════════════════════════════════════
# MODULE-LOAD BANNER — server restart pe terminal mein dikhega
# Aap dekh sakte ho ki naya file load hua hai ya purana
# ════════════════════════════════════════════════════════════════
sys.stderr.write("\n" + "=" * 60 + "\n")
sys.stderr.write("  ✓  QR-SCANNER v2.3 LOADED  (in/out lists + stats)\n")
sys.stderr.write("     Routes:  /hr/attendance/qr-scan\n")
sys.stderr.write("              /hr/attendance/qr-lookup\n")
sys.stderr.write("              /hr/attendance/qr-stats\n")
sys.stderr.write("              /hr/attendance/qr-today-list\n")
sys.stderr.write("              /hr/attendance/qr-version\n")
sys.stderr.write("=" * 60 + "\n\n")
sys.stderr.flush()


qr_scan_bp = Blueprint('qr_scan', __name__)


# ── Config ──────────────────────────────────────────────────────
PUNCH_COOLDOWN_SEC = 30      # ek hi emp 30 sec mein dobara scan = ignore
HALF_DAY_HOURS     = 4.0     # 4hr se kam = Half Day
KIOSK_DEVICE_NAME  = 'QR_KIOSK'
VERSION            = '2.3'


def _log(msg):
    """Terminal mein clearly visible diagnostic log."""
    sys.stderr.write(f"[QR-SCAN] {msg}\n")
    sys.stderr.flush()


# ══════════════════════════════════════════════════════════════
# HELPER: QR payload parse
# ══════════════════════════════════════════════════════════════
def _parse_qr_payload(raw):
    if not raw:
        return ''
    s = str(raw).strip().strip('\r\n\t ')
    if s.startswith('{') and s.endswith('}'):
        try:
            j = json.loads(s)
            for k in ('emp_code', 'employee_code', 'EmployeeCode',
                      'employee_id', 'EmpCode', 'emp_id',
                      'code', 'id'):
                if j.get(k):
                    return str(j[k]).strip()
        except Exception:
            pass
    if ('://' in s or s.count('/') >= 2) and ' ' not in s:
        s = s.rstrip('/').split('/')[-1].strip()
    return s


# ══════════════════════════════════════════════════════════════
# CORE: attendance row ko raw_punch_logs se recompute karo
# ══════════════════════════════════════════════════════════════
def _refresh_attendance(emp_code_log_key, today_date):
    punches = RawPunchLog.query.filter(
        RawPunchLog.employee_code == emp_code_log_key,
        db.func.date(RawPunchLog.log_date) == today_date
    ).order_by(RawPunchLog.log_date.asc()).all()

    if not punches:
        return None

    first = punches[0]
    last  = punches[-1]

    punch_in   = first.log_date
    in_device  = first.serial_number
    punch_out  = last.log_date  if len(punches) > 1 else None
    out_device = last.serial_number if len(punches) > 1 else None

    total_hours = None
    if punch_in and punch_out and punch_out > punch_in:
        total_hours = round((punch_out - punch_in).total_seconds() / 3600, 2)

    if punch_out is None:
        status = 'MIS-PUNCH'
    elif total_hours is not None and total_hours < HALF_DAY_HOURS:
        status = 'Half Day'
    else:
        status = 'Present'

    att = Attendance.query.filter_by(
        employee_code=emp_code_log_key,
        attendance_date=today_date
    ).first()
    if not att:
        att = Attendance(
            employee_code=emp_code_log_key,
            attendance_date=today_date
        )
        db.session.add(att)

    att.punch_in    = punch_in
    att.punch_out   = punch_out
    att.in_device   = in_device
    att.out_device  = out_device
    att.total_hours = total_hours
    att.status      = status
    att.updated_at  = datetime.now()

    _log(f"refresh_attendance → punches={len(punches)}, "
         f"in={punch_in}, out={punch_out}, status={status}")
    return att


# ══════════════════════════════════════════════════════════════
# CORE: punch register karo
# ══════════════════════════════════════════════════════════════
def _do_punch(emp_code_log_key, today_date):
    now = datetime.now()

    # ── Cooldown check ──
    last_raw = RawPunchLog.query.filter(
        RawPunchLog.employee_code == emp_code_log_key,
        db.func.date(RawPunchLog.log_date) == today_date
    ).order_by(RawPunchLog.log_date.desc()).first()

    if last_raw and last_raw.log_date:
        elapsed = (now - last_raw.log_date).total_seconds()
        if elapsed < PUNCH_COOLDOWN_SEC:
            _log(f"COOLDOWN — {emp_code_log_key} ka pichla scan {int(elapsed)}s "
                 f"pehle hua tha, ignored")
            return ('cooldown', last_raw)

    # ── Direction (raw punches ke count se determine karo, Attendance se nahi) ──
    todays_punches_count = RawPunchLog.query.filter(
        RawPunchLog.employee_code == emp_code_log_key,
        db.func.date(RawPunchLog.log_date) == today_date
    ).count()

    if todays_punches_count == 0:
        direction = 'IN';  action = 'in'
    elif todays_punches_count == 1:
        direction = 'OUT'; action = 'out'
    else:
        direction = 'OUT'; action = 'updated'

    # ── Insert raw punch ──
    raw = RawPunchLog(
        employee_code   = emp_code_log_key,
        log_date        = now,
        serial_number   = KIOSK_DEVICE_NAME,
        punch_direction = direction,
        synced_at       = now,
    )
    db.session.add(raw)
    db.session.flush()
    _log(f"PUNCH [{action.upper()}] log_key={emp_code_log_key!r} time={now} "
         f"(today's punches before this: {todays_punches_count})")

    # ── Attendance recompute ──
    att = _refresh_attendance(emp_code_log_key, today_date)
    if att:
        _log(f"  ✓ Attendance row: in={att.punch_in} out={att.punch_out} "
             f"hours={att.total_hours} status={att.status}")
    else:
        _log(f"  ⚠️  Attendance row NOT created")

    return (action, raw)


# ══════════════════════════════════════════════════════════════
# DEBUG: GET /hr/attendance/qr-debug-attendance
# Aaj ke saare attendance rows + raw punch counts dekho
# Useful for verifying ki QR scans → attendance table mein ja rahe ya nahi
# ══════════════════════════════════════════════════════════════
@qr_scan_bp.route('/hr/attendance/qr-debug-attendance')
def qr_debug_attendance():
    today = date.today()

    # Today's attendance rows
    att_rows = Attendance.query.filter_by(attendance_date=today).all()
    att_data = [{
        'employee_code': a.employee_code,
        'punch_in':      a.punch_in.strftime('%I:%M:%S %p') if a.punch_in else None,
        'punch_out':     a.punch_out.strftime('%I:%M:%S %p') if a.punch_out else None,
        'in_device':     a.in_device,
        'out_device':    a.out_device,
        'total_hours':   float(a.total_hours) if a.total_hours is not None else None,
        'status':        a.status,
        'updated_at':    a.updated_at.strftime('%I:%M:%S %p') if a.updated_at else None,
    } for a in att_rows]

    # Today's raw punch counts grouped by employee_code
    raw_counts_q = db.session.query(
        RawPunchLog.employee_code,
        db.func.count(RawPunchLog.id).label('cnt'),
        db.func.min(RawPunchLog.log_date).label('first'),
        db.func.max(RawPunchLog.log_date).label('last'),
    ).filter(
        db.func.date(RawPunchLog.log_date) == today
    ).group_by(RawPunchLog.employee_code).all()

    raw_data = [{
        'employee_code': r.employee_code,
        'count':         r.cnt,
        'first_punch':   r.first.strftime('%I:%M:%S %p') if r.first else None,
        'last_punch':    r.last.strftime('%I:%M:%S %p') if r.last else None,
    } for r in raw_counts_q]

    return jsonify({
        'date':           today.strftime('%d-%b-%Y'),
        'attendance_rows': len(att_data),
        'attendance':     att_data,
        'raw_punch_counts': raw_data,
        'note': 'Agar attendance_rows=0 hai but raw_punch_counts data hai, '
                'toh attendance create nahi ho raha — bug hai.',
    }), 200


# ══════════════════════════════════════════════════════════════
# DEBUG: GET /hr/attendance/qr-version  → confirms which version is running
# ══════════════════════════════════════════════════════════════
@qr_scan_bp.route('/hr/attendance/qr-version')
def qr_version():
    return jsonify({
        'version':  VERSION,
        'punch':    True,
        'cooldown': PUNCH_COOLDOWN_SEC,
        'message':  '✓ NEW backend running — punch logic enabled',
    }), 200


# ══════════════════════════════════════════════════════════════
# STATS: GET /hr/attendance/qr-stats
# Aaj ke unique IN / OUT counts. Database se aata hai isiliye:
#   • Duplicate scans count nahi hote (1 emp = 1 IN, 1 OUT max)
#   • Biometric device ke punches bhi shaamil hain
#   • Page refresh pe persistent rehte hain
# ══════════════════════════════════════════════════════════════
@qr_scan_bp.route('/hr/attendance/qr-stats')
def qr_stats():
    today = date.today()
    total_in = Attendance.query.filter(
        Attendance.attendance_date == today,
        Attendance.punch_in.isnot(None)
    ).count()
    total_out = Attendance.query.filter(
        Attendance.attendance_date == today,
        Attendance.punch_out.isnot(None)
    ).count()
    inside_now = total_in - total_out
    return jsonify({
        'date':       today.strftime('%d-%b-%Y'),
        'total_in':   total_in,
        'total_out':  total_out,
        'inside_now': max(0, inside_now),
    }), 200


# ══════════════════════════════════════════════════════════════
# TODAY'S LIST: GET /hr/attendance/qr-today-list
# Return karta hai:
#   in_list  → har employee jo aaj IN hua, with first punch time (1 entry per emp)
#   out_list → har employee jo aaj OUT hua, with latest punch time (1 entry per emp)
# Sorted descending by time (latest first).
# ══════════════════════════════════════════════════════════════
@qr_scan_bp.route('/hr/attendance/qr-today-list')
def qr_today_list():
    today = date.today()

    rows = Attendance.query.filter_by(attendance_date=today).all()
    if not rows:
        return jsonify({
            'date':     today.strftime('%d-%b-%Y'),
            'in_list':  [],
            'out_list': [],
        }), 200

    # ── Batch-fetch employees taaki N+1 queries na ho ──
    all_codes = {r.employee_code for r in rows if r.employee_code}
    emps_by_code = {}
    emps_by_id   = {}
    if all_codes:
        for e in Employee.query.filter(Employee.employee_code.in_(all_codes)).all():
            if e.employee_code:
                emps_by_code[e.employee_code] = e
        for e in Employee.query.filter(Employee.employee_id.in_(all_codes)).all():
            if e.employee_id:
                emps_by_id[e.employee_id] = e

    def _resolve(code):
        return emps_by_code.get(code) or emps_by_id.get(code)

    in_list, out_list = [], []

    for r in rows:
        emp = _resolve(r.employee_code)
        if emp:
            parts = [emp.first_name, emp.middle_name, emp.last_name]
            name  = ' '.join(p for p in parts if p and p.strip())
            code  = emp.employee_code or emp.employee_id or r.employee_code
            photo = emp.profile_photo
        else:
            name, code, photo = r.employee_code, r.employee_code, None

        if r.punch_in:
            in_list.append({
                'name':  name,
                'code':  code,
                'photo': photo,
                'time':  r.punch_in.strftime('%I:%M %p'),
                '_sort': r.punch_in.isoformat(),
            })
        if r.punch_out:
            out_list.append({
                'name':  name,
                'code':  code,
                'photo': photo,
                'time':  r.punch_out.strftime('%I:%M %p'),
                '_sort': r.punch_out.isoformat(),
            })

    # Latest first
    in_list .sort(key=lambda x: x['_sort'], reverse=True)
    out_list.sort(key=lambda x: x['_sort'], reverse=True)
    for x in in_list:  x.pop('_sort', None)
    for x in out_list: x.pop('_sort', None)

    return jsonify({
        'date':     today.strftime('%d-%b-%Y'),
        'in_list':  in_list,
        'out_list': out_list,
    }), 200


# ══════════════════════════════════════════════════════════════
# PAGE: GET /hr/attendance/qr-scan   (NO login required)
# ══════════════════════════════════════════════════════════════
@qr_scan_bp.route('/hr/attendance/qr-scan')
def qr_scan_page():
    return render_template(
        'hr/attendance/qr_scan.html',
        active_page='qr_scan'
    )


# ══════════════════════════════════════════════════════════════
# API: POST /hr/attendance/qr-lookup  (NO login required)
# ══════════════════════════════════════════════════════════════
@qr_scan_bp.route('/hr/attendance/qr-lookup', methods=['POST', 'GET'])
def qr_lookup():
    raw  = (request.values.get('code') or '').strip()
    code = _parse_qr_payload(raw)

    _log("─" * 50)
    _log(f"qr_lookup INCOMING: raw={raw!r} parsed={code!r}")

    if not code:
        return jsonify({'success': False, 'error': 'No code provided'}), 400

    # ── Employee dhundo ──
    emp = Employee.query.filter_by(employee_code=code).first()
    if not emp:
        emp = Employee.query.filter_by(employee_id=code).first()
    if not emp:
        try:
            emp = db.session.get(Employee, int(code))
        except (ValueError, TypeError):
            pass

    if not emp:
        _log(f"EMP NOT FOUND for code={code!r}")
        return jsonify({
            'success':  False,
            'error':    f'Employee nahi mila code "{code}" ke liye',
            'scanned':  code,
        }), 404

    log_key = emp.employee_id or emp.employee_code
    today   = date.today()
    _log(f"EMP MATCHED: id={emp.id} name={emp.first_name} {emp.last_name} "
         f"emp_code={emp.employee_code!r} emp_id={emp.employee_id!r} "
         f"→ log_key={log_key!r}")

    lookup_only = request.values.get('lookup_only') in ('1', 'true', 'yes', 'on')
    action      = None
    action_at   = None

    if not lookup_only:
        try:
            action, raw_punch = _do_punch(log_key, today)
            if raw_punch and raw_punch.log_date:
                action_at = raw_punch.log_date.strftime('%I:%M %p')
            db.session.commit()
            _log(f"COMMIT OK — action={action} action_at={action_at}")
        except Exception as e:
            db.session.rollback()
            _log(f"❌ PUNCH FAILED: {type(e).__name__}: {e}")
            import traceback; traceback.print_exc(file=sys.stderr); sys.stderr.flush()
            return jsonify({
                'success': False,
                'error':   f'Punch save fail: {str(e)}',
                'scanned': code,
            }), 500

    # ── Updated attendance fetch ──
    att = Attendance.query.filter_by(
        employee_code=log_key,
        attendance_date=today
    ).first()
    if not att and log_key != emp.employee_code:
        att = Attendance.query.filter_by(
            employee_code=emp.employee_code,
            attendance_date=today
        ).first()

    if att:
        _log(f"ATTENDANCE row: in={att.punch_in} out={att.punch_out} "
             f"hours={att.total_hours} status={att.status}")
    else:
        _log("ATTENDANCE row: NONE FOUND")

    full_name = ' '.join(p for p in
                         [emp.first_name, emp.middle_name, emp.last_name]
                         if p and p.strip())

    return jsonify({
        'success':   True,
        'version':   VERSION,
        'action':    action,
        'action_at': action_at,
        'employee': {
            'id':          emp.id,
            'code':        emp.employee_code or '',
            'employee_id': emp.employee_id or '',
            'name':        full_name,
            'department':  emp.department or '',
            'designation': emp.designation or '',
            'photo':       emp.profile_photo or '',
        },
        'attendance': {
            'date':        today.strftime('%d-%b-%Y'),
            'time_in':     att.punch_in.strftime('%I:%M %p')
                                if (att and att.punch_in) else None,
            'time_out':    att.punch_out.strftime('%I:%M %p')
                                if (att and att.punch_out) else None,
            'total_hours': att.working_hours_display if att else '—',
            'status':      att.status if att else 'No Punch Today',
        },
        'scanned_at': datetime.now().strftime('%H:%M:%S'),
    }), 200
