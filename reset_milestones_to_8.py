"""
reset_milestones_to_8.py
────────────────────────
AGGRESSIVE CLEANUP: Sirf yeh 8 milestones rakhta hai, baaki sab DELETE:

  1. BOM
  2. Ingredients List & Marketing Sheet
  3. Quotation
  4. Packing Material
  5. Artwork / Design
  6. Artwork QC Approval
  7. FDA
  8. Barcode

Kya karta hai:
  - npd_milestone_templates table me sirf yeh 8 rakhta hai
  - Har project ke milestone_masters me:
      * Jo rows in 8 types me nahi hain → DELETE (related logs bhi delete)
      * Jo 8 types missing hain → add kare (deselected by default)
      * Maintain karoga is_selected / status / notes / attachments as-is
        agar already set hain — yeh sirf orphan rows nikalta hai

⚠️  WARNING: Purani rows pe jo bhi notes/attachments/logs hai sab DELETE
    ho jaayega. Agar preserve karna ho to pehle backup lo.

Usage:
    python reset_milestones_to_8.py          # dry-run — sirf dikhayega
    python reset_milestones_to_8.py --apply  # actually delete karega
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app, db
from models.npd import NPDProject, MilestoneMaster, NPDMilestoneTemplate, MilestoneLog

APPLY = '--apply' in sys.argv

# EXACTLY these 8 milestones — no more, no less
CORRECT = [
    # (milestone_type,      title,                                 icon,  sort)
    ('bom',                 'BOM',                                 '📄',  1),
    ('ingredients',         'Ingredients List & Marketing Sheet',  '📋',  2),
    ('quotation',           'Quotation',                           '💰',  3),
    ('packing_material',    'Packing Material',                    '📦',  4),
    ('artwork',             'Artwork / Design',                    '🎨',  5),
    ('artwork_qc',          'Artwork QC Approval',                 '✅',  6),
    ('fda',                 'FDA',                                 '🏛️', 7),
    ('barcode',             'Barcode',                             '🔢',  8),
]
CORRECT_TYPES = {r[0] for r in CORRECT}
CORRECT_MAP   = {r[0]: r for r in CORRECT}


def main():
    with app.app_context():
        mode = "APPLY" if APPLY else "DRY-RUN"
        print(f"\n{'='*70}")
        print(f"  RESET MILESTONES TO 8   [{mode}]")
        print(f"{'='*70}\n")

        # ── STEP 1: Clean npd_milestone_templates ──
        print("STEP 1: Template master — sirf 8 correct milestones rakhe")
        print("-" * 70)

        all_templates = NPDMilestoneTemplate.query.all()
        del_tpl = 0
        for t in all_templates:
            if t.milestone_type not in CORRECT_TYPES:
                print(f"   ❌ DELETE template: {t.milestone_type} — {t.title}")
                if APPLY:
                    db.session.delete(t)
                del_tpl += 1

        # Ensure all 8 correct templates exist
        existing_tpl_types = {t.milestone_type for t in all_templates if t.milestone_type in CORRECT_TYPES}
        add_tpl = 0
        for mtype, title, icon, sort in CORRECT:
            if mtype not in existing_tpl_types:
                print(f"   ➕ INSERT template: {mtype} — {title}")
                if APPLY:
                    db.session.add(NPDMilestoneTemplate(
                        milestone_type   = mtype,
                        title            = title,
                        icon             = icon,
                        applies_to       = 'both',
                        default_selected = True,
                        is_mandatory     = False,
                        sort_order       = sort,
                        is_active        = True,
                    ))
                add_tpl += 1
            else:
                # Update title/icon/sort for existing correct templates
                existing = next(t for t in all_templates if t.milestone_type == mtype)
                changed = False
                if existing.title != title:
                    changed = True
                    if APPLY: existing.title = title
                if existing.icon != icon:
                    changed = True
                    if APPLY: existing.icon = icon
                if existing.sort_order != sort:
                    changed = True
                    if APPLY: existing.sort_order = sort
                if not existing.is_active:
                    changed = True
                    if APPLY: existing.is_active = True
                if changed:
                    print(f"   ✏️  UPDATE template: {mtype} — {title} (sort={sort})")

        if APPLY:
            db.session.flush()
        print(f"\n  → {del_tpl} template(s) deleted, {add_tpl} inserted")

        # ── STEP 2: Clean milestone_masters for every project ──
        print(f"\n\nSTEP 2: Har project ke milestone_masters clean karo")
        print("-" * 70)

        projects = NPDProject.query.filter_by(is_deleted=False).all()
        total_del_rows  = 0
        total_del_logs  = 0
        total_add_rows  = 0
        projects_touched = 0

        for p in projects:
            rows = MilestoneMaster.query.filter_by(project_id=p.id)\
                                         .order_by(MilestoneMaster.sort_order, MilestoneMaster.id)\
                                         .all()
            if not rows:
                continue

            bad_rows  = [r for r in rows if r.milestone_type not in CORRECT_TYPES]
            good_types = {r.milestone_type for r in rows if r.milestone_type in CORRECT_TYPES}
            missing_types = CORRECT_TYPES - good_types

            if not bad_rows and not missing_types:
                continue  # already clean

            projects_touched += 1
            print(f"\n  📁 {p.code} — {p.product_name}")

            # Delete bad rows (and their logs)
            for r in bad_rows:
                logs = MilestoneLog.query.filter_by(milestone_id=r.id).all()
                sel = '✓' if r.is_selected else '✗'
                print(f"     ❌ DELETE  [{sel}] id={r.id} {r.milestone_type:<22} status={r.status:<10} "
                      f"({len(logs)} log{'s' if len(logs)!=1 else ''}) — {r.title}")
                if APPLY:
                    for lg in logs:
                        db.session.delete(lg)
                    db.session.delete(r)
                total_del_rows += 1
                total_del_logs += len(logs)

            # Add missing correct rows
            for mtype in missing_types:
                _, title, _, sort = CORRECT_MAP[mtype]
                print(f"     ➕ ADD     {mtype:<22} — {title}")
                if APPLY:
                    db.session.add(MilestoneMaster(
                        project_id    = p.id,
                        milestone_type= mtype,
                        title         = title,
                        sort_order    = sort,
                        is_selected   = False,  # user selects later in form
                        status        = 'pending',
                    ))
                total_add_rows += 1

            if APPLY:
                p.milestone_master_created = True

        if APPLY:
            db.session.commit()

        # ── Summary ──
        print(f"\n\n{'='*70}")
        print(f"  SUMMARY")
        print(f"{'='*70}")
        print(f"  Templates deleted:      {del_tpl}")
        print(f"  Templates inserted:     {add_tpl}")
        print(f"  Projects touched:       {projects_touched} / {len(projects)}")
        print(f"  Project rows deleted:   {total_del_rows}  (+ {total_del_logs} related logs)")
        print(f"  Project rows added:     {total_add_rows}")

        if APPLY:
            print(f"\n  ✅ Changes committed. App restart karo, phir edit form me jao.")
        else:
            print(f"\n  ℹ️  Dry-run only. Agar output theek lage to re-run with --apply")
        print()


if __name__ == '__main__':
    main()
