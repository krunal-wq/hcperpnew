"""
diagnose_redirect.py
─────────────────────
Diagnostic tool — find out why /hr/employees redirects somewhere unexpected.

Usage:
    cd /var/www/hcperp     # or wherever your app lives
    python3 diagnose_redirect.py
"""
import sys
sys.path.insert(0, '.')

from index import app
from models import db, User, Employee


def main():
    with app.app_context():
        print("=" * 70)
        print("HCP-ERP: /hr/employees redirect diagnostic")
        print("=" * 70)

        # 1. Check route registration
        print("\n[1/4] Registered routes for /hr/employees:")
        found = False
        for rule in sorted(app.url_map.iter_rules(), key=lambda r: r.rule):
            if rule.rule == '/hr/employees':
                methods = sorted(rule.methods - {'HEAD','OPTIONS'})
                print(f"  ✓ {methods}  {rule.rule}  →  {rule.endpoint}")
                found = True
        if not found:
            print("  ✗ NO route registered at /hr/employees! That's the bug.")
            print("    Check that 'hr' blueprint is registered in index.py.")
            return

        # 2. Make actual unauthenticated request
        print("\n[2/4] Unauthenticated request to /hr/employees:")
        client = app.test_client()
        resp = client.get('/hr/employees', follow_redirects=False)
        print(f"  Status: {resp.status_code}")
        loc = resp.headers.get('Location')
        if loc:
            print(f"  Location header: {loc}")
            if '/login' in loc:
                print("  → Expected: redirects to /login (because not authenticated)")
            elif '/hr/masters' in loc:
                print("  ⚠  BUG: /hr/employees is redirecting to /hr/masters!")
                print("     Check hr_routes.py line 142 — there must be a redirect there.")
                return
            else:
                print(f"  ⚠  UNEXPECTED redirect location: {loc}")

        # 3. Authenticated request (auto-login as first admin user)
        print("\n[3/4] Authenticated request (as admin):")
        admin = User.query.filter_by(role='admin').first() or User.query.first()
        if not admin:
            print("  ✗ No users in DB — cannot test authenticated flow.")
            return
        print(f"  Test user: {admin.username} (role: {admin.role}, id: {admin.id})")

        # Check permissions
        from permissions import get_perm
        with app.test_request_context('/'):
            from flask_login import login_user
            login_user(admin)
            perm = get_perm('hr_employees')
            print(f"  Permission object: {perm}")
            if perm:
                print(f"  can_view: {perm.can_view}")
                if not perm.can_view:
                    print("  ⚠  User has NO can_view permission for hr_employees module!")
                    print("     This is why /hr/employees redirects — go to:")
                    print("     /users → Edit your user → Grant 'View' on HR Employees module")
            else:
                print("  ⚠  No permission row exists for module 'hr_employees'!")
                print("     Run: python3 -c 'from permissions import seed_permissions; seed_permissions()'")
                print("     Or visit /seed-modules in your browser.")

        # Now test full request as that admin
        with client.session_transaction() as sess:
            sess['_user_id'] = str(admin.id)
            sess['_fresh']   = True
        resp = client.get('/hr/employees', follow_redirects=False)
        print(f"\n  Logged-in request status: {resp.status_code}")
        loc = resp.headers.get('Location')
        if resp.status_code == 200:
            print("  ✓ SUCCESS — page renders for logged-in admin")
        elif resp.status_code == 302:
            print(f"  ⚠  REDIRECTED to: {loc}")
            print("     This is the bug! Now check why:")
            if loc and '/login' in loc:
                print("     → Session not loading. Try clearing browser cookies.")
            elif loc and '/dashboard' in loc:
                print("     → Permission check failed (perm.can_view = False).")
            elif loc and '/hr/masters' in loc:
                print("     → /hr/employees route itself has a redirect — check hr_routes.py")
        elif resp.status_code == 500:
            print("  ⚠  500 error — exception in route handler")
            print(f"  Body: {resp.get_data(as_text=True)[:500]}")

        # 4. Check Employee table count
        print("\n[4/4] Employee table check:")
        try:
            count = Employee.query.count()
            print(f"  ✓ Employee table has {count} rows")
        except Exception as e:
            print(f"  ✗ Employee table query FAILED: {type(e).__name__}: {e}")
            print("     This causes 500 → maybe Flask falls back somewhere unexpected.")

        print("\n" + "=" * 70)
        print("Diagnostic complete.")
        print("=" * 70)


if __name__ == '__main__':
    main()
