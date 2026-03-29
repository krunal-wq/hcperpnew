"""
hr_routes.py — HR Module: Employee & Contractor CRUD
"""
import base64, io, json
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file, Response
from flask_login import login_required, current_user
from audit_helper import audit, snapshot
from datetime import datetime
from models import db, User, Employee, Contractor, WishLog, SalaryConfig, SalaryComponent
from permissions import get_perm, get_grid_columns, save_grid_columns
from id_card_generator import generate_id_card_pdf

hr = Blueprint('hr', __name__, url_prefix='/hr')


def _parse_date(val):
    try:
        return datetime.strptime(val, '%Y-%m-%d').date() if val else None
    except ValueError:
        return None


# Default grid columns
EMP_COLS_DEFAULT = ['employee_code','full_name','mobile','email','department',
                    'designation','employee_type','date_of_joining','status','qr']
EMP_COLS_ALL = {
    'employee_code':  'Emp Code',
    'full_name':      'Name',
    'mobile':         'Mobile',
    'email':          'Email',
    'department':     'Department',
    'designation':    'Designation',
    'employee_type':  'Type',
    'date_of_joining':'Date of Joining',
    'location':       'Location',
    'is_contractor':  'Contractor?',
    'marital_status': 'Marital Status',
    'blood_group':    'Blood Group',
    'status':         'Status',
    'qr':             'QR Code',
}

CTR_COLS_DEFAULT = ['contract_id','company_name','supply','contact_person','contact_no','email_address','pancard','gstno','status']
CTR_COLS_ALL = {
    'contract_id':    'Contract ID',
    'company_name':   'Company',
    'supply':         'Supply',
    'contact_person': 'Contact Person',
    'contact_no':     'Mobile',
    'email_address':  'Email',
    'pancard':        'PAN',
    'gstno':          'GST No',
    'remarks':        'Remarks',
    'status':         'Status',
}


# ══════════════════════════════════════
# EMPLOYEE
# ══════════════════════════════════════

@hr.route('/employees')
@login_required
def employees():
    perm = get_perm('hr_employees')
    if not perm or not perm.can_view:
        flash('Access denied.', 'error'); return redirect(url_for('dashboard'))

    search     = request.args.get('search', '')
    dept       = request.args.get('dept', '')
    status     = request.args.get('status', '')
    emptype    = request.args.get('emptype', '')
    em_status_f= request.args.get('status_f', '')
    show_trash = request.args.get('trash', '') == '1'

    # Trash view: sirf deleted, Normal view: sirf non-deleted
    q = Employee.query.filter_by(is_deleted=True) if show_trash         else Employee.query.filter_by(is_deleted=False)

    if not show_trash:
        if search:
            q = q.filter(
                Employee.first_name.ilike(f'%{search}%') |
                Employee.last_name.ilike(f'%{search}%') |
                Employee.employee_code.ilike(f'%{search}%') |
                Employee.mobile.ilike(f'%{search}%') |
                Employee.email.ilike(f'%{search}%')
            )
        if dept:    q = q.filter_by(department=dept)
        if status:  q = q.filter_by(status=status)
        if emptype: q = q.filter_by(employee_type=emptype)

    sort_by  = request.args.get('sort_by', 'created_at')
    sort_dir = request.args.get('sort_dir', 'desc')
    sort_col = getattr(Employee, sort_by, Employee.created_at)
    emps = q.order_by(sort_col.asc() if sort_dir == 'asc' else sort_col.desc()).all()

    all_depts     = [r[0] for r in db.session.query(Employee.department).distinct().all() if r[0]]
    grid_cols     = get_grid_columns('employees', EMP_COLS_DEFAULT, list(EMP_COLS_ALL.keys()))
    deleted_count = Employee.query.filter_by(is_deleted=True).count()

    return render_template('hr/employees/index.html',
        employees=emps, perm=perm, active_page='hr_employees',
        search=search, dept=dept, status=status, emptype=emptype,
        em_status_f=em_status_f,
        sort_by=sort_by, sort_dir=sort_dir,
        show_trash=show_trash, deleted_count=deleted_count,
        all_depts=all_depts, grid_cols=grid_cols, all_cols=EMP_COLS_ALL)


@hr.route('/employees/dashboard')
@login_required
def emp_dashboard():
    from sqlalchemy import func, extract
    from datetime import date, timedelta
    perm = get_perm('hr_employees')
    if not perm or not perm.can_view:
        flash('Access denied.', 'error'); return redirect(url_for('dashboard'))

    today = date.today()
    this_month_start = today.replace(day=1)
    last_month_start = (this_month_start - timedelta(days=1)).replace(day=1)

    all_emps = Employee.query.filter(Employee.status != 'terminated').all()
    total       = len(all_emps)
    active      = sum(1 for e in all_emps if e.status == 'active')
    inactive    = sum(1 for e in all_emps if e.status == 'inactive')
    on_leave    = sum(1 for e in all_emps if e.status == 'on_leave')
    terminated  = Employee.query.filter_by(status='terminated').count()
    probation   = sum(1 for e in all_emps if e.is_probation)
    on_block    = sum(1 for e in all_emps if e.is_block)
    contractors = sum(1 for e in all_emps if e.is_contractor)

    # New joinings this month
    new_this_month = sum(1 for e in all_emps if e.date_of_joining and e.date_of_joining >= this_month_start)
    new_last_month = sum(1 for e in all_emps if e.date_of_joining and last_month_start <= e.date_of_joining < this_month_start)

    # By department
    dept_counts = {}
    for e in all_emps:
        d = e.department or 'Unassigned'
        dept_counts[d] = dept_counts.get(d, 0) + 1
    dept_data = sorted(dept_counts.items(), key=lambda x: -x[1])

    # By employee type
    type_counts = {}
    for e in all_emps:
        t = e.employee_type or 'Unknown'
        type_counts[t] = type_counts.get(t, 0) + 1

    # By gender
    gender_counts = {}
    for e in all_emps:
        g = e.gender or 'Not Specified'
        gender_counts[g] = gender_counts.get(g, 0) + 1

    # Monthly joining trend (last 6 months)
    months_trend = []
    for i in range(5, -1, -1):
        m_start = (today.replace(day=1) - timedelta(days=i*28)).replace(day=1)
        if i > 0:
            m_end = (today.replace(day=1) - timedelta(days=(i-1)*28)).replace(day=1)
        else:
            m_end = today
        cnt = sum(1 for e in all_emps if e.date_of_joining and m_start <= e.date_of_joining < m_end)
        months_trend.append({'label': m_start.strftime('%b %Y'), 'count': cnt})

    # Salary stats
    sal_emps = [e for e in all_emps if e.salary_ctc]
    total_ctc = sum(float(e.salary_ctc) for e in sal_emps)
    avg_ctc   = total_ctc / len(sal_emps) if sal_emps else 0

    # Upcoming birthdays (next 30 days)
    bday_emps = []
    for e in all_emps:
        if e.date_of_birth:
            try:
                bday_this_year = e.date_of_birth.replace(year=today.year)
                if 0 <= (bday_this_year - today).days <= 30:
                    bday_emps.append({'emp': e, 'bday': bday_this_year, 'days': (bday_this_year - today).days})
            except ValueError:
                pass
    bday_emps.sort(key=lambda x: x['days'])

    # Work anniversaries (joined exactly N years ago this month)
    anniv_emps = []
    for e in all_emps:
        if e.date_of_joining:
            years = today.year - e.date_of_joining.year
            if years > 0:
                try:
                    anniv = e.date_of_joining.replace(year=today.year)
                    if 0 <= (anniv - today).days <= 30:
                        anniv_emps.append({'emp': e, 'years': years, 'days': (anniv - today).days})
                except ValueError:
                    pass
    anniv_emps.sort(key=lambda x: x['days'])

    # KYC completeness
    kyc_complete   = sum(1 for e in all_emps if e.aadhar_number and e.pan_number)
    bank_complete  = sum(1 for e in all_emps if e.bank_account_number and e.bank_ifsc)
    photo_complete = sum(1 for e in all_emps if e.profile_photo)
    sal_filled     = len(sal_emps)

    # Recent joiners (last 5)
    recent = sorted([e for e in all_emps if e.date_of_joining], key=lambda e: e.date_of_joining, reverse=True)[:5]

    # Expiring documents (passport/DL in next 60 days)
    expiring_docs = []
    for e in all_emps:
        for doc_name, expiry in [('Passport', e.passport_expiry), ('Driving License', e.dl_expiry)]:
            if expiry and 0 <= (expiry - today).days <= 60:
                expiring_docs.append({'emp': e, 'doc': doc_name, 'expiry': expiry, 'days': (expiry - today).days})
    expiring_docs.sort(key=lambda x: x['days'])

    import json
    return render_template('hr/employees/dashboard.html',
        perm=perm, active_page='hr_emp_dashboard',
        total=total, active=active, inactive=inactive, on_leave=on_leave,
        terminated=terminated, probation=probation, on_block=on_block, contractors=contractors,
        new_this_month=new_this_month, new_last_month=new_last_month,
        dept_data=dept_data[:10],
        type_counts=type_counts,
        gender_counts=gender_counts,
        months_trend=months_trend,
        total_ctc=round(total_ctc/12),  # monthly payroll
        avg_ctc=round(avg_ctc),
        sal_filled=sal_filled,
        bday_emps=bday_emps[:8],
        anniv_emps=anniv_emps[:5],
        kyc_complete=kyc_complete, bank_complete=bank_complete,
        photo_complete=photo_complete,
        recent=recent,
        expiring_docs=expiring_docs[:5],
        dept_json=json.dumps(dict(dept_data[:8])),
        type_json=json.dumps(type_counts),
        gender_json=json.dumps(gender_counts),
        trend_json=json.dumps(months_trend),
    )


