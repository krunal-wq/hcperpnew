"""
add_qc_param_master.py
──────────────────────
Run ONCE to create the `qc_param_options` table and seed the existing
TRS dropdown values for:

    • Physical State
    • Appearance
    • Odour

After this, the values are managed from Masters → QC Parameters master page
(add / edit / activate-deactivate / delete), and the TRS form loads them
from the DB instead of the hard-coded lists in models/trs.py.

Safe to re-run — fully idempotent (existing values are skipped).

Usage:
    python add_qc_param_master.py
"""
import os
import sys
from datetime import datetime


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
# DEFAULT VALUES — current hard-coded lists from models/trs.py
# (category, value, sort_order)
# ────────────────────────────────────────────────────────────────
DEFAULTS = {
    'physical_state': [
        'Solid', 'Liquid', 'Powder', 'Flakes',
        'Granules', 'Crystals', 'Pellets', 'Paste', 'Other',
    ],
    'appearance': [
        'White', 'Off-white', 'Yellow', 'Pale-yellow',
        'Brown', 'Colourless', 'Flakes', 'Powder',
        'Crystals', 'Liquid', 'Other',
    ],
    'odour': [
        'Pleasant', 'Odourless', 'Pungent',
        'Characteristic', 'Aromatic', 'Mild', 'Strong', 'Other',
    ],
}


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
        if 'qc_param_options' not in insp.get_table_names():
            print("ℹ️  Creating 'qc_param_options' table…")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS `qc_param_options` (
                    `id`          INT NOT NULL AUTO_INCREMENT,
                    `category`    VARCHAR(30)  NOT NULL,
                    `value`       VARCHAR(120) NOT NULL,
                    `sort_order`  INT DEFAULT 0,
                    `status`      TINYINT(1) DEFAULT 1,
                    `is_deleted`  TINYINT(1) DEFAULT 0,
                    `created_at`  DATETIME DEFAULT CURRENT_TIMESTAMP,
                    `created_by`  INT NULL,
                    `modified_at` DATETIME NULL,
                    `modified_by` INT NULL,
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `uq_qc_param_cat_value` (`category`, `value`),
                    KEY `idx_qc_param_category` (`category`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            print("✅ Table created.")
        else:
            print("ℹ️  Table already exists — skipping CREATE.")

        # ── Seed defaults (skip if already present) ──
        added = 0
        for category, values in DEFAULTS.items():
            for idx, val in enumerate(values):
                exists = conn.execute(text("""
                    SELECT id FROM qc_param_options
                    WHERE category = :c AND value = :v
                """), {'c': category, 'v': val}).first()
                if exists:
                    continue
                conn.execute(text("""
                    INSERT INTO qc_param_options
                        (category, value, sort_order, status, is_deleted, created_at)
                    VALUES (:c, :v, :s, 1, 0, :t)
                """), {'c': category, 'v': val, 's': idx, 't': datetime.now()})
                added += 1
        print(f"✅ Seeded {added} new value(s). (existing skipped)")

    print("🎉 Done. Restart Flask and open Masters → QC Parameters.")


if __name__ == '__main__':
    run()
