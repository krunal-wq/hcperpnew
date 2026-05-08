"""
Run this script ONCE to create the `qualification_master` table and seed it
with default qualifications. Safe to re-run — idempotent.

Usage:
    python add_qualification_master_table.py

`config.py` se DB URI automatically uthega.
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


# Default list — Indian degrees + new requested entries (B.Pharm, M.Pharm, Diploma / ITI)
DEFAULT_QUALIFICATIONS = [
    '10th (SSC)', '12th (HSC)',
    'Diploma', 'ITI', 'Diploma / ITI',
    'B.Sc', 'B.Com', 'B.A',
    'B.E / B.Tech', 'BBA', 'BCA',
    'B.Pharm',
    'M.Sc', 'M.Com', 'M.A',
    'M.E / M.Tech', 'MBA', 'MCA',
    'M.Pharm',
    'PhD', 'Other',
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
        if 'qualification_master' not in insp.get_table_names():
            print("ℹ️  Creating 'qualification_master' table…")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS `qualification_master` (
                    `id`         INT NOT NULL AUTO_INCREMENT,
                    `name`       VARCHAR(100) NOT NULL,
                    `sort_order` INT DEFAULT 0,
                    `is_active`  TINYINT(1) DEFAULT 1,
                    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                    `created_by` INT NULL,
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `uq_qualification_name` (`name`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            print("✅ Table created.")
        else:
            print("ℹ️  Table already exists.")

        # Seed
        rows = conn.execute(text("SELECT name FROM qualification_master")).fetchall()
        existing = {r[0].strip().lower() for r in rows if r[0]}

        added = 0
        skipped = 0
        for i, name in enumerate(DEFAULT_QUALIFICATIONS):
            if name.strip().lower() in existing:
                skipped += 1
                continue
            conn.execute(
                text("INSERT INTO qualification_master (name, sort_order, is_active) "
                     "VALUES (:n, :s, 1)"),
                {'n': name, 's': i}
            )
            added += 1

        print(f"✅ Seed done — {added} added, {skipped} already present.")
        total = conn.execute(text("SELECT COUNT(*) FROM qualification_master")).scalar()
        print(f"📊 Total qualifications in DB: {total}")


if __name__ == '__main__':
    run()
