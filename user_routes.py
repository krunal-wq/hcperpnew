"""
user_routes.py — User Management + Profile + Permission Admin
"""
import json
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from audit_helper import audit, snapshot
from functools import wraps
from datetime import datetime
from models import db, User, LoginLog, Module, RolePermission
from permissions import seed_permissions

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
    all_users = User.query.order_by(User.full_name).all()
    return render_template('admin/users/index.html', users=all_users, active_page='user_mgmt')


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
    if request.method == 'POST':
        action = request.form.get('action', 'profile')
        if action == 'password':
            old_pw = request.form.get('old_password', '')
            new_pw = request.form.get('new_password', '')
            if not current_user.check_password(old_pw):
                flash('Current password is incorrect.', 'error')
            elif len(new_pw) < 6:
                flash('New password must be at least 6 characters.', 'error')
            else:
                current_user.set_password(new_pw)
                db.session.commit()
                flash('Password changed!', 'success')
        else:
            current_user.full_name = request.form.get('full_name', '').strip()
            current_user.email     = request.form.get('email', '').strip()
            db.session.commit()
            flash('Profile updated!', 'success')
        return redirect(url_for('users_bp.profile'))

    # Login history
    logs = LoginLog.query.filter_by(user_id=current_user.id)\
               .order_by(LoginLog.timestamp.desc()).limit(10).all()
    return render_template('admin/profile.html', logs=logs, active_page='profile')


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
    from flask import Response

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