@hr.route('/api/celebrations')
@login_required
def api_celebrations():
    """Return today/upcoming birthdays, work anniversaries, marriage anniversaries."""
    from datetime import date
    try:
        today = date.today()
        all_emps = Employee.query.filter(Employee.status == 'active').all()

        my_emp = Employee.query.filter_by(user_id=current_user.id).first()
        my_emp_id = my_emp.id if my_emp else None

        # Load wishes safely (wish_logs table may not exist yet)
        wished_today = set()
        try:
            for w in WishLog.query.filter_by(sender_id=current_user.id, wish_date=today).all():
                wished_today.add(f"{w.target_emp_id}_{w.wish_type}")
        except Exception:
            pass

        celebrations = []

        def _ord(n):
            return str(n) + ('st' if n==1 else 'nd' if n==2 else 'rd' if n==3 else 'th')

        for e in all_emps:
            emp_data = {
                'id': e.id,
                'name': e.full_name,
                'first_name': e.first_name or e.full_name,
                'code': e.employee_code or '',
                'dept': e.department or '',
                'designation': e.designation or '',
                'photo': e.profile_photo or '',
                'view_url': f'/hr/employees/{e.id}/view',
                'is_self': e.id == my_emp_id,
            }

            # ── Birthday ──
            if e.date_of_birth:
                try:
                    bday = e.date_of_birth.replace(year=today.year)
                    days = (bday - today).days
                    if -1 <= days <= 7:
                        age = today.year - e.date_of_birth.year
                        fn = e.first_name or e.full_name
                        self_wish = f"🎂 Aaj aapka birthday hai, {fn}ji! Team ki taraf se aapko bahut bahut Happy Birthday! 🎉🥳 Aapki zindagi mein khushiyan aur safalta barhti rahe. Have a wonderful day! 🌟"
                        other_wish = f"Aaj {e.full_name} ka birthday hai! 🎂 Unhe wish karo:\n\nDear {fn},\nWishing you a very Happy Birthday! 🎂🎉 May this year bring you lots of joy, health and success. Team wishes you all the best! 🥳"
                        key = f"{e.id}_birthday"
                        celebrations.append({**emp_data,
                            'type': 'birthday',
                            'type_label': '🎂 Birthday',
                            'days': days,
                            'extra': f'Turning {age}' if days >= 0 else f'Was yesterday ({age} yrs)',
                            'today': days == 0,
                            'self_wish': self_wish,
                            'wish_template': other_wish,
                            'already_wished': key in wished_today,
                        })
                except ValueError:
                    pass

            # ── Work Anniversary ──
            if e.date_of_joining:
                try:
                    anniv = e.date_of_joining.replace(year=today.year)
                    days = (anniv - today).days
                    if -1 <= days <= 7:
                        years = today.year - e.date_of_joining.year
                        if years > 0:
                            fn = e.first_name or e.full_name
                            self_wish = f"🎖️ Aaj aapki {_ord(years)} Work Anniversary hai, {fn}ji! Hamare saath {years} saal poore karne par bahut bahut badhai! Aapka yogdan hamare liye anmol hai. 💪"
                            other_wish = f"Aaj {e.full_name} ki {_ord(years)} Work Anniversary hai! 🎖️ Unhe congratulate karo:\n\nDear {fn},\nHappy {_ord(years)} Work Anniversary! 🎉 Thank you for your {years} wonderful year{'s' if years!=1 else ''} of dedication. We're proud to have you! 💪"
                            key = f"{e.id}_work_anniversary"
                            celebrations.append({**emp_data,
                                'type': 'work_anniversary',
                                'type_label': '🎖️ Work Anniversary',
                                'days': days,
                                'extra': f'{years} year{"s" if years != 1 else ""} with us',
                                'today': days == 0,
                                'self_wish': self_wish,
                                'wish_template': other_wish,
                                'already_wished': key in wished_today,
                            })
                except ValueError:
                    pass

            # ── Marriage Anniversary ──
            if getattr(e, 'marital_status', None) == 'Married' and getattr(e, 'marriage_anniversary', None):
                try:
                    manniv = e.marriage_anniversary.replace(year=today.year)
                    days = (manniv - today).days
                    if -1 <= days <= 7:
                        years = today.year - e.marriage_anniversary.year
                        yrs_label = f'{_ord(years)} Wedding' if years > 0 else 'Wedding'
                        fn = e.first_name or e.full_name
                        self_wish = f"💍 Aaj aapki {yrs_label} Anniversary hai, {fn}ji! Dil se mubarak ho! ❤️ Aapki zindagi mein pyaar aur khushiyaan hamesha bani rahe. Team ki taraf se dher saari shubhkamnayein! 🌹"
                        other_wish = f"Aaj {e.full_name} ki {yrs_label} Anniversary hai! 💍 Unhe wish karo:\n\nDear {fn},\nHappy {yrs_label} Anniversary! 💍❤️ Wishing you and your family a lifetime of love and happiness! 🌹"
                        key = f"{e.id}_marriage_anniversary"
                        celebrations.append({**emp_data,
                            'type': 'marriage_anniversary',
                            'type_label': '💍 Marriage Anniversary',
                            'days': days,
                            'extra': f'{years} year{"s" if years != 1 else ""} of togetherness' if years > 0 else 'First Anniversary!',
                            'today': days == 0,
                            'self_wish': self_wish,
                            'wish_template': other_wish,
                            'already_wished': key in wished_today,
                        })
                except ValueError:
                    pass

        celebrations.sort(key=lambda x: (0 if x['today'] else 1, x['days']))
        return jsonify(celebrations=celebrations, count=len(celebrations),
                       today_count=sum(1 for c in celebrations if c['today']))
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify(celebrations=[], count=0, today_count=0, error=str(e))


@hr.route('/api/send-wish', methods=['POST'])
@login_required
def api_send_wish():
    """Log that current user sent a wish. Prevents duplicate notifications."""
    from datetime import date
    data = request.get_json() or {}
    target_emp_id = data.get('emp_id')
    wish_type     = data.get('wish_type')
    wish_text     = data.get('wish_text', '')
    today         = date.today()

    if not target_emp_id or not wish_type:
        return jsonify(success=False, error='Missing params')

    if wish_type not in ('birthday','work_anniversary','marriage_anniversary'):
        return jsonify(success=False, error='Invalid type')

    # Check already wished
    existing = WishLog.query.filter_by(
        sender_id=current_user.id,
        target_emp_id=target_emp_id,
        wish_type=wish_type,
        wish_date=today
    ).first()

    if existing:
        return jsonify(success=True, already=True, msg='Already wished today!')

    try:
        w = WishLog(
            sender_id=current_user.id,
            target_emp_id=target_emp_id,
            wish_type=wish_type,
            wish_date=today,
            wish_text=wish_text[:500] if wish_text else ''
        )
        db.session.add(w)
        db.session.commit()
        return jsonify(success=True, already=False, msg='Wish logged!')
    except Exception as ex:
        db.session.rollback()
        return jsonify(success=False, error=str(ex))


@hr.route('/employees/grid-config', methods=['POST'])
@login_required
def emp_grid_config():
    cols = request.json.get('cols', [])
    save_grid_columns('employees', cols)
    return jsonify(success=True)


@hr.route('/contractors/grid-config', methods=['POST'])
@login_required
def contractor_grid_config():
    cols = request.json.get('cols', [])
    save_grid_columns('contractors', cols)
    return jsonify(success=True)


@hr.route('/employees/save-qr', methods=['POST'])
@login_required
def emp_save_qr():
    """Save QR code generated by browser JS"""
    data   = request.json
    emp_id = data.get('emp_id')
    qr_b64 = data.get('qr_base64', '').strip()
    if not emp_id or not qr_b64:
        return jsonify(success=False, error='Missing data')
    e = Employee.query.get_or_404(emp_id)
    e.qr_code_base64 = qr_b64
    db.session.commit()
    return jsonify(success=True)


@hr.route('/employees/add', methods=['GET', 'POST'])
@login_required
def emp_add():
    perm = get_perm('hr_employees')
    if not perm or not perm.can_add:
        flash('Access denied.', 'error'); return redirect(url_for('hr.employees'))

    contractors = Contractor.query.filter_by(status=1, is_deleted=0).order_by(Contractor.company_name).all()

    if request.method == 'POST':
        emp_code = request.form.get('employee_code', '').strip()
        if not emp_code:
            flash('Employee Code is required.', 'error')
            return redirect(url_for('hr.emp_add'))

        if Employee.query.filter(Employee.employee_code.ilike(emp_code)).first():
            flash(f'Employee code "{emp_code}" already exists.', 'error')
            return redirect(url_for('hr.emp_add'))

        photo   = request.form.get('photo_base64', '').strip() or None
        qr_b64  = request.form.get('qr_base64', '').strip() or None

        rto = request.form.get('reports_to', '').strip()
        emp_id_val = request.form.get('employee_id', '').strip() or None
        e = Employee(
            employee_code   = emp_code,
            employee_id     = emp_id_val,
            first_name      = request.form.get('first_name', '').strip(),
            last_name       = request.form.get('last_name', '').strip(),
            mobile          = request.form.get('mobile', '').strip(),
            email           = request.form.get('email', '').strip(),
            gender          = request.form.get('gender', ''),
            profile_photo   = photo,
            qr_code_base64  = qr_b64,
            linkedin        = request.form.get('linkedin', '').strip(),
            facebook        = request.form.get('facebook', '').strip(),
            department      = request.form.get('department', '').strip(),
            designation     = request.form.get('designation', '').strip(),
            employee_type   = request.form.get('employee_type', ''),
            date_of_joining = _parse_date(request.form.get('date_of_joining')),
            location        = request.form.get('location', '').strip(),
            is_contractor   = request.form.get('is_contractor') == 'yes',
            contractor_id   = int(request.form['contractor_id']) if request.form.get('contractor_id') and request.form.get('is_contractor') == 'yes' else None,
            date_of_birth   = _parse_date(request.form.get('date_of_birth')),
            blood_group     = request.form.get('blood_group', '').strip(),
            marital_status  = request.form.get('marital_status', ''),
            is_block        = request.form.get('is_block') == 'yes',
            is_late         = request.form.get('is_late') == 'yes',
            is_probation    = request.form.get('is_probation') == 'yes',
            status          = request.form.get('status', 'active'),
            remark          = request.form.get('remark', '').strip(),
            reports_to      = int(rto) if rto else None,
            # KYC
            nationality     = request.form.get('nationality','Indian').strip(),
            aadhar_number   = request.form.get('aadhar_number','').strip(),
            pan_number      = request.form.get('pan_number','').strip().upper(),
            uan_number      = request.form.get('uan_number','').strip(),
            esic_number     = request.form.get('esic_number','').strip(),
            emergency_name  = request.form.get('emergency_name','').strip(),
            emergency_relation = request.form.get('emergency_relation','').strip(),
            emergency_phone = request.form.get('emergency_phone','').strip(),
            # Bank
            bank_name       = request.form.get('bank_name','').strip(),
            bank_account_number = request.form.get('bank_account_number','').strip(),
            bank_ifsc       = request.form.get('bank_ifsc','').strip().upper(),
            bank_account_type = request.form.get('bank_account_type','').strip(),
            bank_account_holder = request.form.get('bank_account_holder','').strip(),
            # Salary
            salary_ctc      = float(request.form.get('salary_ctc') or 0) or None,
            salary_net      = float(request.form.get('salary_net') or 0) or None,
            salary_mode     = request.form.get('salary_mode','').strip(),
            # Work
            pay_grade       = request.form.get('pay_grade','').strip(),
            shift           = request.form.get('shift','').strip(),
            weekly_off      = request.form.get('weekly_off','').strip(),
            # Education
            highest_qualification = request.form.get('highest_qualification','').strip(),
            # Documents
            documents_json  = request.form.get('documents_json','[]'),
            marriage_anniversary = _parse_date(request.form.get('marriage_anniversary')) if request.form.get('marital_status')=='Married' else None,
            created_by      = current_user.id,
        )
        db.session.add(e)
        db.session.flush()

        # Auto-create login user for every employee
        uname = emp_code.lower().replace('-', '').replace(' ', '')
        if not User.query.filter_by(username=uname).first():
            u = User(
                username  = uname,
                email     = e.email or f'{uname}@hcp.com',
                full_name = e.full_name,
                role      = 'user',
                is_active = True
            )
            u.set_password('HCP@123')
            db.session.add(u)
            db.session.flush()
            e.user_id = u.id

        db.session.commit()
        audit('hr','EMP_ADD', e.id, emp_code, f'Employee added by {current_user.username}: {e.full_name} ({emp_code}) | Dept: {e.department}')
        flash(f'Employee {emp_code} added! Login: {uname} / HCP@123', 'success')
        return redirect(url_for('hr.emp_id_card', id=e.id))

    all_employees = Employee.query.filter_by(status='active').order_by(Employee.first_name).all()
    from models.employee import EmployeeTypeMaster, EmployeeLocationMaster
    emp_types = EmployeeTypeMaster.query.filter_by(is_active=True).order_by(EmployeeTypeMaster.sort_order).all()
    locations = EmployeeLocationMaster.query.filter_by(is_active=True).order_by(EmployeeLocationMaster.sort_order).all()
    return render_template('hr/employees/form.html',
        employee=None, contractors=contractors, perm=perm, active_page='hr_employees',
        all_employees=all_employees, emp_types=emp_types, locations=locations)


