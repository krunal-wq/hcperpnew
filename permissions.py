"""
permissions.py — Permission helpers used across the app
Priority: UserPermission (user-specific) → RolePermission (role fallback)
"""
from functools import wraps
from flask import flash, redirect, url_for, abort
from flask_login import current_user
from models import db, RolePermission, Module, UserGridConfig, UserPermission


# ── Sub-permission keys per module ──────────────────────────────────────────
# Ye dict define karta hai har module ke andar kaunse granular sub-permissions hain
MODULE_SUB_PERMS = {
    'crm_leads': [
        ('discussion_board', 'Discussion Board'),
        ('activity_log',     'Activity Log'),
        ('reminder',         'Reminder'),
        ('quotation',        'Quotation'),
        ('sample_order',     'Sample Order'),
        ('attachments',      'Attachments List'),
        ('whatsapp',         'WhatsApp'),
    ],
    'crm_clients': [
        ('create_npd',       'Create NPD Project'),
        ('create_epd',       'Create EPD Project'),
        ('npd_quote',        'NPD Quote'),
    ],
    'hr_employees': [
        ('salary_details',   'Salary Details'),
        ('documents',        'Documents'),
        ('bank_details',     'Bank Details'),
        ('kyc_details',      'KYC Details'),
    ],
    'npd': [
        ('create_project',   'Create Project'),
        ('milestone',        'Milestone'),
        ('epd',              'EPD'),
        ('reports',          'Reports'),
        ('close_project',    'Close Project (All Milestones Done)'),
    ],
    'rd': [
        ('create_project',   'Create Project'),
        ('trials',           'Trials'),
        ('discussion',       'Discussion'),
        ('performance',      'Performance'),
        ('settings',         'Settings'),
    ],
}


# ── Fetch permission for current user ───────────────────────────────────────
def get_perm(module_name):
    """
    Priority:
    1. UserPermission record hai → use that (ALL users including admin)
    2. Warna role_permissions se fallback
    3. Koi record nahi → no perm
    """
    if not current_user.is_authenticated:
        return None
    try:
        mod = Module.query.filter_by(name=module_name).first()
        if not mod:
            return _view_only_perm()

        # Priority 1: User-specific override (admin bhi)
        user_perm = UserPermission.query.filter_by(
            user_id=current_user.id, module_id=mod.id
        ).first()
        if user_perm is not None:
            return user_perm

        # Priority 2: Role fallback
        return RolePermission.query.filter_by(
            role=current_user.role, module_id=mod.id
        ).first() or _no_perm()
    except Exception:
        return _view_only_perm()


def get_sub_perm(module_name, key):
    """Check specific sub-permission for current user on a module."""
    if not current_user.is_authenticated:
        return False
    try:
        mod = Module.query.filter_by(name=module_name).first()
        if not mod:
            return False
        # User-specific override check karo
        user_perm = UserPermission.query.filter_by(
            user_id=current_user.id, module_id=mod.id
        ).first()
        if user_perm is not None:
            return user_perm.has_sub_perm(key)
        # User ka koi record nahi — sub-perm nahi deni by default
        # (Admin bhi yahan aayega — use bhi set karna hoga explicitly)
        return False
    except Exception:
        return False


def _full_perm(module_name=None):
    class FullPerm:
        can_view = can_add = can_edit = can_delete = can_export = True
        def get_visible_fields(self): return []
    return FullPerm()


def _view_only_perm():
    class ViewPerm:
        can_view = True
        can_add = can_edit = can_delete = can_export = False
        def get_visible_fields(self): return []
    return ViewPerm()


def _no_perm():
    class NoPerm:
        can_view = can_add = can_edit = can_delete = can_export = False
        def get_visible_fields(self): return []
    return NoPerm()


