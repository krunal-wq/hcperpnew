"""
user_routes.py — User Management + Profile + Permission Admin
"""
import json
from flask import send_file, Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from audit_helper import audit, snapshot
from functools import wraps
from datetime import datetime
from models import db, User, LoginLog, Module, RolePermission, UserPermission
from permissions import seed_permissions, MODULE_SUB_PERMS

users_bp = Blueprint('users_bp', __name__, url_prefix='/admin')


def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Admin access required.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ══════════════════════════════════════
# USER CRUD
# ══════════════════════════════════════

@users_bp.route('/users')
@login_required
@admin_required
def users():
    from flask import send_file, request
    search   = request.args.get('search', '').strip()
    role_f   = request.args.get('role_f', '')
    status_f = request.args.get('status_f', '')
    sort_by  = request.args.get('sort_by', 'full_name')
    sort_dir = request.args.get('sort_dir', 'asc')

    q = User.query
    if search:
        s = f'%{search}%'
        q = q.filter(User.full_name.ilike(s) | User.email.ilike(s) | User.username.ilike(s))
    if role_f:
        q = q.filter_by(role=role_f)
    if status_f:
        q = q.filter_by(is_active=(status_f == 'active'))

    sort_col = getattr(User, sort_by, User.full_name)
    q = q.order_by(sort_col.asc() if sort_dir == 'asc' else sort_col.desc())
    all_users = q.all()

    return render_template('admin/users/index.html',
        users=all_users, active_page='user_mgmt',
        search=search, role_f=role_f, status_f=status_f,
        sort_by=sort_by, sort_dir=sort_dir)


@users_bp.route('/users/add', methods=['GET', 'POST'])
@login_required
@admin_required
def user_add():
    if request.method == 'POST':
        username  = request.form.get('username','').strip().lower()
        email     = request.form.get('email','').strip().lower()
        full_name = request.form.get('full_name','').strip()
        role      = request.form.get('role','user')
        password  = request.form.get('password','').strip() or 'HCP@123'
        is_active = 'is_active' in request.form

        if not username or not email:
            flash('Username and email required.','error')
            return redirect(url_for('users_bp.user_add'))
        if User.query.filter_by(username=username).first():
            flash(f'Username "{username}" exists.','error')
            return redirect(url_for('users_bp.user_add'))
        if User.query.filter_by(email=email).first():
            flash(f'Email "{email}" exists.','error')
            return redirect(url_for('users_bp.user_add'))

        u = User(username=username, email=email, full_name=full_name,
                 role=role, is_active=is_active)
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        audit('users','INSERT', u.id, username, f'User created by {current_user.username}: {username} | Role: {u.role} | Email: {u.email}')
        flash(f'User "{full_name or username}" created! Default password: {password}','success')
        return redirect(url_for('users_bp.users'))

    return render_template('admin/users/form.html', user=None, active_page='user_mgmt')


@users_bp.route('/users/<int:id>/edit', methods=['GET', 'POST'])
@login_required
@admin_required
def user_edit(id):
    u = User.query.get_or_404(id)
    if request.method == 'POST':
        u.full_name = request.form.get('full_name','').strip()
        u.email     = request.form.get('email','').strip().lower()
        u.role      = request.form.get('role','user')
        u.is_active = 'is_active' in request.form
        new_pw = request.form.get('password','').strip()
        if new_pw: u.set_password(new_pw)
        db.session.commit()
        audit('users','UPDATE', u.id, u.username, f'User updated by {current_user.username}: {u.username} | Role: {u.role}')
        flash('User updated!','success')
        return redirect(url_for('users_bp.users'))
    return render_template('admin/users/form.html', user=u, active_page='user_mgmt')


@users_bp.route('/users/<int:id>/delete', methods=['POST'])
@login_required
@admin_required
def user_delete(id):
    u = User.query.get_or_404(id)
    if u.id == current_user.id:
        flash("Can't delete yourself.",'error')
        return redirect(url_for('users_bp.users'))
    db.session.delete(u)
    db.session.commit()
    audit('users','DELETE', id, '', f'User deleted by {current_user.username}')
    flash(f'User deleted.','success')
    return redirect(url_for('users_bp.users'))