@hr.route('/employees/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def emp_edit(id):
    perm = get_perm('hr_employees')
    if not perm or not perm.can_edit:
        flash('Access denied.', 'error'); return redirect(url_for('hr.employees'))

    e = Employee.query.get_or_404(id)
    contractors = Contractor.query.filter_by(status=1, is_deleted=0).order_by(Contractor.company_name).all()

    if request.method == 'POST':
        photo  = request.form.get('photo_base64', '').strip()
        if photo: e.profile_photo = photo

        qr_b64 = request.form.get('qr_base64', '').strip()
        if qr_b64: e.qr_code_base64 = qr_b64

        # Employee code: editable only if currently blank
        new_code = request.form.get('employee_code', '').strip()
        if not e.employee_code and new_code:
            if Employee.query.filter(Employee.employee_code.ilike(new_code), Employee.id != e.id).first():
                flash(f'Code "{new_code}" already in use.', 'error')
                return redirect(url_for('hr.emp_edit', id=id))
            e.employee_code = new_code

        # Employee ID (Biometric/Device) — editable only if currently blank
        new_emp_id = request.form.get('employee_id', '').strip()
        if not e.employee_id and new_emp_id:
            if Employee.query.filter(Employee.employee_id == new_emp_id, Employee.id != e.id).first():
                flash(f'Employee ID "{new_emp_id}" already in use.', 'error')
                return redirect(url_for('hr.emp_edit', id=id))
            e.employee_id = new_emp_id

        e.first_name     = request.form.get('first_name', e.first_name).strip()
        e.last_name      = request.form.get('last_name', e.last_name).strip()
        e.mobile         = request.form.get('mobile', e.mobile).strip()
        e.email          = request.form.get('email', '').strip()
        e.gender         = request.form.get('gender', '')
        e.linkedin       = request.form.get('linkedin', '').strip()
        e.facebook       = request.form.get('facebook', '').strip()
        e.department     = request.form.get('department', '').strip()
        e.designation    = request.form.get('designation', '').strip()
        e.employee_type  = request.form.get('employee_type', '')
        e.location       = request.form.get('location', '').strip()
        e.is_contractor  = request.form.get('is_contractor') == 'yes'
        cid              = request.form.get('contractor_id') or None
        e.contractor_id  = int(cid) if cid and e.is_contractor else None
        e.date_of_joining= _parse_date(request.form.get('date_of_joining'))
        e.date_of_birth  = _parse_date(request.form.get('date_of_birth'))
        e.blood_group    = request.form.get('blood_group', '').strip()
        e.marital_status = request.form.get('marital_status', '')
        e.is_block       = request.form.get('is_block') == 'yes'
        e.is_late        = request.form.get('is_late') == 'yes'
        e.is_probation   = request.form.get('is_probation') == 'yes'
        e.status         = request.form.get('status', 'active')
        e.remark         = request.form.get('remark', '').strip()
        rto = request.form.get('reports_to', '').strip()
        e.reports_to     = int(rto) if rto else None

        # Professional
        e.pay_grade      = request.form.get('pay_grade','').strip()
        e.shift          = request.form.get('shift','').strip()
        e.weekly_off     = request.form.get('weekly_off','').strip()
        e.notice_period_days = int(request.form.get('notice_period_days') or 30)
        e.work_hours_per_day = float(request.form.get('work_hours_per_day') or 8)
        e.rehire_eligible = request.form.get('rehire_eligible') == 'yes'
        e.confirmation_date  = _parse_date(request.form.get('confirmation_date'))
        e.resignation_date   = _parse_date(request.form.get('resignation_date'))
        e.last_working_date  = _parse_date(request.form.get('last_working_date'))

        # KYC
        e.nationality        = request.form.get('nationality','Indian').strip()
        e.religion           = request.form.get('religion','').strip()
        e.caste              = request.form.get('caste','').strip()
        e.physically_handicapped = request.form.get('physically_handicapped') == 'yes'
        ma_raw = request.form.get('marriage_anniversary','').strip()
        if e.marital_status == 'Married' and ma_raw:
            e.marriage_anniversary = _parse_date(ma_raw)
        elif e.marital_status != 'Married':
            e.marriage_anniversary = None
        e.aadhar_number      = request.form.get('aadhar_number','').strip()
        e.pan_number         = request.form.get('pan_number','').strip().upper()
        e.uan_number         = request.form.get('uan_number','').strip()
        e.esic_number        = request.form.get('esic_number','').strip()
        e.passport_number    = request.form.get('passport_number','').strip()
        e.passport_expiry    = _parse_date(request.form.get('passport_expiry'))
        e.driving_license    = request.form.get('driving_license','').strip()
        e.dl_expiry          = _parse_date(request.form.get('dl_expiry'))

        # Emergency
        e.emergency_name     = request.form.get('emergency_name','').strip()
        e.emergency_relation = request.form.get('emergency_relation','').strip()
        e.emergency_phone    = request.form.get('emergency_phone','').strip()
        e.emergency_address  = request.form.get('emergency_address','').strip()

        # Bank
        e.bank_account_holder= request.form.get('bank_account_holder','').strip()
        e.bank_name          = request.form.get('bank_name','').strip()
        e.bank_account_number= request.form.get('bank_account_number','').strip()
        e.bank_ifsc          = request.form.get('bank_ifsc','').strip().upper()
        e.bank_branch        = request.form.get('bank_branch','').strip()
        e.bank_account_type  = request.form.get('bank_account_type','').strip()

        # Salary
        def _dec(v): 
            try: return float(v) if v else None
            except: return None
        e.salary_ctc           = _dec(request.form.get('salary_ctc'))
        e.salary_basic         = _dec(request.form.get('salary_basic'))
        e.salary_hra           = _dec(request.form.get('salary_hra'))
        e.salary_da            = _dec(request.form.get('salary_da'))
        e.salary_ta            = _dec(request.form.get('salary_ta'))
        e.salary_medical_allow = _dec(request.form.get('salary_medical_allow'))
        e.salary_special_allow = _dec(request.form.get('salary_special_allow'))
        e.salary_pf_employee   = _dec(request.form.get('salary_pf_employee'))
        e.salary_pf_employer   = _dec(request.form.get('salary_pf_employer'))
        e.salary_esic_employee = _dec(request.form.get('salary_esic_employee'))
        e.salary_esic_employer = _dec(request.form.get('salary_esic_employer'))
        e.salary_professional_tax = _dec(request.form.get('salary_professional_tax'))
        e.salary_tds           = _dec(request.form.get('salary_tds'))
        e.salary_net           = _dec(request.form.get('salary_net'))
        e.salary_mode          = request.form.get('salary_mode','').strip()
        e.salary_effective_date= _parse_date(request.form.get('salary_effective_date'))
        e.pay_grade            = request.form.get('pay_grade','').strip()

        # Education
        e.highest_qualification= request.form.get('highest_qualification','').strip()
        e.university           = request.form.get('university','').strip()
        e.passing_year         = int(request.form.get('passing_year') or 0) or None
        e.specialization       = request.form.get('specialization','').strip()
        e.prev_company         = request.form.get('prev_company','').strip()
        e.prev_designation     = request.form.get('prev_designation','').strip()
        e.total_experience_yrs = _dec(request.form.get('total_experience_yrs'))
        e.prev_from_date       = _parse_date(request.form.get('prev_from_date'))
        e.prev_to_date         = _parse_date(request.form.get('prev_to_date'))
        e.prev_leaving_reason  = request.form.get('prev_leaving_reason','').strip()

        # Documents
        e.documents_json       = request.form.get('documents_json','[]')

        e.updated_at     = datetime.utcnow()
        db.session.commit()
        audit('hr','EMP_EDIT', e.id, e.employee_code, f'Employee updated by {current_user.username}: {e.full_name} ({e.employee_code})')
        flash('Employee updated!', 'success')
        return redirect(url_for('hr.employees'))

    all_employees = Employee.query.filter_by(status='active').order_by(Employee.first_name).all()
    from models.employee import EmployeeTypeMaster, EmployeeLocationMaster
    emp_types = EmployeeTypeMaster.query.filter_by(is_active=True).order_by(EmployeeTypeMaster.sort_order).all()
    locations = EmployeeLocationMaster.query.filter_by(is_active=True).order_by(EmployeeLocationMaster.sort_order).all()
    return render_template('hr/employees/form.html',
        employee=e, contractors=contractors, perm=perm, active_page='hr_employees',
        all_employees=all_employees, emp_types=emp_types, locations=locations)



# ─────────────────────────────────────────────
# AJAX TAB-WISE SAVE ROUTES
# ─────────────────────────────────────────────

@hr.route('/employees/ajax-init', methods=['POST'])
@login_required
def emp_ajax_init():
    """Step 1: Create employee with basic info only. Returns emp_id."""
    perm = get_perm('hr_employees')
    if not perm or not perm.can_add:
        return {'ok': False, 'error': 'Access denied'}, 403

    from flask import request as req
    data = req.get_json(force=True) or {}

    emp_code = (data.get('employee_code') or '').strip()
    if not emp_code:
        return {'ok': False, 'error': 'Employee Code is required'}, 400

    if Employee.query.filter(Employee.employee_code.ilike(emp_code)).first():
        return {'ok': False, 'error': f'Employee code "{emp_code}" already exists'}, 400

    # Check email duplicate
    email = (data.get('email') or '').strip()
    if email and Employee.query.filter_by(email=email).first():
        return {'ok': False, 'error': f'Email "{email}" already in use'}, 400

    rto = data.get('reports_to', '')
    e = Employee(
        employee_code  = emp_code,
        first_name     = (data.get('first_name') or '').strip(),
        last_name      = (data.get('last_name') or '').strip(),
        mobile         = (data.get('mobile') or '').strip(),
        email          = email,
        gender         = data.get('gender', ''),
        profile_photo  = data.get('photo_base64') or None,
        qr_code_base64 = data.get('qr_base64') or None,
        date_of_birth  = _parse_date(data.get('date_of_birth')),
        blood_group    = (data.get('blood_group') or '').strip(),
        marital_status = data.get('marital_status', ''),
        marriage_anniversary = _parse_date(data.get('marriage_anniversary')) if data.get('marital_status') == 'Married' else None,
        address        = (data.get('address') or '').strip(),
        city           = (data.get('city') or '').strip(),
        state          = (data.get('state') or '').strip(),
        country        = (data.get('country') or '').strip(),
        zip_code       = (data.get('zip_code') or '').strip(),
        linkedin       = (data.get('linkedin') or '').strip(),
        facebook       = (data.get('facebook') or '').strip(),
        status         = 'active',
        created_by     = current_user.id,
        reports_to     = int(rto) if rto else None,
    )
    db.session.add(e)
    db.session.flush()

    # Auto-create login
    uname = emp_code.lower().replace('-','').replace(' ','')
    if not User.query.filter_by(username=uname).first():
        email_for_user = email or f'{uname}@hcp.com'
        # Avoid duplicate email in users table
        if User.query.filter_by(email=email_for_user).first():
            email_for_user = f'{uname}@hcp.com'
        u = User(username=uname, email=email_for_user,
                 full_name=e.full_name, role='user', is_active=True)
        u.set_password('HCP@123')
        db.session.add(u)
        db.session.flush()
        e.user_id = u.id

    db.session.commit()
    return {'ok': True, 'emp_id': e.id, 'emp_code': emp_code,
            'msg': f'Employee {emp_code} created! Login: {uname} / HCP@123'}


@hr.route('/employees/<int:id>/ajax-save-tab', methods=['POST'])
@login_required
def emp_ajax_save_tab(id):
    """Save a specific tab's data for existing employee."""
    perm = get_perm('hr_employees')
    if not perm or not (perm.can_add or perm.can_edit):
        return {'ok': False, 'error': 'Access denied'}, 403

    e = Employee.query.get_or_404(id)
    data = request.get_json(force=True) or {}
    tab  = data.get('tab', '')

    def _dec(v):
        try: return float(v) if v else None
        except: return None

    if tab == 'basic':
        photo = (data.get('photo_base64') or '').strip()
        if photo: e.profile_photo = photo
        qr = (data.get('qr_base64') or '').strip()
        if qr: e.qr_code_base64 = qr
        e.first_name     = (data.get('first_name') or '').strip()
        e.last_name      = (data.get('last_name') or '').strip()
        e.mobile         = (data.get('mobile') or '').strip()
        new_email        = (data.get('email') or '').strip()
        if new_email and new_email != e.email:
            dup = Employee.query.filter(Employee.email == new_email, Employee.id != id).first()
            if dup:
                return {'ok': False, 'error': f'Email "{new_email}" already in use by {dup.employee_code}'}, 400
        e.email          = new_email
        e.gender         = data.get('gender', '')
        e.date_of_birth  = _parse_date(data.get('date_of_birth'))
        e.blood_group    = (data.get('blood_group') or '').strip()
        e.marital_status = data.get('marital_status', '')
        e.marriage_anniversary = _parse_date(data.get('marriage_anniversary')) if data.get('marital_status') == 'Married' else None
        e.address        = (data.get('address') or '').strip()
        e.city           = (data.get('city') or '').strip()
        e.state          = (data.get('state') or '').strip()
        e.country        = (data.get('country') or '').strip()
        e.zip_code       = (data.get('zip_code') or '').strip()
        e.linkedin       = (data.get('linkedin') or '').strip()
        e.facebook       = (data.get('facebook') or '').strip()
        rto = data.get('reports_to', '')
        e.reports_to     = int(rto) if rto else None

    elif tab == 'professional':
        e.department     = (data.get('department') or '').strip()
        e.designation    = (data.get('designation') or '').strip()
        e.employee_type  = data.get('employee_type', '')
        e.date_of_joining= _parse_date(data.get('date_of_joining'))
        e.location       = (data.get('location') or '').strip()
        e.pay_grade      = (data.get('pay_grade') or '').strip()
        e.shift          = (data.get('shift') or '').strip()
        e.weekly_off     = (data.get('weekly_off') or '').strip()
        e.work_hours_per_day = _dec(data.get('work_hours_per_day')) or 8
        e.notice_period_days = int(data.get('notice_period_days') or 30)
        e.is_contractor  = data.get('is_contractor') == 'yes'
        cid = data.get('contractor_id') or None
        e.contractor_id  = int(cid) if cid and e.is_contractor else None
        e.is_block       = data.get('is_block') == 'yes'
        e.is_late        = data.get('is_late') == 'yes'
        e.is_probation   = data.get('is_probation') == 'yes'
        e.status         = data.get('status', 'active')
        e.remark         = (data.get('remark') or '').strip()
        e.confirmation_date  = _parse_date(data.get('confirmation_date'))
        e.resignation_date   = _parse_date(data.get('resignation_date'))
        e.last_working_date  = _parse_date(data.get('last_working_date'))
        e.rehire_eligible    = data.get('rehire_eligible') == 'yes'

    elif tab == 'kyc':
        e.nationality        = (data.get('nationality') or 'Indian').strip()
        e.religion           = (data.get('religion') or '').strip()
        e.caste              = (data.get('caste') or '').strip()
        e.physically_handicapped = data.get('physically_handicapped') == 'yes'
        e.aadhar_number      = (data.get('aadhar_number') or '').strip()
        e.pan_number         = (data.get('pan_number') or '').strip().upper()
        e.uan_number         = (data.get('uan_number') or '').strip()
        e.esic_number        = (data.get('esic_number') or '').strip()
        e.passport_number    = (data.get('passport_number') or '').strip()
        e.passport_expiry    = _parse_date(data.get('passport_expiry'))
        e.driving_license    = (data.get('driving_license') or '').strip()
        e.dl_expiry          = _parse_date(data.get('dl_expiry'))
        e.emergency_name     = (data.get('emergency_name') or '').strip()
        e.emergency_relation = (data.get('emergency_relation') or '').strip()
        e.emergency_phone    = (data.get('emergency_phone') or '').strip()
        e.emergency_address  = (data.get('emergency_address') or '').strip()

    elif tab == 'bank':
        e.bank_account_holder= (data.get('bank_account_holder') or '').strip()
        e.bank_name          = (data.get('bank_name') or '').strip()
        e.bank_account_number= (data.get('bank_account_number') or '').strip()
        e.bank_ifsc          = (data.get('bank_ifsc') or '').strip().upper()
        e.bank_branch        = (data.get('bank_branch') or '').strip()
        e.bank_account_type  = (data.get('bank_account_type') or '').strip()

    elif tab == 'salary':
        e.salary_ctc           = _dec(data.get('salary_ctc'))
        e.salary_basic         = _dec(data.get('salary_basic'))
        e.salary_hra           = _dec(data.get('salary_hra'))
        e.salary_da            = _dec(data.get('salary_da'))
        e.salary_ta            = _dec(data.get('salary_ta'))
        e.salary_medical_allow = _dec(data.get('salary_medical_allow'))
        e.salary_special_allow = _dec(data.get('salary_special_allow'))
        e.salary_pf_employee   = _dec(data.get('salary_pf_employee'))
        e.salary_pf_employer   = _dec(data.get('salary_pf_employer'))
        e.salary_esic_employee = _dec(data.get('salary_esic_employee'))
        e.salary_esic_employer = _dec(data.get('salary_esic_employer'))
        e.salary_professional_tax = _dec(data.get('salary_professional_tax'))
        e.salary_tds           = _dec(data.get('salary_tds'))
        e.salary_net           = _dec(data.get('salary_net'))
        e.salary_mode          = (data.get('salary_mode') or '').strip()
        e.salary_effective_date= _parse_date(data.get('salary_effective_date'))

    elif tab == 'education':
        e.highest_qualification= (data.get('highest_qualification') or '').strip()
        e.university           = (data.get('university') or '').strip()
        e.passing_year         = int(data.get('passing_year') or 0) or None
        e.specialization       = (data.get('specialization') or '').strip()
        e.prev_company         = (data.get('prev_company') or '').strip()
        e.prev_designation     = (data.get('prev_designation') or '').strip()
        e.total_experience_yrs = _dec(data.get('total_experience_yrs'))
        e.prev_from_date       = _parse_date(data.get('prev_from_date'))
        e.prev_to_date         = _parse_date(data.get('prev_to_date'))
        e.prev_leaving_reason  = (data.get('prev_leaving_reason') or '').strip()

    elif tab == 'documents':
        e.documents_json = data.get('documents_json', '[]')

    else:
        return {'ok': False, 'error': f'Unknown tab: {tab}'}, 400

    e.updated_at = datetime.utcnow()
    audit('hr', 'EMP_TAB_SAVE', e.id, e.employee_code, f'Employee {tab} tab saved by {current_user.username}: {e.full_name}')
    db.session.commit()
    return {'ok': True, 'msg': f'{tab.title()} saved successfully!'}

@hr.route('/employees/<int:id>/view')
@login_required
def emp_view(id):
    perm = get_perm('hr_employees')
    if not perm or not perm.can_view:
        flash('Access denied.', 'error'); return redirect(url_for('hr.employees'))
    e = Employee.query.get_or_404(id)
    audit('employees','VIEW', id, f'{e.employee_code or id} / {e.full_name}', obj=e)
    from datetime import date
    from permissions import get_sub_perm
    sub_perms = {
        'salary_details' : get_sub_perm('hr_employees', 'salary_details'),
        'documents'      : get_sub_perm('hr_employees', 'documents'),
        'bank_details'   : get_sub_perm('hr_employees', 'bank_details'),
        'kyc_details'    : get_sub_perm('hr_employees', 'kyc_details'),
    }
    return render_template('hr/employees/view.html', employee=e, perm=perm,
        sub_perms=sub_perms, active_page='hr_employees', today=date.today())


@hr.route('/employees/<int:id>/delete', methods=['POST'])
@login_required
def emp_delete(id):
    perm = get_perm('hr_employees')
    if not perm or not perm.can_delete:
        flash('Access denied.', 'error'); return redirect(url_for('hr.employees'))
    e = Employee.query.get_or_404(id)
    name = e.full_name
    e.is_deleted = True
    e.deleted_at = datetime.utcnow()
    db.session.commit()
    audit('hr','EMP_DELETE', id, name, f'Employee deleted by {current_user.username}: {name}')
    flash(f'Employee "{name}" moved to trash.', 'warning')
    return redirect(url_for('hr.employees'))


@hr.route('/employees/<int:id>/restore', methods=['POST'])
@login_required
def emp_restore(id):
    perm = get_perm('hr_employees')
    if not perm or not perm.can_delete:
        flash('Access denied.', 'error'); return redirect(url_for('hr.employees'))
    e = Employee.query.get_or_404(id)
    e.is_deleted = False
    e.deleted_at = None
    db.session.commit()
    audit('hr','EMP_RESTORE', id, e.emp_code, f'Employee restored by {current_user.username}: {e.full_name}')
    flash(f'Employee "{e.full_name}" restored successfully!', 'success')
    return redirect(url_for('hr.employees', trash=1))


@hr.route('/employees/<int:id>/regenerate-qr', methods=['POST'])
@login_required
def regen_qr(id):
    """QR is now generated client-side; this just clears the stored QR so form re-generates"""
    e = Employee.query.get_or_404(id)
    return jsonify(success=True, employee_code=e.employee_code or '')




@hr.route('/employees/<int:id>/create-login', methods=['POST'])
@login_required
def emp_create_login(id):
    e = Employee.query.get_or_404(id)
    if e.user_id and User.query.get(e.user_id):
        flash('Login already exists for this employee.', 'info')
        return redirect(url_for('hr.employees'))
    uname = (e.employee_code or str(e.id)).lower().replace('-','').replace(' ','')
    if User.query.filter_by(username=uname).first():
        flash(f'Username "{uname}" already taken.', 'error')
        return redirect(url_for('hr.employees'))
    u = User(
        username  = uname,
        email     = e.email or f'{uname}@hcp.com',
        full_name = e.full_name,
        role      = 'user',
        is_active = True
    )
    u.set_password('HCP@123')
    db.session.add(u)
    db.session.flush()
    e.user_id = u.id
    db.session.commit()
    audit('hr','LOGIN_CREATE', e.id, e.employee_code, f'Login created by {current_user.username} for {e.full_name}: username={uname}')
    flash(f'Login created! Username: {uname}  Password: HCP@123', 'success')
    return redirect(url_for('hr.employees'))

# ══════════════════════════════════════
# CONTRACTOR
# ══════════════════════════════════════

@hr.route('/employees/<int:id>/id-card')
@login_required
def emp_id_card(id):
    """Download or view employee ID card as 100×70mm PDF."""
    e = Employee.query.get_or_404(id)
    try:
        pdf_bytes = generate_id_card_pdf(e)
    except Exception as ex:
        flash(f'ID Card generation failed: {ex}', 'error')
        return redirect(url_for('hr.emp_view', id=id))

    filename = f'ID_Card_{e.employee_code or id}.pdf'
    action = request.args.get('action', 'download')   # ?action=view  to open in browser

    if action == 'view':
        return Response(pdf_bytes, mimetype='application/pdf',
                        headers={'Content-Disposition': f'inline; filename="{filename}"'})
    else:
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )



