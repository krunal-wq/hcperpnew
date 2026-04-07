"""
fix_milestones.py — Milestone templates aur existing project milestones fix karo
Run: python fix_milestones.py

Kya karta hai:
1. npd_milestone_templates table — extra milestones delete, sirf correct 8 rakhega
2. milestone_masters table — existing projects ke extra milestone rows deactivate karega
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; E = "\033[0m"
def ok(m):   print(f"  {G}✅ {m}{E}")
def warn(m): print(f"  {Y}⚠️  {m}{E}")
def err(m):  print(f"  {R}❌ {m}{E}")

# ── Load DB config ──────────────────────────────────────────────────────────
try:
    from config import Config
    import pymysql
    from urllib.parse import unquote_plus
    url = Config.SQLALCHEMY_DATABASE_URI
    m = re.match(r'mysql\+pymysql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+)', url)
    if not m:
        err("config.py mein DATABASE_URI sahi nahi hai")
        sys.exit(1)
    DB_USER, DB_PASS_ENC, DB_HOST, DB_PORT, DB_NAME = m.groups()
    DB_PASS = unquote_plus(DB_PASS_ENC)
    DB_PORT = int(DB_PORT or 3306)
except Exception as e:
    err(f"Config load failed: {e}")
    sys.exit(1)

con = pymysql.connect(
    host=DB_HOST, port=DB_PORT,
    user=DB_USER, password=DB_PASS,
    database=DB_NAME, charset='utf8mb4'
)
cur = con.cursor()

print(f"\n{'='*60}")
print(f"  {B}MILESTONE FIX SCRIPT{E}")
print(f"{'='*60}\n")

# ── Correct 8 milestones ────────────────────────────────────────────────────
CORRECT = [
    # (milestone_type,   title,                                icon,  sort)
    ('bom',              'BOM',                                '📄',  1),
    ('ingredients',      'Ingredients List & Marketing Sheet', '📋',  2),
    ('quotation',        'Quotation',                          '💰',  3),
    ('packing_material', 'Packing Material',                   '📦',  4),
    ('artwork',          'Artwork / Design',                   '🎨',  5),
    ('artwork_qc',       'Artwork QC Approval',                '✅',  6),
    ('fda',              'FDA',                                '🏛️', 7),
    ('barcode',          'Barcode',                            '🔢',  8),
]
CORRECT_TYPES = {r[0] for r in CORRECT}

# ── STEP 1: Fix npd_milestone_templates ────────────────────────────────────
print(f"  {B}STEP 1: npd_milestone_templates fix kar raha hai...{E}")
try:
    # Delete all extra types
    cur.execute("SELECT milestone_type, title FROM npd_milestone_templates ORDER BY sort_order")
    existing = cur.fetchall()
    print(f"  Current templates ({len(existing)}):")
    for mtype, title in existing:
        status = "✅ KEEP" if mtype in CORRECT_TYPES else "❌ DELETE"
        print(f"     {status} — {mtype}: {title}")

    # Delete extras
    extra_types = [mtype for mtype, _ in existing if mtype not in CORRECT_TYPES]
    if extra_types:
        placeholders = ','.join(['%s'] * len(extra_types))
        cur.execute(f"DELETE FROM npd_milestone_templates WHERE milestone_type IN ({placeholders})", extra_types)
        con.commit()
        ok(f"{len(extra_types)} extra templates deleted")
    else:
        ok("No extra templates found")

    # Insert missing correct ones
    for mtype, title, icon, sort in CORRECT:
        cur.execute("SELECT id FROM npd_milestone_templates WHERE milestone_type=%s", (mtype,))
        row = cur.fetchone()
        if row:
            # Update title, icon, sort_order, is_active
            cur.execute(
                "UPDATE npd_milestone_templates SET title=%s, icon=%s, sort_order=%s, is_active=1 WHERE milestone_type=%s",
                (title, icon, sort, mtype)
            )
            ok(f"Updated: {mtype} — {title}")
        else:
            cur.execute(
                "INSERT INTO npd_milestone_templates (milestone_type, title, icon, applies_to, default_selected, is_mandatory, sort_order, is_active, created_by) VALUES (%s,%s,%s,'both',1,0,%s,1,1)",
                (mtype, title, icon, sort)
            )
            ok(f"Inserted: {mtype} — {title}")
    con.commit()

except Exception as e:
    err(f"Step 1 failed: {e}")

# ── STEP 2: Fix milestone_masters — deselect extra types ──────────────────
print(f"\n  {B}STEP 2: milestone_masters table — extra milestones deselect kar raha hai...{E}")
try:
    cur.execute("SHOW TABLES LIKE 'milestone_masters'")
    if not cur.fetchone():
        warn("milestone_masters table nahi mila — skip")
    else:
        placeholders = ','.join(['%s'] * len(CORRECT_TYPES))
        cur.execute(
            f"SELECT COUNT(*) FROM milestone_masters WHERE milestone_type NOT IN ({placeholders}) AND is_selected=1",
            list(CORRECT_TYPES)
        )
        count = cur.fetchone()[0]
        if count > 0:
            cur.execute(
                f"UPDATE milestone_masters SET is_selected=0 WHERE milestone_type NOT IN ({placeholders})",
                list(CORRECT_TYPES)
            )
            con.commit()
            ok(f"{count} extra milestone rows deselected from existing projects")
        else:
            ok("No extra selected milestones in projects")
except Exception as e:
    err(f"Step 2 failed: {e}")

cur.close()
con.close()

print(f"\n{'='*60}")
print(f"  {G}{B}✅ FIX COMPLETE!{E}")
print(f"{'='*60}")
print(f"\n  Ab server restart karo: {B}python index.py{E}\n")
