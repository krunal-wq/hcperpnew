"""
check_project_milestones.py — Specific project ke milestones DB state dikhata hai

Run:
    python check_project_milestones.py NPD-T001
    python check_project_milestones.py 19              # can pass project ID too
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app, db
from models.npd import NPDProject, MilestoneMaster, NPDMilestoneTemplate, MilestoneLog

if len(sys.argv) < 2:
    print("Usage: python check_project_milestones.py <project_code_or_id>")
    sys.exit(1)

arg = sys.argv[1].strip()

with app.app_context():
    # Resolve project
    if arg.isdigit():
        proj = NPDProject.query.get(int(arg))
    else:
        proj = NPDProject.query.filter_by(code=arg).first()

    if not proj:
        print(f"❌ Project not found: {arg}")
        sys.exit(1)

    print(f"\n{'='*70}")
    print(f"  PROJECT: {proj.code} — {proj.product_name}")
    print(f"  ID: {proj.id}   Type: {proj.project_type}   Status: {proj.status}")
    print(f"  milestone_master_created: {proj.milestone_master_created}")
    print(f"{'='*70}\n")

    # Show current NPDMilestoneTemplate (master list)
    print("── Current Template Master (NPDMilestoneTemplate) ──")
    tmpls = NPDMilestoneTemplate.query.filter_by(is_active=True)\
                                       .order_by(NPDMilestoneTemplate.sort_order).all()
    for t in tmpls:
        print(f"   {t.sort_order:>2}. [{t.milestone_type:<22}]  {t.icon} {t.title}")
    print()

    # All MilestoneMaster rows for this project
    print(f"── MilestoneMaster rows for this project ──")
    rows = MilestoneMaster.query.filter_by(project_id=proj.id)\
                                 .order_by(MilestoneMaster.sort_order,
                                           MilestoneMaster.id).all()
    print(f"Total rows in DB: {len(rows)}\n")
    if not rows:
        print("   (none)")
    else:
        print(f"   {'ID':>4}  {'sel':>4}  {'sort':>4}  {'type':<22}  {'status':<12}  title")
        print(f"   {'-'*4}  {'-'*4}  {'-'*4}  {'-'*22}  {'-'*12}  {'-'*30}")
        for r in rows:
            sel = '✓' if r.is_selected else '✗'
            acts = []
            if r.status and r.status != 'pending': acts.append(f"status={r.status}")
            if r.attachments: acts.append("files")
            if r.notes: acts.append("notes")
            if r.approved_by: acts.append("approved")
            logs_count = MilestoneLog.query.filter_by(milestone_id=r.id).count()
            if logs_count: acts.append(f"{logs_count}_logs")
            act_str = f"  [{', '.join(acts)}]" if acts else ""
            print(f"   {r.id:>4}  {sel:>4}  {r.sort_order:>4}  {r.milestone_type:<22}  {r.status:<12}  {r.title}{act_str}")

    # Selected-only count
    sel_count = sum(1 for r in rows if r.is_selected)
    print(f"\n   → {sel_count} rows with is_selected=True  (yeh Milestones tab me dikhega)")
    print()
