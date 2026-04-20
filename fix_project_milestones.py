"""
fix_project_milestones.py — Milestone data cleanup aur diagnostic tool

Problem: Kuch projects me purani milestone rows (Brief Received, Initial
Formulation, Client Sample Sent, Client Feedback, etc.) milestone_masters
table me padi hain jo current template se match nahi karti. Yeh Milestones
tab me galat cheezein dikha deti hain.

Yeh script:
  1. npd_milestone_templates table ko correct 8 milestones tak rakhti hai
  2. Saare projects ke milestone_masters rows scan karti hai
  3. Jo rows current templates me nahi hain, unhe DELETE karti hai
     (sirf rows jahan no activity hui — status='pending', no attachments,
      no notes, no approval — to purani usage ka data preserve rahe)
  4. Active rows (jinme kaam hua hai) ko sirf deselect karti hai — data
     preserve rahe for audit

Run karne ka tareeka:
    python fix_project_milestones.py              # dry-run (kuch change nahi)
    python fix_project_milestones.py --apply      # actual save
    python fix_project_milestones.py --verbose    # pura detail dekhne ke liye
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app, db
from models.npd import NPDProject, MilestoneMaster, NPDMilestoneTemplate, MilestoneLog

APPLY   = '--apply'   in sys.argv
VERBOSE = '--verbose' in sys.argv

# The only 8 milestones we want (matches fix_milestones.py in your project)
CORRECT_MILESTONES = [
    ('bom',              'BOM',                                '📄',  1),
    ('ingredients',      'Ingredients List & Marketing Sheet', '📋',  2),
    ('quotation',        'Quotation',                          '💰',  3),
    ('packing_material', 'Packing Material',                   '📦',  4),
    ('artwork',          'Artwork / Design',                   '🎨',  5),
    ('artwork_qc',       'Artwork QC Approval',                '✅',  6),
    ('fda',              'FDA',                                '🏛️', 7),
    ('barcode',          'Barcode',                            '🔢',  8),
]
CORRECT_TYPES = {r[0] for r in CORRECT_MILESTONES}


def has_activity(ms):
    """True if this milestone row has any meaningful data we should preserve."""
    if ms.status and ms.status not in ('pending', ''):
        return True
    if ms.attachments:
        return True
    if ms.notes:
        return True
    if ms.approved_by or ms.approved_at or ms.completed_at:
        return True
    # Check if any logs attached
    log_count = MilestoneLog.query.filter_by(milestone_id=ms.id).count()
    if log_count > 0:
        return True
    return False


def main():
    with app.app_context():
        mode = "APPLY (changes will be saved)" if APPLY else "DRY-RUN (no changes)"
        print(f"\n{'='*70}")
        print(f"  MILESTONE DIAGNOSTIC + CLEANUP   [{mode}]")
        print(f"{'='*70}\n")

        # ── STEP 1: Fix npd_milestone_templates ──
        print("STEP 1: Template master cleanup")
        print("-" * 70)
        templates = NPDMilestoneTemplate.query.all()
        print(f"Current templates in DB: {len(templates)}")
        to_delete = []
        for t in templates:
            keep = t.milestone_type in CORRECT_TYPES
            mark = "✅ keep" if keep else "❌ delete"
            print(f"   {mark}  {t.milestone_type:<22} — {t.title}")
            if not keep:
                to_delete.append(t)

        # Insert missing correct ones
        existing_types = {t.milestone_type for t in templates}
        to_insert = []
        for mtype, title, icon, sort in CORRECT_MILESTONES:
            if mtype not in existing_types:
                to_insert.append((mtype, title, icon, sort))
                print(f"   ➕ insert  {mtype:<22} — {title}")

        print(f"\n  → {len(to_delete)} templates to delete, {len(to_insert)} to insert")

        if APPLY:
            for t in to_delete:
                db.session.delete(t)
            for mtype, title, icon, sort in to_insert:
                db.session.add(NPDMilestoneTemplate(
                    milestone_type  = mtype,
                    title           = title,
                    icon            = icon,
                    applies_to      = 'both',
                    default_selected= True,
                    is_mandatory    = False,
                    sort_order      = sort,
                    is_active       = True,
                ))
            db.session.commit()
            print("  ✅ Template cleanup committed")

        # ── STEP 2: Project-by-project milestone cleanup ──
        print(f"\n\nSTEP 2: Per-project milestone cleanup")
        print("-" * 70)

        projects = NPDProject.query.filter_by(is_deleted=False).all()
        total_delete  = 0
        total_deselect= 0
        total_ok      = 0

        for p in projects:
            all_ms = MilestoneMaster.query.filter_by(project_id=p.id)\
                                          .order_by(MilestoneMaster.sort_order).all()
            if not all_ms:
                continue

            bad_rows = [m for m in all_ms if m.milestone_type not in CORRECT_TYPES]
            good_rows = [m for m in all_ms if m.milestone_type in CORRECT_TYPES]

            if not bad_rows and not VERBOSE:
                total_ok += 1
                continue

            print(f"\n  📁 {p.code} — {p.product_name}")
            print(f"     Total rows: {len(all_ms)} ({len(good_rows)} valid, {len(bad_rows)} invalid)")

            if VERBOSE:
                for m in good_rows:
                    sel = '✓' if m.is_selected else '✗'
                    print(f"       [{sel}] valid   — {m.milestone_type:<22} [{m.status}] {m.title}")

            for m in bad_rows:
                sel = '✓' if m.is_selected else '✗'
                if has_activity(m):
                    # Has real data — just deselect, don't delete
                    print(f"       [{sel}] KEEP    — {m.milestone_type:<22} [{m.status}] {m.title}  (has activity → deselect only)")
                    if APPLY and m.is_selected:
                        m.is_selected = False
                    total_deselect += 1
                else:
                    # No real data — safe to delete
                    print(f"       [{sel}] DELETE  — {m.milestone_type:<22} [{m.status}] {m.title}  (no activity → remove row)")
                    if APPLY:
                        db.session.delete(m)
                    total_delete += 1

            # Check missing correct milestones for this project
            present_types = {m.milestone_type for m in good_rows}
            missing = [t for t in CORRECT_MILESTONES if t[0] not in present_types]
            if missing:
                print(f"     ⚠️  {len(missing)} standard milestone(s) missing — will add as deselected:")
                for mtype, title, icon, sort in missing:
                    print(f"       ➕ add     — {mtype:<22} {title}")
                    if APPLY:
                        db.session.add(MilestoneMaster(
                            project_id    = p.id,
                            milestone_type= mtype,
                            title         = title,
                            sort_order    = sort,
                            is_selected   = False,   # off by default — user selects later
                            status        = 'pending',
                        ))

        if APPLY:
            db.session.commit()

        print(f"\n\n{'='*70}")
        print(f"  SUMMARY")
        print(f"{'='*70}")
        print(f"  Projects scanned:          {len(projects)}")
        print(f"  Projects already clean:    {total_ok}")
        print(f"  Bad rows to DELETE:        {total_delete}  (no activity on them)")
        print(f"  Bad rows to DESELECT:      {total_deselect}  (have activity — preserved)")

        if APPLY:
            print(f"\n  ✅ Changes committed to database.")
            print(f"  ➡️  Restart the app / refresh the Milestones tab.")
        else:
            print(f"\n  ℹ️  Dry-run only. Re-run with --apply to save.")
            print(f"     For per-row detail on clean projects, add --verbose.")
        print()


if __name__ == '__main__':
    main()
