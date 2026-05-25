"""
add_grade_master_table.py
─────────────────────────
Run this script ONCE to create the `grade_master` table aur usme default
grades (J1-J3, M1-M3, S1-S3, MG1-MG3) seed karne ke liye.

Safe to re-run — fully idempotent.

Usage:
    python add_grade_master_table.py

`config.py` se DB URI automatically uthega (DATABASE_URL env var bhi support).
"""
import os
import sys


def _load_uri():
    uri = os.environ.get('DATABASE_URL')
    if uri:
        return uri
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from config import Config
        return Config.SQLALCHEMY_DATABASE_URI
    except Exception as e:
        print(f"❌ config.py se DB URI load nahi hua: {e}")
        return None


def _safe_uri(uri):
    try:
        if '://' in uri and '@' in uri:
            scheme, rest = uri.split('://', 1)
            creds, host = rest.split('@', 1)
            if ':' in creds:
                user, _ = creds.split(':', 1)
                return f"{scheme}://{user}:****@{host}"
        return uri
    except Exception:
        return uri


# ────────────────────────────────────────────────────────────────
# DEFAULT GRADES — image se exact data
# Format: (grade_code, grade_level, grade_positions, remarks)
# ────────────────────────────────────────────────────────────────
DEFAULT_GRADES = [
    # Junior
    ('J1',  'Junior',     'Trainee, Assistant',
        'Entry Level & support staffs'),
    ('J2',  'Junior',     'Jr. Chemist',
        'Entry Level & support staffs'),
    ('J3',  'Junior',     'Jr. Executive, Jr. Officer',
        'Entry Level & support staffs'),

    # Mid
    ('M1',  'Mid',        'DEO, Driver, Receptionist, Security',
        'Skilled Professionals'),
    ('M2',  'Mid',        'Accountant, Client Coordinator, Electrician, Executive, Foreman, Machine Operator, Technician, Utility Operator',
        'Skilled Professionals'),
    ('M3',  'Mid',        'Batch Operator, Chemist, Graphics Designer, Microbiologist, Officer, Security Supervisor, Supervisor',
        'Skilled Professionals'),

    # Senior
    ('S1',  'Senior',     'Incharge, Security Officer',
        'Expert Professionals'),
    ('S2',  'Senior',     'Software Developer, Sr. Positions',
        'Expert Professionals'),
    ('S3',  'Senior',     'Assistant Manager',
        'Expert Professionals'),

    # Management
    ('MG1', 'Management', 'Manager',
        'Managers, Heads'),
    ('MG2', 'Management', 'Head',
        'Managers, Heads'),
    ('MG3', 'Management', 'Director',
        'Managers, Heads'),
]


def run():
    uri = _load_uri()
    if not uri:
        return
    print(f"🔗 DB URI: {_safe_uri(uri)}")

    try:
        from sqlalchemy import create_engine, text, inspect
    except ImportError:
        print("❌ pip install sqlalchemy pymysql cryptography")
        return

    engine = create_engine(uri, pool_pre_ping=True)

    with engine.begin() as conn:
        insp = inspect(conn)
        if 'grade_master' not in insp.get_table_names():
            print("ℹ️  Creating 'grade_master' table…")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS `grade_master` (
                    `id`              INT NOT NULL AUTO_INCREMENT,
                    `grade_code`      VARCHAR(20)  NOT NULL,
                    `grade_level`     VARCHAR(50)  NOT NULL,
                    `grade_positions` TEXT         NULL,
                    `remarks`         VARCHAR(255) NULL,
                    `sort_order`      INT DEFAULT 0,
                    `is_active`       TINYINT(1) DEFAULT 1,
                    `created_at`      DATETIME DEFAULT CURRENT_TIMESTAMP,
                    `created_by`      INT NULL,
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `uq_grade_code` (`grade_code`),
                    KEY `idx_grade_level` (`grade_level`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            print("✅ Table created.")
        else:
            print("ℹ️  Table already exists — skipping CREATE.")

        # ── Seed ──
        rows = conn.execute(text("SELECT grade_code FROM grade_master")).fetchall()
        existing = {r[0].strip().upper() for r in rows if r[0]}

        added = 0
        skipped = 0
        for i, (code, level, positions, remarks) in enumerate(DEFAULT_GRADES):
            if code.strip().upper() in existing:
                skipped += 1
                continue
            conn.execute(
                text("""INSERT INTO grade_master
                        (grade_code, grade_level, grade_positions, remarks, sort_order, is_active)
                        VALUES (:c, :l, :p, :r, :s, 1)"""),
                {'c': code, 'l': level, 'p': positions, 'r': remarks, 's': i}
            )
            added += 1

        print(f"✅ Seed done — {added} added, {skipped} already present.")
        total = conn.execute(text("SELECT COUNT(*) FROM grade_master")).scalar()
        print(f"📊 Total grades in DB: {total}")


if __name__ == '__main__':
    run()
