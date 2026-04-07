"""
clean_for_testing.py — Sirf Admin + Master data rakho, baaki sab clean karo
Run: python clean_for_testing.py
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; E = "\033[0m"
def ok(m):   print(f"  {G}✅ {m}{E}")
def warn(m): print(f"  {Y}⚠️  {m}{E}")
def err(m):  print(f"  {R}❌ {m}{E}")
def step(m): print(f"\n{B}── {m}{E}")

try:
    from config import Config
    import pymysql
    from urllib.parse import unquote_plus
    url = Config.SQLALCHEMY_DATABASE_URI
    m = re.match(r'mysql\+pymysql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+)', url)
    if not m:
        err("DATABASE_URI sahi nahi hai"); sys.exit(1)
    DB_USER, DB_PASS_ENC, DB_HOST, DB_PORT, DB_NAME = m.groups()
    DB_PASS = unquote_plus(DB_PASS_ENC)
    DB_PORT = int(DB_PORT or 3306)
except Exception as e:
    err(f"Config load failed: {e}"); sys.exit(1)

con = pymysql.connect(host=DB_HOST, port=DB_PORT, user=DB_USER,
    password=DB_PASS, database=DB_NAME, charset='utf8mb4', autocommit=False)
cur = con.cursor()

print(f"\n{'='*62}")
print(f"  {B}CLEAN FOR TESTING — DATA RESET SCRIPT{E}")
print(f"{'='*62}")
print(f"\n  {R}YEH SCRIPT TRANSACTION DATA DELETE KAREGA!{E}")

confirm = input("\n  Aage badhna hai? (yes likhkar Enter dabao): ").strip().lower()
if confirm != 'yes':
    print(f"\n  {Y}Script cancel.{E}\n"); sys.exit(0)

# Disable FK checks globally
cur.execute("SET FOREIGN_KEY_CHECKS=0")
con.commit()

def tbl_exists(t):
    cur.execute("SHOW TABLES LIKE %s", (t,))
    return bool(cur.fetchone())

def clean(table, where=None, params=None):
    if not tbl_exists(table):
        warn(f"{table} — nahi mila, skip"); return
    try:
        if where:
            cur.execute(f"DELETE FROM `{table}` WHERE {where}", params or [])
        else:
            cur.execute(f"DELETE FROM `{table}`")
        con.commit()
        ok(f"{table} — {cur.rowcount} rows deleted")
    except Exception as e:
        con.rollback(); err(f"{table} — {e}")

# STEP 1: Users — sirf admin/master rakhenge
step("STEP 1: Users check kar raha hai...")
cur.execute("SELECT id, username, role, full_name FROM users ORDER BY id")
all_users = cur.fetchall()
print(f"\n  Current users ({len(all_users)}):")
keep_ids, delete_ids = [], []
for uid, uname, role, fname in all_users:
    keep = role in ('admin', 'master', 'superadmin')
    tag  = f"{G}KEEP  {E}" if keep else f"{R}DELETE{E}"
    print(f"     [{tag}] ID:{uid} | {uname} | role:{role} | {fname}")
    (keep_ids if keep else delete_ids).append(uid)

if delete_ids:
    ph = ','.join(['%s'] * len(delete_ids))
    cur.execute(f"DELETE FROM users WHERE id IN ({ph})", delete_ids)
    con.commit()
    ok(f"{len(delete_ids)} users deleted, {len(keep_ids)} kept")
else:
    ok("Sirf admin users hain — kuch delete nahi kiya")

# STEP 2: Leads
step("STEP 2: Leads aur related data...")
for t in ['lead_activity_logs','lead_discussions','lead_attachments',
          'lead_notes','lead_reminders','lead_contributions','wish_logs','leads']:
    clean(t)

# STEP 3: Clients
step("STEP 3: Clients...")
for t in ['client_addresses','client_brands','client_masters','customers','customer_addresses']:
    clean(t)

# STEP 4: NPD/EPD Projects
step("STEP 4: NPD/EPD Projects aur related data...")
for t in ['npd_activity_logs','npd_comments','npd_notes','npd_formulations',
          'npd_packing_materials','npd_artworks','milestone_logs','milestone_masters',
          'npd_projects','office_dispatch_items','office_dispatch_tokens',
          'rd_projects','rd_trials','rd_test_results']:
    clean(t)

# STEP 5: Sample Orders, Quotations
step("STEP 5: Sample Orders, Quotations...")
for t in ['sample_orders','quotations']:
    clean(t)

# STEP 6: Employees + HR
step("STEP 6: Employees aur HR transaction data...")
for t in ['attendance','raw_punch_logs','salary_components','payroll_months',
          'employee_leaves','payroll_details','leave_balances',
          'compoff_requests','employees']:
    clean(t)

# STEP 7: Contractors
step("STEP 7: Contractors...")
clean('contractors')

# STEP 8: Logs
step("STEP 8: Logs aur misc data...")
for t in ['audit_logs','login_logs','approval_requests','notification_logs','user_grid_configs']:
    clean(t)

# Re-enable FK checks
cur.execute("SET FOREIGN_KEY_CHECKS=1")
con.commit()
cur.close()
con.close()

print(f"\n{'='*62}")
print(f"  {G}{B}CLEAN COMPLETE!{E}")
print(f"{'='*62}")
print(f"""
  Bacha hai:  Admin/Master users, Masters, HR Rules,
              NPD Templates, Permissions, Email Templates

  Delete hua: Leads, Clients, NPD Projects, Employees,
              Attendance, Quotations, Contractors, Logs

  Ab server restart karo: {B}python index.py{E}
""")
