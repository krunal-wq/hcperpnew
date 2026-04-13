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
        ('filter',            'Filter'),
        ('sort',              'Sort'),
        ('columns',           'Columns'),
        ('discussion_board',  'Discussion Board'),
        ('activity_log',      'Activity Log'),
        ('reminder',          'Reminder'),
        ('personal_notes',    'Personal Notes'),
        ('whatsapp',          'WhatsApp'),
        ('sample_order',      'Sample Order'),
        ('quotation',         'Quotation'),
        ('send_npd',          'Send NPD'),
        ('create_npd',        'Create NPD Project'),
        ('create_epd',        'Create EPD Project'),
        ('change_status',     'Change Status'),
        ('inline_edit',       'Inline Edit'),
        ('attachments',       'Attachments'),
        ('restore',           'Restore'),
        ('permanent_delete',  'Permanent Delete'),
        ('view_deleted',      'View Deleted Tab'),
        # Sample Order sub-perms
        ('sample_order_view', 'SO: View Listing'),
        ('lead_view',         'SO: Lead View'),
        ('invoice_download',  'SO: Invoice Download'),
        ('pdf_download',      'SO: Download PDF'),
        ('mail_send',         'SO: Mail Send'),
        ('invoice_upload',    'SO: Invoice Upload'),
        # Quotation sub-perms
        ('quot_view',         'Quot: View Listing'),
        ('send_email',        'Quot: Send Email'),
        ('status_change',     'Quot: Status Change'),
    ],
    'crm_quotations': [
        ('pdf_download',      'Download PDF'),
        ('send_email',        'Send Email'),
        ('status_change',     'Status Change'),
        ('view_deleted',      'View Deleted Tab'),
        ('restore',           'Restore'),
        ('permanent_delete',  'Permanent Delete'),
    ],
    'crm_sample_orders': [
        ('lead_view',         'Lead View'),
        ('invoice_download',  'Invoice Download'),
        ('pdf_download',      'Download Sample Order PDF'),
        ('mail_send',         'Mail Send'),
        ('invoice_upload',    'Invoice Upload'),
        ('change_status',     'Change Status'),
        ('view_deleted',      'View Deleted Tab'),
        ('restore',           'Restore'),
        ('permanent_delete',  'Permanent Delete'),
    ],
    'crm_clients': [
        ('filter',            'Filter'),
        ('sort',              'Sort'),
        ('columns',           'Columns'),
        ('inline_edit',       'Inline Edit'),
        ('create_npd',        'Create NPD Project'),
        ('create_epd',        'Create EPD Project'),
        ('npd_quote',         'NPD Quote'),
        ('restore',           'Restore'),
        ('permanent_delete',  'Permanent Delete'),
        ('view_deleted',      'View Deleted Tab'),
    ],
    'hr_employees': [
        ('salary_details',    'Salary Details'),
        ('bank_details',      'Bank Details'),
        ('kyc_details',       'KYC Details'),
        ('documents',         'Documents'),
        ('filter',            'Filter'),
        ('sort',              'Sort'),
        ('columns',           'Columns'),
        ('inline_edit',       'Inline Edit'),
        ('id_card',           'ID Card'),
        ('org_chart',         'Org Chart'),
        ('restore',           'Restore'),
        ('permanent_delete',  'Permanent Delete'),
    ],
    'hr': [
        ('manual_entry',      'Manual Entry'),
        ('late_absent',       'Late & Absent'),
        ('holiday',           'Holiday'),
    ],
    'hr_contractors': [
        ('filter',            'Filter'),
        ('sort',              'Sort'),
        ('columns',           'Columns'),
        ('inline_edit',       'Inline Edit'),
        ('restore',           'Restore'),
        ('permanent_delete',  'Permanent Delete'),
    ],
    'npd': [
        ('create_project',    'Create Project'),
        ('inline_edit',       'Inline Edit'),
        ('milestone',         'Milestone'),
        ('epd',               'EPD'),
        ('print',             'Print'),
        ('discussion_board',  'Discussion Board'),
        ('internal_discussion','Internal Discussion'),
        ('activity_log',      'Activity Log'),
        ('attachments',       'Attachments'),
        ('notes',             'Notes'),
        ('reports',           'Reports'),
        ('close_project',     'Close Project'),
        ('restore',           'Restore'),
        ('permanent_delete',  'Permanent Delete'),
    ],
    'rd': [
        ('create_project',    'Create Project'),
        ('trials',            'Trials'),
        ('assign',            'Assign NPD'),
        ('discussion',        'Discussion'),
        ('performance',       'Performance'),
        ('settings',          'Settings'),
    ],
}


# ── Fetch permission for current user ───────────────────────────────────────
def get_perm(module_name):
    """
    Priority:
    1. UserPermission record hai → use that
    2. RolePermission se fallback
    3. Koi record nahi → view_only (menu dikhega)
    
    Note: Agar UserPermission exist karta hai to usse use karo.
    Admin ne explicitly disable kiya hoga tabhi can_view=False hoga.
    """
    if not current_user.is_authenticated:
        return None
    try:
        mod = Module.query.filter_by(name=module_name).first()
        if not mod:
            # Module DB mein nahi — admin ko full, others ko view_only
            if current_user.role == 'admin':
                return _full_perm()
            return _view_only_perm()

        # Priority 1: User-specific override (admin ke liye bhi)
        user_perm = UserPermission.query.filter_by(
            user_id=current_user.id, module_id=mod.id
        ).first()
        if user_perm is not None:
            return user_perm

        # Priority 2: Admin ko full access agar koi UserPermission nahi
        if current_user.role == 'admin':
            return _full_perm()

        # Priority 3: Role fallback
        role_perm = RolePermission.query.filter_by(
            role=current_user.role, module_id=mod.id
        ).first()
        if role_perm is not None:
            return role_perm

        # Koi record nahi — by default view allow karo
        return _view_only_perm()
    except Exception:
        if current_user.role == 'admin':
            return _full_perm()
        return _view_only_perm()


def get_sub_perm(module_name, key):
    """Check specific sub-permission for current user on a module."""
    if not current_user.is_authenticated:
        return False
    try:
        mod = Module.query.filter_by(name=module_name).first()
        if not mod:
            # Module DB mein nahi — default True
            return True
        # User-specific override check karo (admin ke liye bhi)
        user_perm = UserPermission.query.filter_by(
            user_id=current_user.id, module_id=mod.id
        ).first()
        if user_perm is not None:
            subs = user_perm.get_sub_permissions()
            # Agar key explicitly set hai toh use karo
            # Agar key missing hai (purana record) — default True (naya perm add hua)
            return subs.get(key, True)
        # UserPermission record nahi — default True (koi restriction nahi lagayi)
        return True
    except Exception:
        return True


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
    {'name':'crm_quotations','label':'Quotations','icon':'📄','url_prefix':'/crm/quotations','sort_order':6,'parent':'crm'},
    {'name':'crm_sample_orders','label':'Sample Orders','icon':'🧾','url_prefix':'/crm/sample-orders','sort_order':5,'parent':'crm'},
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
