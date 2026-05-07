"""
add_country_state_master.py
─────────────────────────────
Run ONCE to create `country_master` and `state_master` tables and seed
default data — India + all 28 States + 8 Union Territories with
short_name (e.g. GJ) and state_code (GST code, e.g. 24).

Also seeds a few common countries (USA, UK, UAE, Australia, Canada,
Singapore, Germany) so you can pick them in the dropdown right away.

Usage:
    cd /var/www/hcperp
    python3 add_country_state_master.py

Safe to re-run — tables are CREATE IF NOT EXISTS aur har row insert se
pehle existing check karta hai.
"""

import sys
from index import app
from models import db


# ── Other countries (with India placed first via sort_order=0) ──
COUNTRIES = [
    # (name, iso2, iso3, phone_code, sort_order)
    ('India',          'IN', 'IND', '+91',  0),
    ('United States',  'US', 'USA', '+1',  10),
    ('United Kingdom', 'GB', 'GBR', '+44', 11),
    ('United Arab Emirates', 'AE', 'ARE', '+971', 12),
    ('Australia',      'AU', 'AUS', '+61', 13),
    ('Canada',         'CA', 'CAN', '+1',  14),
    ('Singapore',      'SG', 'SGP', '+65', 15),
    ('Germany',        'DE', 'DEU', '+49', 16),
    ('China',          'CN', 'CHN', '+86', 17),
    ('Japan',          'JP', 'JPN', '+81', 18),
    ('Saudi Arabia',   'SA', 'SAU', '+966', 19),
    ('Bangladesh',     'BD', 'BGD', '+880', 20),
    ('Sri Lanka',      'LK', 'LKA', '+94', 21),
    ('Nepal',          'NP', 'NPL', '+977', 22),
]

# ── 28 States + 8 Union Territories with GST state code ──
INDIAN_STATES = [
    # (name, short_name, state_code/GST)
    ('Andhra Pradesh',                'AP', '37'),
    ('Arunachal Pradesh',             'AR', '12'),
    ('Assam',                         'AS', '18'),
    ('Bihar',                         'BR', '10'),
    ('Chhattisgarh',                  'CG', '22'),
    ('Goa',                           'GA', '30'),
    ('Gujarat',                       'GJ', '24'),
    ('Haryana',                       'HR', '06'),
    ('Himachal Pradesh',              'HP', '02'),
    ('Jharkhand',                     'JH', '20'),
    ('Karnataka',                     'KA', '29'),
    ('Kerala',                        'KL', '32'),
    ('Madhya Pradesh',                'MP', '23'),
    ('Maharashtra',                   'MH', '27'),
    ('Manipur',                       'MN', '14'),
    ('Meghalaya',                     'ML', '17'),
    ('Mizoram',                       'MZ', '15'),
    ('Nagaland',                      'NL', '13'),
    ('Odisha',                        'OD', '21'),
    ('Punjab',                        'PB', '03'),
    ('Rajasthan',                     'RJ', '08'),
    ('Sikkim',                        'SK', '11'),
    ('Tamil Nadu',                    'TN', '33'),
    ('Telangana',                     'TG', '36'),
    ('Tripura',                       'TR', '16'),
    ('Uttar Pradesh',                 'UP', '09'),
    ('Uttarakhand',                   'UK', '05'),
    ('West Bengal',                   'WB', '19'),
    # Union Territories
    ('Andaman and Nicobar Islands',   'AN', '35'),
    ('Chandigarh',                    'CH', '04'),
    ('Dadra and Nagar Haveli and Daman and Diu', 'DN', '26'),
    ('Delhi',                         'DL', '07'),
    ('Jammu and Kashmir',             'JK', '01'),
    ('Ladakh',                        'LA', '38'),
    ('Lakshadweep',                   'LD', '31'),
    ('Puducherry',                    'PY', '34'),
]


