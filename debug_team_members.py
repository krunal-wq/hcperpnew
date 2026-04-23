"""
debug_team_members.py — Quick diagnostic
Usage:
    python debug_team_members.py            # sab users ki list dikhao
    python debug_team_members.py <user_id>  # specific user ke liye test karo
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app
from models import db, Lead, User

def list_all_users():
    with app.app_context():
        users = User.query.filter(User.is_active == True).order_by(User.id).all()
        print("\n═══ Active Users ═══")
        print(f"{'ID':>4} | {'NAME':<35} | {'ROLE':<10} | EMAIL")
        print("─" * 90)
        for u in users:
            print(f"{u.id:>4} | {(u.full_name or '')[:35]:<35} | {(u.role or '')[:10]:<10} | {u.email or ''}")
        print()

# No arg -> just list users and exit
if len(sys.argv) < 2 or sys.argv[1].strip() in ('', '0'):
    print("Usage: python debug_team_members.py <user_id>")
    list_all_users()
    sys.exit(0)

try:
    test_uid = int(sys.argv[1])
except ValueError:
    print(f"'{sys.argv[1]}' is not a valid user ID.")
    list_all_users()
    sys.exit(1)

with app.app_context():
    user = db.session.get(User, test_uid)
    if not user:
        print(f"User id={test_uid} not found.")
        list_all_users()
        sys.exit(1)

    print(f"\n=== Testing visibility for: {user.full_name} (id={test_uid}, role={user.role}) ===\n")

    uid_str = str(test_uid)
    leads = Lead.query.filter_by(is_deleted=False).all()
    print(f"Total active leads in DB: {len(leads)}\n")
    print(f"{'ID':>4} | {'NAME':<25} | {'ASSIGNED':>8} | {'CREATED_BY':>10} | TEAM_MEMBERS (exact repr)")
    print("-" * 115)

    visible = 0
    for l in leads:
        tm = l.team_members or ""

        is_in_team = False
        reason = "NOT in any field"
        if l.assigned_to == test_uid:
            is_in_team = True; reason = "assigned_to"
        elif l.created_by == test_uid:
            is_in_team = True; reason = "created_by"
        elif tm == uid_str:
            is_in_team = True; reason = "team_members (single value)"
        elif f",{uid_str}," in f",{tm},":
            is_in_team = True; reason = "team_members (in comma list)"

        loose_match = bool(tm) and uid_str in tm
        marker = "[YES]" if is_in_team else ("[LOOSE]" if loose_match else "[NO] ")
        tm_repr = repr(tm)

        print(f"{l.id:>4} | {(l.contact_name or '')[:25]:<25} | {str(l.assigned_to or '-'):>8} | {str(l.created_by or '-'):>10} | {tm_repr}")
        extra = f"  (loose match succeeds but strict fails -- FORMAT ISSUE!)" if loose_match and not is_in_team else ""
        print(f"     {marker} {reason}{extra}")

        if is_in_team:
            visible += 1

    print("-" * 115)
    print(f"\nSUMMARY: {visible} / {len(leads)} leads visible to {user.full_name}")

    print(f"\n--- Suspicious rows (uid '{uid_str}' appears in team_members but strict logic FAILS): ---")
    mismatches = 0
    for l in leads:
        tm = l.team_members or ""
        if tm and uid_str in tm:
            strict = (
                l.assigned_to == test_uid or l.created_by == test_uid or
                tm == uid_str or f",{uid_str}," in f",{tm},"
            )
            if not strict:
                mismatches += 1
                print(f"  Lead #{l.id} ({l.contact_name}): team_members = {repr(tm)}")
    if mismatches == 0:
        print("  (none -- strict logic is not missing anything)")
