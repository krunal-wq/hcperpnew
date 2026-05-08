"""
Run this script ONCE to populate the `nationality_master` table with a
comprehensive list of nationalities. Indian is sort_order=0 (top of dropdown);
the rest are alphabetical.

Safe to run multiple times — duplicates are skipped.

Usage:
    python seed_nationalities.py
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


# Indian on top, rest alphabetical
NATIONALITIES = [
    'Indian',
    'Afghan', 'American', 'Argentine', 'Australian', 'Austrian',
    'Bahraini', 'Bangladeshi', 'Belgian', 'Bhutanese', 'Brazilian', 'British',
    'Bulgarian', 'Burmese (Myanmar)',
    'Cambodian', 'Canadian', 'Chilean', 'Chinese', 'Colombian', 'Czech',
    'Danish', 'Dutch',
    'Egyptian', 'Emirati (UAE)', 'Ethiopian',
    'Filipino', 'Finnish', 'French',
    'German', 'Ghanaian', 'Greek',
    'Hong Konger', 'Hungarian',
    'Icelandic', 'Indonesian', 'Iranian', 'Iraqi', 'Irish', 'Israeli', 'Italian',
    'Japanese', 'Jordanian',
    'Kazakh', 'Kenyan', 'Korean (South)', 'Kuwaiti',
    'Lebanese', 'Libyan',
    'Malaysian', 'Maldivian', 'Maltese', 'Mauritian', 'Mexican', 'Mongolian', 'Moroccan',
    'Nepalese', 'New Zealander', 'Nigerian', 'Norwegian',
    'Omani',
    'Pakistani', 'Palestinian', 'Peruvian', 'Polish', 'Portuguese',
    'Qatari',
    'Romanian', 'Russian',
    'Saudi Arabian', 'Singaporean', 'Slovak', 'South African', 'Spanish',
    'Sri Lankan', 'Swedish', 'Swiss', 'Syrian',
    'Taiwanese', 'Tanzanian', 'Thai', 'Tunisian', 'Turkish',
    'Ugandan', 'Ukrainian', 'Uzbek',
    'Venezuelan', 'Vietnamese',
    'Yemeni',
    'Zambian', 'Zimbabwean',
    'Other',
]


def seed():
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
        if 'nationality_master' not in insp.get_table_names():
            # Table doesn't exist yet — create it
            print("ℹ️  'nationality_master' table missing — creating it now…")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS `nationality_master` (
                    `id`         INT NOT NULL AUTO_INCREMENT,
                    `name`       VARCHAR(100) NOT NULL,
                    `sort_order` INT DEFAULT 0,
                    `is_active`  TINYINT(1) DEFAULT 1,
                    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                    `created_by` INT NULL,
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `uq_nationality_name` (`name`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """))
            print("✅ Table created.")

        # Fetch existing names (case-insensitive)
        rows = conn.execute(text("SELECT name FROM nationality_master")).fetchall()
        existing = {r[0].strip().lower() for r in rows if r[0]}

        added = 0
        skipped = 0
        for i, name in enumerate(NATIONALITIES):
            if name.strip().lower() in existing:
                skipped += 1
                continue
            conn.execute(
                text("INSERT INTO nationality_master (name, sort_order, is_active) "
                     "VALUES (:n, :s, 1)"),
                {'n': name, 's': i}
            )
            added += 1

        print(f"✅ Done — {added} added, {skipped} already present.")
        # Final count
        total = conn.execute(text("SELECT COUNT(*) FROM nationality_master")).scalar()
        print(f"📊 Total nationalities in DB: {total}")


if __name__ == '__main__':
    seed()
