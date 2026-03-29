"""
hr_master_routes.py — HR Masters: Employee Type + Location
Blueprint: hr_masters at /hr/masters
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db
from models.employee import EmployeeTypeMaster, EmployeeLocationMaster
from datetime import datetime

hr_masters = Blueprint('hr_masters', __name__, url_prefix='/hr/masters')

# ── Default seed data ──
DEFAULT_EMP_TYPES = [
    'HCP OFFICE', 'HCP FACTORY STAFF', 'HCP WORKER', 'HCP CONTRACTOR',
    'Full Time', 'Part Time', 'Contract', 'Intern', 'Consultant'
]
DEFAULT_LOCATIONS = [
    'Office', 'Factory', 'Head Office', 'Branch Office',
    'Warehouse', 'Remote', 'Site A', 'Site B'
]


def _admin_only():
    if current_user.role not in ('admin', 'manager', 'hr'):
        from flask import abort; abort(403)


# ══════════════════════════════════════════════════════════════
# MAIN PAGE — Both masters on one page
# ══════════════════════════════════════════════════════════════
@hr_masters.route('/')
@login_required
def index():
    _admin_only()
    emp_types  = EmployeeTypeMaster.query.order_by(
        EmployeeTypeMaster.sort_order, EmployeeTypeMaster.name).all()
    locations  = EmployeeLocationMaster.query.order_by(
        EmployeeLocationMaster.sort_order, EmployeeLocationMaster.name).all()

    return render_template('hr/masters/index.html',
        emp_types=emp_types, locations=locations,
        active_page='hr_masters'
    )


# ══════════════════════════════════════════════════════════════
# EMPLOYEE TYPE — Add / Edit / Delete / Toggle
# ══════════════════════════════════════════════════════════════
@hr_masters.route('/emp-type/add', methods=['POST'])
@login_required
def emp_type_add():
    _admin_only()
    name = request.form.get('name', '').strip().upper()
    if not name:
        flash('Name required.', 'error')
        return redirect(url_for('hr_masters.index'))

    if EmployeeTypeMaster.query.filter_by(name=name).first():
        flash(f'"{name}" already exists.', 'error')
        return redirect(url_for('hr_masters.index'))

    sort = EmployeeTypeMaster.query.count()
    db.session.add(EmployeeTypeMaster(name=name, sort_order=sort, created_by=current_user.id))
    db.session.commit()
    flash(f'Employee Type "{name}" added!', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/emp-type/<int:id>/edit', methods=['POST'])
@login_required
def emp_type_edit(id):
    _admin_only()
    rec  = EmployeeTypeMaster.query.get_or_404(id)
    name = request.form.get('name', '').strip().upper()
    if name:
        dup = EmployeeTypeMaster.query.filter(
            EmployeeTypeMaster.name == name,
            EmployeeTypeMaster.id   != id
        ).first()
        if dup:
            flash(f'"{name}" already exists.', 'error')
            return redirect(url_for('hr_masters.index'))
        rec.name = name
    rec.sort_order = request.form.get('sort_order', rec.sort_order, type=int)
    db.session.commit()
    flash('Updated!', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/emp-type/<int:id>/delete', methods=['POST'])
@login_required
def emp_type_delete(id):
    _admin_only()
    rec = EmployeeTypeMaster.query.get_or_404(id)
    db.session.delete(rec)
    db.session.commit()
    flash(f'"{rec.name}" deleted.', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/emp-type/<int:id>/toggle', methods=['POST'])
@login_required
def emp_type_toggle(id):
    _admin_only()
    rec = EmployeeTypeMaster.query.get_or_404(id)
    rec.is_active = not rec.is_active
    db.session.commit()
    return jsonify(success=True, is_active=rec.is_active)


# ══════════════════════════════════════════════════════════════
# LOCATION — Add / Edit / Delete / Toggle
# ══════════════════════════════════════════════════════════════
@hr_masters.route('/location/add', methods=['POST'])
@login_required
def location_add():
    _admin_only()
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name required.', 'error')
        return redirect(url_for('hr_masters.index'))

    if EmployeeLocationMaster.query.filter_by(name=name).first():
        flash(f'"{name}" already exists.', 'error')
        return redirect(url_for('hr_masters.index'))

    sort = EmployeeLocationMaster.query.count()
    db.session.add(EmployeeLocationMaster(name=name, sort_order=sort, created_by=current_user.id))
    db.session.commit()
    flash(f'Location "{name}" added!', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/location/<int:id>/edit', methods=['POST'])
@login_required
def location_edit(id):
    _admin_only()
    rec  = EmployeeLocationMaster.query.get_or_404(id)
    name = request.form.get('name', '').strip()
    if name:
        dup = EmployeeLocationMaster.query.filter(
            EmployeeLocationMaster.name == name,
            EmployeeLocationMaster.id   != id
        ).first()
        if dup:
            flash(f'"{name}" already exists.', 'error')
            return redirect(url_for('hr_masters.index'))
        rec.name = name
    rec.sort_order = request.form.get('sort_order', rec.sort_order, type=int)
    db.session.commit()
    flash('Updated!', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/location/<int:id>/delete', methods=['POST'])
@login_required
def location_delete(id):
    _admin_only()
    rec = EmployeeLocationMaster.query.get_or_404(id)
    db.session.delete(rec)
    db.session.commit()
    flash(f'"{rec.name}" deleted.', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/location/<int:id>/toggle', methods=['POST'])
@login_required
def location_toggle(id):
    _admin_only()
    rec = EmployeeLocationMaster.query.get_or_404(id)
    rec.is_active = not rec.is_active
    db.session.commit()
    return jsonify(success=True, is_active=rec.is_active)


# ══════════════════════════════════════════════════════════════
# API — Form mein dynamic options ke liye
# ══════════════════════════════════════════════════════════════
@hr_masters.route('/api/emp-types')
def api_emp_types():
    types = EmployeeTypeMaster.query.filter_by(is_active=True).order_by(
        EmployeeTypeMaster.sort_order, EmployeeTypeMaster.name).all()
    return jsonify([{'id': t.id, 'name': t.name} for t in types])


@hr_masters.route('/api/locations')
def api_locations():
    locs = EmployeeLocationMaster.query.filter_by(is_active=True).order_by(
        EmployeeLocationMaster.sort_order, EmployeeLocationMaster.name).all()
    return jsonify([{'id': l.id, 'name': l.name} for l in locs])


# ══════════════════════════════════════════════════════════════
# SEED — Default data insert karo
# ══════════════════════════════════════════════════════════════
def seed_defaults():
    """Default Employee Types aur Locations seed karo."""
    for i, name in enumerate(DEFAULT_EMP_TYPES):
        if not EmployeeTypeMaster.query.filter_by(name=name).first():
            db.session.add(EmployeeTypeMaster(name=name, sort_order=i, is_active=True))

    for i, name in enumerate(DEFAULT_LOCATIONS):
        if not EmployeeLocationMaster.query.filter_by(name=name).first():
            db.session.add(EmployeeLocationMaster(name=name, sort_order=i, is_active=True))

    db.session.commit()
