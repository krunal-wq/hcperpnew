"""
hr_master_routes.py — HR Masters: Employee Type + Location
Blueprint: hr_masters at /hr/masters
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db
from models.employee import EmployeeTypeMaster, EmployeeLocationMaster, DepartmentMaster, DesignationMaster
from datetime import datetime

hr_masters = Blueprint('hr_masters', __name__, url_prefix='/hr/masters')

# ── Default seed data ──
DEFAULT_EMP_TYPES = [
    'HCP OFFICE', 'HCP FACTORY STAFF', 'HCP WORKER', 'HCP CONTRACTOR', 'WFH',
]
DEFAULT_LOCATIONS = [
    'Office', 'Factory',
]
DEFAULT_DEPARTMENTS = [
    'Administration', 'Accounts', 'HR', 'Production', 'Quality',
    'Sales', 'R&D', 'IT', 'Stores', 'Purchase', 'Marketing',
]
DEFAULT_DESIGNATIONS = [
    'Director', 'Manager', 'Assistant Manager', 'Executive',
    'Senior Executive', 'Officer', 'Supervisor', 'Technician',
    'Worker', 'Intern', 'Trainee',
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

    departments  = DepartmentMaster.query.order_by(DepartmentMaster.sort_order, DepartmentMaster.name).all()
    designations = DesignationMaster.query.order_by(DesignationMaster.sort_order, DesignationMaster.name).all()

    return render_template('hr/masters/index.html',
        emp_types=emp_types, locations=locations,
        departments=departments, designations=designations,
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
# DEPARTMENT — Add / Edit / Delete / Toggle
# ══════════════════════════════════════════════════════════════
@hr_masters.route('/department/add', methods=['POST'])
@login_required
def department_add():
    _admin_only()
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name required.', 'error')
        return redirect(url_for('hr_masters.index'))
    if DepartmentMaster.query.filter_by(name=name).first():
        flash(f'"{name}" already exists.', 'error')
        return redirect(url_for('hr_masters.index'))
    sort = DepartmentMaster.query.count()
    db.session.add(DepartmentMaster(name=name, sort_order=sort, created_by=current_user.id))
    db.session.commit()
    flash(f'Department "{name}" added!', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/department/<int:id>/edit', methods=['POST'])
@login_required
def department_edit(id):
    _admin_only()
    rec  = DepartmentMaster.query.get_or_404(id)
    name = request.form.get('name', '').strip()
    if name:
        dup = DepartmentMaster.query.filter(DepartmentMaster.name==name, DepartmentMaster.id!=id).first()
        if dup:
            flash(f'"{name}" already exists.', 'error')
            return redirect(url_for('hr_masters.index'))
        rec.name = name
    db.session.commit()
    flash('Updated!', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/department/<int:id>/delete', methods=['POST'])
@login_required
def department_delete(id):
    _admin_only()
    rec = DepartmentMaster.query.get_or_404(id)
    db.session.delete(rec); db.session.commit()
    flash(f'"{rec.name}" deleted.', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/department/<int:id>/toggle', methods=['POST'])
@login_required
def department_toggle(id):
    _admin_only()
    rec = DepartmentMaster.query.get_or_404(id)
    rec.is_active = not rec.is_active; db.session.commit()
    return jsonify(success=True, is_active=rec.is_active)


# ══════════════════════════════════════════════════════════════
# DESIGNATION — Add / Edit / Delete / Toggle
# ══════════════════════════════════════════════════════════════
@hr_masters.route('/designation/add', methods=['POST'])
@login_required
def designation_add():
    _admin_only()
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name required.', 'error')
        return redirect(url_for('hr_masters.index'))
    if DesignationMaster.query.filter_by(name=name).first():
        flash(f'"{name}" already exists.', 'error')
        return redirect(url_for('hr_masters.index'))
    sort = DesignationMaster.query.count()
    db.session.add(DesignationMaster(name=name, sort_order=sort, created_by=current_user.id))
    db.session.commit()
    flash(f'Designation "{name}" added!', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/designation/<int:id>/edit', methods=['POST'])
@login_required
def designation_edit(id):
    _admin_only()
    rec  = DesignationMaster.query.get_or_404(id)
    name = request.form.get('name', '').strip()
    if name:
        dup = DesignationMaster.query.filter(DesignationMaster.name==name, DesignationMaster.id!=id).first()
        if dup:
            flash(f'"{name}" already exists.', 'error')
            return redirect(url_for('hr_masters.index'))
        rec.name = name
    db.session.commit()
    flash('Updated!', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/designation/<int:id>/delete', methods=['POST'])
@login_required
def designation_delete(id):
    _admin_only()
    rec = DesignationMaster.query.get_or_404(id)
    db.session.delete(rec); db.session.commit()
    flash(f'"{rec.name}" deleted.', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/designation/<int:id>/toggle', methods=['POST'])
@login_required
def designation_toggle(id):
    _admin_only()
    rec = DesignationMaster.query.get_or_404(id)
    rec.is_active = not rec.is_active; db.session.commit()
    return jsonify(success=True, is_active=rec.is_active)


# ── API ──
@hr_masters.route('/api/departments')
def api_departments():
    depts = DepartmentMaster.query.filter_by(is_active=True).order_by(DepartmentMaster.sort_order).all()
    return jsonify([{'id': d.id, 'name': d.name} for d in depts])


@hr_masters.route('/api/designations')
def api_designations():
    desigs = DesignationMaster.query.filter_by(is_active=True).order_by(DesignationMaster.sort_order).all()
    return jsonify([{'id': d.id, 'name': d.name} for d in desigs])


# ══════════════════════════════════════════════════════════════
# SEED — Default data insert karo
# ══════════════════════════════════════════════════════════════
def seed_defaults():
    """Default data seed karo."""
    for i, name in enumerate(DEFAULT_EMP_TYPES):
        if not EmployeeTypeMaster.query.filter_by(name=name).first():
            db.session.add(EmployeeTypeMaster(name=name, sort_order=i, is_active=True))

    for i, name in enumerate(DEFAULT_LOCATIONS):
        if not EmployeeLocationMaster.query.filter_by(name=name).first():
            db.session.add(EmployeeLocationMaster(name=name, sort_order=i, is_active=True))

    for i, name in enumerate(DEFAULT_DEPARTMENTS):
        if not DepartmentMaster.query.filter_by(name=name).first():
            db.session.add(DepartmentMaster(name=name, sort_order=i, is_active=True))

    for i, name in enumerate(DEFAULT_DESIGNATIONS):
        if not DesignationMaster.query.filter_by(name=name).first():
            db.session.add(DesignationMaster(name=name, sort_order=i, is_active=True))

    db.session.commit()