@users_bp.route('/users/<int:id>/toggle', methods=['POST'])
@login_required
@admin_required
def user_toggle(id):
    u = User.query.get_or_404(id)
    if u.id == current_user.id:
        return jsonify(success=False, error="Can't deactivate yourself")
    u.is_active = not u.is_active
    action_lbl = 'ENABLE' if u.is_active else 'DISABLE'
    audit('users', action_lbl, id, f'{u.username}', f'User {action_lbl.lower()}d by {current_user.username}')
    db.session.commit()
    return jsonify(success=True, is_active=u.is_active)


# ══════════════════════════════════════
# PERMISSION MATRIX
# ══════════════════════════════════════

@users_bp.route('/permissions')
@login_required
@admin_required
def permissions():
    modules = Module.query.filter_by(is_active=True).order_by(Module.sort_order).all()
    roles   = ['admin','manager','hr','user']
    # Build matrix: role → module_id → RolePermission
    matrix  = {}
    for role in roles:
        matrix[role] = {}
        perms = RolePermission.query.filter_by(role=role).all()
        for p in perms:
            matrix[role][p.module_id] = p
    return render_template('admin/permissions/index.html',
        modules=modules, roles=roles, matrix=matrix, active_page='permissions')


@users_bp.route('/permissions/save', methods=['POST'])
@login_required
@admin_required
def perm_save():
    data = request.json  # {role, module_id, action, value}
    role      = data.get('role')
    module_id = data.get('module_id')
    action    = data.get('action')
    value     = data.get('value', False)

    if action not in ('can_view','can_add','can_edit','can_delete','can_export'):
        return jsonify(success=False, error='Invalid action')

    p = RolePermission.query.filter_by(role=role, module_id=module_id).first()
    if not p:
        p = RolePermission(role=role, module_id=module_id)
        db.session.add(p)

    setattr(p, action, bool(value))
    # If disabling view, disable all others too
    if action == 'can_view' and not value:
        p.can_add = p.can_edit = p.can_delete = p.can_export = False
    audit('users','PERMISSION_CHANGE', p.id, role, f'Permission updated by {current_user.username}: role={role} module={module_id} {action}={value}')
    db.session.commit()
    return jsonify(success=True)


@users_bp.route('/permissions/seed', methods=['POST'])
@login_required
@admin_required
def perm_seed():
    seed_permissions()
    flash('Default permissions seeded!', 'success')
    return redirect(url_for('users_bp.permissions'))


# ══════════════════════════════════════
# PROFILE (any logged-in user)
# ══════════════════════════════════════

@users_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    from models.employee import Employee
    from datetime import date as date_type
    # Find linked employee
    emp = Employee.query.filter_by(user_id=current_user.id).first()

    if request.method == 'POST':
        action = request.form.get('action', 'profile')
        if action == 'password':
            old_pw = request.form.get('old_password', '')
            new_pw = request.form.get('new_password', '')
            conf   = request.form.get('confirm_password', '')
            if not current_user.check_password(old_pw):
                flash('Current password is incorrect.', 'error')
            elif len(new_pw) < 6:
                flash('New password must be at least 6 characters.', 'error')
            elif new_pw != conf:
                flash('Passwords do not match.', 'error')
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                audit('users','PASSWORD_CHANGE', current_user.id, current_user.username, f'Password changed by {current_user.username}')
                flash('Password changed successfully!', 'success')
        else:
            # Update user basic info
            current_user.full_name = request.form.get('full_name', '').strip()
            current_user.email     = request.form.get('email', '').strip()

            # Update employee fields if linked
            if emp:
                def _pd(v):
                    try: return date_type.fromisoformat(v) if v else None
                    except: return None

                photo = request.form.get('photo_base64', '').strip()
                if photo: emp.profile_photo = photo

                emp.first_name     = request.form.get('first_name', '').strip() or emp.first_name
                emp.last_name      = request.form.get('last_name', '').strip() or emp.last_name
                emp.mobile         = request.form.get('mobile', '').strip()
                emp.email          = current_user.email
                emp.gender         = request.form.get('gender', '')
                emp.linkedin       = request.form.get('linkedin', '').strip()
                emp.facebook       = request.form.get('facebook', '').strip()
                emp.date_of_birth  = _pd(request.form.get('date_of_birth'))
                emp.blood_group    = request.form.get('blood_group', '').strip()
                emp.marital_status = request.form.get('marital_status', '')
                emp.address        = request.form.get('address', '').strip()
                emp.city           = request.form.get('city', '').strip()
                emp.state          = request.form.get('state', '').strip()
                emp.country        = request.form.get('country', '').strip()
                emp.zip_code       = request.form.get('zip_code', '').strip()
                emp.remark         = request.form.get('remark', '').strip()

            db.session.commit()
            audit('users','PROFILE_UPDATE', current_user.id, current_user.username, f'Profile updated by {current_user.username}')
            flash('Profile updated successfully!', 'success')
        return redirect(url_for('users_bp.profile'))

    logs = LoginLog.query.filter_by(user_id=current_user.id)\
               .order_by(LoginLog.timestamp.desc()).limit(10).all()
    return render_template('admin/profile.html', employee=emp, logs=logs, active_page='profile')