def create_tables_if_missing():
    """Idempotent CREATE TABLE — works on MySQL/MariaDB."""
    print("─" * 60)
    print("Step 1: Creating tables (if not exists)…")

    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS country_master (
            id         INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            name       VARCHAR(100) NOT NULL UNIQUE,
            iso2       VARCHAR(2)   NULL,
            iso3       VARCHAR(3)   NULL,
            phone_code VARCHAR(10)  NULL,
            sort_order INT          DEFAULT 0,
            is_active  TINYINT(1)   DEFAULT 1,
            created_at DATETIME     NULL,
            created_by INT          NULL
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    db.session.execute(db.text("""
        CREATE TABLE IF NOT EXISTS state_master (
            id         INT NOT NULL AUTO_INCREMENT PRIMARY KEY,
            country_id INT NOT NULL,
            name       VARCHAR(100) NOT NULL,
            short_name VARCHAR(10)  NULL,
            state_code VARCHAR(10)  NULL,
            sort_order INT          DEFAULT 0,
            is_active  TINYINT(1)   DEFAULT 1,
            created_at DATETIME     NULL,
            created_by INT          NULL,
            CONSTRAINT fk_state_country FOREIGN KEY (country_id)
                REFERENCES country_master(id) ON DELETE CASCADE,
            CONSTRAINT uq_state_country_name UNIQUE (country_id, name),
            INDEX idx_state_country (country_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
    """))

    db.session.commit()
    print("  ✓ country_master ready")
    print("  ✓ state_master ready")

    # ── Safety: backfill any missing columns if tables existed already ──
    print("─" * 60)
    print("Step 1b: Ensuring columns exist (for older installs)…")

    def _col_exists(table, col):
        sql = db.text("""
            SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME   = :t
              AND COLUMN_NAME  = :c
        """)
        return (db.session.execute(sql, {'t': table, 'c': col}).scalar() or 0) > 0

    # country_master
    for col, ddl in [
        ('iso2',       "VARCHAR(2) NULL"),
        ('iso3',       "VARCHAR(3) NULL"),
        ('phone_code', "VARCHAR(10) NULL"),
        ('sort_order', "INT DEFAULT 0"),
        ('is_active',  "TINYINT(1) DEFAULT 1"),
        ('created_at', "DATETIME NULL"),
        ('created_by', "INT NULL"),
    ]:
        if not _col_exists('country_master', col):
            db.session.execute(db.text(f"ALTER TABLE country_master ADD COLUMN {col} {ddl}"))
            db.session.commit()
            print(f"  [ADD]  country_master.{col}")

    # state_master
    for col, ddl in [
        ('short_name', "VARCHAR(10) NULL"),
        ('state_code', "VARCHAR(10) NULL"),
        ('sort_order', "INT DEFAULT 0"),
        ('is_active',  "TINYINT(1) DEFAULT 1"),
        ('created_at', "DATETIME NULL"),
        ('created_by', "INT NULL"),
    ]:
        if not _col_exists('state_master', col):
            db.session.execute(db.text(f"ALTER TABLE state_master ADD COLUMN {col} {ddl}"))
            db.session.commit()
            print(f"  [ADD]  state_master.{col}")

    print("  ✓ all required columns present")


def seed_countries_and_states():
    from models.employee import CountryMaster, StateMaster

    print("─" * 60)
    print("Step 2: Seeding countries…")
    added_c = 0
    for name, iso2, iso3, phone, sort_order in COUNTRIES:
        if CountryMaster.query.filter_by(name=name).first():
            print(f"  [SKIP] {name}")
            continue
        db.session.add(CountryMaster(
            name=name, iso2=iso2, iso3=iso3,
            phone_code=phone, sort_order=sort_order, is_active=True
        ))
        added_c += 1
    db.session.commit()
    print(f"  Added {added_c} country/countries")

    print("─" * 60)
    print("Step 3: Seeding Indian states…")
    india = CountryMaster.query.filter_by(name='India').first()
    if not india:
        print("  ✗ India row missing — abort.")
        sys.exit(1)

    added_s = 0
    for i, (sname, short, code) in enumerate(INDIAN_STATES):
        existing = StateMaster.query.filter_by(country_id=india.id, name=sname).first()
        if existing:
            # Backfill short_name / state_code if missing
            updated = False
            if not existing.short_name and short:
                existing.short_name = short; updated = True
            if not existing.state_code and code:
                existing.state_code = code; updated = True
            if updated:
                print(f"  [UPD]  {sname:40s} short={short}, code={code}")
            else:
                print(f"  [SKIP] {sname}")
            continue
        db.session.add(StateMaster(
            country_id=india.id, name=sname,
            short_name=short, state_code=code,
            sort_order=i, is_active=True
        ))
        added_s += 1
    db.session.commit()
    print(f"  Added {added_s} state(s)")


def migrate():
    print("=" * 60)
    print("Country / State Master — Migration & Seed")
    print("=" * 60)

    with app.app_context():
        try:
            create_tables_if_missing()
            seed_countries_and_states()
        except Exception as e:
            db.session.rollback()
            print(f"\n✗ Migration failed: {e}")
            sys.exit(2)

    print("=" * 60)
    print("✓ Done. Restart Flask service:")
    print("    systemctl restart hcperp")
    print("=" * 60)


if __name__ == '__main__':
    migrate()
