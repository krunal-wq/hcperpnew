"""
approval_routes.py — Hierarchy Management + Approval Workflow
"""
from audit_helper import audit
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from datetime import datetime
from models import db, User
from models.employee import Employee
from models.approval import ApprovalRequest, ApprovalLevel
from permissions import get_perm

approval_bp = Blueprint('approval', __name__)


# ══════════════════════════════════════════════════════
# HIERARCHY TREE
# ══════════════════════════════════════════════════════

def build_tree(emp, depth=0, max_depth=10):
    """Recursively build employee hierarchy tree."""
    if depth > max_depth:
        return None
    subs = Employee.query.filter_by(reports_to=emp.id, status='active').order_by(Employee.first_name).all()
    return {
        'emp': emp,
        'depth': depth,
        'children': [build_tree(s, depth+1) for s in subs]
    }


@approval_bp.route('/hierarchy')
@login_required
def hierarchy():
    """Show full org chart — admin sees all, managers see their subtree."""
    if current_user.role == 'admin':
        # Top-level: employees with no manager
        roots = Employee.query.filter(
            Employee.reports_to == None,
            Employee.status == 'active'
        ).order_by(Employee.first_name).all()
        trees = [build_tree(r) for r in roots]
        unassigned = []
    else:
        # Find current user's employee record
        my_emp = Employee.query.filter_by(user_id=current_user.id).first()
        trees = [build_tree(my_emp)] if my_emp else []
        unassigned = []

    all_employees = Employee.query.filter_by(status='active').order_by(Employee.first_name).all()
    return render_template('approval/hierarchy.html',
        trees=trees, all_employees=all_employees,
        active_page='hierarchy')


@approval_bp.route('/hierarchy/set-manager', methods=['POST'])
@login_required
def set_manager():
    """Set reporting manager for an employee."""
    if current_user.role not in ('admin', 'manager'):
        return jsonify(success=False, error='Access denied'), 403

    emp_id     = request.form.get('emp_id', type=int)
    manager_id = request.form.get('manager_id', type=int)  # 0 = remove manager

    emp = Employee.query.get_or_404(emp_id)

    # Prevent circular — manager can't report to their own subordinate
    if manager_id:
        # Check manager_id is not a descendant of emp
        def get_all_sub_ids(e):
            ids = set()
            for s in Employee.query.filter_by(reports_to=e.id).all():
                ids.add(s.id)
                ids |= get_all_sub_ids(s)
            return ids
        if manager_id in get_all_sub_ids(emp):
            return jsonify(success=False, error='Circular hierarchy detected'), 400

    emp.reports_to = manager_id if manager_id else None
    audit('approvals','SET_MANAGER', emp_id, emp.full_name, f'Manager set by {current_user.username}: {emp.full_name} → {manager_id if manager_id else "None"}')
    db.session.commit()
    mgr = Employee.query.get(manager_id) if manager_id else None
    return jsonify(success=True, manager_name=mgr.full_name if mgr else 'None')


# ══════════════════════════════════════════════════════
# APPROVAL REQUESTS
# ══════════════════════════════════════════════════════

@approval_bp.route('/approvals')
@login_required
def approvals():
    """List approvals — pending ones needing my action at top."""
    my_emp = Employee.query.filter_by(user_id=current_user.id).first()

    if current_user.role == 'admin':
        pending = ApprovalRequest.query.filter_by(status='pending').order_by(ApprovalRequest.created_at.desc()).all()
        mine    = []
    else:
        # Requests from my direct subordinates
        sub_user_ids = []
        if my_emp:
            for s in Employee.query.filter_by(reports_to=my_emp.id).all():
                if s.user_id:
                    sub_user_ids.append(s.user_id)
        pending = ApprovalRequest.query.filter(
            ApprovalRequest.status == 'pending',
            ApprovalRequest.requested_by.in_(sub_user_ids)
        ).order_by(ApprovalRequest.created_at.desc()).all()
        mine = ApprovalRequest.query.filter_by(
            requested_by=current_user.id
        ).order_by(ApprovalRequest.created_at.desc()).limit(20).all()

    # Approval level config
    levels = {al.module: al for al in ApprovalLevel.query.all()}
    return render_template('approval/approvals.html',
        pending=pending, mine=mine, levels=levels,
        active_page='approvals')