# ══════════════════════════════════════
# AUDIT LOG ROUTES
# ══════════════════════════════════════

@users_bp.route('/audit-logs')
@login_required
def audit_logs():
    from models import AuditLog, User
    from datetime import datetime, timedelta
    from sqlalchemy import func

    # Filters
    module    = request.args.get('module', '')
    action    = request.args.get('action', '')
    user_id   = request.args.get('user_id', '')
    date_from = request.args.get('date_from', '')
    date_to   = request.args.get('date_to', '')
    search    = request.args.get('search', '')
    page      = int(request.args.get('page', 1))
    per_page  = int(request.args.get('per_page', 50))

    q = AuditLog.query
    if module:    q = q.filter(AuditLog.module == module)
    if action:    q = q.filter(AuditLog.action == action)
    if user_id:   q = q.filter(AuditLog.user_id == int(user_id))
    if date_from: q = q.filter(AuditLog.created_at >= datetime.strptime(date_from,'%Y-%m-%d'))
    if date_to:   q = q.filter(AuditLog.created_at <= datetime.strptime(date_to+' 23:59:59','%Y-%m-%d %H:%M:%S'))
    if search:    q = q.filter(
        AuditLog.record_label.ilike(f'%{search}%') |
        AuditLog.detail.ilike(f'%{search}%') |
        AuditLog.username.ilike(f'%{search}%')
    )

    total  = q.count()
    logs   = q.order_by(AuditLog.created_at.desc()).offset((page-1)*per_page).limit(per_page).all()
    total_pages = max(1, (total + per_page - 1) // per_page)

    # Distinct filter options
    modules = [r[0] for r in db.session.query(AuditLog.module).distinct().all() if r[0]]
    actions = [r[0] for r in db.session.query(AuditLog.action).distinct().all() if r[0]]
    all_users = User.query.filter_by(is_active=True).order_by(User.full_name).all()

    # Stats — last 30 days action counts
    since = datetime.now() - timedelta(days=30)
    stats = db.session.query(AuditLog.action, func.count(AuditLog.id).label('cnt'))\
                      .filter(AuditLog.created_at >= since)\
                      .group_by(AuditLog.action)\
                      .order_by(func.count(AuditLog.id).desc()).all()

    return render_template('admin/audit/index.html',
        logs=logs, total=total, page=page, per_page=per_page, total_pages=total_pages,
        module=module, action=action, user_id=user_id,
        date_from=date_from, date_to=date_to, search=search,
        modules=modules, actions=actions, all_users=all_users,
        stats=[{'action': s.action, 'cnt': s.cnt} for s in stats],
        active_page='audit_logs'
    )


@users_bp.route('/audit-logs/export')
@login_required
def audit_export():
    from models import AuditLog
    import csv
    from io import StringIO
    from flask import send_file, Response

    logs = AuditLog.query.order_by(AuditLog.created_at.desc()).limit(5000).all()
    si   = StringIO()
    w    = csv.writer(si)
    w.writerow(['ID','Datetime','Username','Role','Module','Action','Record ID','Record Label','Detail','IP'])
    for l in logs:
        w.writerow([l.id, l.created_at.strftime('%d-%m-%Y %H:%M:%S'),
                    l.username, l.user_role, l.module, l.action,
                    l.record_id or '', l.record_label or '', l.detail or '', l.ip_address or ''])
    output = si.getvalue()
    return Response(output, mimetype='text/csv',
                    headers={'Content-Disposition': 'attachment;filename=audit_logs.csv'})


@users_bp.route('/users/export')
@login_required
@admin_required
def users_export():
    import io, sys, subprocess
    try:
        import openpyxl
    except ImportError:
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'openpyxl', '--quiet'], check=True)
        import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    from datetime import datetime as dt

    search   = request.args.get('search', '')
    role_f   = request.args.get('role_f', '')
    status_f = request.args.get('status_f', '')
    sort_by  = request.args.get('sort_by', 'full_name')
    sort_dir = request.args.get('sort_dir', 'asc')

    q = User.query
    if search:
        s = f'%{search}%'
        q = q.filter(User.full_name.ilike(s)|User.email.ilike(s)|User.username.ilike(s))
    if role_f:   q = q.filter_by(role=role_f)
    if status_f: q = q.filter_by(is_active=(status_f=='active'))
    sort_col = getattr(User, sort_by, User.full_name)
    users_data = q.order_by(sort_col.asc() if sort_dir=='asc' else sort_col.desc()).all()

    headers = ["#","Full Name","Username","Email","Role","Status",
               "Last Login","Login Attempts","Created At"]
    rows = []
    for i, u in enumerate(users_data, 1):
        rows.append([
            i, u.full_name or '', u.username or '', u.email or '',
            (u.role or '').title(),
            'Active' if u.is_active else 'Inactive',
            u.last_login.strftime('%d-%m-%Y %H:%M') if u.last_login else '',
            u.login_attempts or 0,
            u.created_at.strftime('%d-%m-%Y %H:%M') if u.created_at else '',
        ])

    wb = openpyxl.Workbook()
    ws = wb.active; ws.title = "Users"
    hdr_fill=PatternFill("solid",fgColor="1E3A5F"); hdr_font=Font(bold=True,color="FFFFFF",size=10)
    hdr_align=Alignment(horizontal="center",vertical="center")
    thin=Side(style="thin",color="D0D7E2"); bdr=Border(left=thin,right=thin,top=thin,bottom=thin)
    alt_fill=PatternFill("solid",fgColor="F0F4FA"); d_font=Font(size=9); d_align=Alignment(vertical="center")
    ws.row_dimensions[1].height=28
    for ci,h in enumerate(headers,1):
        cell=ws.cell(1,ci,h); cell.font=hdr_font; cell.fill=hdr_fill
        cell.alignment=hdr_align; cell.border=bdr
    for ri,row in enumerate(rows,2):
        ws.row_dimensions[ri].height=17; fill=alt_fill if ri%2==0 else None
        for ci,val in enumerate(row,1):
            cell=ws.cell(ri,ci,val); cell.font=d_font; cell.alignment=d_align; cell.border=bdr
            if fill: cell.fill=fill
    for ci in range(1,len(headers)+1):
        col=get_column_letter(ci)
        mx=max((len(str(ws.cell(r,ci).value or '')) for r in range(1,ws.max_row+1)),default=8)
        ws.column_dimensions[col].width=min(mx+2,40)
    ws.freeze_panes="A2"

    buf=io.BytesIO(); wb.save(buf); buf.seek(0)
    return send_file(buf,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f"users_export_{dt.now().strftime('%Y%m%d_%H%M')}.xlsx")