@hr.route('/contractors')
@login_required
def contractors():
    perm = get_perm('hr_contractors')
    if not perm or not perm.can_view:
        flash('Access denied.', 'error'); return redirect(url_for('dashboard'))

    search      = request.args.get('search', '')
    ct_status_f = request.args.get('status_f', '')
    ct_supply_f = request.args.get('supply_f', '')
    show_trash  = request.args.get('trash', '') == '1'

    # Trash view: sirf deleted, Normal view: sirf non-deleted
    q = Contractor.query.filter_by(is_deleted=True) if show_trash         else Contractor.query.filter_by(is_deleted=False)

    if not show_trash:
        if search:
            q = q.filter(
                Contractor.company_name.ilike(f'%{search}%') |
                Contractor.contact_person.ilike(f'%{search}%') |
                Contractor.contract_id.ilike(f'%{search}%') |
                Contractor.contact_no.ilike(f'%{search}%')
            )
        if ct_status_f != '':
            q = q.filter_by(status=int(ct_status_f))
        if ct_supply_f:
            q = q.filter_by(supply=ct_supply_f)

    sort_by  = request.args.get('sort_by', 'created_date')
    sort_dir = request.args.get('sort_dir', 'desc')
    sort_col = getattr(Contractor, sort_by, Contractor.created_date)
    ctrs = q.order_by(sort_col.asc() if sort_dir == 'asc' else sort_col.desc()).all()

    all_supplies  = [r[0] for r in db.session.query(Contractor.supply).distinct().all() if r[0]]
    deleted_count = Contractor.query.filter_by(is_deleted=True).count()
    grid_cols     = get_grid_columns('contractors', CTR_COLS_DEFAULT, list(CTR_COLS_ALL.keys()))

    return render_template('hr/contractors/index.html',
        contractors=ctrs, perm=perm, active_page='hr_contractors',
        search=search, ct_status_f=ct_status_f, ct_supply_f=ct_supply_f,
        sort_by=sort_by, sort_dir=sort_dir,
        show_trash=show_trash, deleted_count=deleted_count,
        all_supplies=all_supplies,
        grid_cols=grid_cols, all_cols=CTR_COLS_ALL)


@hr.route('/contractors/add', methods=['GET', 'POST'])
@login_required
def contractor_add():
    perm = get_perm('hr_contractors')
    if not perm or not perm.can_add:
        flash('Access denied.', 'error'); return redirect(url_for('hr.contractors'))

    if request.method == 'POST':
        last = Contractor.query.order_by(Contractor.id.desc()).first()
        num  = (last.id + 1) if last else 1
        c = Contractor(
            company_name   = request.form.get('company_name', '').strip(),
            supply         = request.form.get('supply', '').strip(),
            pancard        = request.form.get('pancard', '').strip(),
            gstno          = request.form.get('gstno', '').strip(),
            remarks        = request.form.get('remarks', '').strip(),
            contract_id    = f"CTR-{num:04d}",
            contact_person = request.form.get('contact_person', '').strip(),
            contact_no     = request.form.get('contact_no', '').strip(),
            email_address  = request.form.get('email_address', '').strip(),
            address        = request.form.get('address', '').strip(),
            status         = 1,
            created_by     = current_user.full_name or current_user.username,
        )
        db.session.add(c)
        db.session.commit()
        audit('hr','CONTRACTOR_ADD', c.id, c.contract_id, f'Contractor added by {current_user.username}: {c.full_name} ({c.contract_id})')
        flash(f'Contractor {c.contract_id} added!', 'success')
        return redirect(url_for('hr.contractors'))

    return render_template('hr/contractors/form.html',
        contractor=None, perm=perm, active_page='hr_contractors')


