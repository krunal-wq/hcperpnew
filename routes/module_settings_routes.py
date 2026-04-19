"""
routes/module_settings_routes.py
Module Enable/Disable Management — Admin Only

Is route se admin modules ko enable/disable kar sakta hai.
Jab module disabled hoga to left sidebar menu se woh hide ho jayega.
"""
from flask import Blueprint, render_template, jsonify, request, redirect, url_for, flash
from flask_login import login_required, current_user
from models import db
from models.permission import Module

module_settings = Blueprint('module_settings', __name__, url_prefix='/settings')


def admin_required(f):
    """Decorator: Only admin users can access this."""
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'admin':
            flash('Access denied. Admin only.', 'error')
            return redirect(url_for('dashboard'))
        return f(*args, **kwargs)
    return decorated


# ──────────────────────────────────────────────
# Module Settings Page
# ──────────────────────────────────────────────

@module_settings.route('/modules')
@login_required
@admin_required
def manage_modules():
    """Module management page — enable/disable modules."""
    # Top-level modules only (parent_id = None)
    top_modules = Module.query.filter_by(parent_id=None).order_by(Module.sort_order).all()

    # Sub-modules grouped by parent
    all_modules = Module.query.order_by(Module.sort_order).all()

    return render_template('settings/module_settings.html',
                           top_modules=top_modules,
                           all_modules=all_modules)


# ──────────────────────────────────────────────
# Toggle Module API (AJAX)
# ──────────────────────────────────────────────

@module_settings.route('/modules/toggle', methods=['POST'])
@login_required
@admin_required
def toggle_module():
    """
    POST /settings/modules/toggle
    Body: { "module_id": 3, "is_active": false }
    
    Module ko enable ya disable karta hai.
    Jab parent disable hoga to uske saare children bhi disable honge.
    """
    data = request.get_json()
    if not data or 'module_id' not in data:
        return jsonify({'success': False, 'message': 'module_id required'}), 400

    module_id = data['module_id']
    is_active = bool(data.get('is_active', True))

    mod = Module.query.get(module_id)
    if not mod:
        return jsonify({'success': False, 'message': 'Module not found'}), 404

    # Update module
    mod.is_active = is_active

    # Agar parent disable hua to sab children bhi disable karo
    if not is_active:
        _disable_children(mod)

    db.session.commit()

    return jsonify({
        'success': True,
        'module_id': module_id,
        'is_active': is_active,
        'message': f"Module '{mod.label or mod.name}' {'enabled' if is_active else 'disabled'} successfully"
    })


def _disable_children(parent_module):
    """Recursively disable all child modules."""
    for child in parent_module.children:
        child.is_active = False
        _disable_children(child)


# ──────────────────────────────────────────────
# Bulk Toggle API
# ──────────────────────────────────────────────

@module_settings.route('/modules/bulk-toggle', methods=['POST'])
@login_required
@admin_required
def bulk_toggle():
    """
    POST /settings/modules/bulk-toggle
    Body: { "module_ids": [1, 2, 3], "is_active": false }
    """
    data = request.get_json()
    module_ids = data.get('module_ids', [])
    is_active = bool(data.get('is_active', True))

    if not module_ids:
        return jsonify({'success': False, 'message': 'No modules selected'}), 400

    modules = Module.query.filter(Module.id.in_(module_ids)).all()
    for mod in modules:
        mod.is_active = is_active
        if not is_active:
            _disable_children(mod)

    db.session.commit()

    return jsonify({
        'success': True,
        'updated': len(modules),
        'message': f"{len(modules)} modules {'enabled' if is_active else 'disabled'}"
    })


# ──────────────────────────────────────────────
# Get Active Modules API (Sidebar ke liye)
# ──────────────────────────────────────────────

@module_settings.route('/modules/active', methods=['GET'])
@login_required
def get_active_modules():
    """
    Returns only active modules — sidebar rendering ke liye use hota hai.
    """
    active = Module.query.filter_by(is_active=True).order_by(Module.sort_order).all()
    return jsonify({
        'modules': [
            {
                'id': m.id,
                'name': m.name,
                'label': m.label,
                'icon': m.icon,
                'url_prefix': m.url_prefix,
                'parent_id': m.parent_id,
            }
            for m in active
        ]
    })
