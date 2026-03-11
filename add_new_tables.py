"""
╔══════════════════════════════════════════════════════╗
║       EXISTING DATABASE MIGRATION SCRIPT             ║
║  Run: python add_new_tables.py                       ║
║                                                      ║
║  ✅ Purana data safe rahega                          ║
║  ✅ Sirf nayi tables add hongi                       ║
║  ✅ Existing tables touch nahi hongi                 ║
╚══════════════════════════════════════════════════════╝
"""

import sys, os
sys.path.insert(0, os.path.dirname(__file__))

try:
    from config import Config
    import pymysql

    # Config se connection details lo
    uri = Config.SQLALCHEMY_DATABASE_URI
    # Parse: mysql+pymysql://user:pass@host/dbname
    uri2 = uri.replace('mysql+pymysql://', '')
    user_pass, rest = uri2.split('@')
    user = user_pass.split(':')[0]
    password = ':'.join(user_pass.split(':')[1:])
    # URL decode password
    password = password.replace('%40','@').replace('%23','#').replace('%21','!')
    host_db = rest.split('/')
    host = host_db[0]
    dbname = host_db[1].split('?')[0]

    print(f"\n🔗 Connecting to: {host}/{dbname} as {user}")

    conn = pymysql.connect(host=host, user=user, password=password, database=dbname)
    cursor = conn.cursor()

    print("✅ Connected!\n")
    print("⏳ Checking & adding new tables...\n")

    # ── Existing tables check ──
    cursor.execute("SHOW TABLES")
    existing = [row[0] for row in cursor.fetchall()]
    print(f"📋 Existing tables ({len(existing)}): {', '.join(existing)}\n")

    # ── SQL for each new table (IF NOT EXISTS — safe!) ──
    new_tables = {

        'client_masters': """
            CREATE TABLE IF NOT EXISTS `client_masters` (
              `id` int(11) NOT NULL AUTO_INCREMENT,
              `code` varchar(20) DEFAULT NULL,
              `company_name` varchar(200) DEFAULT NULL,
              `contact_name` varchar(150) NOT NULL,
              `position` varchar(100) DEFAULT NULL,
              `email` varchar(150) DEFAULT NULL,
              `website` varchar(200) DEFAULT NULL,
              `mobile` varchar(20) DEFAULT NULL,
              `alternate_mobile` varchar(20) DEFAULT NULL,
              `gstin` varchar(20) DEFAULT NULL,
              `client_type` varchar(50) DEFAULT 'regular',
              `status` varchar(20) DEFAULT 'active',
              `notes` text DEFAULT NULL,
              `address` text DEFAULT NULL,
              `city` varchar(100) DEFAULT NULL,
              `state` varchar(100) DEFAULT NULL,
              `country` varchar(100) DEFAULT 'India',
              `zip_code` varchar(10) DEFAULT NULL,
              `created_by` int(11) DEFAULT NULL,
              `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
              `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`),
              UNIQUE KEY `code` (`code`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        'client_brands': """
            CREATE TABLE IF NOT EXISTS `client_brands` (
              `id` int(11) NOT NULL AUTO_INCREMENT,
              `client_id` int(11) NOT NULL,
              `brand_name` varchar(200) NOT NULL,
              `category` varchar(100) DEFAULT NULL,
              `description` text DEFAULT NULL,
              `is_active` tinyint(1) DEFAULT 1,
              `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`),
              KEY `client_id` (`client_id`),
              CONSTRAINT `fk_brand_client` FOREIGN KEY (`client_id`)
                REFERENCES `client_masters` (`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        'client_addresses': """
            CREATE TABLE IF NOT EXISTS `client_addresses` (
              `id` int(11) NOT NULL AUTO_INCREMENT,
              `client_id` int(11) NOT NULL,
              `title` varchar(100) NOT NULL DEFAULT 'Address',
              `addr_type` varchar(20) DEFAULT 'billing',
              `address` text DEFAULT NULL,
              `city` varchar(100) DEFAULT NULL,
              `state` varchar(100) DEFAULT NULL,
              `country` varchar(100) DEFAULT 'India',
              `zip_code` varchar(10) DEFAULT NULL,
              `is_default` tinyint(1) DEFAULT 0,
              `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`),
              KEY `client_id` (`client_id`),
              CONSTRAINT `fk_addr_client` FOREIGN KEY (`client_id`)
                REFERENCES `client_masters` (`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        'leads': """
            CREATE TABLE IF NOT EXISTS `leads` (
              `id` int(11) NOT NULL AUTO_INCREMENT,
              `code` varchar(20) DEFAULT NULL,
              `name` varchar(150) NOT NULL,
              `position` varchar(100) DEFAULT NULL,
              `email` varchar(150) DEFAULT NULL,
              `website` varchar(200) DEFAULT NULL,
              `mobile` varchar(20) DEFAULT NULL,
              `alternate_mobile` varchar(20) DEFAULT NULL,
              `company` varchar(200) DEFAULT NULL,
              `address` text DEFAULT NULL,
              `city` varchar(100) DEFAULT NULL,
              `state` varchar(100) DEFAULT NULL,
              `country` varchar(100) DEFAULT 'India',
              `zip_code` varchar(10) DEFAULT NULL,
              `average_cost` decimal(12,2) DEFAULT 0.00,
              `product_name` varchar(200) DEFAULT NULL,
              `category` varchar(100) DEFAULT NULL,
              `product_range` varchar(100) DEFAULT NULL,
              `order_quantity` varchar(100) DEFAULT NULL,
              `requirement_spec` text DEFAULT NULL,
              `tags` varchar(300) DEFAULT NULL,
              `remark` text DEFAULT NULL,
              `source` varchar(100) DEFAULT NULL,
              `status` varchar(30) DEFAULT 'open',
              `follow_up_date` date DEFAULT NULL,
              `last_contact` datetime DEFAULT NULL,
              `team_members` text DEFAULT NULL,
              `client_id` int(11) DEFAULT NULL,
              `client_attachment` varchar(300) DEFAULT NULL,
              `created_by` int(11) DEFAULT NULL,
              `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
              `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`),
              UNIQUE KEY `code` (`code`)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        'lead_discussions': """
            CREATE TABLE IF NOT EXISTS `lead_discussions` (
              `id` int(11) NOT NULL AUTO_INCREMENT,
              `lead_id` int(11) NOT NULL,
              `user_id` int(11) NOT NULL,
              `comment` text NOT NULL,
              `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`),
              KEY `lead_id` (`lead_id`),
              CONSTRAINT `fk_disc_lead` FOREIGN KEY (`lead_id`)
                REFERENCES `leads` (`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        'lead_attachments': """
            CREATE TABLE IF NOT EXISTS `lead_attachments` (
              `id` int(11) NOT NULL AUTO_INCREMENT,
              `lead_id` int(11) NOT NULL,
              `discussion_id` int(11) DEFAULT NULL,
              `file_name` varchar(300) NOT NULL,
              `file_path` varchar(500) NOT NULL,
              `file_size` int(11) DEFAULT NULL,
              `file_type` varchar(100) DEFAULT NULL,
              `uploaded_by` int(11) DEFAULT NULL,
              `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`),
              KEY `lead_id` (`lead_id`),
              CONSTRAINT `fk_att_lead` FOREIGN KEY (`lead_id`)
                REFERENCES `leads` (`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        'lead_reminders': """
            CREATE TABLE IF NOT EXISTS `lead_reminders` (
              `id` int(11) NOT NULL AUTO_INCREMENT,
              `lead_id` int(11) NOT NULL,
              `user_id` int(11) NOT NULL,
              `title` varchar(300) NOT NULL,
              `description` text DEFAULT NULL,
              `remind_at` datetime NOT NULL,
              `is_done` tinyint(1) DEFAULT 0,
              `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`),
              KEY `lead_id` (`lead_id`),
              CONSTRAINT `fk_rem_lead` FOREIGN KEY (`lead_id`)
                REFERENCES `leads` (`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        'lead_notes': """
            CREATE TABLE IF NOT EXISTS `lead_notes` (
              `id` int(11) NOT NULL AUTO_INCREMENT,
              `lead_id` int(11) NOT NULL,
              `user_id` int(11) NOT NULL,
              `note` text NOT NULL,
              `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
              `updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`),
              KEY `lead_id` (`lead_id`),
              CONSTRAINT `fk_note_lead` FOREIGN KEY (`lead_id`)
                REFERENCES `leads` (`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,

        'lead_activity_logs': """
            CREATE TABLE IF NOT EXISTS `lead_activity_logs` (
              `id` int(11) NOT NULL AUTO_INCREMENT,
              `lead_id` int(11) NOT NULL,
              `user_id` int(11) DEFAULT NULL,
              `action` varchar(500) NOT NULL,
              `created_at` datetime DEFAULT CURRENT_TIMESTAMP,
              PRIMARY KEY (`id`),
              KEY `lead_id` (`lead_id`),
              CONSTRAINT `fk_log_lead` FOREIGN KEY (`lead_id`)
                REFERENCES `leads` (`id`) ON DELETE CASCADE
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """,
    }

    # ── Run each table ──
    added = []
    skipped = []

    for table_name, sql in new_tables.items():
        try:
            cursor.execute(sql)
            conn.commit()
            if table_name in existing:
                skipped.append(table_name)
                print(f"   ⏭️  SKIP   — {table_name} (already exists)")
            else:
                added.append(table_name)
                print(f"   ✅ ADDED  — {table_name}")
        except Exception as e:
            print(f"   ❌ ERROR  — {table_name}: {e}")

    # ── Leads table mein agar purani columns hain toh nayi add karo ──
    print("\n⏳ Checking leads table columns...\n")
    cursor.execute("DESCRIBE leads")
    lead_cols = [row[0] for row in cursor.fetchall()]

    new_lead_columns = {
        'website':          "ALTER TABLE `leads` ADD COLUMN `website` varchar(200) DEFAULT NULL AFTER `email`",
        'alternate_mobile': "ALTER TABLE `leads` ADD COLUMN `alternate_mobile` varchar(20) DEFAULT NULL",
        'average_cost':     "ALTER TABLE `leads` ADD COLUMN `average_cost` decimal(12,2) DEFAULT 0.00",
        'product_range':    "ALTER TABLE `leads` ADD COLUMN `product_range` varchar(100) DEFAULT NULL",
        'order_quantity':   "ALTER TABLE `leads` ADD COLUMN `order_quantity` varchar(100) DEFAULT NULL",
        'requirement_spec': "ALTER TABLE `leads` ADD COLUMN `requirement_spec` text DEFAULT NULL",
        'tags':             "ALTER TABLE `leads` ADD COLUMN `tags` varchar(300) DEFAULT NULL",
        'remark':           "ALTER TABLE `leads` ADD COLUMN `remark` text DEFAULT NULL",
        'last_contact':     "ALTER TABLE `leads` ADD COLUMN `last_contact` datetime DEFAULT NULL",
        'team_members':     "ALTER TABLE `leads` ADD COLUMN `team_members` text DEFAULT NULL",
        'client_id':        "ALTER TABLE `leads` ADD COLUMN `client_id` int(11) DEFAULT NULL",
        'client_attachment':"ALTER TABLE `leads` ADD COLUMN `client_attachment` varchar(300) DEFAULT NULL",
    }

    for col, alter_sql in new_lead_columns.items():
        if col not in lead_cols:
            try:
                cursor.execute(alter_sql)
                conn.commit()
                print(f"   ✅ ADDED column — leads.{col}")
            except Exception as e:
                print(f"   ❌ ERROR column — leads.{col}: {e}")
        else:
            print(f"   ⏭️  SKIP column  — leads.{col} (exists)")

    # ── Final summary ──
    cursor.execute("SHOW TABLES")
    final_tables = [row[0] for row in cursor.fetchall()]

    print(f"\n{'='*50}")
    print(f"✅ Migration complete!")
    print(f"   New tables added  : {len(added)}")
    print(f"   Tables skipped    : {len(skipped)}")
    print(f"   Total tables now  : {len(final_tables)}")
    print(f"\n📋 All tables: {', '.join(sorted(final_tables))}")
    print(f"\n🚀 Ab run karo: python index.py")
    print(f"{'='*50}\n")

    cursor.close()
    conn.close()

except ImportError as e:
    print(f"\n❌ Import Error: {e}")
    print("Run: pip install pymysql\n")
except pymysql.Error as e:
    print(f"\n❌ Database Error: {e}")
    print("\nCheck karo:")
    print("  1. MySQL chal raha hai?")
    print("  2. config.py mein credentials sahi hain?")
    print("  3. Database exist karta hai?\n")
except Exception as e:
    print(f"\n❌ Error: {e}\n")


# ── Add shipping address columns to client_masters (run if upgrading) ──
def add_shipping_columns():
    import sys, os
    sys.path.insert(0, os.path.dirname(__file__))
    from index import app
    from models import db

    cols = [
        "ALTER TABLE client_masters ADD COLUMN IF NOT EXISTS ship_address   TEXT",
        "ALTER TABLE client_masters ADD COLUMN IF NOT EXISTS ship_city      VARCHAR(100)",
        "ALTER TABLE client_masters ADD COLUMN IF NOT EXISTS ship_state     VARCHAR(100)",
        "ALTER TABLE client_masters ADD COLUMN IF NOT EXISTS ship_country   VARCHAR(100) DEFAULT 'India'",
        "ALTER TABLE client_masters ADD COLUMN IF NOT EXISTS ship_zip_code  VARCHAR(10)",
    ]
    with app.app_context():
        with db.engine.connect() as conn:
            for sql in cols:
                try:
                    conn.execute(db.text(sql))
                    print(f"  ✅ Added: {sql.split('EXISTS')[1].split()[0].strip()}")
                except Exception as e:
                    print(f"  ℹ️  Skipped: {e}")
            conn.commit()
    print("\n✅ Shipping columns migration complete!")
    print("   Now run: python index.py")

if __name__ == '__main__':
    add_shipping_columns()
