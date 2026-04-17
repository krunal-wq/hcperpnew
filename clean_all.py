"""
╔══════════════════════════════════════════════════════════════════╗
║                FULL DATA CLEAN SCRIPT                            ║
║  Run:  python clean_all.py                                       ║
║  ✅  SAFE  — Users, Employees RAKHE JAAYENGE                     ║
║  ❌  DELETE — Baaki sab data                                     ║
╚══════════════════════════════════════════════════════════════════╝
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

G="\033[92m"; Y="\033[93m"; R="\033[91m"; C="\033[96m"; B="\033[1m"; E="\033[0m"
def ok(m):   print(f"  {G}✅ {m}{E}")
def warn(m): print(f"  {Y}⚠️  {m}{E}")
def info(m): print(f"  {C}ℹ️  {m}{E}")

print(f"\n{'='*55}")
print(f"  {R}{B}WARNING: FULL DATA CLEAN — PERMANENT DELETE{E}")
print(f"{'='*55}")
print(f"\n  {G}SAFE  : users, employees{E}")
print(f"  {R}DELETE: Clients, Leads, CRM, NPD, R&D,{E}")
print(f"  {R}        Attendance, Approvals, Audit Logs{E}\n")

ans = input(f"  {R}{B}Type YES to confirm: {E}").strip()
if ans != 'YES':
    info("Cancelled.")
    sys.exit(0)

try:
    from index import app
    from models import db
except Exception as e:
    print(f"  App load failed: {e}"); sys.exit(1)

with app.app_context():
    import pymysql
    uri = db.engine.url
    con = pymysql.connect(host=str(uri.host), port=int(uri.port or 3306),
        user=str(uri.username), password=str(uri.password),
        database=str(uri.database), charset='utf8mb4')
    cur = con.cursor()

    def clean(table, label=None):
        try:
            cur.execute(f"DELETE FROM `{table}`")
            con.commit()
            ok(f"{label or table}: {cur.rowcount} deleted")
        except Exception as ex:
            warn(f"{label or table}: {ex}")

    cur.execute("SET FOREIGN_KEY_CHECKS=0"); con.commit()

    print(f"\n  {B}── CLIENTS ──{E}")
    clean('client_brands',          'Client Brands')
    clean('client_addresses',       'Client Addresses')
    clean('client_masters',         'Client Masters')

    print(f"\n  {B}── LEADS / CRM ──{E}")
    clean('lead_activity_logs',     'Lead Activity Logs')
    clean('lead_contributions',     'Lead Contributions')
    clean('lead_reminders',         'Lead Reminders')
    clean('lead_notes',             'Lead Notes')
    clean('lead_discussions',       'Lead Discussions')
    clean('lead_attachments',       'Lead Attachments')
    clean('sample_orders',          'Sample Orders')
    clean('quotations',             'Quotations')
    clean('leads',                  'Leads')

    print(f"\n  {B}── NPD / R&D ──{E}")
    clean('office_dispatch_items',  'Office Dispatch Items')
    clean('office_dispatch_tokens', 'Office Dispatch Tokens')
    clean('npd_activity_logs',      'NPD Activity Logs')
    clean('npd_comments',           'NPD Comments')
    clean('npd_notes',              'NPD Notes')
    clean('npd_artworks',           'NPD Artworks')
    clean('npd_packing_materials',  'NPD Packing Materials')
    clean('npd_formulations',       'NPD Formulations')
    clean('milestone_logs',         'Milestone Logs')
    clean('milestone_masters',      'Milestone Masters')
    clean('npd_projects',           'NPD Projects')

    print(f"\n  {B}── ATTENDANCE ──{E}")
    clean('attendance',             'Attendance')
    clean('raw_punch_logs',         'Raw Punch Logs')

    print(f"\n  {B}── APPROVALS / AUDIT ──{E}")
    clean('approvals',              'Approvals')
    clean('audit_logs',             'Audit Logs')

    print(f"\n  {B}── PACKING ──{E}")
    clean('packing_entries',        'Packing Entries')

    cur.execute("SET FOREIGN_KEY_CHECKS=1"); con.commit()
    cur.close(); con.close()

    print(f"\n{'='*55}")
    print(f"  {G}{B}CLEAN COMPLETE! Users & Employees safe hain.{E}")
    print(f"  Server restart karo: python index.py")
    print(f"{'='*55}\n")
