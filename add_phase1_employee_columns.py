"""
add_phase1_employee_columns.py
─────────────────────────────────
Run this ONCE to add 46 missing Phase-1 columns to the `employees` table.

Yeh columns user_routes.py / hr_routes.py / forms mein use ho rahe hain
lekin model + DB mein add nahi hue the. Isliye export crash kar raha tha
aur form se save karte time data silently lost ho raha tha.

Usage (production server pe):
    cd /var/www/hcperp
    python3 add_phase1_employee_columns.py

Safe to re-run — har column ke liye INFORMATION_SCHEMA check karta hai
pehle ki kahin already exist toh nahi karta.
"""

import sys
from index import app
from models import db


# ── Column definitions ────────────────────────────────────────────────
# (column_name, MySQL DDL type)
PHASE1_COLUMNS = [
    # Family / Contact
    ('father_name',                 'VARCHAR(150) NULL'),
    ('mother_name',                 'VARCHAR(150) NULL'),
    ('alternate_mobile',            'VARCHAR(20) NULL'),
    ('personal_email',              'VARCHAR(150) NULL'),

    # Permanent Address
    ('permanent_address',           'TEXT NULL'),
    ('permanent_city',              'VARCHAR(100) NULL'),
    ('permanent_state',             'VARCHAR(100) NULL'),
    ('permanent_country',           "VARCHAR(100) NULL DEFAULT 'India'"),
    ('permanent_zip',               'VARCHAR(20) NULL'),
    ('same_as_current_addr',        'TINYINT(1) NOT NULL DEFAULT 0'),

    # Grade / Probation
    ('grade_level',                 'VARCHAR(50) NULL'),
    ('probation_period_months',     'INT NULL DEFAULT 6'),
    ('probation_end_date',          'DATE NULL'),

    # PF
    ('pf_applicable',               'TINYINT(1) NOT NULL DEFAULT 0'),
    ('pf_number',                   'VARCHAR(50) NULL'),
    ('eps_applicable',              'TINYINT(1) NOT NULL DEFAULT 0'),
    ('previous_pf_transfer',        'TINYINT(1) NOT NULL DEFAULT 0'),
    ('previous_pf_number',          'VARCHAR(50) NULL'),

    # ESIC
    ('esic_applicable',             'TINYINT(1) NOT NULL DEFAULT 0'),
    ('esic_nominee_name',           'VARCHAR(150) NULL'),
    ('esic_nominee_relation',       'VARCHAR(50) NULL'),
    ('esic_family_details',         'TEXT NULL'),
    ('esic_dispensary',             'VARCHAR(150) NULL'),

    # TDS / Tax
    ('aadhaar_pan_linked',          'TINYINT(1) NOT NULL DEFAULT 0'),
    ('tax_regime',                  "VARCHAR(20) NULL DEFAULT 'New'"),
    ('prev_employer_income',        'DECIMAL(12,2) NULL'),
    ('monthly_tds',                 'DECIMAL(12,2) NULL'),
    ('investment_declaration',      'TEXT NULL'),
    ('proof_submission_status',     "VARCHAR(30) NULL DEFAULT 'Pending'"),

    # Statutory
    ('professional_tax_applicable', 'TINYINT(1) NOT NULL DEFAULT 1'),
    ('labour_welfare_fund',         'TINYINT(1) NOT NULL DEFAULT 0'),
    ('gratuity_eligible',           'TINYINT(1) NOT NULL DEFAULT 0'),
    ('bonus_eligible',              'TINYINT(1) NOT NULL DEFAULT 1'),

    # Attendance / Leave
    ('attendance_code',             'VARCHAR(50) NULL'),
    ('overtime_eligible',           'TINYINT(1) NOT NULL DEFAULT 0'),
    ('casual_leave_balance',        'DECIMAL(5,1) NULL DEFAULT 0'),
    ('sick_leave_balance',          'DECIMAL(5,1) NULL DEFAULT 0'),
    ('paid_leave_balance',          'DECIMAL(5,1) NULL DEFAULT 0'),
    ('leave_policy',                'VARCHAR(100) NULL'),

    # System Access
    ('official_email',              'VARCHAR(150) NULL'),
    ('role_access',                 'VARCHAR(100) NULL'),

    # Exit extras
    ('exit_interview_done',         'TINYINT(1) NOT NULL DEFAULT 0'),
    ('exit_interview_notes',        'TEXT NULL'),
    ('ff_settlement_status',        "VARCHAR(30) NULL DEFAULT 'Pending'"),
    ('ff_settlement_amount',        'DECIMAL(12,2) NULL'),
    ('ff_settlement_date',          'DATE NULL'),

    # Salary extras (HR-only, used in /hr/employees forms + export)
    ('salary_conveyance',           'DECIMAL(12,2) NULL'),
    ('salary_bonus',                'DECIMAL(12,2) NULL'),
    ('salary_incentive',            'DECIMAL(12,2) NULL'),
    ('salary_gross',                'DECIMAL(12,2) NULL'),

    # Soft delete
    ('deleted_at',                  'DATETIME NULL'),
]


def column_exists(col_name):
    """Check if column exists using INFORMATION_SCHEMA (works on MySQL)."""
    sql = db.text("""
        SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_SCHEMA = DATABASE()
          AND TABLE_NAME   = 'employees'
          AND COLUMN_NAME  = :col
    """)
    result = db.session.execute(sql, {'col': col_name}).scalar()
    return (result or 0) > 0


def migrate():
    print("=" * 60)
    print("Phase-1 Employee Columns Migration")
    print("=" * 60)

    with app.app_context():
        # Sanity check — kya `employees` table exists?
        try:
            db.session.execute(db.text("SELECT 1 FROM employees LIMIT 1"))
        except Exception as e:
            print(f"❌ 'employees' table query failed: {e}")
            print("   Check DB connection / schema name.")
            sys.exit(1)

        added, skipped, failed = 0, 0, 0
        for col_name, ddl_type in PHASE1_COLUMNS:
            try:
                if column_exists(col_name):
                    print(f"  [SKIP]  {col_name:32s} already exists")
                    skipped += 1
                    continue

                sql = f"ALTER TABLE employees ADD COLUMN {col_name} {ddl_type}"
                db.session.execute(db.text(sql))
                db.session.commit()
                print(f"  [ADD]   {col_name:32s} {ddl_type}")
                added += 1
            except Exception as e:
                db.session.rollback()
                print(f"  [FAIL]  {col_name:32s} {e}")
                failed += 1

        print("=" * 60)
        print(f"  Added:   {added}")
        print(f"  Skipped: {skipped} (already existed)")
        print(f"  Failed:  {failed}")
        print("=" * 60)

        if failed:
            print("\n⚠  Kuch columns add nahi ho paaye — error message check karo.")
            sys.exit(2)
        else:
            print("\n✓ Migration complete. Ab Flask service restart karo:")
            print("    systemctl restart hcperp")


if __name__ == '__main__':
    migrate()
