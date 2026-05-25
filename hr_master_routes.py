"""
hr_master_routes.py — HR Masters: Employee Type + Location
Blueprint: hr_masters at /hr/masters
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify
from flask_login import login_required, current_user
from models import db
from models.employee import EmployeeTypeMaster, EmployeeLocationMaster, DepartmentMaster, DesignationMaster, CountryMaster, StateMaster, NationalityMaster, QualificationMaster, GradeMaster
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

    countries = CountryMaster.query.order_by(CountryMaster.sort_order, CountryMaster.name).all()
    states    = StateMaster.query.order_by(StateMaster.country_id, StateMaster.sort_order, StateMaster.name).all()
    nationalities = NationalityMaster.query.order_by(NationalityMaster.sort_order, NationalityMaster.name).all()
    qualifications= QualificationMaster.query.order_by(QualificationMaster.sort_order, QualificationMaster.name).all()
    grades        = GradeMaster.query.order_by(GradeMaster.sort_order, GradeMaster.grade_code).all()

    # Map ?tab= → sidebar active_page slug so the right submenu item highlights
    _tab_to_page = {
        'emp_type':    'hr_emptype_master',
        'location':    'hr_loc_master',
        'department':  'hr_dept_master',
        'designation': 'hr_desig_master',
        'country':     'hr_country_master',
        'state':       'hr_state_master',
        'shift':       'hr_shift_master',
        'nationality': 'hr_nationality_master',
        'qualification':'hr_qualification_master',
        'grade':       'hr_grade_master',
    }
    _tab = (request.args.get('tab') or 'emp_type').strip()
    _ap  = _tab_to_page.get(_tab, 'hr_masters')

    return render_template('hr/masters/index.html',
        emp_types=emp_types, locations=locations,
        departments=departments, designations=designations,
        countries=countries, states=states,
        nationalities=nationalities,
        qualifications=qualifications,
        grades=grades,
        active_page=_ap
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

    # Optional fields: notice_period_days + grade_id
    notice = request.form.get('notice_period_days', type=int)
    gid    = request.form.get('grade_id', type=int)
    if gid and not GradeMaster.query.get(gid):
        gid = None  # ignore invalid grade id silently

    sort = DesignationMaster.query.count()
    db.session.add(DesignationMaster(
        name=name,
        notice_period_days=notice,
        grade_id=gid,
        sort_order=sort,
        created_by=current_user.id,
    ))
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

    # Optional fields — accept blank to clear
    if 'notice_period_days' in request.form:
        val = request.form.get('notice_period_days', '').strip()
        rec.notice_period_days = int(val) if val.isdigit() else None

    if 'grade_id' in request.form:
        val = request.form.get('grade_id', '').strip()
        if val.isdigit():
            gid = int(val)
            rec.grade_id = gid if GradeMaster.query.get(gid) else None
        else:
            rec.grade_id = None

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
# COUNTRY MASTER — Add / Edit / Delete / Toggle / List JSON
# ══════════════════════════════════════════════════════════════
@hr_masters.route('/api/countries', methods=['GET'])
@login_required
def countries_list_json():
    """Active countries list — used by Employee form Country dropdown."""
    rows = CountryMaster.query.filter_by(is_active=True)\
        .order_by(CountryMaster.sort_order, CountryMaster.name).all()
    return jsonify([
        {'id': c.id, 'name': c.name, 'iso2': c.iso2, 'iso3': c.iso3, 'phone_code': c.phone_code}
        for c in rows
    ])


@hr_masters.route('/api/states/<int:country_id>', methods=['GET'])
@login_required
def states_list_json(country_id):
    """Active states for a given country — cascading dropdown ke liye."""
    rows = StateMaster.query.filter_by(country_id=country_id, is_active=True)\
        .order_by(StateMaster.sort_order, StateMaster.name).all()
    return jsonify([
        {'id': s.id, 'name': s.name, 'short_name': s.short_name, 'state_code': s.state_code}
        for s in rows
    ])


@hr_masters.route('/api/states/by-country-name', methods=['GET'])
@login_required
def states_by_country_name_json():
    """Lookup states by country *name* (used when employee record stores name, not id)."""
    cname = (request.args.get('country') or '').strip()
    if not cname:
        return jsonify([])
    c = CountryMaster.query.filter(db.func.lower(CountryMaster.name) == cname.lower()).first()
    if not c:
        return jsonify([])
    rows = StateMaster.query.filter_by(country_id=c.id, is_active=True)\
        .order_by(StateMaster.sort_order, StateMaster.name).all()
    return jsonify([
        {'id': s.id, 'name': s.name, 'short_name': s.short_name, 'state_code': s.state_code}
        for s in rows
    ])


@hr_masters.route('/country/add', methods=['POST'])
@login_required
def country_add():
    _admin_only()
    name = request.form.get('name', '').strip()
    if not name:
        flash('Country name required.', 'error')
        return redirect(url_for('hr_masters.index'))
    if CountryMaster.query.filter_by(name=name).first():
        flash(f'"{name}" already exists.', 'error')
        return redirect(url_for('hr_masters.index'))

    sort = CountryMaster.query.count()
    db.session.add(CountryMaster(
        name       = name,
        iso2       = (request.form.get('iso2') or '').strip().upper() or None,
        iso3       = (request.form.get('iso3') or '').strip().upper() or None,
        phone_code = (request.form.get('phone_code') or '').strip() or None,
        sort_order = sort,
        created_by = current_user.id,
    ))
    db.session.commit()
    flash(f'Country "{name}" added!', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/country/<int:id>/edit', methods=['POST'])
@login_required
def country_edit(id):
    _admin_only()
    rec  = CountryMaster.query.get_or_404(id)
    name = request.form.get('name', '').strip()
    if name:
        dup = CountryMaster.query.filter(
            CountryMaster.name == name,
            CountryMaster.id   != id
        ).first()
        if dup:
            flash(f'"{name}" already exists.', 'error')
            return redirect(url_for('hr_masters.index'))
        rec.name = name
    rec.iso2       = (request.form.get('iso2') or '').strip().upper() or None
    rec.iso3       = (request.form.get('iso3') or '').strip().upper() or None
    rec.phone_code = (request.form.get('phone_code') or '').strip() or None
    rec.sort_order = request.form.get('sort_order', rec.sort_order, type=int)
    db.session.commit()
    flash('Country updated.', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/country/<int:id>/delete', methods=['POST'])
@login_required
def country_delete(id):
    _admin_only()
    rec = CountryMaster.query.get_or_404(id)
    n = rec.name
    db.session.delete(rec)
    db.session.commit()
    flash(f'Country "{n}" deleted.', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/country/<int:id>/toggle', methods=['POST'])
@login_required
def country_toggle(id):
    _admin_only()
    rec = CountryMaster.query.get_or_404(id)
    rec.is_active = not rec.is_active
    db.session.commit()
    return jsonify(success=True, is_active=rec.is_active)


# ══════════════════════════════════════════════════════════════
# STATE MASTER — Add / Edit / Delete / Toggle
# ══════════════════════════════════════════════════════════════
@hr_masters.route('/state/add', methods=['POST'])
@login_required
def state_add():
    _admin_only()
    country_id = request.form.get('country_id', type=int)
    name       = request.form.get('name', '').strip()
    if not country_id or not name:
        flash('Country and State name required.', 'error')
        return redirect(url_for('hr_masters.index'))

    if not CountryMaster.query.get(country_id):
        flash('Invalid country.', 'error')
        return redirect(url_for('hr_masters.index'))

    if StateMaster.query.filter_by(country_id=country_id, name=name).first():
        flash(f'State "{name}" already exists for this country.', 'error')
        return redirect(url_for('hr_masters.index'))

    sort = StateMaster.query.filter_by(country_id=country_id).count()
    db.session.add(StateMaster(
        country_id = country_id,
        name       = name,
        short_name = (request.form.get('short_name') or '').strip().upper() or None,
        state_code = (request.form.get('state_code') or '').strip() or None,
        sort_order = sort,
        created_by = current_user.id,
    ))
    db.session.commit()
    flash(f'State "{name}" added!', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/state/<int:id>/edit', methods=['POST'])
@login_required
def state_edit(id):
    _admin_only()
    rec        = StateMaster.query.get_or_404(id)
    country_id = request.form.get('country_id', type=int) or rec.country_id
    name       = request.form.get('name', '').strip()
    if name:
        dup = StateMaster.query.filter(
            StateMaster.country_id == country_id,
            StateMaster.name == name,
            StateMaster.id != id
        ).first()
        if dup:
            flash(f'"{name}" already exists for this country.', 'error')
            return redirect(url_for('hr_masters.index'))
        rec.name = name
    rec.country_id = country_id
    rec.short_name = (request.form.get('short_name') or '').strip().upper() or None
    rec.state_code = (request.form.get('state_code') or '').strip() or None
    rec.sort_order = request.form.get('sort_order', rec.sort_order, type=int)
    db.session.commit()
    flash('State updated.', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/state/<int:id>/delete', methods=['POST'])
@login_required
def state_delete(id):
    _admin_only()
    rec = StateMaster.query.get_or_404(id)
    n = rec.name
    db.session.delete(rec)
    db.session.commit()
    flash(f'State "{n}" deleted.', 'success')
    return redirect(url_for('hr_masters.index'))


@hr_masters.route('/state/<int:id>/toggle', methods=['POST'])
@login_required
def state_toggle(id):
    _admin_only()
    rec = StateMaster.query.get_or_404(id)
    rec.is_active = not rec.is_active
    db.session.commit()
    return jsonify(success=True, is_active=rec.is_active)


# ══════════════════════════════════════════════════════════════
# NATIONALITY — Add / Edit / Delete / Toggle
# ══════════════════════════════════════════════════════════════
@hr_masters.route('/nationality/add', methods=['POST'])
@login_required
def nationality_add():
    _admin_only()
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name required.', 'error')
        return redirect(url_for('hr_masters.index', tab='nationality'))

    # Title-case the input to keep list visually consistent (Indian, American)
    name = name[:1].upper() + name[1:] if name else name

    if NationalityMaster.query.filter(NationalityMaster.name.ilike(name)).first():
        flash(f'"{name}" already exists.', 'error')
        return redirect(url_for('hr_masters.index', tab='nationality'))

    sort = NationalityMaster.query.count()
    db.session.add(NationalityMaster(name=name, sort_order=sort, created_by=current_user.id))
    db.session.commit()
    flash(f'Nationality "{name}" added!', 'success')
    return redirect(url_for('hr_masters.index', tab='nationality'))


@hr_masters.route('/nationality/<int:id>/edit', methods=['POST'])
@login_required
def nationality_edit(id):
    _admin_only()
    rec  = NationalityMaster.query.get_or_404(id)
    name = request.form.get('name', '').strip()
    if name:
        name = name[:1].upper() + name[1:] if name else name
        dup = NationalityMaster.query.filter(
            NationalityMaster.name.ilike(name),
            NationalityMaster.id != id
        ).first()
        if dup:
            flash(f'"{name}" already exists.', 'error')
            return redirect(url_for('hr_masters.index', tab='nationality'))
        rec.name = name
    rec.sort_order = request.form.get('sort_order', rec.sort_order, type=int)
    db.session.commit()
    flash('Updated!', 'success')
    return redirect(url_for('hr_masters.index', tab='nationality'))


@hr_masters.route('/nationality/<int:id>/delete', methods=['POST'])
@login_required
def nationality_delete(id):
    _admin_only()
    rec = NationalityMaster.query.get_or_404(id)
    db.session.delete(rec)
    db.session.commit()
    flash(f'"{rec.name}" deleted.', 'success')
    return redirect(url_for('hr_masters.index', tab='nationality'))


@hr_masters.route('/nationality/<int:id>/toggle', methods=['POST'])
@login_required
def nationality_toggle(id):
    _admin_only()
    rec = NationalityMaster.query.get_or_404(id)
    rec.is_active = not rec.is_active
    db.session.commit()
    return jsonify(success=True, is_active=rec.is_active)


# ══════════════════════════════════════════════════════════════
# QUALIFICATION CRUD
# ══════════════════════════════════════════════════════════════
@hr_masters.route('/qualification/add', methods=['POST'])
@login_required
def qualification_add():
    _admin_only()
    name = request.form.get('name', '').strip()
    if not name:
        flash('Name required.', 'error')
        return redirect(url_for('hr_masters.index', tab='qualification'))

    if QualificationMaster.query.filter(QualificationMaster.name.ilike(name)).first():
        flash(f'"{name}" already exists.', 'error')
        return redirect(url_for('hr_masters.index', tab='qualification'))

    sort = QualificationMaster.query.count()
    db.session.add(QualificationMaster(name=name, sort_order=sort, created_by=current_user.id))
    db.session.commit()
    flash(f'Qualification "{name}" added!', 'success')
    return redirect(url_for('hr_masters.index', tab='qualification'))


@hr_masters.route('/qualification/<int:id>/edit', methods=['POST'])
@login_required
def qualification_edit(id):
    _admin_only()
    rec  = QualificationMaster.query.get_or_404(id)
    name = request.form.get('name', '').strip()
    if name:
        dup = QualificationMaster.query.filter(
            QualificationMaster.name.ilike(name),
            QualificationMaster.id != id
        ).first()
        if dup:
            flash(f'"{name}" already exists.', 'error')
            return redirect(url_for('hr_masters.index', tab='qualification'))
        rec.name = name
    rec.sort_order = request.form.get('sort_order', rec.sort_order, type=int)
    db.session.commit()
    flash('Updated!', 'success')
    return redirect(url_for('hr_masters.index', tab='qualification'))


@hr_masters.route('/qualification/<int:id>/delete', methods=['POST'])
@login_required
def qualification_delete(id):
    _admin_only()
    rec = QualificationMaster.query.get_or_404(id)
    db.session.delete(rec)
    db.session.commit()
    flash(f'"{rec.name}" deleted.', 'success')
    return redirect(url_for('hr_masters.index', tab='qualification'))


@hr_masters.route('/qualification/<int:id>/toggle', methods=['POST'])
@login_required
def qualification_toggle(id):
    _admin_only()
    rec = QualificationMaster.query.get_or_404(id)
    rec.is_active = not rec.is_active
    db.session.commit()
    return jsonify(success=True, is_active=rec.is_active)


# ══════════════════════════════════════════════════════════════
# GRADE CRUD — J1, J2, M1, MG1 ... with level + positions
# ══════════════════════════════════════════════════════════════
ALLOWED_GRADE_LEVELS = ['Junior', 'Mid', 'Senior', 'Management']


@hr_masters.route('/grade/add', methods=['POST'])
@login_required
def grade_add():
    _admin_only()
    code      = (request.form.get('grade_code') or '').strip().upper()
    level     = (request.form.get('grade_level') or '').strip()
    positions = (request.form.get('grade_positions') or '').strip()
    remarks   = (request.form.get('remarks') or '').strip()

    if not code:
        flash('Grade Code required (e.g. J1, M2, MG3).', 'error')
        return redirect(url_for('hr_masters.index', tab='grade'))
    if level not in ALLOWED_GRADE_LEVELS:
        flash(f'Invalid level. Allowed: {", ".join(ALLOWED_GRADE_LEVELS)}.', 'error')
        return redirect(url_for('hr_masters.index', tab='grade'))

    if GradeMaster.query.filter(GradeMaster.grade_code.ilike(code)).first():
        flash(f'Grade "{code}" already exists.', 'error')
        return redirect(url_for('hr_masters.index', tab='grade'))

    sort = GradeMaster.query.count()
    db.session.add(GradeMaster(
        grade_code=code,
        grade_level=level,
        grade_positions=positions or None,
        remarks=remarks or None,
        sort_order=sort,
        created_by=current_user.id,
    ))
    db.session.commit()
    flash(f'Grade "{code}" added!', 'success')
    return redirect(url_for('hr_masters.index', tab='grade'))


@hr_masters.route('/grade/<int:id>/edit', methods=['POST'])
@login_required
def grade_edit(id):
    _admin_only()
    rec = GradeMaster.query.get_or_404(id)

    code      = (request.form.get('grade_code') or '').strip().upper()
    level     = (request.form.get('grade_level') or '').strip()
    positions = (request.form.get('grade_positions') or '').strip()
    remarks   = (request.form.get('remarks') or '').strip()

    if code:
        dup = GradeMaster.query.filter(
            GradeMaster.grade_code.ilike(code),
            GradeMaster.id != id
        ).first()
        if dup:
            flash(f'Grade "{code}" already exists.', 'error')
            return redirect(url_for('hr_masters.index', tab='grade'))
        rec.grade_code = code

    if level:
        if level not in ALLOWED_GRADE_LEVELS:
            flash(f'Invalid level. Allowed: {", ".join(ALLOWED_GRADE_LEVELS)}.', 'error')
            return redirect(url_for('hr_masters.index', tab='grade'))
        rec.grade_level = level

    if 'grade_positions' in request.form:
        rec.grade_positions = positions or None
    if 'remarks' in request.form:
        rec.remarks = remarks or None

    rec.sort_order = request.form.get('sort_order', rec.sort_order, type=int)
    db.session.commit()
    flash('Grade updated!', 'success')
    return redirect(url_for('hr_masters.index', tab='grade'))


@hr_masters.route('/grade/<int:id>/delete', methods=['POST'])
@login_required
def grade_delete(id):
    _admin_only()
    rec = GradeMaster.query.get_or_404(id)
    db.session.delete(rec)
    db.session.commit()
    flash(f'Grade "{rec.grade_code}" deleted.', 'success')
    return redirect(url_for('hr_masters.index', tab='grade'))


@hr_masters.route('/grade/<int:id>/toggle', methods=['POST'])
@login_required
def grade_toggle(id):
    _admin_only()
    rec = GradeMaster.query.get_or_404(id)
    rec.is_active = not rec.is_active
    db.session.commit()
    return jsonify(success=True, is_active=rec.is_active)


# ══════════════════════════════════════════════════════════════
# SEED — Default data insert karo
# ══════════════════════════════════════════════════════════════
DEFAULT_NATIONALITIES = [
    'Indian', 'Afghan', 'American', 'Argentine', 'Australian', 'Austrian',
    'Bahraini', 'Bangladeshi', 'Belgian', 'Bhutanese', 'Brazilian', 'British', 'Bulgarian', 'Burmese (Myanmar)',
    'Cambodian', 'Canadian', 'Chilean', 'Chinese', 'Colombian', 'Czech',
    'Danish', 'Dutch', 'Egyptian', 'Emirati (UAE)', 'Ethiopian',
    'Filipino', 'Finnish', 'French',
    'German', 'Ghanaian', 'Greek',
    'Hong Konger', 'Hungarian',
    'Icelandic', 'Indonesian', 'Iranian', 'Iraqi', 'Irish', 'Israeli', 'Italian',
    'Japanese', 'Jordanian',
    'Kazakh', 'Kenyan', 'Korean (South)', 'Kuwaiti',
    'Lebanese', 'Libyan',
    'Malaysian', 'Maldivian', 'Maltese', 'Mauritian', 'Mexican', 'Mongolian', 'Moroccan',
    'Nepalese', 'New Zealander', 'Nigerian', 'Norwegian',
    'Omani',
    'Pakistani', 'Palestinian', 'Peruvian', 'Polish', 'Portuguese',
    'Qatari',
    'Romanian', 'Russian',
    'Saudi Arabian', 'Singaporean', 'Slovak', 'South African', 'Spanish', 'Sri Lankan', 'Swedish', 'Swiss', 'Syrian',
    'Taiwanese', 'Tanzanian', 'Thai', 'Tunisian', 'Turkish',
    'Ugandan', 'Ukrainian', 'Uzbek',
    'Venezuelan', 'Vietnamese',
    'Yemeni',
    'Zambian', 'Zimbabwean',
    'Other',
]


DEFAULT_QUALIFICATIONS = [
    '10th (SSC)', '12th (HSC)',
    'Diploma', 'ITI', 'Diploma / ITI',
    'B.Sc', 'B.Com', 'B.A',
    'B.E / B.Tech', 'BBA', 'BCA',
    'B.Pharm',
    'M.Sc', 'M.Com', 'M.A',
    'M.E / M.Tech', 'MBA', 'MCA',
    'M.Pharm',
    'PhD', 'Other',
]


DEFAULT_GRADES = [
    # (code, level, positions, remarks)
    ('J1',  'Junior',     'Trainee, Assistant',                                                                                              'Entry Level & support staffs'),
    ('J2',  'Junior',     'Jr. Chemist',                                                                                                     'Entry Level & support staffs'),
    ('J3',  'Junior',     'Jr. Executive, Jr. Officer',                                                                                      'Entry Level & support staffs'),
    ('M1',  'Mid',        'DEO, Driver, Receptionist, Security',                                                                             'Skilled Professionals'),
    ('M2',  'Mid',        'Accountant, Client Coordinator, Electrician, Executive, Foreman, Machine Operator, Technician, Utility Operator', 'Skilled Professionals'),
    ('M3',  'Mid',        'Batch Operator, Chemist, Graphics Designer, Microbiologist, Officer, Security Supervisor, Supervisor',            'Skilled Professionals'),
    ('S1',  'Senior',     'Incharge, Security Officer',                                                                                      'Expert Professionals'),
    ('S2',  'Senior',     'Software Developer, Sr. Positions',                                                                               'Expert Professionals'),
    ('S3',  'Senior',     'Assistant Manager',                                                                                               'Expert Professionals'),
    ('MG1', 'Management', 'Manager',                                                                                                         'Managers, Heads'),
    ('MG2', 'Management', 'Head',                                                                                                            'Managers, Heads'),
    ('MG3', 'Management', 'Director',                                                                                                        'Managers, Heads'),
]


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

    for i, name in enumerate(DEFAULT_NATIONALITIES):
        if not NationalityMaster.query.filter(NationalityMaster.name.ilike(name)).first():
            db.session.add(NationalityMaster(name=name, sort_order=i, is_active=True))

    for i, name in enumerate(DEFAULT_QUALIFICATIONS):
        if not QualificationMaster.query.filter(QualificationMaster.name.ilike(name)).first():
            db.session.add(QualificationMaster(name=name, sort_order=i, is_active=True))

    for i, (code, level, positions, remarks) in enumerate(DEFAULT_GRADES):
        if not GradeMaster.query.filter(GradeMaster.grade_code.ilike(code)).first():
            db.session.add(GradeMaster(
                grade_code=code, grade_level=level,
                grade_positions=positions, remarks=remarks,
                sort_order=i, is_active=True,
            ))

    db.session.commit()
