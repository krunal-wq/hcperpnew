"""
fix_orphaned_child_permissions.py   (v2 — robust)
──────────────────────────────────────────────────
Saare users me check karta hai: agar kisi ke pass child module ka
can_view=True hai but parent module ka UserPermission record missing
ya disabled hai, to parent chain ko enable karta hai.

Isme yeh improvements hain v1 se:
  - Per-user try/except
  - Per-user commit (ek user fail ho to baaki chalte rahe)
  - Sab required fields explicitly set hote hain create time pe
  - Cycle detection in parent walk

Run:
    python fix_orphaned_child_permissions.py         # dry-run
    python fix_orphaned_child_permissions.py --apply # actually save
    python fix_orphaned_child_permissions.py --apply --verbose
"""
import sys, os, traceback
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app, db
from models import User, Module, UserPermission

APPLY   = '--apply'   in sys.argv
VERBOSE = '--verbose' in sys.argv


def main():
    with app.app_context():
        mode = "APPLY" if APPLY else "DRY-RUN"
        print(f"\n{'='*70}")
        print(f"  FIX ORPHANED CHILD PERMISSIONS   [{mode}]")
        print(f"{'='*70}\n")

        all_mods = {m.id: m for m in Module.query.all()}
        print(f"  Loaded {len(all_mods)} modules")

        users = User.query.filter_by(is_active=True).all()
        print(f"  Scanning {len(users)} active users\n")

        total_fixed_users = 0
        total_fixes       = 0
        errors            = []

        for u in users:
            try:
                ups = UserPermission.query.filter_by(user_id=u.id).all()
                if not ups:
                    if VERBOSE:
                        print(f"  {u.username}: no UserPermission rows, skip")
                    continue

                up_map = {up.module_id: up for up in ups}
                fixed_for_this_user = 0

                # For every child permission with can_view=True, walk parent chain up
                for up in list(ups):
                    if not up.can_view:
                        continue
                    mod = all_mods.get(up.module_id)
                    if not mod or not mod.parent_id:
                        continue

                    current_parent_id = mod.parent_id
                    visited = set()
                    while current_parent_id and current_parent_id not in visited:
                        visited.add(current_parent_id)
                        parent = all_mods.get(current_parent_id)
                        if not parent:
                            break

                        parent_up = up_map.get(parent.id)
                        needs_fix = False
                        reason = ""

                        if parent_up is None:
                            needs_fix = True
                            reason = "missing record"
                        elif not parent_up.can_view:
                            needs_fix = True
                            reason = "can_view was False"

                        if needs_fix:
                            print(f"  {u.username:<22} child='{mod.name}' → enable parent='{parent.name}' ({reason})")
                            if APPLY:
                                if parent_up is None:
                                    parent_up = UserPermission()
                                    parent_up.user_id    = u.id
                                    parent_up.module_id  = parent.id
                                    parent_up.can_view   = True
                                    parent_up.can_add    = False
                                    parent_up.can_edit   = False
                                    parent_up.can_delete = False
                                    parent_up.can_export = False
                                    parent_up.can_import = False
                                    parent_up.sub_permissions = '{}'
                                    db.session.add(parent_up)
                                    up_map[parent.id] = parent_up
                                else:
                                    parent_up.can_view = True
                            fixed_for_this_user += 1
                            total_fixes += 1

                        current_parent_id = parent.parent_id

                if fixed_for_this_user:
                    total_fixed_users += 1
                    if APPLY:
                        try:
                            db.session.commit()
                        except Exception as e:
                            db.session.rollback()
                            err = f"{u.username}: commit failed — {type(e).__name__}: {e}"
                            errors.append(err)
                            print(f"    ❌ {err}")
                            if VERBOSE:
                                traceback.print_exc()

            except Exception as e:
                try: db.session.rollback()
                except: pass
                err = f"{u.username}: {type(e).__name__} — {e}"
                errors.append(err)
                print(f"    ❌ {err}")
                if VERBOSE:
                    traceback.print_exc()

        print(f"\n{'='*70}")
        print(f"  SUMMARY")
        print(f"{'='*70}")
        print(f"  Users scanned:         {len(users)}")
        print(f"  Users fixed:           {total_fixed_users}")
        print(f"  Parent records fixed:  {total_fixes}")
        if errors:
            print(f"\n  ⚠️  Errors ({len(errors)}):")
            for e in errors:
                print(f"     {e}")

        if APPLY and total_fixes:
            print(f"\n  ✅ Changes saved. User ko logout-login karna hoga.")
        elif APPLY:
            print(f"\n  ✅ Koi change zaroori nahi tha.")
        else:
            print(f"\n  ℹ️  Dry-run only. Re-run with --apply to save.")
        print()


if __name__ == '__main__':
    main()
