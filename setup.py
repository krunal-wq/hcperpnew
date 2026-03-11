#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║           ERP CRM — ONE-CLICK SETUP SCRIPT                       ║
║  Run: python setup.py                                            ║
║  Yeh script automatically:                                       ║
║    1. Python packages install karega                             ║
║    2. Database + user create karega                              ║
║    3. Saari tables create karega                                 ║
║    4. Master data seed karega (modules, permissions, statuses)   ║
║    5. Admin user create karega                                   ║
╚══════════════════════════════════════════════════════════════════╝
"""

import sys
import os
import subprocess

# ══════════════════════════════════════════════════════════
# STEP 0 — CONFIG (sirf yahan change karo)
# ══════════════════════════════════════════════════════════

DB_HOST     = "localhost"
DB_PORT     = 3306
DB_NAME     = "erpdb"
DB_USER     = "root"          # MySQL root user
DB_PASSWORD = "Krunal@2424"   # MySQL root password
APP_SECRET  = "erp-super-secret-key-2024"

# Admin user jo create hoga
ADMIN_NAME     = "Admin"
ADMIN_EMAIL    = "admin@erp.com"
ADMIN_PASSWORD = "Admin@123"
ADMIN_ROLE     = "admin"

# ══════════════════════════════════════════════════════════

CYAN   = "\033[96m"
GREEN  = "\033[92m"
YELLOW = "\033[93m"
RED    = "\033[91m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def banner():
    print(f"""
{CYAN}{BOLD}
╔══════════════════════════════════════════════════════════╗
║           ERP CRM — SETUP SCRIPT v7                     ║
╚══════════════════════════════════════════════════════════╝
{RESET}""")

def ok(msg):   print(f"  {GREEN}✅ {msg}{RESET}")
def info(msg): print(f"  {CYAN}ℹ  {msg}{RESET}")
def warn(msg): print(f"  {YELLOW}⚠  {msg}{RESET}")
def err(msg):  print(f"  {RED}❌ {msg}{RESET}")
def step(msg): print(f"\n{BOLD}{YELLOW}── {msg}{RESET}")

# ══════════════════════════════════════════════════════════
# STEP 1 — Install Python packages
# ══════════════════════════════════════════════════════════

def install_packages():
    step("STEP 1: Python packages install kar raha hai...")
    req_file = os.path.join(os.path.dirname(__file__), "requirements.txt")
    if not os.path.exists(req_file):
        err("requirements.txt nahi mila!")
        sys.exit(1)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-r", req_file, "--quiet"],
        capture_output=True, text=True
    )
    if result.returncode != 0:
        err("Package install failed:")
        print(result.stderr)
        sys.exit(1)
    ok("Saare packages install ho gaye")

# ══════════════════════════════════════════════════════════
# STEP 2 — Create Database
# ══════════════════════════════════════════════════════════

def create_database():
    step("STEP 2: Database create kar raha hai...")
    try:
        import pymysql
    except ImportError:
        subprocess.run([sys.executable, "-m", "pip", "install", "pymysql", "--quiet"])
        import pymysql

    try:
        conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD,
            charset='utf8mb4'
        )
        cur = conn.cursor()
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
        cur.execute(f"USE `{DB_NAME}`")
        conn.commit()
        conn.close()
        ok(f"Database '{DB_NAME}' ready hai")
    except pymysql.err.OperationalError as e:
        err(f"MySQL connection failed: {e}")
        print(f"\n  {YELLOW}Check karo:{RESET}")
        print(f"    • MySQL server chal raha hai?")
        print(f"    • DB_USER/DB_PASSWORD sahi hai? (setup.py ke upar change karo)")
        print(f"    • Host: {DB_HOST}:{DB_PORT}")
        sys.exit(1)

# ══════════════════════════════════════════════════════════
# STEP 3 — Update config.py with correct DB URL
# ══════════════════════════════════════════════════════════

def update_config():
    step("STEP 3: config.py update kar raha hai...")
    from urllib.parse import quote_plus
    encoded_pass = quote_plus(DB_PASSWORD)
    db_url = f"mysql+pymysql://{DB_USER}:{encoded_pass}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

    config_path = os.path.join(os.path.dirname(__file__), "config.py")
    config_content = f'''import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or '{APP_SECRET}'

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \\
        '{db_url}'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {{
        'pool_recycle': 280,
        'pool_pre_ping': True,
    }}

    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = 1800
'''
    with open(config_path, 'w') as f:
        f.write(config_content)
    ok(f"config.py updated — DB: {DB_HOST}/{DB_NAME}")

# ══════════════════════════════════════════════════════════
# STEP 4 — Create all tables
# ══════════════════════════════════════════════════════════

def create_tables():
    step("STEP 4: Database tables create kar raha hai...")
    sys.path.insert(0, os.path.dirname(__file__))

    from flask import Flask
    from config import Config
    from models.base import db
    import models.user
    import models.lead
    import models.client
    import models.employee
    import models.master
    import models.permission
    import models.audit
    import models.legacy

    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)

    with app.app_context():
        db.create_all()
        ok("Saari tables create ho gayi")

    return app, db

# ══════════════════════════════════════════════════════════
# STEP 5 — Seed master data
# ══════════════════════════════════════════════════════════

def seed_master_data(app, db):
    step("STEP 5: Master data seed kar raha hai...")

    from models.master import LeadStatus, LeadSource, LeadCategory, ProductRange
    from models.permission import Module, RolePermission

    with app.app_context():

        # ── Lead Statuses ──
        statuses = [
            ("open",       "Open",       "📧", "#6366f1", 1),
            ("in_process", "In Process", "⚙️",  "#1e3a5f", 2),
            ("close",      "Close",      "✅", "#059669", 3),
            ("cancel",     "Cancel",     "❌", "#dc2626", 4),
        ]
        for val, label, icon, color, sort in statuses:
            if not LeadStatus.query.filter_by(value=val).first():
                db.session.add(LeadStatus(value=val, label=label, icon=icon,
                                          color=color, sort_order=sort, is_active=True))

        # ── Lead Sources ──
        sources = ["India Mart","Just Dial","Cold Call","Social Media","HCP Website",
                   "Exhibition","Pharma Hopper","Reference","WhatsApp","Email Campaign"]
        for i, s in enumerate(sources, 1):
            if not LeadSource.query.filter_by(name=s).first():
                db.session.add(LeadSource(name=s, sort_order=i, is_active=True))

        # ── Lead Categories ──
        categories = ["Cosmetics","Baby Care","Oral Care","Hair Care","Pharma",
                      "Nutraceutical","Veterinary","Food Supplement"]
        for i, c in enumerate(categories, 1):
            if not LeadCategory.query.filter_by(name=c).first():
                db.session.add(LeadCategory(name=c, sort_order=i, is_active=True))

        # ── Product Ranges ──
        ranges = ["Body Lotion","Face Cream","Shampoo","Gel","Syrup","Tablets",
                  "Lip Balm","Serum","Toner","Eye Drop","Ointment","Capsules"]
        for i, r in enumerate(ranges, 1):
            if not ProductRange.query.filter_by(name=r).first():
                db.session.add(ProductRange(name=r, sort_order=i, is_active=True))

        db.session.commit()
        ok("Lead statuses, sources, categories, product ranges added")

        # ── Modules ──
        modules_data = [
            # (name, label, icon, url_prefix, sort)
            ("dashboard", "Dashboard",  "🏠", "/",          1),
            ("crm",       "CRM",        "📋", "/crm",       2),
            ("leads",     "Leads",      "📋", "/crm/leads", 3),
            ("clients",   "Clients",    "🏢", "/crm/clients",4),
            ("hr",        "HR",         "👥", "/hr",        5),
            ("employees", "Employees",  "👤", "/hr/employees",6),
            ("contractors","Contractors","🔧","/hr/contractors",7),
            ("masters",   "Masters",    "⚙️",  "/masters",   8),
            ("admin",     "Admin",      "🔐", "/admin",     9),
            ("users",     "Users",      "👤", "/admin/users",10),
            ("audit",     "Audit Logs", "🔍", "/admin/audit-logs",11),
        ]
        for name, label, icon, url, sort in modules_data:
            if not Module.query.filter_by(name=name).first():
                db.session.add(Module(name=name, label=label, icon=icon,
                                      url_prefix=url, sort_order=sort, is_active=True))
        db.session.commit()

        # ── Role Permissions — admin gets all ──
        roles = ["admin", "manager", "sales", "hr", "viewer"]
        modules = Module.query.all()
        for role in roles:
            for mod in modules:
                if not RolePermission.query.filter_by(role=role, module_id=mod.id).first():
                    can_write = role in ("admin", "manager", "sales")
                    can_delete = role == "admin"
                    db.session.add(RolePermission(
                        role=role, module_id=mod.id,
                        can_view=True,
                        can_create=can_write,
                        can_edit=can_write,
                        can_delete=can_delete,
                        can_export=(role != "viewer"),
                    ))
        db.session.commit()
        ok("Modules aur role permissions seed ho gaye")

# ══════════════════════════════════════════════════════════
# STEP 6 — Create Admin User
# ══════════════════════════════════════════════════════════

def create_admin(app, db):
    step("STEP 6: Admin user create kar raha hai...")
    from models.user import User
    from werkzeug.security import generate_password_hash

    with app.app_context():
        existing = User.query.filter_by(email=ADMIN_EMAIL).first()
        if existing:
            warn(f"Admin user already exists: {ADMIN_EMAIL}")
            return

        admin = User(
            full_name=ADMIN_NAME,
            email=ADMIN_EMAIL,
            username=ADMIN_EMAIL.split('@')[0],
            role=ADMIN_ROLE,
            is_active=True,
            password_hash=generate_password_hash(ADMIN_PASSWORD)
        )
        db.session.add(admin)
        db.session.commit()
        ok(f"Admin user created!")
        print(f"\n  {BOLD}Login credentials:{RESET}")
        print(f"  {CYAN}Email   : {ADMIN_EMAIL}{RESET}")
        print(f"  {CYAN}Password: {ADMIN_PASSWORD}{RESET}")

# ══════════════════════════════════════════════════════════
# STEP 7 — Add missing columns (safe ALTER TABLE)
# ══════════════════════════════════════════════════════════

def add_missing_columns(app, db):
    step("STEP 7: Missing columns check kar raha hai (ALTER TABLE)...")
    import pymysql
    from urllib.parse import quote_plus

    try:
        conn = pymysql.connect(
            host=DB_HOST, port=DB_PORT,
            user=DB_USER, password=DB_PASSWORD,
            database=DB_NAME, charset='utf8mb4'
        )
        cur = conn.cursor()

        # Safe add column helper
        def safe_add(table, col, col_def):
            cur.execute(f"SHOW COLUMNS FROM `{table}` LIKE '{col}'")
            if not cur.fetchone():
                try:
                    cur.execute(f"ALTER TABLE `{table}` ADD COLUMN `{col}` {col_def}")
                    info(f"  Added: {table}.{col}")
                except Exception as e:
                    warn(f"  Skip {table}.{col}: {e}")

        # leads table
        safe_add("leads", "code",             "VARCHAR(20) UNIQUE")
        safe_add("leads", "title",            "VARCHAR(200)")
        safe_add("leads", "position",         "VARCHAR(100)")
        safe_add("leads", "address",          "TEXT")
        safe_add("leads", "city",             "VARCHAR(100)")
        safe_add("leads", "state",            "VARCHAR(100)")
        safe_add("leads", "country",          "VARCHAR(100) DEFAULT 'India'")
        safe_add("leads", "zip_code",         "VARCHAR(10)")
        safe_add("leads", "average_cost",     "DECIMAL(12,2) DEFAULT 0")
        safe_add("leads", "category",         "VARCHAR(100)")
        safe_add("leads", "product_range",    "VARCHAR(100)")
        safe_add("leads", "order_quantity",   "VARCHAR(100)")
        safe_add("leads", "requirement_spec", "TEXT")
        safe_add("leads", "tags",             "VARCHAR(300)")
        safe_add("leads", "remark",           "TEXT")
        safe_add("leads", "last_contact",     "DATETIME")
        safe_add("leads", "team_members",     "TEXT")
        safe_add("leads", "client_id",        "INT")
        safe_add("leads", "client_attachment","VARCHAR(300)")
        safe_add("leads", "modified_by",      "INT")
        safe_add("leads", "alternate_mobile", "VARCHAR(20)")

        # users table
        safe_add("users", "created_by",  "INT")
        safe_add("users", "modified_by", "INT")
        safe_add("users", "updated_at",  "DATETIME")
        safe_add("users", "phone",       "VARCHAR(20)")
        safe_add("users", "department",  "VARCHAR(100)")
        safe_add("users", "avatar",      "VARCHAR(300)")

        # employees table
        safe_add("employees", "modified_by", "INT")

        # client_masters table
        safe_add("client_masters", "modified_by", "INT")

        # contractors table
        safe_add("contractors", "modified_by", "INT")

        # lead_statuses / sources / categories / product_ranges
        for tbl in ["lead_statuses", "lead_sources", "lead_categories", "product_ranges"]:
            safe_add(tbl, "created_by",  "INT")
            safe_add(tbl, "modified_by", "INT")
            safe_add(tbl, "modified_at", "DATETIME")

        conn.commit()
        conn.close()
        ok("Column check complete")
    except Exception as e:
        warn(f"Column migration warning: {e}")

# ══════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════

def main():
    banner()

    print(f"  {BOLD}Database : {DB_HOST}/{DB_NAME}{RESET}")
    print(f"  {BOLD}DB User  : {DB_USER}{RESET}")
    print(f"  {BOLD}App Dir  : {os.path.dirname(os.path.abspath(__file__))}{RESET}")

    print(f"\n  {YELLOW}Proceed karna hai? (y/n):{RESET} ", end="")
    ans = input().strip().lower()
    if ans not in ('y', 'yes', ''):
        print("  Setup cancelled.")
        sys.exit(0)

    try:
        install_packages()
        create_database()
        update_config()
        app, db = create_tables()
        seed_master_data(app, db)
        create_admin(app, db)
        add_missing_columns(app, db)

        print(f"""
{GREEN}{BOLD}
╔══════════════════════════════════════════════════════════╗
║              ✅  SETUP COMPLETE!                         ║
╠══════════════════════════════════════════════════════════╣
║  Ab server start karo:                                   ║
║    python index.py                                       ║
║                                                          ║
║  Browser mein kholo:                                     ║
║    http://localhost:5000                                 ║
║                                                          ║
║  Login:                                                  ║
║    Email   : {ADMIN_EMAIL:<42}║
║    Password: {ADMIN_PASSWORD:<42}║
╚══════════════════════════════════════════════════════════╝
{RESET}""")

    except KeyboardInterrupt:
        print(f"\n\n  {YELLOW}Setup cancelled by user.{RESET}")
        sys.exit(0)
    except Exception as e:
        err(f"Setup failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
