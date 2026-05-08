"""
Run this script ONCE to create the `nationality_master` table in your MySQL
database (erpdb) and seed it with default nationalities.

Usage:
    python add_nationality_master_table.py

`config.py` se DB URI automatically uthega.
"""
import os
import sys


# Default seed list — same order/items as the form's hardcoded fallback
DEFAULT_NATIONALITIES = [
    'Indian', 'Afghan', 'American', 'Argentine', 'Australian', 'Austrian',
    'Bahraini', 'Bangladeshi', 'Belgian', 'Bhutanese', 'Brazilian', 'British', 'Bulgarian', 'Burmese (Myanmar)',
    'Cambodian', 'Canadian', 'Chilean', 'Chinese', 'Colombian', 'Czech',
    'Danish', 'Dutch', 'Egyptian', 'Emirati (UAE)', 'Ethiopian',
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
    'Saudi Arabian', 'Singaporean', 'Slovak', 'South African', 'Spanish', 'Sri Lankan', 'Swedish', 'Swiss', 'Syrian',
    'Taiwanese', 'Tanzanian', 'Thai', 'Tunisian', 'Turkish',
    'Ugandan', 'Ukrainian', 'Uzbek',
    'Venezuelan', 'Vietnamese',
    'Yemeni',
    'Zambian', 'Zimbabwean',
    'Other',
]


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


def migrate():
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
    with engine.connect() as conn:
        insp = inspect(conn)

        # 1) Create the table if it doesn't exist
        if 'nationality_master' in insp.get_table_names():
            print("ℹ️  nationality_master table already exists — skip create.")
        else:
            create_sql = """
                CREATE TABLE `nationality_master` (
                    `id`         INT NOT NULL AUTO_INCREMENT,
                    `name`       VARCHAR(100) NOT NULL,
                    `sort_order` INT DEFAULT 0,
                    `is_active`  TINYINT(1) DEFAULT 1,
                    `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                    `created_by` INT NULL,
                    PRIMARY KEY (`id`),
                    UNIQUE KEY `ux_nationality_name` (`name`)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
            print("🛠  Creating nationality_master table…")
            conn.execute(text(create_sql))
            try:
                conn.commit()
            except AttributeError:
                pass
            print("✅ nationality_master table created.")

        # 2) Seed default rows (skip duplicates by case-insensitive match)
        print("🌱 Seeding default nationalities…")
        existing = {row[0].lower() for row in conn.execute(text("SELECT name FROM nationality_master")).fetchall()}
        added = 0
        for i, name in enumerate(DEFAULT_NATIONALITIES):
            if name.lower() in existing:
                continue
            conn.execute(
                text("INSERT INTO nationality_master (name, sort_order, is_active) VALUES (:n, :so, 1)"),
                {"n": name, "so": i}
            )
            added += 1
        try:
            conn.commit()
        except AttributeError:
            pass
        print(f"✅ {added} nationalities seeded ({len(DEFAULT_NATIONALITIES) - added} already present).")
        print("👉 Done. Open /hr/masters/?tab=nationality to manage.")


if __name__ == '__main__':
    migrate()