# ═══════════════════════════════════════════════════════════════════
# USER-WISE PERMISSIONS
# ═══════════════════════════════════════════════════════════════════

@users_bp.route('/user-permissions')
@login_required
@admin_required
def user_permissions_list():
    """Redirect to ACP panel."""
    return redirect(url_for('users_bp.acp_panel'))


@users_bp.route('/acp')
@users_bp.route('/acp/<int:user_id>')
@login_required
@admin_required
def acp_panel(user_id=None):
    """Access Control Panel — split panel design."""
    all_users = User.query.filter_by(is_active=True).order_by(User.full_name).all()
    modules   = Module.query.filter_by(is_active=True).order_by(Module.sort_order).all()

    selected_user = None
    perm_map = {}
    role_perm_map = {}
    sub_perm_map = {}

    if user_id:
        selected_user = User.query.get_or_404(user_id)
        for up in UserPermission.query.filter_by(user_id=user_id).all():
            perm_map[up.module_id] = up
        sub_perm_map = {mid: up.get_sub_permissions() for mid, up in perm_map.items()}
        for rp in RolePermission.query.filter_by(role=selected_user.role).all():
            role_perm_map[rp.module_id] = rp

    return render_template('admin/permissions/acp_panel.html',
                           all_users=all_users,
                           selected_user=selected_user,
                           modules=modules,
                           perm_map=perm_map,
                           sub_perm_map=sub_perm_map,
                           role_perm_map=role_perm_map,
                           module_sub_perms=MODULE_SUB_PERMS,
                           active_page='user_permissions')


