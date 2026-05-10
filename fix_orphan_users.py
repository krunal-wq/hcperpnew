"""
fix_orphan_users.py  (v2 — improved)
──────────────────────────────────────
Jo users kisi active employee se linked nahi hain unhe deactivate karo.

Logic:
  - Admin role → kabhi touch nahi karo
  - User ka employee exist karta hai aur active → keep active
  - User ka employee deleted hai → deactivate
  - User ka koi employee linked nahi → deactivate

Run: python fix_orphan_users.py
"""
from index import app
from models import db, User, Employee

with app.app_context():

    all_users = User.query.filter(User.role != 'admin').all()

    # Set of user_ids that have an ACTIVE linked employee
    active_emp_user_ids = set(
        row[0] for row in
        db.session.query(Employee.user_id)
        .filter(Employee.is_deleted == False, Employee.user_id.isnot(None))
        .all()
    )

    deactivated = []
    kept = []

    for u in all_users:
        if u.id in active_emp_user_ids:
            if not u.is_active:
                u.is_active = True
                kept.append(f"  Re-activated : {u.username} - {u.full_name}")
        else:
            if u.is_active:
                u.is_active = False
                deactivated.append(f"  Deactivated  : {u.username} - {u.full_name}")

    db.session.commit()

    print(f"\n{'='*55}")
    print(f"  RESULT: {len(deactivated)} deactivated, {len(kept)} re-activated")
    print(f"{'='*55}")

    if deactivated:
        print("\nDeactivated (no active employee):")
        for line in deactivated: print(line)

    if kept:
        print("\nRe-activated (has active employee):")
        for line in kept: print(line)

    print(f"\nDone! Ab ACP mein sirf active employees ke users dikhenge.")