@hr.route('/contractors/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def contractor_edit(id):
    perm = get_perm('hr_contractors')
    if not perm or not perm.can_edit:
        flash('Access denied.', 'error'); return redirect(url_for('hr.contractors'))

    c = Contractor.query.get_or_404(id)
    if request.method == 'POST':
        c.company_name   = request.form.get('company_name', '').strip()
        c.supply         = request.form.get('supply', '').strip()
        c.pancard        = request.form.get('pancard', '').strip()
        c.gstno          = request.form.get('gstno', '').strip()
        c.remarks        = request.form.get('remarks', '').strip()
        c.contact_person = request.form.get('contact_person', '').strip()
        c.contact_no     = request.form.get('contact_no', '').strip()
        c.email_address  = request.form.get('email_address', '').strip()
        c.address        = request.form.get('address', '').strip()
        c.status         = int(request.form.get('status', 1))
        c.modified_by    = current_user.full_name or current_user.username
        c.modified_date  = datetime.utcnow()
        db.session.commit()
        audit('hr','CONTRACTOR_EDIT', con.id, con.contract_id, f'Contractor updated by {current_user.username}: {con.full_name}')
        flash('Contractor updated!', 'success')
        return redirect(url_for('hr.contractors'))

    return render_template('hr/contractors/form.html',
        contractor=c, perm=perm, active_page='hr_contractors')


@hr.route('/contractors/<int:id>/delete', methods=['POST'])
@login_required
def contractor_delete(id):
    perm = get_perm('hr_contractors')
    if not perm or not perm.can_delete:
        flash('Access denied.', 'error'); return redirect(url_for('hr.contractors'))
    c = Contractor.query.get_or_404(id)
    c.is_deleted = True
    c.deleted_at = datetime.utcnow()
    c.modified_by = current_user.full_name or current_user.username
    db.session.commit()
    audit('hr','CONTRACTOR_DELETE', id, c.company_name, f'Contractor deleted by {current_user.username}: {c.company_name}')
    flash(f'Contractor "{c.company_name}" moved to trash.', 'warning')
    return redirect(url_for('hr.contractors'))


@hr.route('/contractors/<int:id>/restore', methods=['POST'])
@login_required
def contractor_restore(id):
    perm = get_perm('hr_contractors')
    if not perm or not perm.can_delete:
        flash('Access denied.', 'error'); return redirect(url_for('hr.contractors'))
    c = Contractor.query.get_or_404(id)
    c.is_deleted = False
    c.deleted_at = None
    c.modified_by = current_user.full_name or current_user.username
    db.session.commit()
    audit('hr','CONTRACTOR_RESTORE', id, c.company_name, f'Contractor restored by {current_user.username}: {c.company_name}')
    flash(f'Contractor "{c.company_name}" restored successfully!', 'success')
    return redirect(url_for('hr.contractors', trash=1))



# ─────────────────────────────────────────────
# EMPLOYEE IMPORT ROUTES
# ─────────────────────────────────────────────

@hr.route('/employees/import', methods=['GET','POST'])
@login_required
def emp_import():
    perm = get_perm('hr_employees')
    if not perm or not perm.can_add:
        flash('Access denied.', 'error'); return redirect(url_for('hr.employees'))

    if request.method == 'POST':
        import openpyxl, json as _json
        from datetime import datetime as _dt

        f = request.files.get('import_file')
        if not f or not f.filename:
            flash('Please select a file!', 'warning')
            return redirect(url_for('hr.emp_import'))

        ext = f.filename.rsplit('.', 1)[-1].lower()
        if ext not in ('xlsx', 'xls'):
            flash('Only Excel (.xlsx) files allowed!', 'danger')
            return redirect(url_for('hr.emp_import'))

        added = skipped = 0
        errors = []

        def _gv(row, *keys):
            for k in keys:
                v = row.get(k)
                if v and str(v).strip() not in ('', 'None', 'nan'):
                    return str(v).strip()
            return ''

        def _pd(val):
            if not val or str(val).strip() in ('', 'None', 'nan'): return None
            for fmt in ('%d-%m-%Y','%Y-%m-%d','%d/%m/%Y','%d %b %Y','%d-%b-%Y'):
                try: return _dt.strptime(str(val).strip(), fmt).date()
                except: pass
            return None

        def _dec(val):
            try: return float(str(val).replace(',','').replace('₹','').strip()) if val else None
            except: return None

        try:
            wb = openpyxl.load_workbook(f, read_only=True, data_only=True)

            def sheet_rows(sheet_name):
                """Read a sheet by name, return list of dicts. Returns [] if sheet not found."""
                if sheet_name not in wb.sheetnames:
                    return []
                ws = wb[sheet_name]
                hdrs = [str(c.value).strip() if c.value else '' for c in next(ws.iter_rows(min_row=1, max_row=1))]
                rows = []
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if any(v is not None and str(v).strip() not in ('','None') for v in row):
                        rows.append(dict(zip(hdrs, [str(v).strip() if v is not None else '' for v in row])))
                return rows

            # Try multi-sheet format first
            has_sheets = any(s in wb.sheetnames for s in ['1 - Basic Info','Basic Info','Sheet1'])

            # Read all sheets
            basic_rows   = sheet_rows('1 - Basic Info') or sheet_rows('Basic Info') or []
            prof_rows    = sheet_rows('2 - Professional') or sheet_rows('Professional') or []
            kyc_rows     = sheet_rows('3 - KYC') or sheet_rows('KYC') or []
            bank_rows    = sheet_rows('4 - Bank Details') or sheet_rows('Bank Details') or []
            sal_rows     = sheet_rows('5 - Salary') or sheet_rows('Salary') or []
            edu_rows     = sheet_rows('6 - Education') or sheet_rows('Education') or []

            # If no multi-sheet, try first sheet as basic
            if not basic_rows:
                ws = wb.active
                hdrs = [str(c.value).strip() if c.value else '' for c in next(ws.iter_rows(min_row=1, max_row=1))]
                for row in ws.iter_rows(min_row=2, values_only=True):
                    if any(v is not None and str(v).strip() not in ('','None') for v in row):
                        basic_rows.append(dict(zip(hdrs, [str(v).strip() if v is not None else '' for v in row])))

            # Index supplementary sheets by employee code
            def idx_by_code(rows):
                d = {}
                for r in rows:
                    code = _gv(r,'Code','Employee Code','employee_code')
                    if code: d[code.upper()] = r
                return d

            prof_idx = idx_by_code(prof_rows)
            kyc_idx  = idx_by_code(kyc_rows)
            bank_idx = idx_by_code(bank_rows)
            sal_idx  = idx_by_code(sal_rows)
            edu_idx  = idx_by_code(edu_rows)

            for i, row in enumerate(basic_rows, 2):
                emp_code = _gv(row, 'Employee Code', 'Code', 'employee_code')
                if not emp_code:
                    errors.append(f'Row {i}: Employee Code missing — skipped')
                    continue

                if Employee.query.filter(Employee.employee_code.ilike(emp_code)).first():
                    skipped += 1
                    errors.append(f'Row {i}: Code "{emp_code}" already exists — skipped')
                    continue

                try:
                    p  = prof_idx.get(emp_code.upper(), {})
                    k  = kyc_idx.get(emp_code.upper(), {})
                    bk = bank_idx.get(emp_code.upper(), {})
                    sl = sal_idx.get(emp_code.upper(), {})
                    ed = edu_idx.get(emp_code.upper(), {})

                    email = _gv(row,'Email','email')
                    # Avoid duplicate email
                    if email and Employee.query.filter_by(email=email).first():
                        email = ''

                    marital = _gv(row,'Marital Status','marital_status') or 'Single'

                    e = Employee(
                        employee_code   = emp_code,
                        first_name      = _gv(row,'First Name','first_name'),
                        last_name       = _gv(row,'Last Name','last_name'),
                        mobile          = _gv(row,'Mobile','mobile'),
                        email           = email,
                        gender          = _gv(row,'Gender','gender'),
                        date_of_birth   = _pd(_gv(row,'DOB','Date of Birth','date_of_birth')),
                        blood_group     = _gv(row,'Blood Group','blood_group'),
                        marital_status  = marital,
                        marriage_anniversary = _pd(_gv(row,'Marriage Anniversary','marriage_anniversary')) if marital=='Married' else None,
                        address         = _gv(row,'Address','address'),
                        city            = _gv(row,'City','city'),
                        state           = _gv(row,'State','state'),
                        country         = _gv(row,'Country','country') or 'India',
                        zip_code        = _gv(row,'ZIP','Zip Code','zip_code'),
                        linkedin        = _gv(row,'LinkedIn','linkedin'),
                        facebook        = _gv(row,'Facebook','facebook'),
                        status          = (_gv(row,'Status','status') or 'active').lower().replace(' ','_'),
                        # Professional
                        department      = _gv(p,'Department','department') or _gv(row,'Department'),
                        designation     = _gv(p,'Designation','designation') or _gv(row,'Designation'),
                        employee_type   = _gv(p,'Employee Type','employee_type') or _gv(row,'Employee Type') or 'Full Time',
                        location        = _gv(p,'Location','location') or _gv(row,'Location'),
                        pay_grade       = _gv(p,'Pay Grade','pay_grade'),
                        date_of_joining = _pd(_gv(p,'DOJ','Date of Joining','date_of_joining') or _gv(row,'DOJ','Date of Joining')),
                        confirmation_date = _pd(_gv(p,'Confirmation','Confirmation Date')),
                        shift           = _gv(p,'Shift','shift'),
                        work_hours_per_day = _dec(_gv(p,'Work Hrs','Work Hours Per Day')) or 8,
                        weekly_off      = _gv(p,'Weekly Off','weekly_off'),
                        notice_period_days = int(_gv(p,'Notice Days','Notice Period (Days)') or 30),
                        is_contractor   = _gv(p,'Contractor','Is Contractor','is_contractor').lower() == 'yes',
                        is_probation    = _gv(p,'Probation','Is Probation','is_probation').lower() == 'yes',
                        is_block        = _gv(p,'Block','Is Block','is_block').lower() == 'yes',
                        is_late         = _gv(p,'Late Mark','Is Late','is_late').lower() == 'yes',
                        rehire_eligible = _gv(p,'Rehire Eligible','rehire_eligible').lower() == 'yes',
                        remark          = _gv(p,'Remark','remark'),
                        # KYC
                        nationality     = _gv(k,'Nationality','nationality') or 'Indian',
                        religion        = _gv(k,'Religion','religion'),
                        aadhar_number   = _gv(k,'Aadhaar','Aadhaar Number','aadhar_number'),
                        pan_number      = (_gv(k,'PAN','PAN Number','pan_number') or '').upper(),
                        uan_number      = _gv(k,'UAN','UAN Number','uan_number'),
                        esic_number     = _gv(k,'ESIC','ESIC Number','esic_number'),
                        passport_number = _gv(k,'Passport No.','Passport Number','passport_number'),
                        passport_expiry = _pd(_gv(k,'Passport Expiry','passport_expiry')),
                        driving_license = _gv(k,'DL No','Driving License','driving_license'),
                        dl_expiry       = _pd(_gv(k,'DL Expiry','dl_expiry')),
                        emergency_name  = _gv(k,'Emergency Name','emergency_name'),
                        emergency_relation = _gv(k,'Emergency Relation','emergency_relation'),
                        emergency_phone = _gv(k,'Emergency Phone','emergency_phone'),
                        emergency_address = _gv(k,'Emergency Address','emergency_address'),
                        # Bank
                        bank_account_holder = _gv(bk,'Account Holder','bank_account_holder'),
                        bank_name       = _gv(bk,'Bank Name','bank_name'),
                        bank_account_number = _gv(bk,'Account Number','bank_account_number'),
                        bank_ifsc       = (_gv(bk,'IFSC Code','IFSC','bank_ifsc') or '').upper(),
                        bank_branch     = _gv(bk,'Branch','bank_branch'),
                        bank_account_type = _gv(bk,'Account Type','bank_account_type'),
                        # Salary
                        salary_ctc      = _dec(_gv(sl,'CTC Annual','salary_ctc')),
                        salary_basic    = _dec(_gv(sl,'Basic','salary_basic')),
                        salary_hra      = _dec(_gv(sl,'HRA','salary_hra')),
                        salary_da       = _dec(_gv(sl,'DA','salary_da')),
                        salary_ta       = _dec(_gv(sl,'TA','salary_ta')),
                        salary_medical_allow = _dec(_gv(sl,'Medical','salary_medical_allow')),
                        salary_special_allow = _dec(_gv(sl,'Special','salary_special_allow')),
                        salary_pf_employee   = _dec(_gv(sl,'PF Emp','salary_pf_employee')),
                        salary_pf_employer   = _dec(_gv(sl,'PF Er','salary_pf_employer')),
                        salary_esic_employee = _dec(_gv(sl,'ESIC Emp','salary_esic_employee')),
                        salary_esic_employer = _dec(_gv(sl,'ESIC Er','salary_esic_employer')),
                        salary_professional_tax = _dec(_gv(sl,'Prof Tax','salary_professional_tax')),
                        salary_tds      = _dec(_gv(sl,'TDS','salary_tds')),
                        salary_net      = _dec(_gv(sl,'Net Salary','salary_net')),
                        salary_mode     = _gv(sl,'Mode','salary_mode'),
                        salary_effective_date = _pd(_gv(sl,'Effective Date','salary_effective_date')),
                        # Education
                        highest_qualification = _gv(ed,'Qualification','highest_qualification'),
                        university      = _gv(ed,'University / Board','university'),
                        passing_year    = int(_gv(ed,'Year','passing_year') or 0) or None,
                        specialization  = _gv(ed,'Specialization','specialization'),
                        prev_company    = _gv(ed,'Prev Company','prev_company'),
                        prev_designation = _gv(ed,'Prev Designation','prev_designation'),
                        prev_from_date  = _pd(_gv(ed,'Prev From','prev_from_date')),
                        prev_to_date    = _pd(_gv(ed,'Prev To','prev_to_date')),
                        prev_leaving_reason = _gv(ed,'Leaving Reason','prev_leaving_reason'),
                        total_experience_yrs = _dec(_gv(ed,'Experience (Yrs)','total_experience_yrs')),
                        documents_json  = '[]',
                        created_by      = current_user.id,
                    )

                    # Validate status
                    valid_statuses = ['active','inactive','on_leave','terminated']
                    if e.status not in valid_statuses:
                        e.status = 'active'

                    db.session.add(e)
                    db.session.flush()

                    # Auto-create login
                    uname = emp_code.lower().replace('-','').replace(' ','')
                    if not User.query.filter_by(username=uname).first():
                        ue_email = e.email or f'{uname}@hcp.com'
                        if User.query.filter_by(email=ue_email).first():
                            ue_email = f'{uname}@hcp.com'
                        u = User(username=uname, email=ue_email,
                                 full_name=e.full_name, role='user', is_active=True)
                        u.set_password('HCP@123')
                        db.session.add(u)
                        db.session.flush()
                        e.user_id = u.id

                    added += 1

                except Exception as ex:
                    errors.append(f'Row {i} ({emp_code}): {str(ex)[:100]}')
                    db.session.rollback()

            db.session.commit()
            msg = f'✅ {added} employees imported!'
            if skipped: msg += f' ⚠️ {skipped} skipped (duplicate codes).'
            flash(msg, 'success')
            if errors:
                for err in errors[:8]:
                    flash(err, 'warning')

        except Exception as ex:
            db.session.rollback()
            flash(f'Import failed: {str(ex)}', 'danger')

        return redirect(url_for('hr.employees'))

    return render_template('hr/employees/import.html', perm=perm, active_page='hr_employees')


@hr.route('/employees/import/template')
@login_required
def emp_import_template():
    """Download 7-tab Excel import template."""
    import io, sys, subprocess
    try:
        import openpyxl
    except ImportError:
        subprocess.run([sys.executable,'-m','pip','install','openpyxl','--quiet'],check=True)
        import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    wb = openpyxl.Workbook()

    def mk_hdr(cell, color):
        cell.font = Font(bold=True, color="FFFFFF", size=10, name="Arial")
        cell.fill = PatternFill("solid", fgColor=color)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin = Side(style="thin", color="D0D7E2")
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def mk_note(cell):
        cell.font = Font(size=9, color="64748B", italic=True, name="Arial")
        cell.fill = PatternFill("solid", fgColor="F8FAFC")
        thin = Side(style="thin", color="E2E8F0")
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
        cell.alignment = Alignment(vertical="center")

    def mk_sample(cell):
        cell.font = Font(size=9, name="Arial")
        thin = Side(style="thin", color="E2E8F0")
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
        cell.alignment = Alignment(vertical="center")

    def build_tpl(ws, color, cols, notes, samples):
        ws.row_dimensions[1].height = 26
        ws.row_dimensions[2].height = 20
        ws.row_dimensions[3].height = 18
        for ci, h in enumerate(cols, 1):
            mk_hdr(ws.cell(1, ci, h), color)
        for ci, n in enumerate(notes, 1):
            mk_note(ws.cell(2, ci, n))
        for ci, s in enumerate(samples, 1):
            mk_sample(ws.cell(3, ci, s))
        # Note row style
        ws.cell(2, 1).font = Font(bold=True, size=9, color="B45309", name="Arial")
        ws.cell(2, 1).fill = PatternFill("solid", fgColor="FFFBEB")
        for ci in range(1, len(cols)+1):
            col = get_column_letter(ci)
            mx = max(len(str(ws.cell(r,ci).value or '')) for r in range(1,4))
            ws.column_dimensions[col].width = min(mx+3, 35)
        ws.freeze_panes = "A3"
        ws.cell(2,1,"⚠️ Row 2 = Notes (delete before import). Row 3+ = your data")

    # ── Sheet 1: Basic Info ──
    ws1 = wb.active; ws1.title = "1 - Basic Info"
    build_tpl(ws1, "1E3A5F",
        ["Employee Code","First Name","Last Name","Mobile","Email","Gender","Date of Birth","Blood Group","Marital Status","Marriage Anniversary","Address","City","State","Country","ZIP","LinkedIn","Facebook","Status"],
        ["Required. Unique code","Required","Optional","10 digits","Valid email","Male/Female/Other","DD-MM-YYYY","A+/B+/O+...","Single/Married/Divorced","DD-MM-YYYY if Married","Street address","City","State","Default: India","Pincode","URL optional","URL optional","active/inactive"],
        ["EMP0001","Krunal","Chandi","9876543210","krunal@hcp.com","Male","15-06-1990","A+","Married","20-02-2015","123 MG Road","Ahmedabad","Gujarat","India","380001","","","active"]
    )

    # ── Sheet 2: Professional ──
    ws2 = wb.create_sheet("2 - Professional")
    build_tpl(ws2, "1D4ED8",
        ["Code","Full Name","Department","Designation","Employee Type","Location","Pay Grade","DOJ","Confirmation","Shift","Work Hrs","Weekly Off","Notice Days","Contractor","Probation","Block","Status","Reports To"],
        ["Match Sheet1 Code","For reference","e.g. Sales","e.g. Manager","Full Time/Part Time/Contract/Intern","City/Branch","G1/G2/G3","DD-MM-YYYY","DD-MM-YYYY","General/Night","8","Sunday","30","Yes/No","Yes/No","Yes/No","active","Manager full name"],
        ["EMP0001","Krunal Chandi","Sales","Sales Manager","Full Time","Ahmedabad","G2","01-01-2022","01-07-2022","General (9-6)","8","Sunday","30","No","No","No","active","Rajesh Shah"]
    )

    # ── Sheet 3: KYC ──
    ws3 = wb.create_sheet("3 - KYC")
    build_tpl(ws3, "7C3AED",
        ["Code","Full Name","Nationality","Religion","Aadhaar","PAN","UAN","ESIC","Passport No.","Passport Expiry","DL No","DL Expiry","Emergency Name","Emergency Relation","Emergency Phone","Emergency Address"],
        ["Match Sheet1 Code","For reference","Indian","Hindu/Muslim/..","12 digits","ABCDE1234F","12 digits","17 digits","A1234567","DD-MM-YYYY","GJ01 2024 123456","DD-MM-YYYY","Contact name","Father/Spouse/..","10 digits","Address"],
        ["EMP0001","Krunal Chandi","Indian","Hindu","123456789012","ABCDE1234F","100123456789","1234567890123456","A1234567","31-12-2030","GJ01 2024 123","31-12-2030","Ramesh Chandi","Father","9876500000","123 MG Road Ahmedabad"]
    )

    # ── Sheet 4: Bank ──
    ws4 = wb.create_sheet("4 - Bank Details")
    build_tpl(ws4, "065F46",
        ["Code","Full Name","Account Holder","Bank Name","Account Number","IFSC Code","Branch","Account Type"],
        ["Match Sheet1 Code","For reference","As per bank record","Bank name","Account number","11 char IFSC","Branch name","Savings/Current"],
        ["EMP0001","Krunal Chandi","Krunal N Chandi","HDFC Bank","50100123456789","HDFC0001234","Ahmedabad Main","Savings"]
    )

    # ── Sheet 5: Salary ──
    ws5 = wb.create_sheet("5 - Salary")
    build_tpl(ws5, "B45309",
        ["Code","Full Name","CTC Annual","Basic","HRA","DA","TA","Medical","Special","PF Emp","PF Er","ESIC Emp","ESIC Er","Prof Tax","TDS","Net Salary","Mode","Effective Date"],
        ["Match Sheet1 Code","For reference","Annual CTC in ₹","Monthly basic","Monthly HRA","Monthly DA","Transport","Medical allow","Special allow","PF deduction","PF employer","ESIC employee","ESIC employer","Prof. tax","TDS monthly","Net take-home","Cash/Bank Transfer/Cheque","DD-MM-YYYY"],
        ["EMP0001","Krunal Chandi","480000","16000","8000","1600","1600","1250","0","1920","1920","0","0","200","0","15280","Bank Transfer","01-01-2022"]
    )

    # ── Sheet 6: Education ──
    ws6 = wb.create_sheet("6 - Education")
    build_tpl(ws6, "0F766E",
        ["Code","Full Name","Qualification","University / Board","Year","Specialization","Prev Company","Prev Designation","Prev From","Prev To","Leaving Reason","Experience (Yrs)"],
        ["Match Sheet1 Code","For reference","12th/Diploma/BCA/MBA..","University name","Passing year","Branch/Subject","Previous employer","Designation there","DD-MM-YYYY","DD-MM-YYYY","Reason","Total yrs"],
        ["EMP0001","Krunal Chandi","MBA","Gujarat University","2015","Marketing","ABC Pvt Ltd","Sales Executive","01-06-2015","31-12-2021","Better opportunity","6.5"]
    )

    # ── Instructions sheet ──
    wsi = wb.create_sheet("📋 Instructions", 0)
    wsi.column_dimensions['A'].width = 8
    wsi.column_dimensions['B'].width = 55
    wsi.column_dimensions['C'].width = 45
    instructions = [
        ("","📋 EMPLOYEE IMPORT TEMPLATE — Instructions",""),
        ("","",""),
        ("","HOW TO USE THIS FILE:",""),
        ("1️⃣","Sheet 1 - Basic Info is REQUIRED. Fill employee code, name, mobile etc.","Employee Code must be unique"),
        ("2️⃣","Sheets 2-6 are OPTIONAL. Fill only what you have.","Match Employee Code exactly in each sheet"),
        ("3️⃣","Delete the Notes row (Row 2) from each sheet before importing.","Or keep it — system will skip non-data rows"),
        ("4️⃣","Date format: DD-MM-YYYY (e.g. 15-06-2024)",""),
        ("5️⃣","Salary fields: Numbers only, no ₹ symbol needed","e.g. 500000 not ₹5,00,000"),
        ("6️⃣","Yes/No fields: type Yes or No exactly",""),
        ("7️⃣","Upload this file at: HR > Employees > Import",""),
        ("","",""),
        ("","SHEETS IN THIS FILE:",""),
        ("📗","1 - Basic Info","Name, Contact, Address, DOB, Gender"),
        ("📘","2 - Professional","Dept, Designation, DOJ, Shift, Status"),
        ("📙","3 - KYC","Aadhaar, PAN, Passport, Emergency Contact"),
        ("📕","4 - Bank Details","Bank Account, IFSC, Branch"),
        ("📒","5 - Salary","CTC, Basic, HRA, PF, ESIC, Net Pay"),
        ("📓","6 - Education","Qualification, Previous Company"),
    ]
    for ri, (a, b, c_) in enumerate(instructions, 1):
        wsi.row_dimensions[ri].height = 20
        ca = wsi.cell(ri, 1, a)
        cb = wsi.cell(ri, 2, b)
        cc = wsi.cell(ri, 3, c_)
        if ri == 1:
            cb.font = Font(bold=True, size=14, color="1E3A5F", name="Arial")
        elif b.startswith(("HOW","SHEETS")):
            cb.font = Font(bold=True, size=10, color="1D4ED8", name="Arial")
        else:
            ca.font = Font(size=10, name="Arial")
            cb.font = Font(size=9, name="Arial")
            cc.font = Font(size=9, color="64748B", italic=True, name="Arial")

    from flask import send_file
    import io as _io
    buf = _io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name='employee_import_template.xlsx')