@approval_bp.route('/approvals/request', methods=['POST'])
@login_required
def request_approval():
    """Submit an approval request."""
    module  = request.form.get('module', '')
    rec_id  = request.form.get('record_id', type=int)
    label   = request.form.get('record_label', '')
    action  = request.form.get('action', 'approve')
    note    = request.form.get('requester_note', '').strip()

    # Check if pending request already exists
    existing = ApprovalRequest.query.filter_by(
        module=module, record_id=rec_id, action=action, status='pending'
    ).first()
    if existing:
        flash('Approval request already pending.', 'info')
        return redirect(request.referrer or url_for('approval.approvals'))

    ar = ApprovalRequest(
        module=module, record_id=rec_id, record_label=label,
        action=action, requested_by=current_user.id, requester_note=note
    )
    db.session.add(ar)
    db.session.commit()
    audit('approvals','REQUEST', ar.id, ar.request_type, f'Approval request submitted by {current_user.username}: {ar.request_type}')
    flash('Approval request submitted.', 'success')
    return redirect(request.referrer or url_for('approval.approvals'))


@approval_bp.route('/approvals/<int:ar_id>/action', methods=['POST'])
@login_required
def approval_action(ar_id):
    """Approve or reject a request."""
    ar      = ApprovalRequest.query.get_or_404(ar_id)
    action  = request.form.get('action')  # approve / reject
    remarks = request.form.get('remarks', '').strip()

    # Permission check — admin can always act; others must be in approver chain
    if current_user.role != 'admin':
        my_emp = Employee.query.filter_by(user_id=current_user.id).first()
        requester_emp = Employee.query.filter_by(user_id=ar.requested_by).first()
        if not my_emp or not requester_emp or requester_emp.reports_to != my_emp.id:
            flash('You are not authorized to approve this request.', 'error')
            return redirect(url_for('approval.approvals'))

    ar.status      = 'approved' if action == 'approve' else 'rejected'
    ar.approved_by = current_user.id
    ar.approved_at = datetime.utcnow()
    ar.remarks     = remarks
    db.session.commit()

    audit('approvals','ACTION', ar.id, ar.request_type, f'Approval {action}d by {current_user.username}: {ar.request_type}')
    flash(f'Request {"approved" if action=="approve" else "rejected"}.', 'success')
    return redirect(url_for('approval.approvals'))


# ══════════════════════════════════════════════════════
# APPROVAL LEVEL CONFIG (Admin only)
# ══════════════════════════════════════════════════════

@approval_bp.route('/approvals/config', methods=['GET', 'POST'])
@login_required
def approval_config():
    if current_user.role != 'admin':
        flash('Admin only.', 'error')
        return redirect(url_for('approval.approvals'))

    MODULES = [
        ('leads',      '📋 Leads'),
        ('clients',    '👤 Clients'),
        ('employees',  '🪪 Employees'),
        ('leave',      '🏖️ Leave'),
        ('expense',    '💰 Expense'),
        ('purchase',   '🛒 Purchase'),
    ]

    if request.method == 'POST':
        for mod, _ in MODULES:
            levels = request.form.get(f'levels_{mod}', type=int, default=1)
            active = request.form.get(f'active_{mod}') == 'on'
            al = ApprovalLevel.query.filter_by(module=mod).first()
            if al:
                al.levels = max(1, min(5, levels))
                al.is_active = active
            else:
                db.session.add(ApprovalLevel(module=mod, label=_, levels=levels, is_active=active))
        db.session.commit()
        audit('approvals','CONFIG_UPDATE', None, '', f'Approval config updated by {current_user.username}')
    flash('Approval config saved.', 'success')
    return redirect(url_for('approval.approval_config'))

    config = {al.module: al for al in ApprovalLevel.query.all()}
    return render_template('approval/config.html',
        modules=MODULES, config=config, active_page='approval_config')
