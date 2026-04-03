"""
late_rule_routes.py — Late Coming Rules Master
Blueprint: late_rules at /hr/late-rules
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db
from models.attendance import LateShiftRule, LatePenaltyRule, EarlyComingRule
from datetime import datetime

late_rules_bp = Blueprint('late_rules', __name__, url_prefix='/hr/late-rules')


def _admin_only():
    if current_user.role not in ('admin', 'manager', 'hr'):
        from flask import abort; abort(403)


# ══════════════════════════════════════════════════════════════
# MAIN PAGE — All shift rules + their penalty slabs
# ══════════════════════════════════════════════════════════════
@late_rules_bp.route('/')
@login_required
def index():
    _admin_only()
    from models.employee import EmployeeTypeMaster
    rules      = LateShiftRule.query.order_by(LateShiftRule.employee_type).all()
    emp_types  = EmployeeTypeMaster.query.filter_by(is_active=True).order_by(
                     EmployeeTypeMaster.sort_order).all()
    # Employee types jo abhi tak rule mein nahi hain
    existing   = {r.employee_type for r in rules}
    available  = [t for t in emp_types if t.name not in existing]

    early_rules   = EarlyComingRule.query.order_by(EarlyComingRule.employee_type).all()
    early_existing = {r.employee_type for r in early_rules}
    early_available = [t for t in emp_types if t.name not in early_existing]

    return render_template('hr/attendance/late_rules.html',
        rules=rules, available=available,
        early_rules=early_rules, early_available=early_available,
        active_page='late_rules'
    )


# ══════════════════════════════════════════════════════════════
# SHIFT RULE — Add
# ══════════════════════════════════════════════════════════════
@late_rules_bp.route('/shift/add', methods=['POST'])
@login_required
def shift_add():
    _admin_only()
    emp_type   = request.form.get('employee_type', '').strip()
    late_after = request.form.get('late_after', '').strip()

    if not emp_type or not late_after:
        flash('Employee Type aur Late After time required hai.', 'error')
        return redirect(url_for('late_rules.index'))

    if LateShiftRule.query.filter_by(employee_type=emp_type).first():
        flash(f'"{emp_type}" ka rule already exist karta hai.', 'error')
        return redirect(url_for('late_rules.index'))

    rule = LateShiftRule(
        employee_type  = emp_type,
        shift_start    = request.form.get('shift_start', '09:00'),
        late_after     = late_after,
        half_day_after = request.form.get('half_day_after') or None,
        absent_after   = request.form.get('absent_after') or None,
        shift_end      = request.form.get('shift_end', '18:00'),
        min_hours_full = float(request.form.get('min_hours_full', 8) or 8),
        min_hours_half = float(request.form.get('min_hours_half', 4) or 4),
        created_by     = current_user.id,
    )
    db.session.add(rule)
    db.session.commit()
    flash(f'"{emp_type}" shift rule added!', 'success')
    return redirect(url_for('late_rules.index'))


# ══════════════════════════════════════════════════════════════
# SHIFT RULE — Edit
# ══════════════════════════════════════════════════════════════
@late_rules_bp.route('/shift/<int:id>/edit', methods=['POST'])
@login_required
def shift_edit(id):
    _admin_only()
    rule = LateShiftRule.query.get_or_404(id)
    rule.shift_start    = request.form.get('shift_start', rule.shift_start)
    rule.late_after     = request.form.get('late_after',  rule.late_after)
    rule.half_day_after = request.form.get('half_day_after') or None
    rule.absent_after   = request.form.get('absent_after')   or None
    rule.shift_end      = request.form.get('shift_end',   rule.shift_end)
    rule.min_hours_full = float(request.form.get('min_hours_full', rule.min_hours_full) or 8)
    rule.min_hours_half = float(request.form.get('min_hours_half', rule.min_hours_half) or 4)
    rule.is_active      = request.form.get('is_active') == '1'
    rule.updated_at     = datetime.now()
    db.session.commit()
    flash('Shift rule updated!', 'success')
    return redirect(url_for('late_rules.index'))


# ══════════════════════════════════════════════════════════════
# SHIFT RULE — Delete
# ══════════════════════════════════════════════════════════════
@late_rules_bp.route('/shift/<int:id>/delete', methods=['POST'])
@login_required
def shift_delete(id):
    _admin_only()
    rule = LateShiftRule.query.get_or_404(id)
    db.session.delete(rule)
    db.session.commit()
    flash(f'"{rule.employee_type}" rule deleted.', 'success')
    return redirect(url_for('late_rules.index'))


# ══════════════════════════════════════════════════════════════
# PENALTY RULE — Add slab to a shift rule
# ══════════════════════════════════════════════════════════════
@late_rules_bp.route('/penalty/add', methods=['POST'])
@login_required
def penalty_add():
    _admin_only()
    shift_rule_id  = request.form.get('shift_rule_id', type=int)
    time_from      = request.form.get('time_from', '').strip()
    from_count     = request.form.get('from_count', type=int)
    penalty_amount = request.form.get('penalty_amount', type=float)

    if not all([shift_rule_id, time_from, from_count is not None, penalty_amount is not None]):
        flash('Sabhi required fields bharein.', 'error')
        return redirect(url_for('late_rules.index'))

    time_to    = request.form.get('time_to', '').strip() or None
    to_count   = request.form.get('to_count', type=int)
    sort_order = LatePenaltyRule.query.filter_by(shift_rule_id=shift_rule_id).count()

    slab = LatePenaltyRule(
        shift_rule_id  = shift_rule_id,
        time_from      = time_from,
        time_to        = time_to,
        from_count     = from_count,
        to_count       = to_count,
        penalty_amount = penalty_amount,
        penalty_type   = request.form.get('penalty_type', 'fixed'),
        description    = request.form.get('description', '').strip(),
        sort_order     = sort_order,
        created_by     = current_user.id,
    )
    db.session.add(slab)
    db.session.commit()
    flash('Penalty slab added!', 'success')
    return redirect(url_for('late_rules.index'))


# ══════════════════════════════════════════════════════════════
# PENALTY RULE — Edit
# ══════════════════════════════════════════════════════════════
@late_rules_bp.route('/penalty/<int:id>/edit', methods=['POST'])
@login_required
def penalty_edit(id):
    _admin_only()
    slab = LatePenaltyRule.query.get_or_404(id)
    slab.time_from      = request.form.get('time_from', slab.time_from)
    slab.time_to        = request.form.get('time_to', '') or None
    slab.from_count     = request.form.get('from_count', slab.from_count, type=int)
    slab.to_count       = request.form.get('to_count', type=int)
    slab.penalty_amount = request.form.get('penalty_amount', slab.penalty_amount, type=float)
    slab.penalty_type   = request.form.get('penalty_type', slab.penalty_type)
    slab.description    = request.form.get('description', '').strip()
    slab.is_active      = request.form.get('is_active', '1') == '1'
    db.session.commit()
    flash('Penalty slab updated!', 'success')
    return redirect(url_for('late_rules.index'))


# ══════════════════════════════════════════════════════════════
# PENALTY RULE — Delete
# ══════════════════════════════════════════════════════════════
@late_rules_bp.route('/penalty/<int:id>/delete', methods=['POST'])
@login_required
def penalty_delete(id):
    _admin_only()
    slab = LatePenaltyRule.query.get_or_404(id)
    db.session.delete(slab)
    db.session.commit()
    flash('Slab deleted.', 'success')
    return redirect(url_for('late_rules.index'))



# ══════════════════════════════════════════════════════════════
# EARLY COMING RULE — Add
# ══════════════════════════════════════════════════════════════
@late_rules_bp.route('/early/add', methods=['POST'])
@login_required
def early_add():
    _admin_only()
    emp_type     = request.form.get('employee_type', '').strip()
    early_before = request.form.get('early_before', '').strip()

    if not emp_type or not early_before:
        flash('Employee Type aur Early Before time required hai.', 'error')
        return redirect(url_for('late_rules.index'))

    if EarlyComingRule.query.filter_by(employee_type=emp_type).first():
        flash(f'"{emp_type}" ka early rule already exist karta hai.', 'error')
        return redirect(url_for('late_rules.index'))

    rule = EarlyComingRule(
        employee_type     = emp_type,
        shift_start       = request.form.get('shift_start', '09:00'),
        early_before      = early_before,
        min_early_minutes = int(request.form.get('min_early_minutes', 15) or 15),
        reward_type       = request.form.get('reward_type', 'none'),
        reward_amount     = float(request.form.get('reward_amount', 0) or 0),
        reward_points     = int(request.form.get('reward_points', 0) or 0),
        min_per_month     = int(request.form.get('min_per_month', 0) or 0),
        track_only        = request.form.get('track_only') == '1',
        notes             = request.form.get('notes', '').strip(),
        created_by        = current_user.id,
    )
    db.session.add(rule)
    db.session.commit()
    flash(f'"{emp_type}" early coming rule added!', 'success')
    return redirect(url_for('late_rules.index'))


@late_rules_bp.route('/early/<int:id>/edit', methods=['POST'])
@login_required
def early_edit(id):
    _admin_only()
    rule = EarlyComingRule.query.get_or_404(id)
    rule.shift_start       = request.form.get('shift_start', rule.shift_start)
    rule.early_before      = request.form.get('early_before', rule.early_before)
    rule.min_early_minutes = int(request.form.get('min_early_minutes', rule.min_early_minutes) or 15)
    rule.reward_type       = request.form.get('reward_type', rule.reward_type)
    rule.reward_amount     = float(request.form.get('reward_amount', 0) or 0)
    rule.reward_points     = int(request.form.get('reward_points', 0) or 0)
    rule.min_per_month     = int(request.form.get('min_per_month', 0) or 0)
    rule.track_only        = request.form.get('track_only') == '1'
    rule.notes             = request.form.get('notes', '').strip()
    rule.is_active         = request.form.get('is_active', '1') == '1'
    rule.updated_at        = datetime.now()
    db.session.commit()
    flash('Early coming rule updated!', 'success')
    return redirect(url_for('late_rules.index'))


@late_rules_bp.route('/early/<int:id>/delete', methods=['POST'])
@login_required
def early_delete(id):
    _admin_only()
    rule = EarlyComingRule.query.get_or_404(id)
    db.session.delete(rule)
    db.session.commit()
    flash(f'"{rule.employee_type}" early rule deleted.', 'success')
    return redirect(url_for('late_rules.index'))


# ══════════════════════════════════════════════════════════════
# ENGINE — Ek employee ka late penalty calculate karo
# ══════════════════════════════════════════════════════════════
def calculate_late_penalty(employee_code, month_start, month_end):
    """
    Ek employee ka ek mahine ka late penalty calculate karo.
    Returns: list of dict with date, punch_in, late_minutes, matched_rule, penalty
    """
    from models import Employee
    from models.attendance import Attendance

    emp = Employee.query.filter_by(employee_code=employee_code).first()
    if not emp:
        return []

    rule = LateShiftRule.query.filter_by(
        employee_type=emp.employee_type, is_active=True
    ).first()
    if not rule:
        return []

    # Us mahine ke saare present records
    records = Attendance.query.filter(
        Attendance.employee_code == employee_code,
        Attendance.attendance_date >= month_start,
        Attendance.attendance_date <= month_end,
        Attendance.punch_in != None,
        Attendance.status.in_(['Present', 'Half Day'])
    ).order_by(Attendance.attendance_date).all()

    late_days = []
    for rec in records:
        late_threshold = rule.late_after_dt(rec.attendance_date)
        if rec.punch_in > late_threshold:
            late_min = int((rec.punch_in - late_threshold).total_seconds() / 60)
            late_days.append({
                'date':        rec.attendance_date,
                'punch_in':    rec.punch_in,
                'late_minutes': late_min,
                'punch_in_str': rec.punch_in.strftime('%I:%M %p'),
            })

    # Ab penalty rules apply karo
    result = []
    late_count_so_far = 0

    for i, day in enumerate(late_days):
        late_count_so_far += 1
        punch_in = day['punch_in']
        matched_slab = None
        penalty = 0

        # Active penalty slabs check karo
        for slab in rule.penalty_rules:
            if not slab.is_active:
                continue

            # Time band check
            time_from_dt = slab.time_from_dt(day['date'])
            time_to_dt   = slab.time_to_dt(day['date'])

            in_time_band = punch_in >= time_from_dt
            if time_to_dt:
                in_time_band = in_time_band and (punch_in <= time_to_dt)

            if not in_time_band:
                continue

            # Count band check
            in_count_band = late_count_so_far >= slab.from_count
            if slab.to_count is not None:
                in_count_band = in_count_band and (late_count_so_far <= slab.to_count)

            if not in_count_band:
                continue

            # Match! — highest penalty wala lena hai
            if slab.penalty_amount > penalty:
                matched_slab = slab
                penalty = float(slab.penalty_amount)

        result.append({
            **day,
            'late_count':   late_count_so_far,
            'matched_rule': matched_slab,
            'penalty':      penalty,
        })

    return result