@hr.route('/employees/<int:id>/export')
@login_required
def emp_export_single(id):
    """Export single employee as 7-tab Excel workbook."""
    import io, sys, subprocess, json
    try:
        import openpyxl
    except ImportError:
        subprocess.run([sys.executable,'-m','pip','install','openpyxl','--quiet'],check=True)
        import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from datetime import datetime as dt2

    e = Employee.query.get_or_404(id)

    wb = openpyxl.Workbook()

    # ── Style helpers ──
    def hdr_style(cell, color="1E3A5F"):
        cell.font = Font(bold=True, color="FFFFFF", size=10, name="Arial")
        cell.fill = PatternFill("solid", fgColor=color)
        cell.alignment = Alignment(horizontal="center", vertical="center")
        thin = Side(style="thin", color="D0D7E2")
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def data_style(cell, bold=False):
        thin = Side(style="thin", color="E2E8F0")
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
        cell.font = Font(size=9, name="Arial", bold=bold)
        cell.alignment = Alignment(vertical="center", wrap_text=True)

    def alt_style(cell, row_idx):
        if row_idx % 2 == 0:
            cell.fill = PatternFill("solid", fgColor="F8FAFC")

    def write_sheet(ws, title_color, pairs):
        """Write label-value pairs to sheet."""
        ws.column_dimensions['A'].width = 28
        ws.column_dimensions['B'].width = 42
        # Header row
        ws.row_dimensions[1].height = 26
        h1 = ws.cell(1, 1, "Field"); h2 = ws.cell(1, 2, "Value")
        hdr_style(h1, title_color); hdr_style(h2, title_color)
        for i, (lbl, val) in enumerate(pairs, 2):
            ws.row_dimensions[i].height = 18
            c1 = ws.cell(i, 1, lbl)
            c2 = ws.cell(i, 2, val if val is not None else "—")
            data_style(c1, bold=True); data_style(c2)
            alt_style(c1, i); alt_style(c2, i)
        ws.freeze_panes = "A2"

    def fmt_date(d):
        return d.strftime('%d-%m-%Y') if d else None

    def fmt_cur(v):
        return f"₹{v:,.0f}" if v else None

    # ── Sheet 1: Basic Info ──
    ws1 = wb.active; ws1.title = "1 - Basic Info"
    write_sheet(ws1, "1E3A5F", [
        ("Employee Code", e.employee_code),
        ("First Name", e.first_name),
        ("Last Name", e.last_name),
        ("Full Name", e.full_name),
        ("Mobile", e.mobile),
        ("Email", e.email),
        ("Gender", e.gender),
        ("Date of Birth", fmt_date(e.date_of_birth)),
        ("Blood Group", e.blood_group),
        ("Marital Status", e.marital_status),
        ("Marriage Anniversary", fmt_date(e.marriage_anniversary)),
        ("Address", e.address),
        ("City", e.city),
        ("State", e.state),
        ("Country", e.country),
        ("ZIP / Pin Code", e.zip_code),
        ("LinkedIn", e.linkedin),
        ("Facebook", e.facebook),
    ])

    # ── Sheet 2: Professional ──
    ws2 = wb.create_sheet("2 - Professional")
    write_sheet(ws2, "1D4ED8", [
        ("Department", e.department),
        ("Designation", e.designation),
        ("Employee Type", e.employee_type),
        ("Location", e.location),
        ("Pay Grade", e.pay_grade),
        ("Date of Joining", fmt_date(e.date_of_joining)),
        ("Confirmation Date", fmt_date(e.confirmation_date)),
        ("Shift", e.shift),
        ("Work Hours Per Day", str(e.work_hours_per_day) if e.work_hours_per_day else None),
        ("Weekly Off", e.weekly_off),
        ("Notice Period (Days)", str(e.notice_period_days) if e.notice_period_days else None),
        ("Is Contractor", "Yes" if e.is_contractor else "No"),
        ("Status", (e.status or "").title()),
        ("Is Probation", "Yes" if e.is_probation else "No"),
        ("Is Block", "Yes" if e.is_block else "No"),
        ("Is Late", "Yes" if e.is_late else "No"),
        ("Rehire Eligible", "Yes" if e.rehire_eligible else "No"),
        ("Resignation Date", fmt_date(e.resignation_date)),
        ("Last Working Date", fmt_date(e.last_working_date)),
        ("Remark", e.remark),
        ("Reports To", e.manager_emp.full_name if e.manager_emp else None),
    ])

    # ── Sheet 3: KYC ──
    ws3 = wb.create_sheet("3 - Personal & KYC")
    write_sheet(ws3, "7C3AED", [
        ("Nationality", e.nationality),
        ("Religion", e.religion),
        ("Caste", e.caste),
        ("Physically Handicapped", "Yes" if e.physically_handicapped else "No"),
        ("Aadhaar Number", e.aadhar_number),
        ("PAN Number", e.pan_number),
        ("UAN Number", e.uan_number),
        ("ESIC Number", e.esic_number),
        ("Passport Number", e.passport_number),
        ("Passport Expiry", fmt_date(e.passport_expiry)),
        ("Driving License", e.driving_license),
        ("DL Expiry", fmt_date(e.dl_expiry)),
        ("Emergency Name", e.emergency_name),
        ("Emergency Relation", e.emergency_relation),
        ("Emergency Phone", e.emergency_phone),
        ("Emergency Address", e.emergency_address),
    ])

    # ── Sheet 4: Bank ──
    ws4 = wb.create_sheet("4 - Bank Details")
    write_sheet(ws4, "065F46", [
        ("Account Holder", e.bank_account_holder),
        ("Bank Name", e.bank_name),
        ("Account Number", e.bank_account_number),
        ("IFSC Code", e.bank_ifsc),
        ("Branch", e.bank_branch),
        ("Account Type", e.bank_account_type),
    ])

    # ── Sheet 5: Salary ──
    ws5 = wb.create_sheet("5 - Salary")
    write_sheet(ws5, "B45309", [
        ("CTC (Annual)", fmt_cur(e.salary_ctc)),
        ("Basic Salary", fmt_cur(e.salary_basic)),
        ("HRA", fmt_cur(e.salary_hra)),
        ("DA (Dearness Allow.)", fmt_cur(e.salary_da)),
        ("Transport Allow.", fmt_cur(e.salary_ta)),
        ("Medical Allow.", fmt_cur(e.salary_medical_allow)),
        ("Special Allow.", fmt_cur(e.salary_special_allow)),
        ("PF Employee (12%)", fmt_cur(e.salary_pf_employee)),
        ("PF Employer (12%)", fmt_cur(e.salary_pf_employer)),
        ("ESIC Employee (0.75%)", fmt_cur(e.salary_esic_employee)),
        ("ESIC Employer (3.25%)", fmt_cur(e.salary_esic_employer)),
        ("Professional Tax", fmt_cur(e.salary_professional_tax)),
        ("TDS", fmt_cur(e.salary_tds)),
        ("Net Salary", fmt_cur(e.salary_net)),
        ("Salary Mode", e.salary_mode),
        ("Effective Date", fmt_date(e.salary_effective_date)),
    ])

    # ── Sheet 6: Education ──
    ws6 = wb.create_sheet("6 - Education")
    write_sheet(ws6, "0F766E", [
        ("Highest Qualification", e.highest_qualification),
        ("University / Board", e.university),
        ("Passing Year", str(e.passing_year) if e.passing_year else None),
        ("Specialization", e.specialization),
        ("Previous Company", e.prev_company),
        ("Previous Designation", e.prev_designation),
        ("Prev From Date", fmt_date(e.prev_from_date)),
        ("Prev To Date", fmt_date(e.prev_to_date)),
        ("Leaving Reason", e.prev_leaving_reason),
        ("Total Experience (Yrs)", str(e.total_experience_yrs) if e.total_experience_yrs else None),
    ])

    # ── Sheet 7: Documents ──
    ws7 = wb.create_sheet("7 - Documents")
    ws7.column_dimensions['A'].width = 5
    ws7.column_dimensions['B'].width = 28
    ws7.column_dimensions['C'].width = 22
    ws7.column_dimensions['D'].width = 22
    ws7.column_dimensions['E'].width = 14
    ws7.column_dimensions['F'].width = 18
    ws7.row_dimensions[1].height = 26

    doc_headers = ["#", "Document Name", "Type", "Filename", "Size (KB)", "Uploaded At"]
    for ci, h in enumerate(doc_headers, 1):
        cell = ws7.cell(1, ci, h)
        hdr_style(cell, "BE185D")

    docs = []
    try:
        if e.documents_json and e.documents_json != '[]':
            docs = json.loads(e.documents_json)
    except Exception:
        pass

    if docs:
        for i, doc in enumerate(docs, 2):
            ws7.row_dimensions[i].height = 18
            vals = [
                i - 1,
                doc.get('name', ''),
                doc.get('type', ''),
                doc.get('filename', ''),
                round(doc.get('size', 0) / 1024, 1),
                (doc.get('uploaded_at', '') or '')[:10],
            ]
            for ci, val in enumerate(vals, 1):
                cell = ws7.cell(i, ci, val)
                data_style(cell)
                alt_style(cell, i)
    else:
        ws7.cell(2, 1, "No documents uploaded").font = Font(italic=True, color="94A3B8", name="Arial")

    ws7.freeze_panes = "A2"

    buf = io.BytesIO(); wb.save(buf); buf.seek(0)
    from flask import send_file
    fname = f"employee_{e.employee_code or e.id}_{dt2.now().strftime('%Y%m%d')}.xlsx"
    return send_file(buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True, download_name=fname)

