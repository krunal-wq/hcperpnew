"""
cleanup_non_rd_assignments.py
─────────────────────────────
One-time cleanup: deactivate any RDSubAssignment (and clear legacy
assigned_rd / assigned_rd_members token fields) that reference a User
who is NOT in the R&D department.

Run:
    python cleanup_non_rd_assignments.py          # dry-run (shows what would change)
    python cleanup_non_rd_assignments.py --apply  # actually apply the changes

Safe to re-run. Idempotent.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app, db
from models import User
from models.employee import Employee
from models.npd import NPDProject, RDSubAssignment

APPLY = '--apply' in sys.argv


def get_rd_user_ids():
    """Active users whose linked Employee is in the R&D department
    (matches all naming variations: R&D, R & D, Research and Development,
    RND, etc.)."""
    from models.rd_department import rd_department_filter, is_rd_department

    emps = Employee.query.filter(
        Employee.is_deleted == False,
        Employee.user_id.isnot(None),
        rd_department_filter(Employee),
    ).all()
    ids = set()
    for e in emps:
        if not is_rd_department(e.department):
            continue
        u = User.query.get(e.user_id)
        if u and u.is_active:
            ids.add(u.id)
    return ids


def main():
    with app.app_context():
        rd_ids = get_rd_user_ids()
        print(f"✔  {len(rd_ids)} active R&D users found: {sorted(rd_ids)}")
        print(f"Mode: {'APPLY (changes will be saved)' if APPLY else 'DRY-RUN (no changes)'}\n")

        # ── 1. Deactivate bad RDSubAssignment rows ─────────────────────
        bad_subs = RDSubAssignment.query.filter(
            RDSubAssignment.is_active == True,
            ~RDSubAssignment.user_id.in_(rd_ids) if rd_ids else True,
        ).all()

        print(f"── RDSubAssignment rows to deactivate: {len(bad_subs)}")
        for s in bad_subs:
            u = User.query.get(s.user_id)
            uname = (u.full_name or u.username) if u else f'user#{s.user_id}'
            proj = NPDProject.query.get(s.project_id)
            pcode = proj.code if proj else f'proj#{s.project_id}'
            print(f"   · {pcode:<12} variant={s.variant_code or '—':<6} user={uname}")
            if APPLY:
                s.is_active = False

        # ── 2. Clean legacy token fields on NPDProject ──────────────────
        print()
        projects = NPDProject.query.filter_by(is_deleted=False).all()
        cleaned_rd_members = 0
        cleared_assigned_rd = 0

        for p in projects:
            # 2a. assigned_rd_members (comma-separated u_<id> / emp_<id> / <id> tokens)
            if p.assigned_rd_members:
                tokens = [t.strip() for t in str(p.assigned_rd_members).split(',') if t.strip()]
                keep = []
                for tok in tokens:
                    keep_it = True
                    if tok.startswith('u_'):
                        try:
                            uid = int(tok[2:])
                            if uid not in rd_ids:
                                keep_it = False
                        except ValueError:
                            keep_it = False
                    elif tok.startswith('emp_'):
                        try:
                            eid = int(tok[4:])
                            emp = Employee.query.get(eid)
                            if not (emp and emp.user_id and emp.user_id in rd_ids):
                                keep_it = False
                        except ValueError:
                            keep_it = False
                    elif tok.isdigit():
                        # legacy plain emp id
                        emp = Employee.query.get(int(tok))
                        if not (emp and emp.user_id and emp.user_id in rd_ids):
                            keep_it = False
                    if keep_it:
                        keep.append(tok)

                new_val = ','.join(keep) if keep else None
                if new_val != p.assigned_rd_members:
                    print(f"   · {p.code}  assigned_rd_members: '{p.assigned_rd_members}'  →  '{new_val or ''}'")
                    cleaned_rd_members += 1
                    if APPLY:
                        p.assigned_rd_members = new_val

            # 2b. assigned_rd (single FK) — clear if user not in R&D
            if p.assigned_rd and p.assigned_rd not in rd_ids:
                u = User.query.get(p.assigned_rd)
                uname = (u.full_name or u.username) if u else f'user#{p.assigned_rd}'
                print(f"   · {p.code}  assigned_rd: {uname}  →  (cleared)")
                cleared_assigned_rd += 1
                if APPLY:
                    p.assigned_rd = None

        print(f"\n── assigned_rd_members rows cleaned: {cleaned_rd_members}")
        print(f"── assigned_rd (FK) rows cleared:    {cleared_assigned_rd}")

        if APPLY:
            db.session.commit()
            print("\n✅ Changes committed to database.")
        else:
            print("\nℹ️  Dry-run only. Re-run with --apply to save changes.")


if __name__ == '__main__':
    main()