def require_perm(module_name, action='view'):
    """Decorator: require specific permission"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            perm = get_perm(module_name)
            if not perm or not getattr(perm, f'can_{action}', False):
                flash(f'Access denied: {action} permission required for {module_name}.', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator


# ── Get user's grid columns for a module ──
def get_grid_columns(module_name, default_cols, all_valid_cols=None):
    """
    module_name: e.g. 'employees'
    default_cols: list of default column keys
    all_valid_cols: list/set of ALL valid column keys (to validate saved config)
    """
    if not current_user.is_authenticated:
        return default_cols
    valid_set = set(all_valid_cols) if all_valid_cols else set(default_cols)
    try:
        cfg = UserGridConfig.query.filter_by(
            user_id=current_user.id, module_name=module_name
        ).first()
        if cfg:
            saved = cfg.get_columns()
            valid = [c for c in saved if c in valid_set]
            return valid if valid else default_cols
    except Exception:
        pass
    return default_cols


def save_grid_columns(module_name, cols):
    try:
        cfg = UserGridConfig.query.filter_by(
            user_id=current_user.id, module_name=module_name
        ).first()
        if not cfg:
            cfg = UserGridConfig(user_id=current_user.id, module_name=module_name)
            db.session.add(cfg)
        cfg.set_columns(cols)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        raise e


# ── Get all visible menu modules for current user ──
def get_menu_modules():
    if not current_user.is_authenticated:
        return []
    if current_user.role == 'admin':
        return Module.query.filter_by(is_active=True, parent_id=None)\
                           .order_by(Module.sort_order).all()
    # Get modules where this role has can_view = True
    perms = RolePermission.query.filter_by(role=current_user.role, can_view=True).all()
    mod_ids = [p.module_id for p in perms]
    return Module.query.filter(
        Module.id.in_(mod_ids),
        Module.is_active == True,
        Module.parent_id == None
    ).order_by(Module.sort_order).all()


# ── Seed default modules and permissions ──
DEFAULT_MODULES = [
    {'name':'dashboard',    'label':'Dashboard',      'icon':'🏠', 'url_prefix':'/',          'sort_order':1},
    {'name':'crm',          'label':'CRM',            'icon':'📊', 'url_prefix':'/crm',       'sort_order':2},
    {'name':'crm_leads',    'label':'Leads',          'icon':'📋', 'url_prefix':'/crm/leads', 'sort_order':3,  'parent':'crm'},
    {'name':'crm_clients',  'label':'Clients',        'icon':'👥', 'url_prefix':'/crm/clients','sort_order':4, 'parent':'crm'},
    {'name':'hr',           'label':'HR',             'icon':'👔', 'url_prefix':'/hr',        'sort_order':5},
    {'name':'hr_employees', 'label':'Employees',      'icon':'🪪', 'url_prefix':'/hr/employees','sort_order':6,'parent':'hr'},
    {'name':'hr_contractors','label':'Contractors',   'icon':'🤝', 'url_prefix':'/hr/contractors','sort_order':7,'parent':'hr'},
    {'name':'masters',      'label':'Masters',        'icon':'⚙️', 'url_prefix':'/masters',   'sort_order':8},
    {'name':'user_mgmt',    'label':'User Management','icon':'🔑', 'url_prefix':'/admin/users','sort_order':9},
]

DEFAULT_ROLE_PERMS = {
    'admin':   {m['name']: dict(can_view=True, can_add=True, can_edit=True, can_delete=True, can_export=True)
                for m in DEFAULT_MODULES},
    'manager': {
        'dashboard':     dict(can_view=True),
        'crm':           dict(can_view=True),
        'crm_leads':     dict(can_view=True, can_add=True, can_edit=True, can_delete=False, can_export=True),
        'crm_clients':   dict(can_view=True, can_add=True, can_edit=True, can_delete=False, can_export=True),
        'hr':            dict(can_view=True),
        'hr_employees':  dict(can_view=True, can_add=False, can_edit=False, can_delete=False, can_export=False),
        'hr_contractors':dict(can_view=True),
        'masters':       dict(can_view=True, can_add=True, can_edit=True, can_delete=False),
    },
    'user': {
        'dashboard':     dict(can_view=True),
        'crm':           dict(can_view=True),
        'crm_leads':     dict(can_view=True, can_add=True, can_edit=True, can_delete=False, can_export=False),
        'crm_clients':   dict(can_view=True, can_add=False, can_edit=False),
        'masters':       dict(can_view=True),
    },
    'hr': {
        'dashboard':     dict(can_view=True),
        'hr':            dict(can_view=True),
        'hr_employees':  dict(can_view=True, can_add=True, can_edit=True, can_delete=False, can_export=True),
        'hr_contractors':dict(can_view=True, can_add=True, can_edit=True, can_delete=False),
        'masters':       dict(can_view=True),
    },
}


def seed_permissions():
    # Create modules
    mod_map = {}
    for m in DEFAULT_MODULES:
        existing = Module.query.filter_by(name=m['name']).first()
        if not existing:
            parent_id = None
            if 'parent' in m:
                parent_mod = Module.query.filter_by(name=m['parent']).first()
                if parent_mod:
                    parent_id = parent_mod.id
            existing = Module(
                name=m['name'], label=m['label'], icon=m['icon'],
                url_prefix=m['url_prefix'], sort_order=m['sort_order'],
                parent_id=parent_id, is_active=True
            )
            db.session.add(existing)
            db.session.flush()
        mod_map[m['name']] = existing.id

    # Create role permissions
    for role, mods in DEFAULT_ROLE_PERMS.items():
        for mod_name, actions in mods.items():
            mod_id = mod_map.get(mod_name)
            if not mod_id:
                continue
            existing = RolePermission.query.filter_by(role=role, module_id=mod_id).first()
            if not existing:
                perm = RolePermission(role=role, module_id=mod_id,
                                      can_view=actions.get('can_view', False),
                                      can_add=actions.get('can_add', False),
                                      can_edit=actions.get('can_edit', False),
                                      can_delete=actions.get('can_delete', False),
                                      can_export=actions.get('can_export', False))
                db.session.add(perm)
    db.session.commit()
    return mod_map