@hr.route('/employees/export')
@login_required
def emp_export():
    import io, sys, subprocess
    try:
        import openpyxl
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'openpyxl', '--quiet'], check=True)
        import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    search  = request.args.get('search', '')
    dept    = request.args.get('dept', '')
    status  = request.args.get('status', '')
    emptype = request.args.get('emptype', '')
    sort_by = request.args.get('sort_by', 'created_at')
    sort_dir= request.args.get('sort_dir', 'desc')

    q = Employee.query
    if search:
        s = f'%{search}%'
        q = q.filter(Employee.first_name.ilike(s)|Employee.last_name.ilike(s)|
                     Employee.employee_code.ilike(s)|Employee.mobile.ilike(s)|Employee.email.ilike(s))
    if dept:    q = q.filter_by(department=dept)
    if status:  q = q.filter_by(status=status)
    if emptype: q = q.filter_by(employee_type=emptype)
    sort_col = getattr(Employee, sort_by, Employee.created_at)
    emps = q.order_by(sort_col.asc() if sort_dir=='asc' else sort_col.desc()).all()

    from models.user import User as UserModel
    users = {u.id: u.full_name for u in UserModel.query.all()}

    headers = ["Employee Code","First Name","Last Name","Full Name","Mobile","Email","Gender",
               "Department","Designation","Employee Type","Date of Joining","Location",
               "Date of Birth","Blood Group","Marital Status","Status",
               "Is Contractor","Is Block","Is Late","Is Probation",
               "LinkedIn","Facebook","Remark","Created At","Updated At"]

    rows = []
    for e in emps:
        full = (e.first_name or '') + ' ' + (e.last_name or '')
        rows.append([
            e.employee_code or '', e.first_name or '', e.last_name or '', full.strip(),
            e.mobile or '', e.email or '', e.gender or '',
            e.department or '', e.designation or '', e.employee_type or '',
            e.date_of_joining.strftime('%d-%m-%Y') if e.date_of_joining else '',
            e.location or '',
            e.date_of_birth.strftime('%d-%m-%Y') if e.date_of_birth else '',
            e.blood_group or '', e.marital_status or '',
            (e.status or '').title(),
            'Yes' if e.is_contractor else 'No',
            'Yes' if e.is_block else 'No',
            'Yes' if e.is_late else 'No',
            'Yes' if e.is_probation else 'No',
            e.linkedin or '', e.facebook or '', e.remark or '',
            e.created_at.strftime('%d-%m-%Y %H:%M') if e.created_at else '',
            e.updated_at.strftime('%d-%m-%Y %H:%M') if e.updated_at else '',
        ])


    # ─── 7 Tab-Wise Sheets ───
    wb = openpyxl.Workbook()

    def mk_hdr(cell, color="1E3A5F"):
        cell.font = Font(bold=True, color="FFFFFF", size=10, name="Arial")
        cell.fill = PatternFill("solid", fgColor=color)
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        thin = Side(style="thin", color="D0D7E2")
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def mk_data(cell, ri):
        thin = Side(style="thin", color="E2E8F0")
        cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)
        cell.font = Font(size=9, name="Arial")
        cell.alignment = Alignment(vertical="center")
        if ri % 2 == 0:
            cell.fill = PatternFill("solid", fgColor="F8FAFC")

    def build_sheet(ws, color, headers, rows_data):
        ws.row_dimensions[1].height = 28
        for ci, h in enumerate(headers, 1):
            mk_hdr(ws.cell(1, ci, h), color)
        for ri, row in enumerate(rows_data, 2):
            ws.row_dimensions[ri].height = 17
            for ci, val in enumerate(row, 1):
                mk_data(ws.cell(ri, ci, val), ri)
        for ci in range(1, len(headers)+1):
            col = get_column_letter(ci)
            mx = max((len(str(ws.cell(r, ci).value or '')) for r in range(1, ws.max_row+1)), default=8)
            ws.column_dimensions[col].width = min(mx + 2, 40)
        ws.freeze_panes = "A2"

    def fd(d): return d.strftime('%d-%m-%Y') if d else ''

    # Sheet 1: Basic Info
    ws1 = wb.active; ws1.title = "1 - Basic Info"
    h1 = ["Code","First Name","Last Name","Full Name","Mobile","Email","Gender","DOB","Blood Group","Marital Status","Address","City","State","Country","ZIP","LinkedIn","Facebook","Status","Created At"]
    r1 = []
    for e in emps:
        r1.append([e.employee_code or '',e.first_name or '',e.last_name or '',e.full_name,
            e.mobile or '',e.email or '',e.gender or '',fd(e.date_of_birth),e.blood_group or '',
            e.marital_status or '',e.address or '',e.city or '',e.state or '',e.country or '',e.zip_code or '',
            e.linkedin or '',e.facebook or'',(e.status or '').title(),
            e.created_at.strftime('%d-%m-%Y') if e.created_at else ''])
    build_sheet(ws1,"1E3A5F",h1,r1)

    # Sheet 2: Professional
    ws2 = wb.create_sheet("2 - Professional")
    h2 = ["Code","Full Name","Department","Designation","Employee Type","Location","Pay Grade","DOJ","Confirmation","Shift","Work Hrs","Weekly Off","Notice Days","Contractor","Probation","Block","Status","Reports To"]
    r2 = []
    for e in emps:
        r2.append([e.employee_code or '',e.full_name,e.department or '',e.designation or '',
            e.employee_type or '',e.location or '',e.pay_grade or '',fd(e.date_of_joining),
            fd(e.confirmation_date),e.shift or '',str(e.work_hours_per_day or ''),e.weekly_off or '',
            str(e.notice_period_days or ''),'Yes' if e.is_contractor else 'No',
            'Yes' if e.is_probation else 'No','Yes' if e.is_block else 'No',
            (e.status or '').title(),e.manager_emp.full_name if e.manager_emp else ''])
    build_sheet(ws2,"1D4ED8",h2,r2)

    # Sheet 3: KYC
    ws3 = wb.create_sheet("3 - KYC")
    h3 = ["Code","Full Name","Nationality","Religion","Aadhaar","PAN","UAN","ESIC","Passport No","Passport Expiry","DL No","DL Expiry","Emergency Name","Emergency Phone"]
    r3 = []
    for e in emps:
        r3.append([e.employee_code or '',e.full_name,e.nationality or '',e.religion or '',
            e.aadhar_number or '',e.pan_number or '',e.uan_number or '',e.esic_number or '',
            e.passport_number or '',fd(e.passport_expiry),e.driving_license or '',fd(e.dl_expiry),
            e.emergency_name or '',e.emergency_phone or ''])
    build_sheet(ws3,"7C3AED",h3,r3)

    # Sheet 4: Bank
    ws4 = wb.create_sheet("4 - Bank Details")
    h4 = ["Code","Full Name","Account Holder","Bank Name","Account Number","IFSC","Branch","Account Type"]
    r4 = []
    for e in emps:
        r4.append([e.employee_code or '',e.full_name,e.bank_account_holder or '',
            e.bank_name or '',e.bank_account_number or '',e.bank_ifsc or '',
            e.bank_branch or '',e.bank_account_type or ''])
    build_sheet(ws4,"065F46",h4,r4)

    # Sheet 5: Salary
    ws5 = wb.create_sheet("5 - Salary")
    h5 = ["Code","Full Name","CTC Annual","Basic","HRA","DA","TA","Medical","Special","PF Emp","PF Er","ESIC Emp","ESIC Er","Prof Tax","TDS","Net Salary","Mode"]
    r5 = []
    def fc(v): return round(float(v),2) if v else ''
    for e in emps:
        r5.append([e.employee_code or '',e.full_name,fc(e.salary_ctc),fc(e.salary_basic),
            fc(e.salary_hra),fc(e.salary_da),fc(e.salary_ta),fc(e.salary_medical_allow),
            fc(e.salary_special_allow),fc(e.salary_pf_employee),fc(e.salary_pf_employer),
            fc(e.salary_esic_employee),fc(e.salary_esic_employer),fc(e.salary_professional_tax),
            fc(e.salary_tds),fc(e.salary_net),e.salary_mode or ''])
    build_sheet(ws5,"B45309",h5,r5)

    # Sheet 6: Education
    ws6 = wb.create_sheet("6 - Education")
    h6 = ["Code","Full Name","Qualification","University","Year","Specialization","Prev Company","Prev Designation","Prev From","Prev To","Experience (Yrs)"]
    r6 = []
    for e in emps:
        r6.append([e.employee_code or '',e.full_name,e.highest_qualification or '',
            e.university or '',str(e.passing_year or ''),e.specialization or '',
            e.prev_company or '',e.prev_designation or '',fd(e.prev_from_date),
            fd(e.prev_to_date),str(e.total_experience_yrs or '')])
    build_sheet(ws6,"0F766E",h6,r6)

    # Sheet 7: Documents summary
    ws7 = wb.create_sheet("7 - Documents")
    h7 = ["Code","Full Name","Doc Name","Doc Type","Filename","Size (KB)","Uploaded At"]
    r7 = []
    import json as _json2
    for e in emps:
        try:
            docs = _json2.loads(e.documents_json or '[]')
        except Exception:
            docs = []
        if docs:
            for doc in docs:
                r7.append([e.employee_code or '',e.full_name,
                    doc.get('name',''),doc.get('type',''),doc.get('filename',''),
                    round(doc.get('size',0)/1024,1),
                    (doc.get('uploaded_at','') or '')[:10]])
        else:
            r7.append([e.employee_code or '',e.full_name,'—','—','—','—','—'])
    build_sheet(ws7,"BE185D",h7,r7)
    from flask import send_file
    from datetime import datetime as dt2
    import io as io2
    buf = io2.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f"employees_export_{dt2.now().strftime('%Y%m%d_%H%M')}.xlsx")

