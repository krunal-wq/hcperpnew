"""
force_sync_milestones.py
────────────────────────
Aapke DB me milestone_type column me CORRECT value hai (e.g. 'ingredients',
'bom', 'quotation') lekin `title` column me galat purane labels hain
(Brief Received, Initial Formulation, Client Sample Sent, Client Feedback).
Yani kisi purani migration ne type update kar diya tha but title update
karna bhool gayi.

Is script:

  1. Har MilestoneMaster row ka title force-update karta hai as per
     current milestone_type. Agar type='ingredients' hai, title automatic
     'Ingredients List & Marketing Sheet' ho jaayega.
  
  2. Agar kisi project me same milestone_type ki DO rows hain (duplicates),
     to script ek row rakhega (jisme activity zyada ho — approved/data)
     aur doosri delete kar dega. Logs merge ho jaayenge.

  3. Jis row ka is_selected=NULL hai, usse 0 kar dega (False) taaki
     display me consistent behaviour rahe.

  4. Saare invalid milestone_type wale rows (jo 8 correct me nahi) bhi
     delete kar dega.

Run:
    python force_sync_milestones.py            # dry-run
    python force_sync_milestones.py --apply    # actually save
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app, db
from models.npd import NPDProject, MilestoneMaster, NPDMilestoneTemplate, MilestoneLog

APPLY = '--apply' in sys.argv

CORRECT = {
    'bom':              ('BOM',                                '📄',  1),
    'ingredients':      ('Ingredients List & Marketing Sheet', '📋',  2),
    'quotation':        ('Quotation',                          '💰',  3),
    'packing_material': ('Packing Material',                   '📦',  4),
    'artwork':          ('Artwork / Design',                   '🎨',  5),
    'artwork_qc':       ('Artwork QC Approval',                '✅',  6),
    'fda':              ('FDA',                                '🏛️', 7),
    'barcode':          ('Barcode',                            '🔢',  8),
}


def activity_score(m):
    """Higher score = more activity on this row → we keep this one when dedup."""
    score = 0
    if m.status == 'approved':   score += 100
    if m.status == 'in_progress': score += 50
    if m.approved_by:            score += 20
    if m.approved_at:            score += 20
    if m.completed_at:           score += 15
    if m.notes:                  score += 10
    if m.attachments:            score += 10
    if m.target_date:            score += 3
    if m.assigned_to:            score += 3
    logs = MilestoneLog.query.filter_by(milestone_id=m.id).count()
    score += logs * 5
    if m.is_selected:            score += 1
    return score


def main():
    with app.app_context():
        mode = "APPLY" if APPLY else "DRY-RUN"
        print(f"\n{'='*70}")
        print(f"  FORCE-SYNC MILESTONE TITLES   [{mode}]")
        print(f"{'='*70}\n")

        # ── STEP 0: Sync template master ──
        print("STEP 0: Template master sync")
        print("-" * 70)
        tmpls = NPDMilestoneTemplate.query.all()
        valid_types = set(CORRECT.keys())
        for t in tmpls:
            if t.milestone_type not in valid_types:
                print(f"   ❌ DELETE template: {t.milestone_type} — {t.title}")
                if APPLY: db.session.delete(t)

        existing = {t.milestone_type: t for t in tmpls if t.milestone_type in valid_types}
        for mtype, (title, icon, sort) in CORRECT.items():
            if mtype in existing:
                t = existing[mtype]
                if t.title != title or t.icon != icon or t.sort_order != sort or not t.is_active:
                    print(f"   ✏️  UPDATE template: {mtype} → title='{title}' sort={sort}")
                    if APPLY:
                        t.title = title; t.icon = icon; t.sort_order = sort; t.is_active = True
            else:
                print(f"   ➕ INSERT template: {mtype} — {title}")
                if APPLY:
                    db.session.add(NPDMilestoneTemplate(
                        milestone_type=mtype, title=title, icon=icon,
                        applies_to='both', default_selected=True,
                        is_mandatory=False, sort_order=sort, is_active=True,
                    ))
        if APPLY: db.session.flush()

        # ── STEP 1: Per-project cleanup ──
        print(f"\n\nSTEP 1: Per-project row cleanup")
        print("-" * 70)

        projects = NPDProject.query.filter_by(is_deleted=False).all()
        stats = {'invalid_deleted':0, 'duplicates_deleted':0,
                 'titles_fixed':0, 'sort_fixed':0, 'is_sel_fixed':0,
                 'logs_merged':0, 'rows_added':0, 'projects_touched':0}

        for p in projects:
            rows = MilestoneMaster.query.filter_by(project_id=p.id).all()
            if not rows:
                continue

            touched = False

            # 1a. Delete rows with invalid milestone_type
            for r in list(rows):
                if r.milestone_type not in valid_types:
                    logs = MilestoneLog.query.filter_by(milestone_id=r.id).all()
                    print(f"  {p.code} ❌ DELETE invalid type: id={r.id} type={r.milestone_type} ({len(logs)} logs)")
                    if APPLY:
                        for lg in logs: db.session.delete(lg)
                        db.session.delete(r)
                    rows.remove(r)
                    stats['invalid_deleted'] += 1
                    touched = True

            # 1b. Group by milestone_type — dedupe duplicates
            by_type = {}
            for r in rows:
                by_type.setdefault(r.milestone_type, []).append(r)

            for mtype, group in by_type.items():
                if len(group) > 1:
                    # Keep highest-activity row, delete rest (move logs first)
                    group.sort(key=activity_score, reverse=True)
                    winner = group[0]
                    losers = group[1:]
                    for loser in losers:
                        logs = MilestoneLog.query.filter_by(milestone_id=loser.id).all()
                        print(f"  {p.code} 🔀 DEDUP  type={mtype}: keep id={winner.id}, delete id={loser.id} (move {len(logs)} logs)")
                        if APPLY:
                            for lg in logs:
                                lg.milestone_id = winner.id
                            db.session.flush()
                            db.session.delete(loser)
                        stats['duplicates_deleted'] += 1
                        stats['logs_merged'] += len(logs)
                        touched = True

            # 1c. Fix title / sort_order / is_selected on the remaining rows
            rows = MilestoneMaster.query.filter_by(project_id=p.id).all() if APPLY else \
                   [r for r in rows if r.milestone_type in valid_types]  # refresh in apply mode

            for r in rows:
                if r.milestone_type not in valid_types:
                    continue
                correct_title, _, correct_sort = CORRECT[r.milestone_type]
                if r.title != correct_title:
                    print(f"  {p.code} ✏️  FIX title: id={r.id} type={r.milestone_type}  '{r.title}' → '{correct_title}'")
                    if APPLY: r.title = correct_title
                    stats['titles_fixed'] += 1
                    touched = True
                if r.sort_order != correct_sort:
                    if APPLY: r.sort_order = correct_sort
                    stats['sort_fixed'] += 1
                    touched = True
                if r.is_selected is None:
                    if APPLY: r.is_selected = False
                    stats['is_sel_fixed'] += 1
                    touched = True

            # 1d. Add missing milestone types for this project
            present = {r.milestone_type for r in rows if r.milestone_type in valid_types}
            for mtype, (title, _, sort) in CORRECT.items():
                if mtype not in present:
                    print(f"  {p.code} ➕ ADD     {mtype}: {title}")
                    if APPLY:
                        db.session.add(MilestoneMaster(
                            project_id=p.id, milestone_type=mtype,
                            title=title, sort_order=sort,
                            is_selected=False, status='pending',
                        ))
                    stats['rows_added'] += 1
                    touched = True

            if touched:
                stats['projects_touched'] += 1
                if APPLY:
                    p.milestone_master_created = True

        if APPLY:
            db.session.commit()

        # ── Summary ──
        print(f"\n\n{'='*70}")
        print(f"  SUMMARY")
        print(f"{'='*70}")
        print(f"  Projects touched:          {stats['projects_touched']} / {len(projects)}")
        print(f"  Invalid-type rows deleted: {stats['invalid_deleted']}")
        print(f"  Duplicate rows deleted:    {stats['duplicates_deleted']}")
        print(f"  Logs migrated to winner:   {stats['logs_merged']}")
        print(f"  Titles fixed:              {stats['titles_fixed']}")
        print(f"  sort_order fixed:          {stats['sort_fixed']}")
        print(f"  is_selected NULL → 0:      {stats['is_sel_fixed']}")
        print(f"  Missing rows added:        {stats['rows_added']}")

        if APPLY:
            print(f"\n  ✅ Changes committed. Ab refresh karo page aur Milestones tab dekho.")
        else:
            print(f"\n  ℹ️  Dry-run. Output verify karke --apply se actually chalao.")
        print()


if __name__ == '__main__':
    main()
