"""
seed_admin_permissions.py
=========================
Admin user ke liye sabhi modules ki full permissions + sub-permissions
UserPermission table me seed karta hai.

Run: python seed_admin_permissions.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app
from models.base import db
from models.user import User
from models.permission import Module, UserPermission

# All sub-permissions per module
MODULE_SUB_PERMS = {
    'crm_leads'    : ['discussion_board','activity_log','reminder','quotation','sample_order','attachments','whatsapp'],
    'crm_clients'  : ['create_npd','create_epd','npd_quote'],
    'hr_employees' : ['salary_details','documents','bank_details','kyc_details'],
    'npd'          : ['create_project','milestone','epd','reports'],
    'rd'           : ['create_project','trials','discussion','performance','settings'],
}

G = "\033[92m"; E = "\033[0m"

with app.app_context():
    import json

    # Get all admin users
    admins = User.query.filter_by(role='admin').all()
    if not admins:
        print("No admin users found!")
        sys.exit(1)

    modules = Module.query.filter_by(is_active=True).all()
    total = 0

    for admin in admins:
        print(f"\n  Setting permissions for: {admin.username} ({admin.full_name})")
        for mod in modules:
            # Build sub_permissions dict
            sub_keys = MODULE_SUB_PERMS.get(mod.name, [])
            sub_dict = {k: True for k in sub_keys}

            up = UserPermission.query.filter_by(
                user_id=admin.id, module_id=mod.id
            ).first()

            if not up:
                up = UserPermission(user_id=admin.id, module_id=mod.id)
                db.session.add(up)

            up.can_view   = True
            up.can_add    = True
            up.can_edit   = True
            up.can_delete = True
            up.can_export = True
            up.can_import = True
            up.set_sub_permissions(sub_dict)
            total += 1
            print(f"     ✅ {mod.name:<20} — all permissions + {len(sub_keys)} sub-perms")

    db.session.commit()
    print(f"\n{G}  Done! {total} module permissions seeded for {len(admins)} admin(s).{E}")
    print(f"  Ab /admin/user-permissions me jaake aur modules adjust kar sakte ho.\n")
