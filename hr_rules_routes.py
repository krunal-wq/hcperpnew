"""
hr_rules_routes.py — HR Rules Pages
Blueprint: hr_rules at /hr/rules

Covers:
  /hr/rules/shifts          — Shift Master
  /hr/rules/locations       — Location Master
  /hr/rules/early-going     — Early Going Rules
  /hr/rules/overtime        — Overtime Rules
  /hr/rules/leave-policy    — Leave Policy
  /hr/rules/lop             — Loss of Pay Rules
  /hr/rules/absent          — Absent Penalty Rules
  /hr/rules/comp-off        — Comp Off Rules
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db
from models.hr_rules import (
    HRShift, HRLocation, HREarlyGoingRule, HROvertimeRule,
    HRLeavePolicy, HRLeaveType, HRLOPRule, HRAbsentRule, HRCompOffRule
)
from datetime import datetime

hr_rules_bp = Blueprint('hr_rules', __name__, url_prefix='/hr/rules')


def _admin_only():
    if current_user.role not in ('admin', 'manager', 'hr'):
        from flask import abort; abort(403)


# ══════════════════════════════════════════════════════════════
# SHIFT MASTER
# ══════════════════════════════════════════════════════════════
@hr_rules_bp.route('/shifts', methods=['GET', 'POST'])
@login_required
def shifts():
    _admin_only()
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            s = HRShift(
                name          = request.form.get('name','').strip(),
                code          = request.form.get('code','').strip().upper(),
                shift_start   = request.form.get('shift_start','09:00'),
                shift_end     = request.form.get('shift_end','18:00'),
                late_after    = request.form.get('late_after') or None,
                half_day_after= request.form.get('half_day_after') or None,
                absent_after  = request.form.get('absent_after') or None,
                early_go_before= request.form.get('early_go_before') or None,
                min_hours_full= float(request.form.get('min_hours_full', 8)),
                min_hours_half= float(request.form.get('min_hours_half', 4)),
                break_minutes = int(request.form.get('break_minutes', 60)),
                weekly_off    = request.form.get('weekly_off','Sunday'),
                color         = request.form.get('color','#2563eb'),
                is_active     = True,
                created_by    = current_user.id,
            )
            db.session.add(s)
            db.session.commit()
            flash(f'Shift "{s.name}" added!', 'success')

        elif action == 'edit':
            sid = int(request.form.get('id'))
            s = HRShift.query.get_or_404(sid)
            s.name           = request.form.get('name', s.name).strip()
            s.code           = request.form.get('code', s.code).strip().upper()
            s.shift_start    = request.form.get('shift_start', s.shift_start)
            s.shift_end      = request.form.get('shift_end', s.shift_end)
            s.late_after     = request.form.get('late_after') or None
            s.half_day_after = request.form.get('half_day_after') or None
            s.absent_after   = request.form.get('absent_after') or None
            s.early_go_before= request.form.get('early_go_before') or None
            s.min_hours_full = float(request.form.get('min_hours_full', s.min_hours_full))
            s.min_hours_half = float(request.form.get('min_hours_half', s.min_hours_half))
            s.break_minutes  = int(request.form.get('break_minutes', s.break_minutes))
            s.weekly_off     = request.form.get('weekly_off', s.weekly_off)
            s.color          = request.form.get('color', s.color)
            s.updated_at     = datetime.now()
            db.session.commit()
            flash('Shift updated!', 'success')

        elif action == 'delete':
            sid = int(request.form.get('id'))
            s = HRShift.query.get_or_404(sid)
            db.session.delete(s)
            db.session.commit()
            flash(f'Shift "{s.name}" deleted.', 'success')

        elif action == 'toggle':
            sid = int(request.form.get('id'))
            s = HRShift.query.get_or_404(sid)
            s.is_active = not s.is_active
            db.session.commit()
            return jsonify(success=True, is_active=s.is_active)

        return redirect(url_for('hr_rules.shifts'))

    shifts = HRShift.query.order_by(HRShift.name).all()
    return render_template('hr/rules/shifts.html', shifts=shifts, active_page='hr_shifts')


# ══════════════════════════════════════════════════════════════
# LOCATION MASTER
# ══════════════════════════════════════════════════════════════
@hr_rules_bp.route('/locations', methods=['GET', 'POST'])
@login_required
def locations():
    _admin_only()
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            loc = HRLocation(
                name          = request.form.get('name','').strip(),
                code          = request.form.get('code','').strip().upper(),
                address       = request.form.get('address','').strip(),
                city          = request.form.get('city','').strip(),
                state         = request.form.get('state','').strip(),
                is_active     = True,
                created_by    = current_user.id,
            )
            db.session.add(loc)
            db.session.commit()
            flash(f'Location "{loc.name}" added!', 'success')

        elif action == 'edit':
            lid = int(request.form.get('id'))
            loc = HRLocation.query.get_or_404(lid)
            loc.name    = request.form.get('name', loc.name).strip()
            loc.code    = request.form.get('code', loc.code).strip().upper()
            loc.address = request.form.get('address', loc.address or '').strip()
            loc.city    = request.form.get('city', loc.city or '').strip()
            loc.state   = request.form.get('state', loc.state or '').strip()
            db.session.commit()
            flash('Location updated!', 'success')

        elif action == 'delete':
            lid = int(request.form.get('id'))
            loc = HRLocation.query.get_or_404(lid)
            db.session.delete(loc)
            db.session.commit()
            flash(f'Location "{loc.name}" deleted.', 'success')

        elif action == 'toggle':
            lid = int(request.form.get('id'))
            loc = HRLocation.query.get_or_404(lid)
            loc.is_active = not loc.is_active
            db.session.commit()
            return jsonify(success=True, is_active=loc.is_active)

        return redirect(url_for('hr_rules.locations'))

    locs = HRLocation.query.order_by(HRLocation.name).all()
    shifts = HRShift.query.filter_by(is_active=True).order_by(HRShift.name).all()
    return render_template('hr/rules/locations.html', locations=locs, shifts=shifts, active_page='hr_locations_master')


# ══════════════════════════════════════════════════════════════
# EARLY GOING RULES
# ══════════════════════════════════════════════════════════════
@hr_rules_bp.route('/early-going', methods=['GET', 'POST'])
@login_required
def early_going():
    _admin_only()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            r = HREarlyGoingRule(
                name             = request.form.get('name','').strip(),
                location_id      = request.form.get('location_id') or None,
                shift_id         = request.form.get('shift_id') or None,
                employee_type    = request.form.get('employee_type','').strip() or None,
                grace_minutes    = int(request.form.get('grace_minutes', 0)),
                half_day_before  = request.form.get('half_day_before') or None,
                absent_before    = request.form.get('absent_before') or None,
                free_early_per_month = int(request.form.get('free_early_per_month', 0)),
                penalty_per_early= float(request.form.get('penalty_per_early', 0)),
                penalty_type     = request.form.get('penalty_type', 'fixed'),
                auto_deduct_lop  = request.form.get('auto_deduct_lop') == 'on',
                notes            = request.form.get('notes','').strip(),
                is_active        = True,
                created_by       = current_user.id,
            )
            db.session.add(r); db.session.commit()
            flash(f'Early Going Rule "{r.name}" added!', 'success')
        elif action == 'edit':
            r = HREarlyGoingRule.query.get_or_404(int(request.form.get('id')))
            r.name             = request.form.get('name', r.name).strip()
            r.location_id      = request.form.get('location_id') or None
            r.shift_id         = request.form.get('shift_id') or None
            r.employee_type    = request.form.get('employee_type','').strip() or None
            r.grace_minutes    = int(request.form.get('grace_minutes', 0))
            r.half_day_before  = request.form.get('half_day_before') or None
            r.absent_before    = request.form.get('absent_before') or None
            r.free_early_per_month = int(request.form.get('free_early_per_month', 0))
            r.penalty_per_early= float(request.form.get('penalty_per_early', 0))
            r.penalty_type     = request.form.get('penalty_type', 'fixed')
            r.auto_deduct_lop  = request.form.get('auto_deduct_lop') == 'on'
            r.notes            = request.form.get('notes','').strip()
            r.updated_at       = datetime.now()
            db.session.commit(); flash('Updated!', 'success')
        elif action == 'delete':
            r = HREarlyGoingRule.query.get_or_404(int(request.form.get('id')))
            db.session.delete(r); db.session.commit()
            flash(f'"{r.name}" deleted.', 'success')
        elif action == 'toggle':
            r = HREarlyGoingRule.query.get_or_404(int(request.form.get('id')))
            r.is_active = not r.is_active; db.session.commit()
            return jsonify(success=True, is_active=r.is_active)
        return redirect(url_for('hr_rules.early_going'))

    rules = HREarlyGoingRule.query.order_by(HREarlyGoingRule.id).all()
    locations = HRLocation.query.filter_by(is_active=True).all()
    shifts    = HRShift.query.filter_by(is_active=True).all()
    return render_template('hr/rules/early_going.html',
        rules=rules, locations=locations, shifts=shifts, active_page='hr_early_rules')


# ══════════════════════════════════════════════════════════════
# OVERTIME RULES
# ══════════════════════════════════════════════════════════════
@hr_rules_bp.route('/overtime', methods=['GET', 'POST'])
@login_required
def overtime():
    _admin_only()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            r = HROvertimeRule(
                name               = request.form.get('name','').strip(),
                location_id        = request.form.get('location_id') or None,
                shift_id           = request.form.get('shift_id') or None,
                employee_type      = request.form.get('employee_type','').strip() or None,
                ot_after_minutes   = int(request.form.get('ot_after_minutes', 30)),
                min_ot_minutes     = int(request.form.get('min_ot_minutes', 60)),
                max_ot_hours_day   = float(request.form.get('max_ot_hours_day', 4)),
                max_ot_hours_month = float(request.form.get('max_ot_hours_month', 50)),
                ot_rate_type       = request.form.get('ot_rate_type', '1.5x'),
                ot_fixed_rate      = float(request.form.get('ot_fixed_rate', 0)) or None,
                weekend_ot_rate    = request.form.get('weekend_ot_rate', '2x'),
                holiday_ot_rate    = request.form.get('holiday_ot_rate', '2x'),
                give_compoff       = request.form.get('give_compoff') == 'on',
                compoff_min_hours  = float(request.form.get('compoff_min_hours', 4)),
                notes              = request.form.get('notes','').strip(),
                is_active          = True,
                created_by         = current_user.id,
            )
            db.session.add(r); db.session.commit()
            flash(f'Overtime Rule "{r.name}" added!', 'success')
        elif action == 'edit':
            r = HROvertimeRule.query.get_or_404(int(request.form.get('id')))
            r.name             = request.form.get('name', r.name).strip()
            r.location_id      = request.form.get('location_id') or None
            r.shift_id         = request.form.get('shift_id') or None
            r.employee_type    = request.form.get('employee_type','').strip() or None
            r.ot_after_minutes = int(request.form.get('ot_after_minutes', 30))
            r.min_ot_minutes   = int(request.form.get('min_ot_minutes', 60))
            r.max_ot_hours_day = float(request.form.get('max_ot_hours_day', 4))
            r.max_ot_hours_month = float(request.form.get('max_ot_hours_month', 50))
            r.ot_rate_type     = request.form.get('ot_rate_type', '1.5x')
            r.ot_fixed_rate    = float(request.form.get('ot_fixed_rate',0)) or None
            r.weekend_ot_rate  = request.form.get('weekend_ot_rate','2x')
            r.holiday_ot_rate  = request.form.get('holiday_ot_rate','2x')
            r.give_compoff     = request.form.get('give_compoff') == 'on'
            r.compoff_min_hours= float(request.form.get('compoff_min_hours', 4))
            r.notes            = request.form.get('notes','').strip()
            r.updated_at       = datetime.now()
            db.session.commit(); flash('Updated!', 'success')
        elif action == 'delete':
            r = HROvertimeRule.query.get_or_404(int(request.form.get('id')))
            db.session.delete(r); db.session.commit()
            flash(f'"{r.name}" deleted.', 'success')
        elif action == 'toggle':
            r = HROvertimeRule.query.get_or_404(int(request.form.get('id')))
            r.is_active = not r.is_active; db.session.commit()
            return jsonify(success=True, is_active=r.is_active)
        return redirect(url_for('hr_rules.overtime'))

    rules = HROvertimeRule.query.order_by(HROvertimeRule.id).all()
    locations = HRLocation.query.filter_by(is_active=True).all()
    shifts    = HRShift.query.filter_by(is_active=True).all()
    return render_template('hr/rules/overtime.html',
        rules=rules, locations=locations, shifts=shifts, active_page='hr_ot_rules')


# ══════════════════════════════════════════════════════════════
# LEAVE POLICY
# ══════════════════════════════════════════════════════════════
@hr_rules_bp.route('/leave-policy', methods=['GET', 'POST'])
@login_required
def leave_policy():
    _admin_only()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add_policy':
            p = HRLeavePolicy(
                name             = request.form.get('name','').strip(),
                location_id      = request.form.get('location_id') or None,
                employee_type    = request.form.get('employee_type','').strip() or None,
                accrual_type     = request.form.get('accrual_type','yearly'),
                sandwich_rule    = request.form.get('sandwich_rule') == 'on',
                carry_forward    = request.form.get('carry_forward') == 'on',
                max_carry_forward= int(request.form.get('max_carry_forward', 15)),
                encashment       = request.form.get('encashment') == 'on',
                max_encashment   = int(request.form.get('max_encashment', 10)),
                probation_leave_allowed = request.form.get('probation_leave_allowed') == 'on',
                allow_negative_leave    = request.form.get('allow_negative_leave') == 'on',
                max_negative_days       = int(request.form.get('max_negative_days', 0)),
                notes            = request.form.get('notes','').strip(),
                is_active        = True,
                created_by       = current_user.id,
            )
            db.session.add(p); db.session.commit()
            flash(f'Leave Policy "{p.name}" added!', 'success')

        elif action == 'add_leave_type':
            pid = int(request.form.get('policy_id'))
            lt = HRLeaveType(
                policy_id         = pid,
                name              = request.form.get('lt_name','').strip(),
                code              = request.form.get('lt_code','').strip().upper(),
                days_per_year     = float(request.form.get('days_per_year', 0)),
                min_days          = float(request.form.get('min_days', 0.5)),
                max_days          = float(request.form.get('max_days', 0)) or None,
                advance_notice_days = int(request.form.get('advance_notice_days', 0)),
                carry_forward     = request.form.get('lt_carry_forward') == 'on',
                max_carry_forward = int(request.form.get('lt_max_carry', 0)) or None,
                encashable        = request.form.get('encashable') == 'on',
                paid              = request.form.get('paid') != 'off',
                gender            = request.form.get('gender') or None,
                color             = request.form.get('color','#2563eb'),
                icon              = request.form.get('icon','📅'),
                sort_order        = HRLeaveType.query.filter_by(policy_id=pid).count(),
                is_active         = True,
            )
            db.session.add(lt); db.session.commit()
            flash(f'Leave Type "{lt.name}" added!', 'success')

        elif action == 'delete_policy':
            p = HRLeavePolicy.query.get_or_404(int(request.form.get('id')))
            db.session.delete(p); db.session.commit()
            flash(f'Policy "{p.name}" deleted.', 'success')

        elif action == 'delete_leave_type':
            lt = HRLeaveType.query.get_or_404(int(request.form.get('id')))
            db.session.delete(lt); db.session.commit()
            flash(f'Leave Type "{lt.name}" deleted.', 'success')

        elif action == 'toggle_policy':
            p = HRLeavePolicy.query.get_or_404(int(request.form.get('id')))
            p.is_active = not p.is_active; db.session.commit()
            return jsonify(success=True, is_active=p.is_active)

        return redirect(url_for('hr_rules.leave_policy'))

    policies  = HRLeavePolicy.query.order_by(HRLeavePolicy.id).all()
    locations = HRLocation.query.filter_by(is_active=True).all()
    return render_template('hr/rules/leave_policy.html',
        policies=policies, locations=locations, active_page='hr_leave_policy')


# ══════════════════════════════════════════════════════════════
# LOP RULES
# ══════════════════════════════════════════════════════════════
@hr_rules_bp.route('/lop', methods=['GET', 'POST'])
@login_required
def lop():
    _admin_only()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            r = HRLOPRule(
                name                    = request.form.get('name','').strip(),
                location_id             = request.form.get('location_id') or None,
                employee_type           = request.form.get('employee_type','').strip() or None,
                lop_basis               = request.form.get('lop_basis','working_days'),
                paid_days_basis         = request.form.get('paid_days_basis','actual'),
                absent_triggers_lop     = request.form.get('absent_triggers_lop') == 'on',
                late_triggers_lop       = request.form.get('late_triggers_lop') == 'on',
                late_lop_after_count    = int(request.form.get('late_lop_after_count', 3)),
                lop_per_late_count      = int(request.form.get('lop_per_late_count', 3)),
                half_day_lop_after_count= int(request.form.get('half_day_lop_after_count', 3)),
                daily_rate_formula      = request.form.get('daily_rate_formula','basic_gross/working_days'),
                include_allowances      = request.form.get('include_allowances') == 'on',
                notes                   = request.form.get('notes','').strip(),
                is_active               = True,
                created_by              = current_user.id,
            )
            db.session.add(r); db.session.commit()
            flash(f'LOP Rule "{r.name}" added!', 'success')
        elif action == 'delete':
            r = HRLOPRule.query.get_or_404(int(request.form.get('id')))
            db.session.delete(r); db.session.commit()
            flash(f'"{r.name}" deleted.', 'success')
        elif action == 'toggle':
            r = HRLOPRule.query.get_or_404(int(request.form.get('id')))
            r.is_active = not r.is_active; db.session.commit()
            return jsonify(success=True, is_active=r.is_active)
        return redirect(url_for('hr_rules.lop'))

    rules = HRLOPRule.query.order_by(HRLOPRule.id).all()
    locations = HRLocation.query.filter_by(is_active=True).all()
    return render_template('hr/rules/lop.html',
        rules=rules, locations=locations, active_page='hr_lop_rules')


# ══════════════════════════════════════════════════════════════
# ABSENT RULES
# ══════════════════════════════════════════════════════════════
@hr_rules_bp.route('/absent', methods=['GET', 'POST'])
@login_required
def absent():
    _admin_only()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            r = HRAbsentRule(
                name                   = request.form.get('name','').strip(),
                location_id            = request.form.get('location_id') or None,
                employee_type          = request.form.get('employee_type','').strip() or None,
                absent_days_from       = int(request.form.get('absent_days_from', 1)),
                absent_days_to         = int(request.form.get('absent_days_to', 0)) or None,
                penalty_per_day        = float(request.form.get('penalty_per_day', 0)),
                penalty_type           = request.form.get('penalty_type','fixed'),
                consecutive_absent_days= int(request.form.get('consecutive_absent_days', 3)),
                auto_terminate_days    = int(request.form.get('auto_terminate_days', 0)) or None,
                notify_hr              = request.form.get('notify_hr') == 'on',
                notes                  = request.form.get('notes','').strip(),
                is_active              = True,
                created_by             = current_user.id,
            )
            db.session.add(r); db.session.commit()
            flash(f'Absent Rule "{r.name}" added!', 'success')
        elif action == 'delete':
            r = HRAbsentRule.query.get_or_404(int(request.form.get('id')))
            db.session.delete(r); db.session.commit()
            flash(f'"{r.name}" deleted.', 'success')
        elif action == 'toggle':
            r = HRAbsentRule.query.get_or_404(int(request.form.get('id')))
            r.is_active = not r.is_active; db.session.commit()
            return jsonify(success=True, is_active=r.is_active)
        return redirect(url_for('hr_rules.absent'))

    rules = HRAbsentRule.query.order_by(HRAbsentRule.id).all()
    locations = HRLocation.query.filter_by(is_active=True).all()
    return render_template('hr/rules/absent.html',
        rules=rules, locations=locations, active_page='hr_absent_rules')


# ══════════════════════════════════════════════════════════════
# COMP OFF RULES
# ══════════════════════════════════════════════════════════════
@hr_rules_bp.route('/comp-off', methods=['GET', 'POST'])
@login_required
def comp_off():
    _admin_only()
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'add':
            r = HRCompOffRule(
                name                   = request.form.get('name','').strip(),
                location_id            = request.form.get('location_id') or None,
                employee_type          = request.form.get('employee_type','').strip() or None,
                min_hours_worked       = float(request.form.get('min_hours_worked', 4)),
                comp_off_days          = float(request.form.get('comp_off_days', 1)),
                applicable_on_sunday   = request.form.get('applicable_on_sunday') == 'on',
                applicable_on_holiday  = request.form.get('applicable_on_holiday') == 'on',
                applicable_on_saturday = request.form.get('applicable_on_saturday') == 'on',
                comp_off_validity_days = int(request.form.get('comp_off_validity_days', 30)),
                needs_approval         = request.form.get('needs_approval') == 'on',
                max_comp_off_balance   = float(request.form.get('max_comp_off_balance', 6)),
                notes                  = request.form.get('notes','').strip(),
                is_active              = True,
                created_by             = current_user.id,
            )
            db.session.add(r); db.session.commit()
            flash(f'Comp Off Rule "{r.name}" added!', 'success')
        elif action == 'delete':
            r = HRCompOffRule.query.get_or_404(int(request.form.get('id')))
            db.session.delete(r); db.session.commit()
            flash(f'"{r.name}" deleted.', 'success')
        elif action == 'toggle':
            r = HRCompOffRule.query.get_or_404(int(request.form.get('id')))
            r.is_active = not r.is_active; db.session.commit()
            return jsonify(success=True, is_active=r.is_active)
        return redirect(url_for('hr_rules.comp_off'))

    rules = HRCompOffRule.query.order_by(HRCompOffRule.id).all()
    locations = HRLocation.query.filter_by(is_active=True).all()
    return render_template('hr/rules/comp_off.html',
        rules=rules, locations=locations, active_page='hr_compoff_rules')


# ══════════════════════════════════════════════════════════════
# API — dropdowns ke liye
# ══════════════════════════════════════════════════════════════
@hr_rules_bp.route('/api/shifts')
@login_required
def api_shifts():
    shifts = HRShift.query.filter_by(is_active=True).order_by(HRShift.name).all()
    return jsonify([{'id': s.id, 'name': s.name, 'code': s.code,
                     'start': s.shift_start, 'end': s.shift_end} for s in shifts])

@hr_rules_bp.route('/api/locations')
@login_required
def api_locations():
    locs = HRLocation.query.filter_by(is_active=True).order_by(HRLocation.name).all()
    return jsonify([{'id': l.id, 'name': l.name, 'code': l.code} for l in locs])
