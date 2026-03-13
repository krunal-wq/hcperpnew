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
    # STEP 5B — Soft Delete columns (is_deleted + deleted_at)
    # ══════════════════════════════════════════════════════
    step("STEP 5B: Soft Delete columns add kar raha hai...")
    soft_delete_cols = [
        ('leads',          'is_deleted', 'TINYINT(1) NOT NULL DEFAULT 0'),
        ('leads',          'deleted_at', 'DATETIME NULL'),
        ('client_masters', 'is_deleted', 'TINYINT(1) NOT NULL DEFAULT 0'),
        ('client_masters', 'deleted_at', 'DATETIME NULL'),
        ('employees',      'is_deleted', 'TINYINT(1) NOT NULL DEFAULT 0'),
        ('employees',      'deleted_at', 'DATETIME NULL'),
        ('contractors',    'is_deleted', 'TINYINT(1) NOT NULL DEFAULT 0'),
        ('contractors',    'deleted_at', 'DATETIME NULL'),
    ]
    sd_added = sum(1 for t, c, d in soft_delete_cols if safe_add(t, c, d))
    ok(f"Soft delete: {sd_added} columns added") if sd_added else ok("Soft delete: all columns already exist")

    # Indexes for soft delete (fast trash queries)
    soft_indexes = [
        ('leads',          'idx_leads_is_deleted',   'is_deleted'),
        ('client_masters', 'idx_clients_is_deleted',  'is_deleted'),
        ('employees',      'idx_emp_is_deleted',      'is_deleted'),
        ('contractors',    'idx_contractors_is_deleted','is_deleted'),
    ]
    for tbl, idx_name, col in soft_indexes:
        if table_exists(tbl) and col_exists(tbl, col):
            try:
                cur.execute(f"CREATE INDEX {idx_name} ON `{tbl}`(`{col}`)")
                raw.commit()
                print(f"     + Index {idx_name}")
            except:
                pass  # already exists — skip silently
    ok("Soft delete indexes ready")

    # ══════════════════════════════════════════════════════
    # STEP 5C — Salary Config table + default seed
    # ══════════════════════════════════════════════════════
    step("STEP 5C: salary_config table create kar raha hai...")
    if not table_exists('salary_config'):
        cur.execute("""
            CREATE TABLE salary_config (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                `key`      VARCHAR(50) NOT NULL UNIQUE,
                value      VARCHAR(50) NOT NULL,
                label      VARCHAR(100),
                updated_by VARCHAR(100),
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        raw.commit()
        ok("salary_config table created")
    else:
        ok("salary_config table already exists")

    # Seed default values (INSERT IGNORE — won't overwrite existing)
    salary_defaults = [
        ('basic_pct',    '40',    'Basic Salary % of Monthly CTC'),
        ('hra_pct',      '50',    'HRA % of Basic'),
        ('da_pct',       '10',    'DA % of Basic'),
        ('ta_fixed',     '1600',  'Transport Allow. Fixed Rs'),
        ('med_fixed',    '1250',  'Medical Allow. Fixed Rs'),
        ('pf_emp_pct',   '12',    'PF Employee % of Basic'),
        ('pf_er_pct',    '12',    'PF Employer % of Basic'),
        ('esic_emp_pct', '0.75',  'ESIC Employee % of Gross'),
        ('esic_er_pct',  '3.25',  'ESIC Employer % of Gross'),
        ('esic_limit',   '21000', 'ESIC Applicable Gross Limit Rs'),
        ('pt_fixed',     '200',   'Professional Tax Fixed Rs/month'),
    ]
    seeded = 0
    for key, value, label in salary_defaults:
        cur.execute("SELECT COUNT(*) FROM salary_config WHERE `key`=%s", (key,))
        if cur.fetchone()[0] == 0:
            cur.execute(
                "INSERT INTO salary_config (`key`, value, label) VALUES (%s, %s, %s)",
                (key, value, label)
            )
            seeded += 1
    raw.commit()
    ok(f"Salary config: {seeded} defaults seeded") if seeded else ok("Salary config: defaults already seeded")

    # ══════════════════════════════════════════════════════
    # STEP 5D — Salary Components table + default components
    # ══════════════════════════════════════════════════════
    step("STEP 5D: salary_components table create kar raha hai...")
    if not table_exists('salary_components'):
        cur.execute("""
            CREATE TABLE salary_components (
                id                 INT AUTO_INCREMENT PRIMARY KEY,
                name               VARCHAR(100) NOT NULL,
                code               VARCHAR(30)  NOT NULL UNIQUE,
                component_type     VARCHAR(20)  NOT NULL COMMENT 'earning/deduction/employer_contrib',
                calc_type          VARCHAR(30)  NOT NULL COMMENT 'pct_of_basic/pct_of_gross/pct_of_ctc/fixed/pct_of_basic_capped',
                value              DECIMAL(10,4) DEFAULT 0,
                cap_amount         DECIMAL(10,2) NULL,
                apply_if_gross_lte DECIMAL(10,2) NULL,
                sort_order         INT DEFAULT 0,
                is_active          TINYINT(1) NOT NULL DEFAULT 1,
                is_system          TINYINT(1) NOT NULL DEFAULT 0,
                description        VARCHAR(255),
                updated_by         VARCHAR(100),
                updated_at         DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                created_at         DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        raw.commit()
        ok("salary_components table created")
    else:
        ok("salary_components table already exists")

    # Seed default components (system components — is_system=1)
    # Columns: code, name, component_type, calc_type, value, cap_amount, apply_if_gross_lte, sort_order, is_system, description
    default_components = [
        # code, name, component_type, calc_type, value, cap_amount, apply_if_gross_lte, sort_order, is_system, description
        ('basic',    'Basic Salary',        'earning',          'pct_of_ctc',          40,    None,  None,  1, 1, 'Basic salary - % of monthly CTC'),
        ('hra',      'HRA',                 'earning',          'pct_of_basic',         50,    None,  None,  2, 1, 'House Rent Allowance - % of Basic'),
        ('da',       'DA',                  'earning',          'pct_of_basic',         10,    None,  None,  3, 1, 'Dearness Allowance - % of Basic'),
        ('ta',       'Transport Allowance', 'earning',          'fixed',              1600,    None,  None,  4, 1, 'Fixed transport allowance per month'),
        ('medical',  'Medical Allowance',   'earning',          'fixed',              1250,    None,  None,  5, 1, 'Fixed medical allowance per month'),
        ('special',  'Special Allowance',   'earning',          'balance',               0,    None,  None,  6, 1, 'Auto-calculated remaining CTC after other earnings'),
        ('pf_emp',   'PF (Employee)',        'deduction',        'pct_of_basic_capped',  12,    1800,  None,  1, 1, 'Provident Fund - 12% of Basic, max Rs 1800'),
        ('esic_emp', 'ESIC (Employee)',      'deduction',        'pct_of_gross',       0.75,    None, 21000,  2, 1, 'ESIC 0.75% of Gross - only if gross <= Rs 21000'),
        ('pt',       'Professional Tax',    'deduction',        'fixed',               200,    None,  None,  3, 1, 'Professional Tax - fixed Rs 200/month'),
        ('pf_er',    'PF (Employer)',        'employer_contrib', 'pct_of_basic_capped',  12,    1800,  None,  1, 1, 'Employer PF - 12% of Basic, max Rs 1800'),
        ('esic_er',  'ESIC (Employer)',      'employer_contrib', 'pct_of_gross',       3.25,    None, 21000,  2, 1, 'Employer ESIC 3.25% of Gross - only if gross <= Rs 21000'),
    ]

    comp_seeded = 0
    for code, name, comp_type, calc_type, value, cap, gross_lte, sort, is_sys, desc in default_components:
        try:
            cur.execute(
                "INSERT IGNORE INTO salary_components (code,name,component_type,calc_type,value,cap_amount,apply_if_gross_lte,sort_order,is_system,description,updated_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (code, name, comp_type, calc_type,
                 float(value),
                 float(cap) if cap is not None else None,
                 float(gross_lte) if gross_lte is not None else None,
                 int(sort), int(is_sys), str(desc), 'System (migrate)')
            )
            if cur.rowcount > 0:
                comp_seeded += 1
            raw.commit()
        except Exception as ex:
            raw.rollback()
            warn(f"Component '{code}' skip: {ex}")
    ok(f"Salary components: {comp_seeded} seeded") if comp_seeded else ok("Salary components: already seeded")

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