@users_bp.route('/user-permissions/<int:user_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def user_permissions(user_id):
    """User-wise permission set/edit karo."""
    u = User.query.get_or_404(user_id)
    modules = Module.query.filter_by(is_active=True).order_by(Module.sort_order).all()

    if request.method == 'POST':
        action = request.form.get('action', 'save')

        if action == 'copy_from_role':
            # Role ke permissions copy karo is user ke liye
            role = request.form.get('role', u.role)
            for mod in modules:
                rp = RolePermission.query.filter_by(role=role, module_id=mod.id).first()
                up = UserPermission.query.filter_by(user_id=user_id, module_id=mod.id).first()
                if not up:
                    up = UserPermission(user_id=user_id, module_id=mod.id)
                    db.session.add(up)
                if rp:
                    up.can_view   = rp.can_view
                    up.can_add    = rp.can_add
                    up.can_edit   = rp.can_edit
                    up.can_delete = rp.can_delete
                    up.can_export = rp.can_export
                else:
                    up.can_view = up.can_add = up.can_edit = up.can_delete = up.can_export = False
                up.updated_by = current_user.id
            db.session.commit()
            flash(f'Permissions copied from role "{role}" for {u.full_name}!', 'success')
            return redirect(url_for('users_bp.user_permissions', user_id=user_id))

        elif action == 'reset':
            # User ke saare overrides delete karo (role pe wapas jaayega)
            UserPermission.query.filter_by(user_id=user_id).delete()
            db.session.commit()
            flash(f'{u.full_name} ke permissions reset ho gaye — ab role permissions follow hongi.', 'success')
            return redirect(url_for('users_bp.user_permissions', user_id=user_id))

        else:
            # Save individual module permissions
            for mod in modules:
                prefix = f'mod_{mod.id}_'
                can_view   = request.form.get(f'{prefix}view') == 'on'
                can_add    = request.form.get(f'{prefix}add') == 'on'
                can_edit   = request.form.get(f'{prefix}edit') == 'on'
                can_delete = request.form.get(f'{prefix}delete') == 'on'
                can_export = request.form.get(f'{prefix}export') == 'on'

                # Sub-permissions
                sub_keys = [k for k, _ in MODULE_SUB_PERMS.get(mod.name, [])]
                sub_dict = {k: (request.form.get(f'{prefix}sub_{k}') == 'on') for k in sub_keys}

                up = UserPermission.query.filter_by(user_id=user_id, module_id=mod.id).first()
                if not up:
                    up = UserPermission(user_id=user_id, module_id=mod.id)
                    db.session.add(up)
                up.can_view   = can_view
                up.can_add    = can_add
                up.can_edit   = can_edit
                up.can_delete = can_delete
                up.can_export = can_export
                up.set_sub_permissions(sub_dict)
                up.updated_by = current_user.id

            db.session.commit()
            audit('users', 'USER_PERM_SAVE', user_id, u.username,
                  f'User permissions saved for {u.full_name} by {current_user.username}')
            flash(f'{u.full_name} ke permissions save ho gaye!', 'success')
            return redirect(url_for('users_bp.user_permissions', user_id=user_id))

    # GET — load existing user permissions
    perm_map = {}  # module_id → UserPermission
    for up in UserPermission.query.filter_by(user_id=user_id).all():
        perm_map[up.module_id] = up

    # Build sub_perm_map: module_id → {key: bool}
    sub_perm_map = {}
    for mod_id, up in perm_map.items():
        sub_perm_map[mod_id] = up.get_sub_permissions()

    role_perm_map = {}  # module_id → RolePermission (for reference)
    for rp in RolePermission.query.filter_by(role=u.role).all():
        role_perm_map[rp.module_id] = rp

    roles = ['admin', 'manager', 'hr', 'user', 'sales', 'viewer']

    return render_template('admin/permissions/user_permissions.html',
                           target_user=u,
                           modules=modules,
                           perm_map=perm_map,
                           sub_perm_map=sub_perm_map,
                           role_perm_map=role_perm_map,
                           module_sub_perms=MODULE_SUB_PERMS,
                           roles=roles,
                           active_page='user_permissions')


@users_bp.route('/user-permissions/<int:user_id>/toggle', methods=['POST'])
@login_required
@admin_required
def user_perm_toggle(user_id):
    """AJAX toggle — single permission on/off."""
    data      = request.json
    module_id = int(data.get('module_id'))
    action    = data.get('action')   # can_view, can_add, can_edit, can_delete, can_export
    value     = bool(data.get('value'))

    up = UserPermission.query.filter_by(user_id=user_id, module_id=module_id).first()
    if not up:
        up = UserPermission(user_id=user_id, module_id=module_id)
        # Naya record — sub_perms sab True set karo by default
        mod = Module.query.get(module_id)
        if mod:
            from permissions import MODULE_SUB_PERMS
            sub_keys = [k for k, _ in MODULE_SUB_PERMS.get(mod.name, [])]
            up.set_sub_permissions({k: True for k in sub_keys})
        db.session.add(up)

    if action in ('can_view', 'can_add', 'can_edit', 'can_delete', 'can_export', 'can_import'):
        # Admin ka can_view kabhi False nahi hoga — warna apna hi module band ho jaata hai
        target_user = User.query.get(user_id)
        if action == 'can_view' and not value and target_user and target_user.role == 'admin':
            return jsonify({'ok': False, 'error': 'Admin ka View permission disable nahi ho sakta'})
        setattr(up, action, value)
        up.updated_by = current_user.id

        # Agar child ka can_view = True kiya → parent ko bhi auto-enable karo
        if action == 'can_view' and value:
            mod = Module.query.get(module_id)
            if mod and mod.parent_id:
                parent_up = UserPermission.query.filter_by(
                    user_id=user_id, module_id=mod.parent_id
                ).first()
                if parent_up and not parent_up.can_view:
                    parent_up.can_view = True
                    parent_up.updated_by = current_user.id

        db.session.commit()
        return jsonify({'ok': True, 'value': value})

    # Module Enable/Disable ALL — sare permissions ek saath on/off
    if action == 'disable_all':
        # Admin ka can_view kabhi False nahi
        target_user = User.query.get(user_id)
        _is_target_admin = target_user and target_user.role == 'admin'
        up.can_view   = True if _is_target_admin else value
        up.can_add    = value
        up.can_edit   = value
        up.can_delete = value
        up.can_export = value
        up.can_import = value
        # Sub-permissions bhi sab on/off karo
        mod = Module.query.get(module_id)
        if mod:
            from permissions import MODULE_SUB_PERMS
            sub_keys = [k for k, _ in MODULE_SUB_PERMS.get(mod.name, [])]
            subs = {k: value for k in sub_keys}
            up.set_sub_permissions(subs)

            # ── Child modules bhi cascade karo (e.g. CRM → crm_leads, crm_clients) ──
            child_modules = Module.query.filter_by(parent_id=module_id, is_active=True).all()
            for child in child_modules:
                child_up = UserPermission.query.filter_by(user_id=user_id, module_id=child.id).first()
                if not child_up:
                    child_up = UserPermission(user_id=user_id, module_id=child.id)
                    db.session.add(child_up)
                child_up.can_view   = value
                child_up.can_add    = value
                child_up.can_edit   = value
                child_up.can_delete = value
                child_up.can_export = value
                child_up.can_import = value
                child_sub_keys = [k for k, _ in MODULE_SUB_PERMS.get(child.name, [])]
                child_up.set_sub_permissions({k: value for k in child_sub_keys})
                child_up.updated_by = current_user.id

            # Enable karte waqt parent bhi enable karo
            if value and mod.parent_id:
                parent_up = UserPermission.query.filter_by(
                    user_id=user_id, module_id=mod.parent_id
                ).first()
                if parent_up and not parent_up.can_view:
                    parent_up.can_view = True
                    parent_up.updated_by = current_user.id

        up.updated_by = current_user.id
        db.session.commit()
        return jsonify({'ok': True, 'value': value})

    # Sub-permission toggle
    if action.startswith('sub_'):
        sub_key = action[4:]
        subs = up.get_sub_permissions()
        subs[sub_key] = value
        up.set_sub_permissions(subs)
        up.updated_by = current_user.id
        db.session.commit()
        return jsonify({'ok': True, 'value': value})

    return jsonify({'ok': False, 'error': 'Unknown action'}), 400