# ── Salary Config Routes ──────────────────────────────────────────────────────

@hr.route('/salary-config', methods=['GET'])
@login_required
def salary_config_get():
    """Return current salary config as JSON."""
    try:
        cfg = SalaryConfig.get_config()
        return jsonify(ok=True, config=cfg)
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


@hr.route('/salary-config', methods=['POST'])
@login_required
def salary_config_save():
    """Save salary config from JSON body."""
    try:
        data = request.get_json() or {}
        allowed_keys = {
            'basic_pct', 'hra_pct', 'da_pct', 'ta_fixed', 'med_fixed',
            'pf_emp_pct', 'pf_er_pct', 'esic_emp_pct', 'esic_er_pct',
            'esic_limit', 'pt_fixed'
        }
        clean = {k: v for k, v in data.items() if k in allowed_keys}
        if not clean:
            return jsonify(ok=False, error='No valid keys provided'), 400
        updated_by = current_user.full_name or current_user.username
        SalaryConfig.save_config(clean, updated_by=updated_by)
        return jsonify(ok=True, msg='Salary config saved successfully!')
    except Exception as e:
        return jsonify(ok=False, error=str(e)), 500


@hr.route('/salary-config/page')
@login_required
def salary_config_page():
    """Render salary config admin page."""
    cfg = SalaryConfig.get_config()
    last = SalaryConfig.query.order_by(SalaryConfig.updated_at.desc()).first()
    cfg['updated_by'] = last.updated_by if last else None
    cfg['updated_at'] = last.updated_at.strftime('%d %b %Y, %I:%M %p') if last and last.updated_at else None
    comps_raw = SalaryComponent.query.order_by(SalaryComponent.component_type, SalaryComponent.sort_order).all()
    components_dict = [c.to_dict() for c in comps_raw]
    return render_template('hr/salary_config.html', cfg=cfg, components=comps_raw, components_json=components_dict, active_page='salary_config')


# ── Salary Components CRUD ────────────────────────────────────────────────────

@hr.route('/salary-components', methods=['GET'])
@login_required
def salary_components_list():
    """Return all components as JSON (for employee form)."""
    comps = SalaryComponent.get_all_active()
    return jsonify(ok=True, components=[c.to_dict() for c in comps])


@hr.route('/salary-components/add', methods=['POST'])
@login_required
def salary_component_add():
    try:
        d = request.get_json() or {}
        # Validate required
        for f in ('name', 'code', 'component_type', 'calc_type'):
            if not d.get(f):
                return jsonify(ok=False, error=f'{f} required'), 400
        # Check duplicate code
        if SalaryComponent.query.filter_by(code=d['code'].strip().lower()).first():
            return jsonify(ok=False, error='Code already exists'), 400
        comp = SalaryComponent(
            name               = d['name'].strip(),
            code               = d['code'].strip().lower(),
            component_type     = d['component_type'],
            calc_type          = d['calc_type'],
            value              = float(d.get('value', 0)),
            cap_amount         = float(d['cap_amount']) if d.get('cap_amount') else None,
            apply_if_gross_lte = float(d['apply_if_gross_lte']) if d.get('apply_if_gross_lte') else None,
            sort_order         = int(d.get('sort_order', 0)),
            is_active          = bool(d.get('is_active', True)),
            description        = d.get('description', ''),
            updated_by         = current_user.full_name or current_user.username,
        )
        db.session.add(comp)
        audit('hr','SALARY_COMP_ADD', comp.id, comp.code, f'Salary component added by {current_user.username}: {comp.name} ({comp.code})')
        db.session.commit()
        return jsonify(ok=True, component=comp.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify(ok=False, error=str(e)), 500


@hr.route('/salary-components/<int:cid>', methods=['POST'])
@login_required
def salary_component_edit(cid):
    try:
        comp = SalaryComponent.query.get_or_404(cid)
        d = request.get_json() or {}
        comp.name               = d.get('name', comp.name).strip()
        comp.component_type     = d.get('component_type', comp.component_type)
        comp.calc_type          = d.get('calc_type', comp.calc_type)
        comp.value              = float(d['value']) if 'value' in d else comp.value
        comp.cap_amount         = float(d['cap_amount']) if d.get('cap_amount') else None
        comp.apply_if_gross_lte = float(d['apply_if_gross_lte']) if d.get('apply_if_gross_lte') else None
        comp.sort_order         = int(d.get('sort_order', comp.sort_order))
        comp.is_active          = bool(d.get('is_active', comp.is_active))
        comp.description        = d.get('description', comp.description)
        comp.updated_by         = current_user.full_name or current_user.username
        comp.updated_at         = datetime.utcnow()
        audit('hr','SALARY_COMP_EDIT', comp.id, comp.code, f'Salary component updated by {current_user.username}: {comp.name}')
        db.session.commit()
        return jsonify(ok=True, component=comp.to_dict())
    except Exception as e:
        db.session.rollback()
        return jsonify(ok=False, error=str(e)), 500


@hr.route('/salary-components/<int:cid>/delete', methods=['POST'])
@login_required
def salary_component_delete(cid):
    try:
        comp = SalaryComponent.query.get_or_404(cid)
        if comp.is_system:
            return jsonify(ok=False, error='System components cannot be deleted'), 400
        audit('hr','SALARY_COMP_DELETE', comp.id, comp.code, f'Salary component deleted by {current_user.username}: {comp.name}')
        db.session.delete(comp)
        db.session.commit()
        return jsonify(ok=True)
    except Exception as e:
        db.session.rollback()
        return jsonify(ok=False, error=str(e)), 500
