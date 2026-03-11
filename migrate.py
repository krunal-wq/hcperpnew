"""
╔══════════════════════════════════════════════════════════════════╗
║           ERPDEMO — MASTER MIGRATION SCRIPT                      ║
║                                                                  ║
║  Pehli baar: python setup.py  (packages + DB create)            ║
║  Phir:       python migrate.py (tables + columns + data)         ║
║                                                                  ║
║  ✅ Safe to run MULTIPLE TIMES                                    ║
║  ✅ Already existing tables/columns → SKIP                       ║
║  ✅ Already existing data → SKIP                                 ║
║  ✅ Missing cheez → CREATE / INSERT                              ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ── Colors ──
G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; C = "\033[96m"; B = "\033[1m"; E = "\033[0m"
def ok(m):   print(f"  {G}✅ {m}{E}")
def warn(m): print(f"  {Y}⚠️  {m}{E}")
def err(m):  print(f"  {R}❌ {m}{E}")
def step(m): print(f"\n{B}{C}── {m}{E}")

print(f"\n{'='*60}")
print(f"  {B}ERPDEMO — MASTER MIGRATION{E}")
print(f"{'='*60}")

# ── Load Flask app ──
try:
    from index import app
    from models import db
except Exception as e:
    err(f"App load failed: {e}")
    err("Pehle 'python setup.py' chalao!")
    sys.exit(1)

with app.app_context():

    import pymysql
    from sqlalchemy import text

    # DB connection for raw ALTER TABLE
    from config import Config
    url = Config.SQLALCHEMY_DATABASE_URI
    # Parse connection params from URL
    import re
    m = re.match(r'mysql\+pymysql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+)', url)
    if m:
        DB_USER, DB_PASS_ENC, DB_HOST, DB_PORT, DB_NAME = m.groups()
        from urllib.parse import unquote_plus
        DB_PASS = unquote_plus(DB_PASS_ENC)
        DB_PORT = int(DB_PORT or 3306)
    else:
        err("config.py mein DATABASE_URI sahi nahi hai")
        sys.exit(1)

    raw = pymysql.connect(
        host=DB_HOST, port=DB_PORT,
        user=DB_USER, password=DB_PASS,
        database=DB_NAME, charset='utf8mb4'
    )
    cur = raw.cursor()

    def table_exists(t):
        cur.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=%s", (t,))
        return cur.fetchone()[0] > 0

    def col_exists(t, c):
        cur.execute("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema=DATABASE() AND table_name=%s AND column_name=%s", (t, c))
        return cur.fetchone()[0] > 0

    def safe_add(table, col, defn):
        """Add column only if it doesn't exist."""
        if table_exists(table) and not col_exists(table, col):
            try:
                cur.execute(f"ALTER TABLE `{table}` ADD COLUMN `{col}` {defn}")
                raw.commit()
                print(f"     + {table}.{col}")
                return True
            except Exception as e:
                warn(f"Skip {table}.{col}: {e}")
        return False

    def safe_modify(table, col, defn):
        """Modify column type if exists."""
        if table_exists(table) and col_exists(table, col):
            try:
                cur.execute(f"ALTER TABLE `{table}` MODIFY COLUMN `{col}` {defn}")
                raw.commit()
            except: pass

    # ══════════════════════════════════════════════════════
    # STEP 1 — Create all tables
    # ══════════════════════════════════════════════════════
    step("STEP 1: Tables create kar raha hai...")
    db.create_all()
    ok("db.create_all() done — sari tables ready")

    # ══════════════════════════════════════════════════════
    # STEP 2 — Fix column types (MEDIUMTEXT for large data)
    # ══════════════════════════════════════════════════════
    step("STEP 2: Column types fix kar raha hai (MEDIUMTEXT)...")
    mediumtext = [
        ('employees', 'profile_photo'),
        ('employees', 'qr_code_base64'),
        ('employees', 'documents_json'),
    ]
    for tbl, col in mediumtext:
        safe_modify(tbl, col, 'MEDIUMTEXT')
    ok("MEDIUMTEXT columns fixed")

    # ══════════════════════════════════════════════════════
    # STEP 3 — Missing columns: employees
    # ══════════════════════════════════════════════════════
    step("STEP 3: employees table — missing columns add kar raha hai...")
    emp_cols = [
        # Basic
        ('blood_group',             'VARCHAR(10)'),
        ('marital_status',          'VARCHAR(20)'),
        ('marriage_anniversary',    'DATE'),
        ('linkedin',                'VARCHAR(200)'),
        ('facebook',                'VARCHAR(200)'),
        ('remark',                  'TEXT'),
        # Address
        ('address',                 'TEXT'),
        ('city',                    'VARCHAR(100)'),
        ('state',                   'VARCHAR(100)'),
        ('country',                 "VARCHAR(100) DEFAULT 'India'"),
        ('zip_code',                'VARCHAR(20)'),
        # KYC
        ('aadhar_number',           'VARCHAR(20)'),
        ('pan_number',              'VARCHAR(20)'),
        ('passport_number',         'VARCHAR(30)'),
        ('passport_expiry',         'DATE'),
        ('driving_license',         'VARCHAR(30)'),
        ('dl_expiry',               'DATE'),
        ('uan_number',              'VARCHAR(20)'),
        ('esic_number',             'VARCHAR(20)'),
        ('nationality',             "VARCHAR(50) DEFAULT 'Indian'"),
        ('religion',                'VARCHAR(50)'),
        ('caste',                   'VARCHAR(50)'),
        ('physically_handicapped',  'TINYINT(1) DEFAULT 0'),
        # Emergency
        ('emergency_name',          'VARCHAR(150)'),
        ('emergency_relation',      'VARCHAR(50)'),
        ('emergency_phone',         'VARCHAR(20)'),
        ('emergency_address',       'TEXT'),
        # Bank
        ('bank_name',               'VARCHAR(150)'),
        ('bank_account_number',     'VARCHAR(50)'),
        ('bank_ifsc',               'VARCHAR(20)'),
        ('bank_branch',             'VARCHAR(150)'),
        ('bank_account_type',       'VARCHAR(30)'),
        ('bank_account_holder',     'VARCHAR(150)'),
        # Salary
        ('salary_ctc',              'DECIMAL(12,2)'),
        ('salary_basic',            'DECIMAL(12,2)'),
        ('salary_hra',              'DECIMAL(12,2)'),
        ('salary_da',               'DECIMAL(12,2)'),
        ('salary_ta',               'DECIMAL(12,2)'),
        ('salary_special_allow',    'DECIMAL(12,2)'),
        ('salary_medical_allow',    'DECIMAL(12,2)'),
        ('salary_pf_employee',      'DECIMAL(12,2)'),
        ('salary_pf_employer',      'DECIMAL(12,2)'),
        ('salary_esic_employee',    'DECIMAL(12,2)'),
        ('salary_esic_employer',    'DECIMAL(12,2)'),
        ('salary_professional_tax', 'DECIMAL(12,2)'),
        ('salary_tds',              'DECIMAL(12,2)'),
        ('salary_net',              'DECIMAL(12,2)'),
        ('salary_mode',             'VARCHAR(30)'),
        ('salary_effective_date',   'DATE'),
        # Professional
        ('pay_grade',               'VARCHAR(50)'),
        ('shift',                   'VARCHAR(50)'),
        ('work_hours_per_day',      'DECIMAL(4,1) DEFAULT 8'),
        ('weekly_off',              'VARCHAR(50)'),
        ('notice_period_days',      'INT DEFAULT 30'),
        ('confirmation_date',       'DATE'),
        ('resignation_date',        'DATE'),
        ('last_working_date',       'DATE'),
        ('rehire_eligible',         'TINYINT(1) DEFAULT 0'),
        # Education
        ('highest_qualification',   'VARCHAR(100)'),
        ('university',              'VARCHAR(200)'),
        ('passing_year',            'INT'),
        ('specialization',          'VARCHAR(100)'),
        ('prev_company',            'VARCHAR(200)'),
        ('prev_designation',        'VARCHAR(100)'),
        ('prev_from_date',          'DATE'),
        ('prev_to_date',            'DATE'),
        ('prev_leaving_reason',     'TEXT'),
        ('total_experience_yrs',    'DECIMAL(4,1)'),
        # Documents & media
        ('documents_json',          'MEDIUMTEXT'),
        ('profile_photo',           'MEDIUMTEXT'),
        ('qr_code_base64',          'MEDIUMTEXT'),
        # Flags & refs
        ('is_block',                'TINYINT(1) DEFAULT 0'),
        ('is_late',                 'TINYINT(1) DEFAULT 0'),
        ('is_probation',            'TINYINT(1) DEFAULT 0'),
        ('is_contractor',           'TINYINT(1) DEFAULT 0'),
        ('user_id',                 'INT'),
        ('reports_to',              'INT'),
        ('updated_at',              'DATETIME'),
    ]
    added = sum(1 for col, defn in emp_cols if safe_add('employees', col, defn))
    ok(f"employees: {added} new columns added") if added else ok("employees: all columns already exist")

    # ══════════════════════════════════════════════════════
    # STEP 4 — Missing columns: leads
    # ══════════════════════════════════════════════════════
    step("STEP 4: leads table — missing columns add kar raha hai...")
    lead_cols = [
        ('code',              'VARCHAR(20)'),
        ('title',             'VARCHAR(200)'),
        ('position',          'VARCHAR(100)'),
        ('alternate_mobile',  'VARCHAR(20)'),
        ('address',           'TEXT'),
        ('city',              'VARCHAR(100)'),
        ('state',             'VARCHAR(100)'),
        ('country',           "VARCHAR(100) DEFAULT 'India'"),
        ('zip_code',          'VARCHAR(20)'),
        ('website',           'VARCHAR(200)'),
        ('product_name',      'VARCHAR(200)'),
        ('category',          'VARCHAR(100)'),
        ('product_range',     'VARCHAR(100)'),
        ('average_cost',      'DECIMAL(12,2)'),
        ('expected_value',    'DECIMAL(12,2)'),
        ('order_quantity',    'VARCHAR(100)'),
        ('requirement_spec',  'TEXT'),
        ('tags',              'VARCHAR(500)'),
        ('remark',            'TEXT'),
        ('notes',             'TEXT'),
        ('lost_reason',       'VARCHAR(200)'),
        ('priority',          "VARCHAR(20) DEFAULT 'medium'"),
        ('follow_up_date',    'DATE'),
        ('note',              'TEXT'),
        ('attachment',        'TEXT'),
        ('team_members',      'TEXT'),
        ('client_id',         'INT'),
        ('assigned_to',       'INT'),
        ('last_contact',      'DATETIME'),
        ('modified_by',       'INT'),
        ('updated_at',        'DATETIME'),
    ]
    added = sum(1 for col, defn in lead_cols if safe_add('leads', col, defn))
    ok(f"leads: {added} new columns added") if added else ok("leads: all columns already exist")

    # ══════════════════════════════════════════════════════
    # STEP 5 — Missing columns: users & other tables
    # ══════════════════════════════════════════════════════
    step("STEP 5: Other tables — missing columns...")
    other = [
        ('users',            'last_login',      'DATETIME'),
        ('users',            'login_attempts',  'INT DEFAULT 0'),
        ('users',            'locked_until',    'DATETIME'),
        ('users',            'updated_at',      'DATETIME'),
        ('approval_requests','requester_note',  'TEXT'),
        ('approval_requests','approved_at',     'DATETIME'),
        ('client_masters',   'updated_at',      'DATETIME'),
        ('contractors',      'updated_at',      'DATETIME'),
    ]
    added = sum(1 for t, c, d in other if safe_add(t, c, d))
    ok(f"{added} columns added to other tables") if added else ok("Other tables: all columns already exist")

    # ══════════════════════════════════════════════════════
    # STEP 6 — Seed: Admin user
    # ══════════════════════════════════════════════════════
    step("STEP 6: Admin user seed kar raha hai...")
    from models import User
    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@hcp.com',
                     full_name='Administrator', role='admin', is_active=True)
        admin.set_password('HCP@123')
        db.session.add(admin)
        db.session.commit()
        ok("Admin user created → admin / HCP@123")
    else:
        ok("Admin user already exists")

    # ══════════════════════════════════════════════════════
    # STEP 7 — Seed: Modules & Permissions
    # ══════════════════════════════════════════════════════
    step("STEP 7: Modules & permissions seed kar raha hai...")
    from models.permission import Module, RolePermission

    modules_data = [
        ("dashboard",   "Dashboard",   "🏠", "/",                    1),
        ("crm",         "CRM",         "📋", "/crm",                 2),
        ("leads",       "Leads",       "📋", "/crm/leads",           3),
        ("clients",     "Clients",     "🏢", "/crm/clients",         4),
        ("hr",          "HR",          "👥", "/hr",                  5),
        ("hr_employees","Employees",   "👤", "/hr/employees",        6),
        ("hr_contractors","Contractors","🔧","/hr/contractors",       7),
        ("masters",     "Masters",     "⚙️",  "/masters",             8),
        ("admin",       "Admin",       "🔐", "/admin",               9),
        ("users",       "Users",       "👤", "/admin/users",         10),
        ("audit",       "Audit Logs",  "🔍", "/admin/audit-logs",    11),
        ("approvals",   "Approvals",   "✅", "/approvals",           12),
    ]
    mod_added = 0
    for name, label, icon, url, sort in modules_data:
        if not Module.query.filter_by(name=name).first():
            db.session.add(Module(name=name, label=label, icon=icon,
                                  url_prefix=url, sort_order=sort, is_active=True))
            mod_added += 1
    db.session.commit()
    ok(f"{mod_added} new modules added") if mod_added else ok("Modules already seeded")

    roles = ["admin", "manager", "sales", "hr", "viewer"]
    all_mods = Module.query.all()
    perm_added = 0
    for role in roles:
        for mod in all_mods:
            if not RolePermission.query.filter_by(role=role, module_id=mod.id).first():
                can_write  = role in ("admin", "manager", "sales", "hr")
                can_delete = role == "admin"
                can_export = role != "viewer"
                db.session.add(RolePermission(
                    role=role, module_id=mod.id,
                    can_view=True, can_add=can_write,
                    can_edit=can_write, can_delete=can_delete,
                    can_export=can_export,
                ))
                perm_added += 1
    db.session.commit()
    ok(f"{perm_added} new permissions added") if perm_added else ok("Permissions already seeded")

    # ══════════════════════════════════════════════════════
    # STEP 8 — Seed: Lead Statuses, Sources, Categories, Ranges
    # ══════════════════════════════════════════════════════
    step("STEP 8: Master data seed kar raha hai...")
    from models import LeadStatus, LeadSource, LeadCategory, ProductRange

    statuses = [
        ("open",       "📧", "#6366f1", 1),
        ("in_process", "⚙️",  "#1e3a5f", 2),
        ("close",      "✅", "#059669", 3),
        ("cancel",     "❌", "#dc2626", 4),
    ]
    s_added = 0
    for name, icon, color, sort in statuses:
        if not LeadStatus.query.filter_by(name=name).first():
            db.session.add(LeadStatus(name=name, icon=icon, color=color,
                                       sort_order=sort, is_active=True))
            s_added += 1

    sources = ["India Mart", "Just Dial", "Cold Call", "Social Media", "HCP Website",
               "Exhibition", "Pharma Hopper", "Reference", "WhatsApp", "Email Campaign"]
    src_added = 0
    for i, s in enumerate(sources, 1):
        if not LeadSource.query.filter_by(name=s).first():
            db.session.add(LeadSource(name=s, sort_order=i, is_active=True))
            src_added += 1

    categories = ["Cosmetics", "Baby Care", "Oral Care", "Hair Care", "Pharma",
                  "Nutraceutical", "Veterinary", "Food Supplement"]
    cat_added = 0
    for c in categories:
        if not LeadCategory.query.filter_by(name=c).first():
            db.session.add(LeadCategory(name=c, is_active=True)); cat_added += 1

    ranges = ["Body Lotion", "Face Cream", "Shampoo", "Gel", "Syrup", "Tablets",
              "Lip Balm", "Serum", "Toner", "Eye Drop", "Ointment", "Capsules"]
    rng_added = 0
    for r in ranges:
        if not ProductRange.query.filter_by(name=r).first():
            db.session.add(ProductRange(name=r, is_active=True)); rng_added += 1

    db.session.commit()
    ok(f"Lead Statuses: {s_added} added")
    ok(f"Lead Categories: {cat_added} added")
    ok(f"Product Ranges: {rng_added} added")

    # ══════════════════════════════════════════════════════
    # STEP 9 — Indexes
    # ══════════════════════════════════════════════════════
    step("STEP 9: Indexes add kar raha hai...")
    indexes = [
        ("employees", "idx_emp_status",   "status"),
        ("employees", "idx_emp_dept",     "department"),
        ("employees", "idx_emp_code",     "employee_code"),
        ("leads",     "idx_leads_status", "status"),
        ("leads",     "idx_leads_created","created_by"),
        ("wish_logs", "idx_wish_date",    "wish_date"),
        ("audit_logs","idx_audit_module", "module"),
    ]
    for tbl, idx_name, col in indexes:
        if table_exists(tbl) and col_exists(tbl, col):
            try:
                cur.execute(f"CREATE INDEX {idx_name} ON `{tbl}`(`{col}`)")
                raw.commit()
                print(f"     + Index {idx_name}")
            except:
                pass  # already exists — skip silently
    ok("Indexes ready")

    raw.close()

    # ══════════════════════════════════════════════════════
    # DONE
    # ══════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"  {G}{B}✅ MIGRATION COMPLETE!{E}")
    print(f"{'='*60}")
    print(f"\n  Ab server start karo:")
    print(f"  {B}python index.py{E}")
    print(f"\n  Login: {B}admin / HCP@123{E}\n")
