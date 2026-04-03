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

    # ── Office Dispatch Tables (Sample Ready → Send to Office) ──
    try:
        with db.engine.connect() as _odc:
            _odc.execute(db.text("""
                CREATE TABLE IF NOT EXISTS `office_dispatch_tokens` (
                    `id`             INT NOT NULL AUTO_INCREMENT,
                    `token_no`       VARCHAR(30) NOT NULL UNIQUE,
                    `dispatched_by`  INT DEFAULT NULL,
                    `dispatched_at`  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    `notes`          TEXT DEFAULT NULL,
                    PRIMARY KEY (`id`),
                    KEY idx_odt_by (`dispatched_by`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            _odc.execute(db.text("""
                CREATE TABLE IF NOT EXISTS `office_dispatch_items` (
                    `id`           INT NOT NULL AUTO_INCREMENT,
                    `token_id`     INT NOT NULL,
                    `project_id`   INT NOT NULL,
                    `sample_code`  VARCHAR(500) DEFAULT NULL,
                    `handover_to`  VARCHAR(200) DEFAULT NULL,
                    `submitted_by` VARCHAR(200) DEFAULT NULL,
                    PRIMARY KEY (`id`),
                    KEY idx_odi_token (`token_id`),
                    KEY idx_odi_project (`project_id`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            _odc.commit()
        ok("office_dispatch_tokens + office_dispatch_items tables ready")
    except Exception as _e:
        warn(f"Office dispatch tables: {_e}")

    # ── Add new columns to office_dispatch_items if missing ──
    try:
        with db.engine.connect() as _adc:
            for _col, _defn in [
                ('sample_code',  'VARCHAR(500) DEFAULT NULL'),
                ('handover_to',  'VARCHAR(200) DEFAULT NULL'),
                ('submitted_by', 'VARCHAR(200) DEFAULT NULL'),
            ]:
                _res = _adc.execute(db.text(
                    "SELECT COUNT(*) FROM information_schema.columns "
                    "WHERE table_schema=DATABASE() AND table_name='office_dispatch_items' AND column_name=:c"
                ), {'c': _col})
                if _res.scalar() == 0:
                    _adc.execute(db.text(f"ALTER TABLE `office_dispatch_items` ADD COLUMN `{_col}` {_defn}"))
                    ok(f"office_dispatch_items.{_col} column added")
            _adc.commit()
    except Exception as _e:
        warn(f"office_dispatch_items alter: {_e}")

    # ══════════════════════════════════════════════════════
    # STEP 1B — Critical columns jo Step 7 se PEHLE chahiye
    # ══════════════════════════════════════════════════════
    step("STEP 1B: Critical missing columns add kar raha hai...")
    import pymysql as _pymysql
    _uri1b = db.engine.url
    _con1b = _pymysql.connect(
        host=str(_uri1b.host),
        port=int(_uri1b.port or 3306),
        user=str(_uri1b.username),
        password=str(_uri1b.password),
        database=str(_uri1b.database),
        charset='utf8mb4'
    )
    _cur1b = _con1b.cursor()

    _critical_cols = [
        ("role_permissions", "can_import",   "TINYINT(1) NOT NULL DEFAULT 0"),
        ("user_permissions", "can_import",   "TINYINT(1) NOT NULL DEFAULT 0"),
        ("employees",        "employee_id",  "VARCHAR(50) DEFAULT NULL"),
    ]
    for _tbl, _col, _defn in _critical_cols:
        try:
            _cur1b.execute(f"SHOW COLUMNS FROM `{_tbl}` LIKE '{_col}'")
            if not _cur1b.fetchone():
                _cur1b.execute(f"ALTER TABLE `{_tbl}` ADD COLUMN `{_col}` {_defn}")
                _con1b.commit()
                ok(f"{_tbl}.{_col} column add kiya ✓")
            else:
                ok(f"{_tbl}.{_col} already exists ✓")
        except Exception as _e:
            ok(f"{_tbl}.{_col} skip: {_e}")

    # Unique index for employees.employee_id
    try:
        _cur1b.execute("SHOW INDEX FROM `employees` WHERE Key_name = 'idx_employee_id'")
        if not _cur1b.fetchone():
            _cur1b.execute("ALTER TABLE `employees` ADD UNIQUE INDEX idx_employee_id (`employee_id`)")
            _con1b.commit()
            ok("employees.employee_id unique index added ✓")
        else:
            ok("employees.employee_id unique index already exists ✓")
    except Exception as _e:
        ok(f"employees.employee_id index skip: {_e}")

    _cur1b.close()
    _con1b.close()

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
        ('title',             'VARCHAR(200) NULL DEFAULT NULL'),
        ('lead_type',         "VARCHAR(20) DEFAULT 'Quality'"),
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
        ('closed_at',         'DATETIME NULL'),
    ]
    added = sum(1 for col, defn in lead_cols if safe_add('leads', col, defn))
    ok(f"leads: {added} new columns added") if added else ok("leads: all columns already exist")

    # Fix: title column NULL allowed karo (import ke liye zaruri)
    step("STEP 4B: leads.title column NULL fix kar raha hai...")
    safe_modify('leads', 'title', 'VARCHAR(200) NULL DEFAULT NULL')
    ok("leads.title → NULL allowed (import fix)")

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
    # STEP 5F — Contractor Document Fields
    # ══════════════════════════════════════════════════════
    step("STEP 5F: contractors table — document fields add kar raha hai...")
    contractor_doc_cols = [
        # Document Numbers
        ('aadhaar_no',       'VARCHAR(14)'),
        ('msme_no',          'VARCHAR(25)'),
        ('trade_license_no', 'VARCHAR(50)'),
        ('bank_account_no',  'VARCHAR(20)'),
        ('ifsc_code',        'VARCHAR(11)'),
        # Document File Paths
        ('aadhaar_file',     'VARCHAR(255)'),
        ('pan_file',         'VARCHAR(255)'),
        ('gst_file',         'VARCHAR(255)'),
        ('msme_file',        'VARCHAR(255)'),
        ('trade_file',       'VARCHAR(255)'),
        ('bank_file',        'VARCHAR(255)'),
        # Other docs (JSON)
        ('other_docs',       'TEXT'),
    ]
    ctr_added = sum(1 for col, defn in contractor_doc_cols if safe_add('contractors', col, defn))
    ok(f"contractors: {ctr_added} document columns added") if ctr_added else ok("contractors: document columns already exist")

    # Create upload directory for contractor documents
    import os as _os
    _ctr_upload = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), 'static', 'uploads', 'contractors')
    _os.makedirs(_ctr_upload, exist_ok=True)
    ok(f"contractors upload dir ready: static/uploads/contractors/")

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
    # STEP 5E — created_at / created_by / updated_at / updated_by
    #           Har table mein yeh standard audit columns hone chahiye
    # ══════════════════════════════════════════════════════
    step("STEP 5E: Standard audit columns (created_at/by, updated_at/by) add kar raha hai...")
    audit_cols = [
        # table                col               definition
        # ── leads ──
        ('leads',              'created_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP'),
        ('leads',              'created_by',      'INT NULL'),
        ('leads',              'updated_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        ('leads',              'updated_by',      'INT NULL'),
        # ── client_masters ──
        ('client_masters',     'created_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP'),
        ('client_masters',     'created_by',      'INT NULL'),
        ('client_masters',     'updated_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        ('client_masters',     'updated_by',      'INT NULL'),
        # ── employees ──
        ('employees',          'created_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP'),
        ('employees',          'created_by',      'INT NULL'),
        ('employees',          'updated_by',      'INT NULL'),
        # ── contractors ──
        ('contractors',        'created_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP'),
        ('contractors',        'created_by',      'INT NULL'),
        ('contractors',        'updated_by',      'INT NULL'),
        # ── users ──
        ('users',              'created_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP'),
        ('users',              'created_by',      'INT NULL'),
        ('users',              'updated_by',      'INT NULL'),
        # ── sample_orders ──
        ('sample_orders',      'updated_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        ('sample_orders',      'updated_by',      'INT NULL'),
        # ── email_templates ──
        ('email_templates',    'created_by',      'INT NULL'),
        # ── lead_discussions ──
        ('lead_discussions',   'updated_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        ('lead_discussions',   'updated_by',      'INT NULL'),
        # ── lead_reminders ──
        ('lead_reminders',     'updated_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        ('lead_reminders',     'created_by',      'INT NULL'),
        # ── lead_notes ──
        ('lead_notes',         'created_by',      'INT NULL'),
        # ── lead_activity_logs ──
        ('lead_activity_logs', 'updated_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        # ── approval_requests ──
        ('approval_requests',  'created_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP'),
        ('approval_requests',  'created_by',      'INT NULL'),
        ('approval_requests',  'updated_by',      'INT NULL'),
        # ── salary_components ──
        ('salary_components',  'created_by',      'INT NULL'),
        ('salary_components',  'updated_by',      'INT NULL'),
        # ── salary_config ──
        ('salary_config',      'created_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP'),
        ('salary_config',      'created_by',      'INT NULL'),
        ('salary_config',      'updated_by',      'INT NULL'),
    ]
    audit_added = sum(1 for t, c, d in audit_cols if safe_add(t, c, d))
    ok(f"Audit columns: {audit_added} added") if audit_added else ok("Audit columns: already exist in all tables")
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

    # Ensure label column exists (purani table mein nahi hoga)
    safe_add('salary_config', 'label', 'VARCHAR(100)')

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
        ("dashboard",      "Dashboard",    "🏠", "/",                     1),
        ("crm",            "CRM",          "📊", "/crm",                  2),
        ("crm_leads",      "Leads",        "📋", "/crm/leads",            3),
        ("crm_clients",    "Clients",      "👥", "/crm/clients",          4),
        ("hr",             "HR",           "👔", "/hr",                   5),
        ("hr_employees",   "Employees",    "🪪", "/hr/employees",         6),
        ("hr_contractors", "Contractors",  "🤝", "/hr/contractors",       7),
        ("npd",            "NPD",          "🔬", "/npd",                  8),
        ("rd",             "R&D",          "🧪", "/rd",                   9),
        ("masters",        "Masters",      "⚙️", "/masters",              10),
        ("approvals",      "Approvals",    "✅", "/approvals",            11),
        ("user_mgmt",      "Users",        "👤", "/admin/users",          12),
        ("audit_logs",     "Audit Logs",   "🔍", "/admin/audit-logs",     13),
    ]
    mod_added = 0
    for name, label, icon, url, sort in modules_data:
        if not Module.query.filter_by(name=name).first():
            db.session.add(Module(name=name, label=label, icon=icon,
                                  url_prefix=url, sort_order=sort, is_active=True))
            mod_added += 1
    db.session.commit()
    ok(f"{mod_added} new modules added") if mod_added else ok("Modules already seeded")

    # ── can_import column ensure karo BEFORE RolePermission query ──
    try:
        import pymysql
        _db_uri = db.engine.url
        _rc = pymysql.connect(
            host=str(_db_uri.host), port=int(_db_uri.port or 3306),
            user=str(_db_uri.username), password=str(_db_uri.password),
            database=str(_db_uri.database), charset='utf8mb4'
        )
        _rc_cur = _rc.cursor()
        for _fix_tbl in ('role_permissions', 'user_permissions'):
            _rc_cur.execute(f"SHOW COLUMNS FROM `{_fix_tbl}` LIKE 'can_import'")
            if not _rc_cur.fetchone():
                _rc_cur.execute(f"ALTER TABLE `{_fix_tbl}` ADD COLUMN `can_import` TINYINT(1) NOT NULL DEFAULT 0")
                _rc.commit()
                ok(f"{_fix_tbl}.can_import column add kiya ✓")
            else:
                ok(f"{_fix_tbl}.can_import already exists ✓")
        _rc_cur.close()
        _rc.close()
    except Exception as _fix_err:
        warn(f"can_import fix attempt: {_fix_err}")

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
                    can_export=can_export, can_import=False,
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
        ("open",             "📧", "#6366f1", 1),
        ("in_process",       "⚙️",  "#1e3a5f", 2),
        ("close",            "✅", "#059669", 3),
        ("cancel",           "❌", "#dc2626", 4),
        ("NPD Project",      "🧪", "#8b5cf6", 5),
        ("Existing Project", "📦", "#0ea5e9", 6),
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
    # ══════════════════════════════════════════════════════
    # STEP 8B — Sample Orders table
    # ══════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════
    # STEP 8A — Quotations table
    # ══════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════
    # STEP 7B — Category Master, UOM Master, HSN Code Master
    # ══════════════════════════════════════════════════════
    step("STEP 7B: Category Master table create kar raha hai...")
    if not table_exists('category_masters'):
        cur.execute("""
            CREATE TABLE category_masters (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                name        VARCHAR(150) NOT NULL UNIQUE,
                status      TINYINT(1) NOT NULL DEFAULT 1,
                is_deleted  TINYINT(1) NOT NULL DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by  INT NULL,
                modified_at DATETIME NULL,
                modified_by INT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        raw.commit()
        ok("category_masters table created")
    else:
        ok("category_masters table already exists")

    step("STEP 7C: UOM Master table create kar raha hai...")
    if not table_exists('uom_masters'):
        cur.execute("""
            CREATE TABLE uom_masters (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                code        VARCHAR(30) NOT NULL UNIQUE,
                name        VARCHAR(100) NOT NULL,
                status      TINYINT(1) NOT NULL DEFAULT 1,
                is_deleted  TINYINT(1) NOT NULL DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by  INT NULL,
                modified_at DATETIME NULL,
                modified_by INT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        raw.commit()
        ok("uom_masters table created")
        # Seed default UOMs
        default_uoms = [
            ('ML',  'Millilitre'),
            ('L',   'Litre'),
            ('GM',  'Gram'),
            ('KG',  'Kilogram'),
            ('PCS', 'Pieces'),
            ('BOX', 'Box'),
            ('SET', 'Set'),
            ('MTR', 'Metre'),
            ('NOS', 'Numbers'),
        ]
        for code, name in default_uoms:
            cur.execute("INSERT IGNORE INTO uom_masters (code, name) VALUES (%s, %s)", (code, name))
        raw.commit()
        ok(f"UOM defaults seeded ({len(default_uoms)} records)")
    else:
        ok("uom_masters table already exists")

    step("STEP 7D: HSN Code Master table create kar raha hai...")
    if not table_exists('hsn_codes'):
        cur.execute("""
            CREATE TABLE hsn_codes (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                hsn_code    VARCHAR(20) NOT NULL UNIQUE,
                description TEXT NULL,
                gst_rate    DECIMAL(5,2) DEFAULT 0,
                cgst        DECIMAL(5,2) DEFAULT 0,
                sgst        DECIMAL(5,2) DEFAULT 0,
                igst        DECIMAL(5,2) DEFAULT 0,
                cess        DECIMAL(5,2) DEFAULT 0,
                status      TINYINT(1) NOT NULL DEFAULT 1,
                is_deleted  TINYINT(1) NOT NULL DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by  INT NULL,
                modified_at DATETIME NULL,
                modified_by INT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        raw.commit()
        ok("hsn_codes table created")
        # Seed common cosmetic HSN codes
        hsn_defaults = [
            ('33049910', 'Face creams, lotions and similar preparations', 18, 9, 9, 18, 0),
            ('33049920', 'Skin care preparations nes',                    18, 9, 9, 18, 0),
            ('33051000', 'Shampoos',                                       18, 9, 9, 18, 0),
            ('33059010', 'Hair oils',                                      18, 9, 9, 18, 0),
            ('33061000', 'Dentifrice / Toothpaste',                        12, 6, 6, 12, 0),
            ('33072000', 'Personal deodorants and antiperspirants',        18, 9, 9, 18, 0),
            ('30049099', 'Medicaments nes',                                12, 6, 6, 12, 0),
            ('21069099', 'Food preparations / Nutraceuticals nes',         18, 9, 9, 18, 0),
        ]
        for hc, desc, gst, cgst, sgst, igst, cess in hsn_defaults:
            cur.execute(
                "INSERT IGNORE INTO hsn_codes (hsn_code, description, gst_rate, cgst, sgst, igst, cess) VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (hc, desc, gst, cgst, sgst, igst, cess)
            )
        raw.commit()
        ok(f"HSN defaults seeded ({len(hsn_defaults)} records)")
    else:
        ok("hsn_codes table already exists")

    step("STEP 8A: quotations table create kar raha hai...")
    if not table_exists('quotations'):
        cur.execute("""
            CREATE TABLE quotations (
                id             INT AUTO_INCREMENT PRIMARY KEY,
                quot_number    VARCHAR(50) NOT NULL UNIQUE,
                lead_id        INT NOT NULL,
                quot_date      DATE NOT NULL,
                valid_until    DATE,
                subject        VARCHAR(300),
                bill_company   VARCHAR(200),
                bill_address   TEXT,
                bill_phone     VARCHAR(20),
                bill_email     VARCHAR(150),
                bill_gst       VARCHAR(20),
                gst_pct        DECIMAL(5,2) DEFAULT 18,
                sub_total      DECIMAL(12,2) DEFAULT 0,
                gst_amount     DECIMAL(12,2) DEFAULT 0,
                total_amount   DECIMAL(12,2) DEFAULT 0,
                items_json     TEXT,
                terms          TEXT,
                notes          TEXT,
                status         VARCHAR(20) DEFAULT 'draft',
                email_sent_at  DATETIME,
                email_sent_to  VARCHAR(150),
                created_by     INT,
                created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        raw.commit()
        ok("quotations table created")
    else:
        ok("quotations table already exists")

    # Purani quotations table mein missing columns add karo (safe to run multiple times)
    quot_cols = [
        ('quot_number',   'VARCHAR(50)'),
        ('lead_id',       'INT'),
        ('quot_date',     'DATE'),
        ('valid_until',   'DATE'),
        ('subject',       'VARCHAR(300)'),
        ('bill_company',  'VARCHAR(200)'),
        ('bill_address',  'TEXT'),
        ('bill_phone',    'VARCHAR(20)'),
        ('bill_email',    'VARCHAR(150)'),
        ('bill_gst',      'VARCHAR(20)'),
        ('gst_pct',       'DECIMAL(5,2) DEFAULT 18'),
        ('sub_total',     'DECIMAL(12,2) DEFAULT 0'),
        ('gst_amount',    'DECIMAL(12,2) DEFAULT 0'),
        ('total_amount',  'DECIMAL(12,2) DEFAULT 0'),
        ('items_json',    'TEXT'),
        ('terms',         'TEXT'),
        ('notes',         'TEXT'),
        ('status',        "VARCHAR(20) DEFAULT 'draft'"),
        ('email_sent_at', 'DATETIME'),
        ('email_sent_to', 'VARCHAR(150)'),
        ('created_by',    'INT'),
        ('created_at',    'DATETIME DEFAULT CURRENT_TIMESTAMP'),
        # ── Soft Delete ──
        ('is_deleted',    'TINYINT(1) NOT NULL DEFAULT 0'),
        ('deleted_at',    'DATETIME NULL DEFAULT NULL'),
        ('deleted_by',    'INT NULL DEFAULT NULL'),
    ]
    q_added = sum(1 for col, defn in quot_cols if safe_add('quotations', col, defn))
    ok(f"quotations: {q_added} missing columns added") if q_added else ok("quotations: all columns already exist")

    # Index for fast deleted tab queries
    if table_exists('quotations') and col_exists('quotations', 'is_deleted'):
        try:
            cur.execute("CREATE INDEX idx_quot_is_deleted ON `quotations`(`is_deleted`)")
            raw.commit()
            print("     + Index idx_quot_is_deleted")
        except:
            pass  # already exists

    # customer_id → lead_id migrate karo (agar purana data hai)
    if col_exists('quotations', 'customer_id') and col_exists('quotations', 'lead_id'):
        try:
            cur.execute("UPDATE quotations SET lead_id = customer_id WHERE lead_id IS NULL AND customer_id IS NOT NULL")
            raw.commit()
            ok("quotations: customer_id → lead_id data migrated")
        except: pass

    # quot_date NULL fix
    if col_exists('quotations', 'quot_date') and col_exists('quotations', 'created_at'):
        try:
            cur.execute("UPDATE quotations SET quot_date = DATE(created_at) WHERE quot_date IS NULL")
            raw.commit()
            ok("quotations: quot_date NULL values fixed")
        except: pass

    # ── Sample Orders soft delete columns ──
    so_soft = [
        ('is_deleted', 'TINYINT(1) NOT NULL DEFAULT 0'),
        ('deleted_at', 'DATETIME NULL DEFAULT NULL'),
        ('deleted_by', 'INT NULL DEFAULT NULL'),
    ]
    so_sd = sum(1 for c,d in so_soft if safe_add('sample_orders', c, d))
    if so_sd: ok(f"sample_orders: {so_sd} soft-delete columns added")
    if table_exists('sample_orders') and col_exists('sample_orders','is_deleted'):
        try:
            cur.execute("CREATE INDEX idx_so_is_deleted ON `sample_orders`(`is_deleted`)")
            raw.commit(); print("     + Index idx_so_is_deleted")
        except: pass

    step("STEP 8B: sample_orders table create kar raha hai...")
    if not table_exists('sample_orders'):
        cur.execute("""
            CREATE TABLE sample_orders (
                id           INT AUTO_INCREMENT PRIMARY KEY,
                order_number VARCHAR(50) NOT NULL UNIQUE,
                lead_id      INT NOT NULL,
                order_date   DATE NOT NULL,
                category     VARCHAR(50) DEFAULT 'Sample Order',
                bill_company VARCHAR(200),
                bill_address TEXT,
                bill_phone   VARCHAR(20),
                bill_email   VARCHAR(150),
                bill_gst     VARCHAR(20),
                gst_pct      DECIMAL(5,2) DEFAULT 18,
                sub_total    DECIMAL(12,2) DEFAULT 0,
                gst_amount   DECIMAL(12,2) DEFAULT 0,
                total_amount DECIMAL(12,2) DEFAULT 0,
                items_json   TEXT,
                terms        TEXT,
                invoice_file VARCHAR(300),
                created_by   INT,
                created_at   DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id),
                FOREIGN KEY (created_by) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        raw.commit()
        ok("sample_orders table created")
    else:
        ok("sample_orders table already exists")

    # invoice_file column — purani table ke liye (safe to run multiple times)
    safe_add('sample_orders', 'invoice_file', 'VARCHAR(300)')

    # ══════════════════════════════════════════════════════
    # STEP 8B2 — client_addresses: brand_index column
    # ══════════════════════════════════════════════════════
    step("STEP 8B2: client_addresses — brand_index column add kar raha hai...")
    safe_add('client_addresses', 'brand_index', 'INT DEFAULT 0 AFTER `client_id`')
    ok("client_addresses.brand_index ready")

    # ══════════════════════════════════════════════════════
    # STEP 8B3 — client_masters: client_type column drop
    # ══════════════════════════════════════════════════════
    step("STEP 8B3: client_masters — client_type column drop kar raha hai...")
    if table_exists('client_masters') and col_exists('client_masters', 'client_type'):
        try:
            cur.execute("ALTER TABLE `client_masters` DROP COLUMN `client_type`")
            raw.commit()
            ok("client_type column dropped!")
        except Exception as e:
            warn(f"client_type drop skip: {e}")
    else:
        ok("client_type column already removed")

    # ══════════════════════════════════════════════════════
    # STEP 8B4 — leads: code column drop
    # ══════════════════════════════════════════════════════
    step("STEP 8B4: leads — code column drop kar raha hai...")
    if table_exists('leads') and col_exists('leads', 'code'):
        try:
            cur.execute("ALTER TABLE `leads` DROP COLUMN `code`")
            raw.commit()
            ok("leads.code column dropped!")
        except Exception as e:
            warn(f"leads.code drop skip: {e}")
    else:
        ok("leads.code column already removed")

    # ══════════════════════════════════════════════════════
    # STEP 8C — Email Templates table
    # ══════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════
    # STEP 8D — Lead Contributions table
    # ══════════════════════════════════════════════════════
    # ══════════════════════════════════════════════════════
    # STEP 8E — Contribution Config table
    # ══════════════════════════════════════════════════════
    step("STEP 8E: contribution_config table create kar raha hai...")
    if not table_exists('contribution_config'):
        cur.execute("""
            CREATE TABLE contribution_config (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                action_type VARCHAR(30) NOT NULL UNIQUE,
                label       VARCHAR(100) NOT NULL,
                points      INT DEFAULT 0,
                description VARCHAR(200),
                updated_by  INT,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        # Seed defaults
        defaults = [
            ('comment',       'Comment Added',       1,  'Discussion board mein comment karne pe'),
            ('edit',          'Lead Edited',          1,  'Lead record update karne pe'),
            ('status_change', 'Status Changed',       2,  'Lead status change karne pe'),
            ('close_slab1',   'Close: 1-7 days',     10, 'Lead 1-7 din mein close'),
            ('close_slab2',   'Close: 8-14 days',     8, 'Lead 8-14 din mein close'),
            ('close_slab3',   'Close: 15-21 days',    6, 'Lead 15-21 din mein close'),
            ('close_slab4',   'Close: 22-28 days',    4, 'Lead 22-28 din mein close'),
            ('close_slab5',   'Close: 29+ days',      0, 'Lead 29+ din baad close'),
            ('cancel',        'Lead Cancelled',        0, 'Lead cancel karne pe'),
            ('follow_up',     'Follow Up Set',         1, 'Follow up date set karne pe'),
            ('reminder',      'Reminder Added',        1, 'Reminder add karne pe'),
        ]
        for at, lbl, pts, desc in defaults:
            cur.execute("INSERT INTO contribution_config (action_type,label,points,description) VALUES (%s,%s,%s,%s)",
                       (at, lbl, pts, desc))
        raw.commit()
        ok("contribution_config table created + seeded")
    else:
        ok("contribution_config table already exists")

    step("STEP 8D: lead_contributions table create kar raha hai...")
    if not table_exists('lead_contributions'):
        cur.execute("""
            CREATE TABLE lead_contributions (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                lead_id     INT NOT NULL,
                user_id     INT NOT NULL,
                action_type VARCHAR(30) NOT NULL,
                points      INT DEFAULT 0,
                note        VARCHAR(200),
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (lead_id) REFERENCES leads(id),
                FOREIGN KEY (user_id) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        raw.commit()
        ok("lead_contributions table created")
    else:
        ok("lead_contributions table already exists")

    step("STEP 8C: email_templates table create kar raha hai...")
    if not table_exists('email_templates'):
        cur.execute("""
            CREATE TABLE email_templates (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                code        VARCHAR(50) NOT NULL UNIQUE,
                name        VARCHAR(200) NOT NULL,
                subject     VARCHAR(500) NOT NULL,
                body        MEDIUMTEXT NOT NULL,
                from_email  VARCHAR(150) DEFAULT 'info@hcpwellness.in',
                from_name   VARCHAR(150) DEFAULT 'HCP Wellness Pvt. Ltd.',
                is_active   TINYINT(1) DEFAULT 1,
                updated_by  INT,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (updated_by) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        raw.commit()
        ok("email_templates table created")
    else:
        ok("email_templates table already exists")

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

    # ══════════════════════════════════════════════════════
    # STEP 10 — Fix customer_id NULL + UOM/Category seed data
    # ══════════════════════════════════════════════════════
    step("STEP 10: quotations.customer_id NULL fix + UOM/Category seed...")

    # Fix customer_id NOT NULL → NULL
    if col_exists('quotations', 'customer_id'):
        try:
            cur.execute("ALTER TABLE quotations MODIFY COLUMN customer_id INT NULL DEFAULT NULL")
            raw.commit()
            ok("quotations.customer_id → nullable")
        except Exception as e:
            ok(f"quotations.customer_id already nullable: {e}")
    else:
        ok("quotations.customer_id column not present — skipping")

    # Seed UOM data (extra ones not already present)
    uom_seed = [
        ('ml',    'Milliliter'),
        ('L',     'Liter'),
        ('g',     'Gram'),
        ('kg',    'Kilogram'),
        ('mg',    'Milligram'),
        ('pcs',   'Pieces'),
        ('nos',   'Numbers'),
        ('box',   'Box'),
        ('pkt',   'Packet'),
        ('btl',   'Bottle'),
        ('tube',  'Tube'),
        ('sachet','Sachet'),
        ('strip', 'Strip'),
        ('vial',  'Vial'),
        ('pouch', 'Pouch'),
    ]
    uom_added = 0
    for code, name in uom_seed:
        try:
            cur.execute("INSERT IGNORE INTO uom_masters (code, name, status, is_deleted) VALUES (%s, %s, 1, 0)", (code, name))
            uom_added += cur.rowcount
        except: pass
    raw.commit()
    ok(f"UOM data: {uom_added} new records added")

    # Seed Category Master data
    categories = [
        'Skin Care', 'Hair Care', 'Body Care', 'Oral Care', 'Baby Care',
        'Eye Care', 'Cosmetics', 'Pharma - OTC', 'Pharma - Prescription',
        'Nutraceutical', 'Food Supplement', 'Veterinary', 'Ayurvedic / Herbal', 'Industrial',
    ]
    cat_added = 0
    for name in categories:
        try:
            cur.execute("INSERT IGNORE INTO category_masters (name, status, is_deleted) VALUES (%s, 1, 0)", (name,))
            cat_added += cur.rowcount
        except: pass
    raw.commit()
    ok(f"Category data: {cat_added} new records added")

    # ══════════════════════════════════════════════════════
    # STEP 11 — leads.code column
    # ══════════════════════════════════════════════════════
    step("STEP 11: leads.code column add kar raha hai...")
    # Add code column if not exists
    if not col_exists('leads', 'code'):
        try:
            cur.execute("ALTER TABLE `leads` ADD COLUMN `code` VARCHAR(30) NULL")
            raw.commit()
            ok("leads.code column added")
        except Exception as e:
            warn(f"leads.code add: {e}")
    else:
        ok("leads.code column already exists")

    # Add unique index separately (safer)
    try:
        cur.execute("ALTER TABLE `leads` ADD UNIQUE INDEX `idx_leads_code` (`code`)")
        raw.commit()
        ok("leads.code unique index added")
    except Exception as e:
        if '1061' in str(e) or 'Duplicate key name' in str(e):
            ok("leads.code index already exists")

    # Back-fill existing leads with codes
    try:
        cur.execute("SELECT id FROM leads WHERE code IS NULL OR code = '' ORDER BY id")
        rows = cur.fetchall()
        updated = 0
        for (lid,) in rows:
            code = f"LD{str(lid).zfill(3)}"
            cur.execute("UPDATE leads SET code = %s WHERE id = %s AND (code IS NULL OR code = '')", (code, lid))
            updated += 1
        raw.commit()
        ok(f"leads code back-fill: {updated} records updated")
    except Exception as e:
        warn(f"Code backfill: {e}")

    # ── NPD Project R&D param defaults ──
    safe_add('npd_projects', 'rd_param_defaults', 'TEXT')

    # ── Ensure npd_comments has attachment column ──
    safe_add('npd_comments', 'attachment', 'VARCHAR(300)')

    # ── NPD Comments & Notes tables ──
    if not table_exists('npd_comments'):
        cur.execute("""
            CREATE TABLE npd_comments (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                project_id  INT NOT NULL,
                user_id     INT NOT NULL,
                comment     TEXT NOT NULL,
                is_internal TINYINT(1) DEFAULT 0,
                attachment  VARCHAR(300),
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES npd_projects(id),
                FOREIGN KEY (user_id)    REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        ok("npd_comments table created")

    if not table_exists('npd_notes'):
        cur.execute("""
            CREATE TABLE npd_notes (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                project_id  INT NOT NULL UNIQUE,
                content     TEXT,
                updated_by  INT,
                updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (project_id) REFERENCES npd_projects(id),
                FOREIGN KEY (updated_by) REFERENCES users(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        ok("npd_notes table created")

    # ══════════════════════════════════════════════════════
    # STEP 11C — NPD Statuses table create + seed
    # ══════════════════════════════════════════════════════
    step("STEP 11C: npd_statuses table create kar raha hai...")
    if not table_exists('npd_statuses'):
        cur.execute("""
            CREATE TABLE npd_statuses (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                name        VARCHAR(100) NOT NULL,
                slug        VARCHAR(60)  NOT NULL UNIQUE,
                color       VARCHAR(20)  DEFAULT '#6b7280',
                icon        VARCHAR(10)  DEFAULT '🔵',
                sort_order  INT          DEFAULT 0,
                is_active   TINYINT(1)   DEFAULT 1,
                created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
                created_by  INT          NULL,
                modified_by INT          NULL,
                modified_at DATETIME     NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        raw.commit()
        ok("npd_statuses table created")
    else:
        ok("npd_statuses table already exists")

    # Seed default statuses (DELETE + re-seed for fresh data)
    cur.execute("SELECT COUNT(*) FROM npd_statuses")
    ns_count = cur.fetchone()[0]
    if ns_count == 0:
        npd_status_defaults = [
            # (name,                                slug,                 color,     icon, sort)
            # ── Project Statuses ──
            ('Not Started',                         'not_started',        '#6b7280', '⭕', 1),
            ('Sample Inprocess',                    'sample_inprocess',   '#8b5cf6', '🔄', 2),
            ('Sample Send to Client',               'sample_sent',        '#06b6d4', '📤', 3),
            ('On Hold',                             'on_hold',            '#f59e0b', '⏸️', 4),
            ('Sample Rejected',                     'sample_rejected',    '#ef4444', '❌', 5),
            ('Sample Approved',                     'sample_approved',    '#10b981', '✅', 6),
            ('Cancelled',                           'cancelled',          '#dc2626', '🚫', 7),
            ('Finish',                              'finish',             '#22c55e', '🏁', 8),
            ('Sample Ready',                        'sample_ready',       '#3b82f6', '📦', 9),
            ('Sent to Office',                      'sent_to_office',     '#6366f1', '🏢', 10),
            ('Rejected by Office',                  'rejected_by_office', '#f97316', '🔴', 11),
            ('Assign',                              'assign',             '#64748b', '👤', 12),
            ('Assigned',                            'assigned',           '#7c3aed', '✔️', 13),
            # ── Milestone Names ──
            ('BOM',                                 'bom',                '#7c3aed', '📄', 14),
            ('Ingredients List & Marketing Sheet',  'ingredients',        '#2563eb', '📋', 15),
            ('Quotation',                           'quotation',          '#d97706', '💰', 16),
            ('Packing Material',                    'packing_material',   '#059669', '📦', 17),
            ('Artwork / Design',                    'artwork',            '#db2777', '🎨', 18),
            ('Artwork QC Approval',                 'artwork_qc',         '#10b981', '✅', 19),
            ('FDA',                                 'fda',                '#1d4ed8', '🏛️', 20),
            ('Barcode',                             'barcode',            '#374151', '🔢', 21),
        ]
        for name, slug, color, icon, sort in npd_status_defaults:
            cur.execute(
                "INSERT IGNORE INTO npd_statuses (name, slug, color, icon, sort_order, is_active) VALUES (%s,%s,%s,%s,%s,1)",
                (name, slug, color, icon, sort)
            )
        raw.commit()
        ok(f"npd_statuses: {len(npd_status_defaults)} statuses seeded!")
        for name, slug, color, icon, sort in npd_status_defaults:
            print(f"     [{sort}] {icon} {name}  ({slug})")
    else:
        # Already seeded — missing milestone names add karo
        milestone_names = [
            ('BOM',                                 'bom',                '#7c3aed', '📄', 14),
            ('Ingredients List & Marketing Sheet',  'ingredients',        '#2563eb', '📋', 15),
            ('Quotation',                           'quotation',          '#d97706', '💰', 16),
            ('Packing Material',                    'packing_material',   '#059669', '📦', 17),
            ('Artwork / Design',                    'artwork',            '#db2777', '🎨', 18),
            ('Artwork QC Approval',                 'artwork_qc',         '#10b981', '✅', 19),
            ('FDA',                                 'fda',                '#1d4ed8', '🏛️', 20),
            ('Barcode',                             'barcode',            '#374151', '🔢', 21),
        ]
        added = 0
        for name, slug, color, icon, sort in milestone_names:
            cur.execute("SELECT COUNT(*) FROM npd_statuses WHERE slug=%s", (slug,))
            if cur.fetchone()[0] == 0:
                cur.execute(
                    "INSERT INTO npd_statuses (name, slug, color, icon, sort_order, is_active) VALUES (%s,%s,%s,%s,%s,1)",
                    (name, slug, color, icon, sort)
                )
                added += 1
        raw.commit()
        ok(f"npd_statuses: {ns_count} existing + {added} milestone names added") if added else ok(f"npd_statuses: {ns_count} records already exist — skip")

    # ══════════════════════════════════════════════════════
    # STEP 11B — NPD Project: missing columns add karo
    # ══════════════════════════════════════════════════════
    step("STEP 11B: npd_projects — missing columns add kar raha hai...")

    npd_cols = [
        # Extended product fields (new form fields)
        ('client_coordinator',      'VARCHAR(200)'),
        ('area_of_application',     'VARCHAR(200)'),
        ('assigned_members',        'VARCHAR(500)'),
        ('assigned_rd_members',     'VARCHAR(500)'),
        ('client_id',               'INT NULL'),
        ('market_level',            'VARCHAR(300)'),
        ('no_of_samples',           'INT DEFAULT 0'),
        ('moq',                     'VARCHAR(100)'),
        ('product_size',            'VARCHAR(100)'),
        ('description',             'TEXT'),
        ('ingredients',             'TEXT'),
        ('active_ingredients',      'VARCHAR(500)'),
        ('video_link',              'VARCHAR(500)'),
        ('reference_brand',         'VARCHAR(200)'),
        ('reference_product_name',  'VARCHAR(300)'),
        ('variant_type',            'VARCHAR(200)'),
        ('appearance',              'VARCHAR(500)'),
        ('product_claim',           'TEXT'),
        ('label_claim',             'TEXT'),
        ('costing_range',           'VARCHAR(200)'),
        ('ph_value',                'VARCHAR(50)'),
        ('packaging_type',          'VARCHAR(200)'),
        ('fragrance',               'VARCHAR(200)'),
        ('viscosity',               'VARCHAR(200)'),
        ('priority',                "VARCHAR(50) DEFAULT 'Normal'"),
        ('project_start_date',      'DATE'),
        ('project_lead_days',       'INT'),
        ('project_end_date',        'DATE'),
        # Fee
        ('npd_fee_paid',            'TINYINT(1) DEFAULT 0'),
        ('npd_fee_amount',          'DECIMAL(10,2) DEFAULT 10000'),
        ('npd_fee_receipt',         'VARCHAR(300)'),
        # Soft delete
        ('is_deleted',              'TINYINT(1) NOT NULL DEFAULT 0'),
        ('deleted_at',              'DATETIME NULL'),
        ('deleted_by',              'INT NULL'),
        # Audit
        ('updated_by',              'INT NULL'),
        ('updated_at',              'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
        # Misc
        ('last_connected',           'DATETIME NULL'),
        ('cancel_reason',           'TEXT'),
        ('cancelled_at',            'DATETIME'),
        ('completed_at',            'DATETIME'),
        ('started_at',              'DATETIME'),
        ('finished_at',             'DATETIME'),
        ('total_duration_seconds',  'INT'),
        ('target_sample_date',      'DATE'),
        ('delay_reason',            'TEXT'),
        ('last_delay_update',       'DATETIME'),
        ('advance_paid',            'TINYINT(1) DEFAULT 0'),
        ('advance_amount',          'DECIMAL(10,2) DEFAULT 2000'),
        ('advance_receipt',         'VARCHAR(300)'),
        ('converted_to_commercial', 'TINYINT(1) DEFAULT 0'),
        ('commercial_converted_at', 'DATETIME'),
        ('milestone_master_created','TINYINT(1) DEFAULT 0'),
        ('rd_param_defaults',       'TEXT'),
    ]
    npd_added = sum(1 for col, defn in npd_cols if safe_add('npd_projects', col, defn))
    ok(f"npd_projects: {npd_added} new columns added") if npd_added else ok("npd_projects: all columns already exist")

    # milestone_masters missing columns
    ms_cols = [
        ('milestone_type',  'VARCHAR(50)'),
        ('description',     'TEXT'),
        ('is_selected',     'TINYINT(1) DEFAULT 1'),
        ('sort_order',      'INT DEFAULT 0'),
        ('target_date',     'DATE'),
        ('completed_at',    'DATETIME'),
        ('assigned_to',     'INT'),
        ('approved_by',     'INT'),
        ('approved_at',     'DATETIME'),
        ('attachments',     'TEXT'),
        ('notes',           'TEXT'),
        ('reject_reason',   'TEXT'),
        ('updated_at',      'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP'),
    ]
    ms_added = sum(1 for col, defn in ms_cols if safe_add('milestone_masters', col, defn))
    ok(f"milestone_masters: {ms_added} columns added") if ms_added else ok("milestone_masters: all columns already exist")

    raw.commit()

    # ══════════════════════════════════════════════════════
    # STEP 12 — R&D Test Parameter Master table + seed
    # ══════════════════════════════════════════════════════
    step("STEP 12: rd_test_parameters table create kar raha hai...")

    if not table_exists('rd_test_parameters'):
        cur.execute("""
            CREATE TABLE rd_test_parameters (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                name        VARCHAR(120) NOT NULL,
                default_val VARCHAR(200) DEFAULT '',
                unit        VARCHAR(50)  DEFAULT '',
                sort_order  INT          DEFAULT 0,
                is_active   TINYINT(1)   DEFAULT 1,
                created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
                updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        raw.commit()
        ok("rd_test_parameters table created")
    else:
        ok("rd_test_parameters table already exists")

    # Add missing columns (safe for re-runs)
    safe_add('rd_test_parameters', 'default_val', "VARCHAR(200) DEFAULT ''")
    safe_add('rd_test_parameters', 'unit',        "VARCHAR(50)  DEFAULT ''")
    safe_add('rd_test_parameters', 'sort_order',  'INT DEFAULT 0')
    safe_add('rd_test_parameters', 'is_active',   'TINYINT(1) DEFAULT 1')
    safe_add('rd_test_parameters', 'created_at',  'DATETIME DEFAULT CURRENT_TIMESTAMP')
    safe_add('rd_test_parameters', 'updated_at',  'DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP')

    # Seed default parameters only if table is empty
    cur.execute("SELECT COUNT(*) FROM rd_test_parameters")
    param_count = cur.fetchone()[0]

    if param_count == 0:
        default_params = [
            (1, 'Appearance',   '',    ''),
            (2, 'Color',        '',    ''),
            (3, 'Odour',        '',    ''),
            (4, 'Transparency', '',    ''),
            (5, 'pH',           '',    ''),
            (6, 'Viscosity',    '',    'cP'),
            (7, 'Spindle No.',  '',    ''),
            (8, 'RPM',          '',    'rpm'),
        ]
        for sort_order, name, default_val, unit in default_params:
            cur.execute(
                "INSERT INTO rd_test_parameters (name, default_val, unit, sort_order, is_active) VALUES (%s, %s, %s, %s, 1)",
                (name, default_val, unit, sort_order)
            )
        raw.commit()
        ok(f"rd_test_parameters: {len(default_params)} default parameters seeded")
    else:
        ok(f"rd_test_parameters: {param_count} parameters already exist — seed skip")

    # Show current parameters
    cur.execute("SELECT sort_order, name, unit, is_active FROM rd_test_parameters ORDER BY sort_order")
    rows = cur.fetchall()
    for sort_order, name, unit, is_active in rows:
        status = f"{G}Active{E}" if is_active else f"{Y}Inactive{E}"
        print(f"     [{sort_order}] {name:<20} unit={unit or '—':<8} {status}")


    # ══════════════════════════════════════════════════════
    # STEP 13 — Seed: NPD Milestone Templates (Default)
    # ══════════════════════════════════════════════════════
    step("STEP 13: NPD Milestone Templates seed kar raha hai...")

    if not table_exists('npd_milestone_templates'):
        ok("npd_milestone_templates table exist nahi — skip (pehle migrate chalao)")
    else:
        # Pehle purane sab delete karo, fresh seed karo
        cur.execute("DELETE FROM npd_milestone_templates")
        raw.commit()

        new_milestones = [
            # (milestone_type,      title,                                icon,  applies_to, default_selected, is_mandatory, sort_order)
            ('bom',                 'BOM',                                '📄', 'both', 1, 0, 1),
            ('ingredients',         'Ingredients List & Marketing Sheet', '📋', 'both', 1, 0, 2),
            ('quotation',           'Quotation',                          '💰', 'both', 1, 0, 3),
            ('packing_material',    'Packing Material',                   '📦', 'both', 1, 0, 4),
            ('artwork',             'Artwork / Design',                   '🎨', 'both', 1, 0, 5),
            ('artwork_qc',          'Artwork QC Approval',                '✅', 'both', 1, 0, 6),
            ('fda',                 'FDA',                                '🏛️', 'both', 1, 0, 7),
            ('barcode',             'Barcode',                            '🔢', 'both', 1, 0, 8),
        ]
        seeded = 0
        for mtype, title, icon, applies_to, default_sel, is_mandatory, sort in new_milestones:
            cur.execute("""
                INSERT INTO npd_milestone_templates
                (milestone_type, title, icon, applies_to, default_selected, is_mandatory, sort_order, is_active, created_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 1, 1)
            """, (mtype, title, icon, applies_to, default_sel, is_mandatory, sort))
            seeded += 1
        raw.commit()
        ok(f"NPD Milestone Templates: {seeded} milestones seeded!")

        # Show current list
        cur.execute("SELECT sort_order, icon, title FROM npd_milestone_templates ORDER BY sort_order")
        for row in cur.fetchall():
            print(f"     [{row[0]}] {row[1]} {row[2]}")

    # ══════════════════════════════════════════════════════
    # STEP 13B — Milestone Status Master table + seed
    # ══════════════════════════════════════════════════════
    step("STEP 13B: milestone_statuses table create kar raha hai...")

    if not table_exists('milestone_statuses'):
        cur.execute("""
            CREATE TABLE milestone_statuses (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                name        VARCHAR(100) NOT NULL,
                slug        VARCHAR(60)  NOT NULL UNIQUE,
                color       VARCHAR(20)  DEFAULT '#6b7280',
                icon        VARCHAR(10)  DEFAULT '🔵',
                sort_order  INT          DEFAULT 0,
                is_active   TINYINT(1)   DEFAULT 1,
                created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
                created_by  INT          NULL,
                modified_by INT          NULL,
                modified_at DATETIME     NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        raw.commit()
        ok("milestone_statuses table created")
    else:
        ok("milestone_statuses table already exists")

    # Seed statuses + milestone names
    cur.execute("SELECT COUNT(*) FROM milestone_statuses")
    ms_st_count = cur.fetchone()[0]
    if ms_st_count == 0:
        milestone_status_defaults = [
            # (name,                                slug,                 color,     icon, sort)
            # ── General statuses ──
            ('Pending',                             'pending',            '#6b7280', '⏳', 1),
            ('In Progress',                         'in_progress',        '#f59e0b', '🔄', 2),
            ('Approved',                            'approved',           '#10b981', '✅', 3),
            ('Rejected',                            'rejected',           '#ef4444', '❌', 4),
            ('Skipped',                             'skipped',            '#94a3b8', '⏭️', 5),
            # ── Milestone names ──
            ('BOM',                                 'bom',                '#7c3aed', '📄', 6),
            ('Ingredients List & Marketing Sheet',  'ingredients',        '#2563eb', '📋', 7),
            ('Quotation',                           'quotation',          '#d97706', '💰', 8),
            ('Packing Material',                    'packing_material',   '#059669', '📦', 9),
            ('Artwork / Design',                    'artwork',            '#db2777', '🎨', 10),
            ('Artwork QC Approval',                 'artwork_qc',         '#10b981', '✅', 11),
            ('FDA',                                 'fda',                '#1d4ed8', '🏛️', 12),
            ('Barcode',                             'barcode',            '#374151', '🔢', 13),
        ]
        for name, slug, color, icon, sort in milestone_status_defaults:
            cur.execute(
                "INSERT IGNORE INTO milestone_statuses (name, slug, color, icon, sort_order, is_active) VALUES (%s,%s,%s,%s,%s,1)",
                (name, slug, color, icon, sort)
            )
        raw.commit()
        ok(f"milestone_statuses: {len(milestone_status_defaults)} records seeded!")
        for name, slug, color, icon, sort in milestone_status_defaults:
            print(f"     [{sort}] {icon} {name}  ({slug})")
    else:
        # Already has some — just add missing milestone names
        cur.execute("SELECT milestone_type, title, icon FROM npd_milestone_templates WHERE is_active=1 ORDER BY sort_order")
        templates = cur.fetchall()
        added = 0
        for idx, (mtype, title, icon) in enumerate(templates, 20):
            cur.execute("SELECT COUNT(*) FROM milestone_statuses WHERE slug=%s", (mtype,))
            if cur.fetchone()[0] == 0:
                cur.execute(
                    "INSERT INTO milestone_statuses (name, slug, color, icon, sort_order, is_active) VALUES (%s,%s,'#6b7280',%s,%s,1)",
                    (title, mtype, icon, idx)
                )
                added += 1
        raw.commit()
        ok(f"milestone_statuses: {ms_st_count} records exist, {added} milestone names added") if added else ok(f"milestone_statuses: {ms_st_count} records already exist — skip")

    # ══════════════════════════════════════════════════════
    # STEP 14 — User-wise Permission Table
    # ══════════════════════════════════════════════════════
    step("STEP 14: user_permissions table create kar raha hai...")

    cur.execute("SHOW TABLES LIKE 'user_permissions'")
    if not cur.fetchone():
        cur.execute("""
            CREATE TABLE user_permissions (
                id            INT AUTO_INCREMENT PRIMARY KEY,
                user_id       INT NOT NULL,
                module_id     INT NOT NULL,
                can_view      TINYINT(1) DEFAULT 0,
                can_add       TINYINT(1) DEFAULT 0,
                can_edit      TINYINT(1) DEFAULT 0,
                can_delete    TINYINT(1) DEFAULT 0,
                can_export    TINYINT(1) DEFAULT 0,
                can_import    TINYINT(1) DEFAULT 0,
                sub_permissions TEXT DEFAULT '{}',
                updated_at    DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                updated_by    INT NULL,
                UNIQUE KEY uq_user_module_perm (user_id, module_id),
                FOREIGN KEY (user_id)   REFERENCES users(id)   ON DELETE CASCADE,
                FOREIGN KEY (module_id) REFERENCES modules(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        raw.commit()
        ok("user_permissions table created!")
    else:
        # Add can_import column if missing
        safe_add('user_permissions', 'can_import', 'TINYINT(1) DEFAULT 0')
        safe_add('role_permissions', 'can_import', 'TINYINT(1) DEFAULT 0')
        ok("user_permissions + role_permissions can_import column ready")

   
    # ══════════════════════════════════════════════════════
    # STEP 14B — Remove deprecated NPD columns
    # ══════════════════════════════════════════════════════
    step("STEP 14B: npd_projects se deprecated columns remove kar raha hai...")

    def safe_drop(table, col):
        """Drop column only if it exists."""
        if table_exists(table) and col_exists(table, col):
            try:
                cur.execute(f"ALTER TABLE `{table}` DROP COLUMN `{col}`")
                raw.commit()
                ok(f"{table}.{col} dropped ✓")
                return True
            except Exception as e:
                warn(f"Could not drop {table}.{col}: {e}")
        else:
            warn(f"{table}.{col} — already removed or doesn't exist, skip")
        return False

    drop_cols = [
        ('npd_projects', 'assigned_sc'),
        ('npd_projects', 'assigned_rd'),
        ('npd_projects', 'npd_poc'),
    ]
    for table, col in drop_cols:
        safe_drop(table, col)

    raw.close()

    # ══════════════════════════════════════════════════════
    # STEP 15 — Fix Duplicate Modules (old names → canonical)
    # ══════════════════════════════════════════════════════
    step("STEP 15: Duplicate modules clean kar raha hai...")

    from models.permission import Module, RolePermission, UserPermission

    # Old name → Canonical name
    RENAME_MAP = {
        'leads'   : 'crm_leads',
        'clients' : 'crm_clients',
        'users'   : 'user_mgmt',
        'admin'   : 'user_mgmt',
        'audit'   : 'audit_logs',
    }

    for old_name, new_name in RENAME_MAP.items():
        old_mod = Module.query.filter_by(name=old_name).first()
        new_mod = Module.query.filter_by(name=new_name).first()
        if not old_mod:
            continue
        if new_mod:
            # Merge: move permissions from old → new, delete old
            for rp in RolePermission.query.filter_by(module_id=old_mod.id).all():
                if not RolePermission.query.filter_by(role=rp.role, module_id=new_mod.id).first():
                    rp.module_id = new_mod.id
                else:
                    db.session.delete(rp)
            for up in UserPermission.query.filter_by(module_id=old_mod.id).all():
                if not UserPermission.query.filter_by(user_id=up.user_id, module_id=new_mod.id).first():
                    up.module_id = new_mod.id
                else:
                    db.session.delete(up)
            for child in Module.query.filter_by(parent_id=old_mod.id).all():
                child.parent_id = new_mod.id
            db.session.delete(old_mod)
            ok(f"Duplicate '{old_name}' → '{new_name}' merged & deleted")
        else:
            old_mod.name = new_name
            ok(f"Module '{old_name}' → '{new_name}' renamed")

    # Fix parent_id for child modules
    parent_map = {'crm_leads': 'crm', 'crm_clients': 'crm',
                  'hr_employees': 'hr', 'hr_contractors': 'hr'}
    for child_name, parent_name in parent_map.items():
        child  = Module.query.filter_by(name=child_name).first()
        parent = Module.query.filter_by(name=parent_name).first()
        if child and parent and child.parent_id != parent.id:
            child.parent_id = parent.id
            ok(f"'{child_name}' parent fixed → '{parent_name}'")

    db.session.commit()
    ok("Duplicate module cleanup done!")


    # ══════════════════════════════════════════════════════
    # STEP 16 — Attendance Tables
    # ══════════════════════════════════════════════════════
    step("STEP 16: Attendance tables create kar raha hai...")

    from models.attendance import RawPunchLog, Attendance

    # Tables already create ho jaayengi db.create_all() se (STEP 1)
    # Lekin agar pehle se run ho chuki hai migration, manually ensure karein

    import pymysql as _pym
    _uri2 = db.engine.url
    _ac = _pym.connect(
        host=str(_uri2.host), port=int(_uri2.port or 3306),
        user=str(_uri2.username), password=str(_uri2.password),
        database=str(_uri2.database), charset='utf8mb4'
    )
    _ac_cur = _ac.cursor()

    # raw_punch_logs table
    _ac_cur.execute("""
        CREATE TABLE IF NOT EXISTS `raw_punch_logs` (
            `id`                INT(11) NOT NULL AUTO_INCREMENT,
            `employee_code`     VARCHAR(100) NOT NULL,
            `log_date`          DATETIME NOT NULL,
            `serial_number`     VARCHAR(100) DEFAULT NULL,
            `punch_direction`   VARCHAR(20) DEFAULT NULL,
            `temperature`       DECIMAL(5,2) DEFAULT 0.00,
            `temperature_state` VARCHAR(50) DEFAULT NULL,
            `synced_at`         DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            INDEX idx_emp_code (employee_code),
            INDEX idx_log_date (log_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
    """)
    _ac.commit()
    ok("raw_punch_logs table ready")

    # attendance table
    _ac_cur.execute("""
        CREATE TABLE IF NOT EXISTS `attendance` (
            `id`              INT(11) NOT NULL AUTO_INCREMENT,
            `employee_code`   VARCHAR(100) NOT NULL,
            `attendance_date` DATE NOT NULL,
            `punch_in`        DATETIME DEFAULT NULL,
            `punch_out`       DATETIME DEFAULT NULL,
            `in_device`       VARCHAR(100) DEFAULT NULL,
            `out_device`      VARCHAR(100) DEFAULT NULL,
            `total_hours`     DECIMAL(5,2) DEFAULT NULL,
            `status`          ENUM('Present','Absent','Half Day','Holiday','MIS-PUNCH')
                              NOT NULL DEFAULT 'Present',
            `created_at`      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
            `updated_at`      DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                              ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY uq_emp_date (`employee_code`, `attendance_date`),
            INDEX idx_att_date (attendance_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
    """)
    _ac.commit()
    ok("attendance table ready")

    # late_shift_rules table
    _ac_cur.execute("""
        CREATE TABLE IF NOT EXISTS `late_shift_rules` (
            `id`              INT NOT NULL AUTO_INCREMENT,
            `employee_type`   VARCHAR(100) NOT NULL,
            `shift_start`     VARCHAR(5) DEFAULT '09:00',
            `late_after`      VARCHAR(5) NOT NULL,
            `half_day_after`  VARCHAR(5) DEFAULT NULL,
            `absent_after`    VARCHAR(5) DEFAULT NULL,
            `shift_end`       VARCHAR(5) DEFAULT '18:00',
            `min_hours_full`  DECIMAL(4,2) DEFAULT 8.00,
            `min_hours_half`  DECIMAL(4,2) DEFAULT 4.00,
            `is_active`       TINYINT(1) DEFAULT 1,
            `created_at`      DATETIME DEFAULT CURRENT_TIMESTAMP,
            `created_by`      INT DEFAULT NULL,
            `updated_at`      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY uq_emp_type (`employee_type`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    _ac.commit()
    ok("late_shift_rules table ready")

    # late_penalty_rules table
    _ac_cur.execute("""
        CREATE TABLE IF NOT EXISTS `late_penalty_rules` (
            `id`              INT NOT NULL AUTO_INCREMENT,
            `shift_rule_id`   INT NOT NULL,
            `time_from`       VARCHAR(5) NOT NULL,
            `time_to`         VARCHAR(5) DEFAULT NULL,
            `from_count`      INT NOT NULL DEFAULT 1,
            `to_count`        INT DEFAULT NULL,
            `penalty_amount`  DECIMAL(8,2) NOT NULL DEFAULT 0,
            `penalty_type`    VARCHAR(20) DEFAULT 'fixed',
            `description`     VARCHAR(200) DEFAULT NULL,
            `is_active`       TINYINT(1) DEFAULT 1,
            `sort_order`      INT DEFAULT 0,
            `created_at`      DATETIME DEFAULT CURRENT_TIMESTAMP,
            `created_by`      INT DEFAULT NULL,
            PRIMARY KEY (`id`),
            KEY idx_shift_rule (`shift_rule_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    _ac.commit()
    ok("late_penalty_rules table ready")

    # employee_type_master table
    _ac_cur.execute("""
        CREATE TABLE IF NOT EXISTS `employee_type_master` (
            `id`         INT(11) NOT NULL AUTO_INCREMENT,
            `name`       VARCHAR(100) NOT NULL,
            `sort_order` INT DEFAULT 0,
            `is_active`  TINYINT(1) DEFAULT 1,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `created_by` INT DEFAULT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY uq_et_name (`name`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    _ac.commit()
    ok("employee_type_master table ready")

    # employee_location_master table
    _ac_cur.execute("""
        CREATE TABLE IF NOT EXISTS `employee_location_master` (
            `id`         INT(11) NOT NULL AUTO_INCREMENT,
            `name`       VARCHAR(100) NOT NULL,
            `sort_order` INT DEFAULT 0,
            `is_active`  TINYINT(1) DEFAULT 1,
            `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
            `created_by` INT DEFAULT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY uq_el_name (`name`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """)
    _ac.commit()
    ok("employee_location_master table ready")

    # holiday_master table
    _ac_cur.execute("""
        CREATE TABLE IF NOT EXISTS `holiday_master` (
            `id`           INT(11) NOT NULL AUTO_INCREMENT,
            `title`        VARCHAR(200) NOT NULL,
            `holiday_date` DATE NOT NULL,
            `holiday_type` VARCHAR(50) DEFAULT 'National',
            `description`  VARCHAR(300) DEFAULT NULL,
            `is_active`    TINYINT(1) DEFAULT 1,
            `created_at`   DATETIME DEFAULT CURRENT_TIMESTAMP,
            `created_by`   INT DEFAULT NULL,
            PRIMARY KEY (`id`),
            UNIQUE KEY uq_holiday_date (`holiday_date`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_general_ci
    """)
    _ac.commit()
    ok("holiday_master table ready")

    _ac_cur.close()
    _ac.close()

    # Add 'hr_attendance' module to permissions
    from models.permission import Module, RolePermission
    att_mod = Module.query.filter_by(name='hr_attendance').first()
    if not att_mod:
        att_mod = Module(
            name='hr_attendance', label='Attendance',
            icon='🕐', url_prefix='/hr/attendance',
            sort_order=50, is_active=True
        )
        db.session.add(att_mod)
        db.session.flush()
        ok("hr_attendance module added")

        roles = ["admin", "manager", "sales", "hr", "viewer"]
        for role in roles:
            can_write  = role in ("admin", "manager", "hr")
            can_delete = role == "admin"
            can_export = role != "viewer"
            db.session.add(RolePermission(
                role=role, module_id=att_mod.id,
                can_view=True, can_add=can_write,
                can_edit=can_write, can_delete=can_delete,
                can_export=can_export, can_import=False,
            ))
        ok("hr_attendance permissions seeded for all roles")
    else:
        ok("hr_attendance module already exists")

    db.session.commit()
    ok("Attendance migration complete!")


    # ══════════════════════════════════════════════════════
    # STEP 17 — Comprehensive HR Rules Tables
    # ══════════════════════════════════════════════════════
    step("STEP 17: HR Rules tables create kar raha hai (Shift/Location/Leave/OT/LOP/CompOff)...")

    import pymysql as _pym17
    _uri17 = db.engine.url
    _c17 = _pym17.connect(
        host=str(_uri17.host), port=int(_uri17.port or 3306),
        user=str(_uri17.username), password=str(_uri17.password),
        database=str(_uri17.database), charset='utf8mb4'
    )
    _cur17 = _c17.cursor()

    def _t(t): 
        _cur17.execute("SELECT COUNT(*) FROM information_schema.tables WHERE table_schema=DATABASE() AND table_name=%s", (t,))
        return _cur17.fetchone()[0] > 0

    # 1. Shift Master
    if not _t('hr_shifts'):
        _cur17.execute("""
            CREATE TABLE hr_shifts (
                id              INT AUTO_INCREMENT PRIMARY KEY,
                name            VARCHAR(100) NOT NULL,
                code            VARCHAR(20) NOT NULL UNIQUE,
                shift_start     VARCHAR(5) NOT NULL,
                shift_end       VARCHAR(5) NOT NULL,
                late_after      VARCHAR(5),
                half_day_after  VARCHAR(5),
                absent_after    VARCHAR(5),
                early_go_before VARCHAR(5),
                min_hours_full  DECIMAL(4,2) DEFAULT 8.00,
                min_hours_half  DECIMAL(4,2) DEFAULT 4.00,
                break_minutes   INT DEFAULT 60,
                weekly_off      VARCHAR(50) DEFAULT 'Sunday',
                color           VARCHAR(10) DEFAULT '#2563eb',
                is_active       TINYINT(1) DEFAULT 1,
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by      INT,
                updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        _c17.commit()
        # Seed default shifts
        _shifts = [
            ('General',  'GEN',  '09:00','18:00','09:15','13:00','14:00','17:30', 8.0, 4.0, 60, 'Sunday',    '#2563eb'),
            ('Morning',  'MORN', '06:00','14:00','06:15','10:00','11:00','13:30', 8.0, 4.0, 30, 'Sunday',    '#16a34a'),
            ('Evening',  'EVE',  '14:00','22:00','14:15','18:00','19:00','21:30', 8.0, 4.0, 30, 'Sunday',    '#d97706'),
            ('Night',    'NGHT', '22:00','06:00','22:15','02:00','03:00','05:30', 8.0, 4.0, 30, 'Sunday',    '#7c3aed'),
            ('Half Day', 'HALF', '09:00','13:00','09:15','11:00', None,   '12:30', 4.0, 4.0, 0,  'Sunday',    '#0d9488'),
        ]
        for name,code,ss,se,la,hda,aa,egb,mhf,mhh,brk,woff,color in _shifts:
            _cur17.execute(
                "INSERT IGNORE INTO hr_shifts (name,code,shift_start,shift_end,late_after,half_day_after,absent_after,early_go_before,min_hours_full,min_hours_half,break_minutes,weekly_off,color) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (name,code,ss,se,la,hda,aa,egb,mhf,mhh,brk,woff,color)
            )
        _c17.commit()
        ok(f"hr_shifts: created + {len(_shifts)} default shifts seeded")
    else:
        ok("hr_shifts: already exists")

    # 2. Location Master
    if not _t('hr_locations'):
        _cur17.execute("""
            CREATE TABLE hr_locations (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                name       VARCHAR(100) NOT NULL UNIQUE,
                code       VARCHAR(20) NOT NULL UNIQUE,
                address    TEXT,
                city       VARCHAR(100),
                state      VARCHAR(100),
                is_active  TINYINT(1) DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by INT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        _c17.commit()
        _locs = [('HCP OFFICE','OFFICE','Surat','Gujarat'),('HCP FACTORY','FACTORY','Surat','Gujarat'),('WFH','WFH','',''),('OTHER','OTHER','','')]
        for name,code,city,state in _locs:
            _cur17.execute("INSERT IGNORE INTO hr_locations (name,code,city,state) VALUES (%s,%s,%s,%s)", (name,code,city,state))
        _c17.commit()
        ok(f"hr_locations: created + {len(_locs)} locations seeded")
    else:
        ok("hr_locations: already exists")

    # 3. HR Late Rules
    if not _t('hr_late_rules'):
        _cur17.execute("""
            CREATE TABLE hr_late_rules (
                id                   INT AUTO_INCREMENT PRIMARY KEY,
                location_id          INT, shift_id INT, employee_type VARCHAR(100),
                grace_minutes        INT DEFAULT 0,
                late_after           VARCHAR(5),
                half_day_after       VARCHAR(5),
                absent_after         VARCHAR(5),
                free_lates_per_month INT DEFAULT 0,
                auto_deduct_lop      TINYINT(1) DEFAULT 0,
                is_active            TINYINT(1) DEFAULT 1,
                notes                TEXT,
                created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by           INT,
                updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES hr_locations(id),
                FOREIGN KEY (shift_id)    REFERENCES hr_shifts(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        _c17.commit()
        ok("hr_late_rules: created")
    else:
        ok("hr_late_rules: already exists")

    # 4. HR Late Penalty Slabs
    if not _t('hr_late_penalty_slabs'):
        _cur17.execute("""
            CREATE TABLE hr_late_penalty_slabs (
                id             INT AUTO_INCREMENT PRIMARY KEY,
                late_rule_id   INT NOT NULL,
                time_from      VARCHAR(5) NOT NULL,
                time_to        VARCHAR(5),
                from_count     INT DEFAULT 1,
                to_count       INT,
                penalty_amount DECIMAL(8,2) DEFAULT 0,
                penalty_type   VARCHAR(20) DEFAULT 'fixed',
                description    VARCHAR(200),
                sort_order     INT DEFAULT 0,
                is_active      TINYINT(1) DEFAULT 1,
                created_at     DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (late_rule_id) REFERENCES hr_late_rules(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        _c17.commit()
        ok("hr_late_penalty_slabs: created")
    else:
        ok("hr_late_penalty_slabs: already exists")

    # 5. Early Going Rules
    if not _t('hr_early_going_rules'):
        _cur17.execute("""
            CREATE TABLE hr_early_going_rules (
                id                   INT AUTO_INCREMENT PRIMARY KEY,
                location_id          INT, shift_id INT, employee_type VARCHAR(100),
                name                 VARCHAR(150) NOT NULL,
                grace_minutes        INT DEFAULT 0,
                half_day_before      VARCHAR(5),
                absent_before        VARCHAR(5),
                free_early_per_month INT DEFAULT 0,
                penalty_per_early    DECIMAL(8,2) DEFAULT 0,
                penalty_type         VARCHAR(20) DEFAULT 'fixed',
                auto_deduct_lop      TINYINT(1) DEFAULT 0,
                is_active            TINYINT(1) DEFAULT 1,
                notes                TEXT,
                created_at           DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by           INT,
                updated_at           DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES hr_locations(id),
                FOREIGN KEY (shift_id)    REFERENCES hr_shifts(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        _c17.commit()
        ok("hr_early_going_rules: created")
    else:
        ok("hr_early_going_rules: already exists")

    # 6. Overtime Rules
    if not _t('hr_overtime_rules'):
        _cur17.execute("""
            CREATE TABLE hr_overtime_rules (
                id                    INT AUTO_INCREMENT PRIMARY KEY,
                location_id           INT, shift_id INT, employee_type VARCHAR(100),
                name                  VARCHAR(150) NOT NULL,
                ot_after_minutes      INT DEFAULT 30,
                min_ot_minutes        INT DEFAULT 60,
                max_ot_hours_day      DECIMAL(4,2) DEFAULT 4,
                max_ot_hours_month    DECIMAL(6,2) DEFAULT 50,
                ot_rate_type          VARCHAR(20) DEFAULT '1.5x',
                ot_fixed_rate         DECIMAL(8,2),
                weekend_ot_rate       VARCHAR(20) DEFAULT '2x',
                holiday_ot_rate       VARCHAR(20) DEFAULT '2x',
                give_compoff          TINYINT(1) DEFAULT 0,
                compoff_min_hours     DECIMAL(4,2) DEFAULT 4,
                is_active             TINYINT(1) DEFAULT 1,
                notes                 TEXT,
                created_at            DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by            INT,
                updated_at            DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES hr_locations(id),
                FOREIGN KEY (shift_id)    REFERENCES hr_shifts(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        _c17.commit()
        ok("hr_overtime_rules: created")
    else:
        ok("hr_overtime_rules: already exists")

    # 7. Leave Policies
    if not _t('hr_leave_policies'):
        _cur17.execute("""
            CREATE TABLE hr_leave_policies (
                id                     INT AUTO_INCREMENT PRIMARY KEY,
                name                   VARCHAR(150) NOT NULL,
                location_id            INT,
                employee_type          VARCHAR(100),
                applicable_from        DATE,
                accrual_type           VARCHAR(20) DEFAULT 'yearly',
                sandwich_rule          TINYINT(1) DEFAULT 1,
                carry_forward          TINYINT(1) DEFAULT 1,
                max_carry_forward      INT DEFAULT 15,
                encashment             TINYINT(1) DEFAULT 0,
                max_encashment         INT DEFAULT 10,
                probation_leave_allowed TINYINT(1) DEFAULT 0,
                allow_negative_leave   TINYINT(1) DEFAULT 0,
                max_negative_days      INT DEFAULT 0,
                is_active              TINYINT(1) DEFAULT 1,
                notes                  TEXT,
                created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by             INT,
                updated_at             DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES hr_locations(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        _c17.commit()
        ok("hr_leave_policies: created")
    else:
        ok("hr_leave_policies: already exists")

    # 8. Leave Types
    if not _t('hr_leave_types'):
        _cur17.execute("""
            CREATE TABLE hr_leave_types (
                id                  INT AUTO_INCREMENT PRIMARY KEY,
                policy_id           INT NOT NULL,
                name                VARCHAR(100) NOT NULL,
                code                VARCHAR(20) NOT NULL,
                days_per_year       DECIMAL(5,1) NOT NULL,
                min_days            DECIMAL(3,1) DEFAULT 0.5,
                max_days            DECIMAL(5,1),
                advance_notice_days INT DEFAULT 0,
                carry_forward       TINYINT(1) DEFAULT 1,
                max_carry_forward   INT,
                encashable          TINYINT(1) DEFAULT 0,
                paid                TINYINT(1) DEFAULT 1,
                gender              VARCHAR(10),
                color               VARCHAR(10) DEFAULT '#2563eb',
                icon                VARCHAR(10) DEFAULT '📅',
                sort_order          INT DEFAULT 0,
                is_active           TINYINT(1) DEFAULT 1,
                created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (policy_id) REFERENCES hr_leave_policies(id) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        _c17.commit()
        ok("hr_leave_types: created")
    else:
        ok("hr_leave_types: already exists")

    # 9. LOP Rules
    if not _t('hr_lop_rules'):
        _cur17.execute("""
            CREATE TABLE hr_lop_rules (
                id                       INT AUTO_INCREMENT PRIMARY KEY,
                name                     VARCHAR(150) NOT NULL,
                location_id              INT,
                employee_type            VARCHAR(100),
                lop_basis                VARCHAR(20) DEFAULT 'working_days',
                paid_days_basis          VARCHAR(20) DEFAULT 'actual',
                absent_triggers_lop      TINYINT(1) DEFAULT 1,
                late_triggers_lop        TINYINT(1) DEFAULT 0,
                late_lop_after_count     INT DEFAULT 3,
                lop_per_late_count       INT DEFAULT 3,
                half_day_lop_after_count INT DEFAULT 3,
                daily_rate_formula       VARCHAR(50) DEFAULT 'basic_gross/working_days',
                include_allowances       TINYINT(1) DEFAULT 1,
                is_active                TINYINT(1) DEFAULT 1,
                notes                    TEXT,
                created_at               DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by               INT,
                updated_at               DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES hr_locations(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        _c17.commit()
        ok("hr_lop_rules: created")
    else:
        ok("hr_lop_rules: already exists")

    # 10. Absent Rules
    if not _t('hr_absent_rules'):
        _cur17.execute("""
            CREATE TABLE hr_absent_rules (
                id                      INT AUTO_INCREMENT PRIMARY KEY,
                name                    VARCHAR(150) NOT NULL,
                location_id             INT, employee_type VARCHAR(100),
                absent_days_from        INT DEFAULT 1,
                absent_days_to          INT,
                penalty_per_day         DECIMAL(8,2) DEFAULT 0,
                penalty_type            VARCHAR(20) DEFAULT 'fixed',
                consecutive_absent_days INT DEFAULT 3,
                auto_terminate_days     INT,
                notify_hr               TINYINT(1) DEFAULT 1,
                is_active               TINYINT(1) DEFAULT 1,
                notes                   TEXT,
                created_at              DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by              INT,
                updated_at              DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES hr_locations(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        _c17.commit()
        ok("hr_absent_rules: created")
    else:
        ok("hr_absent_rules: already exists")

    # 11. Comp Off Rules
    if not _t('hr_compoff_rules'):
        _cur17.execute("""
            CREATE TABLE hr_compoff_rules (
                id                     INT AUTO_INCREMENT PRIMARY KEY,
                name                   VARCHAR(150) NOT NULL,
                location_id            INT, employee_type VARCHAR(100),
                min_hours_worked       DECIMAL(4,2) DEFAULT 4,
                comp_off_days          DECIMAL(3,1) DEFAULT 1,
                applicable_on_sunday   TINYINT(1) DEFAULT 1,
                applicable_on_holiday  TINYINT(1) DEFAULT 1,
                applicable_on_saturday TINYINT(1) DEFAULT 1,
                comp_off_validity_days INT DEFAULT 30,
                needs_approval         TINYINT(1) DEFAULT 1,
                max_comp_off_balance   DECIMAL(4,1) DEFAULT 6,
                is_active              TINYINT(1) DEFAULT 1,
                notes                  TEXT,
                created_at             DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by             INT,
                updated_at             DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                FOREIGN KEY (location_id) REFERENCES hr_locations(id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        _c17.commit()
        ok("hr_compoff_rules: created")
    else:
        ok("hr_compoff_rules: already exists")


    # ── Early Coming Rules table ──
    if not _t('early_coming_rules'):
        _cur17.execute("""
            CREATE TABLE early_coming_rules (
                id                INT AUTO_INCREMENT PRIMARY KEY,
                employee_type     VARCHAR(100) NOT NULL UNIQUE,
                shift_start       VARCHAR(5) DEFAULT '09:00',
                early_before      VARCHAR(5) NOT NULL,
                min_early_minutes INT DEFAULT 15,
                reward_type       VARCHAR(20) DEFAULT 'none',
                reward_amount     DECIMAL(8,2) DEFAULT 0,
                reward_points     INT DEFAULT 0,
                min_per_month     INT DEFAULT 0,
                track_only        TINYINT(1) DEFAULT 1,
                is_active         TINYINT(1) DEFAULT 1,
                notes             TEXT,
                created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_by        INT,
                updated_at        DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        _c17.commit()
        ok("early_coming_rules: created")
    else:
        ok("early_coming_rules: already exists")

    _cur17.close()
    _c17.close()
    ok("✅ All HR Rules tables ready!")

    # ══════════════════════════════════════════════════════
    # DONE
    # ══════════════════════════════════════════════════════
    print(f"\n{'='*60}")
    print(f"  {G}{B}✅ MIGRATION COMPLETE!{E}")
    print(f"{'='*60}")
    print(f"\n  Ab server start karo:")
    print(f"  {B}python index.py{E}")
    print(f"\n  Login: {B}admin / HCP@123{E}\n")
