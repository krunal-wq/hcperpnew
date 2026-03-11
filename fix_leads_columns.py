"""
Run: python fix_leads_columns.py
Leads table mein saare missing columns add karega
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

try:
    from config import Config
    import pymysql

    uri = Config.SQLALCHEMY_DATABASE_URI.replace('mysql+pymysql://', '')
    user_pass, rest = uri.split('@')
    user = user_pass.split(':')[0]
    password = ':'.join(user_pass.split(':')[1:]).replace('%40','@').replace('%23','#').replace('%21','!')
    host = rest.split('/')[0]
    dbname = rest.split('/')[1].split('?')[0]

    conn = pymysql.connect(host=host, user=user, password=password, database=dbname)
    cursor = conn.cursor()

    # Get existing columns
    cursor.execute("DESCRIBE leads")
    existing_cols = [row[0] for row in cursor.fetchall()]
    print(f"\n📋 Existing leads columns: {existing_cols}\n")

    # ALL columns that model expects — add only if missing
    columns_to_add = [
        ("position",         "VARCHAR(100) DEFAULT NULL"),
        ("address",          "TEXT DEFAULT NULL"),
        ("city",             "VARCHAR(100) DEFAULT NULL"),
        ("state",            "VARCHAR(100) DEFAULT NULL"),
        ("country",          "VARCHAR(100) DEFAULT 'India'"),
        ("zip_code",         "VARCHAR(10) DEFAULT NULL"),
        ("average_cost",     "DECIMAL(12,2) DEFAULT 0.00"),
        ("product_name",     "VARCHAR(200) DEFAULT NULL"),
        ("category",         "VARCHAR(100) DEFAULT NULL"),
        ("product_range",    "VARCHAR(100) DEFAULT NULL"),
        ("order_quantity",   "VARCHAR(100) DEFAULT NULL"),
        ("requirement_spec", "TEXT DEFAULT NULL"),
        ("tags",             "VARCHAR(300) DEFAULT NULL"),
        ("remark",           "TEXT DEFAULT NULL"),
        ("last_contact",     "DATETIME DEFAULT NULL"),
        ("team_members",     "TEXT DEFAULT NULL"),
        ("client_id",        "INT(11) DEFAULT NULL"),
        ("client_attachment","VARCHAR(300) DEFAULT NULL"),
        ("alternate_mobile", "VARCHAR(20) DEFAULT NULL"),
        ("website",          "VARCHAR(200) DEFAULT NULL"),
    ]

    added = []
    skipped = []

    for col_name, col_def in columns_to_add:
        if col_name not in existing_cols:
            try:
                cursor.execute(f"ALTER TABLE `leads` ADD COLUMN `{col_name}` {col_def}")
                conn.commit()
                print(f"   ✅ ADDED   — leads.{col_name}")
                added.append(col_name)
            except Exception as e:
                print(f"   ❌ ERROR   — leads.{col_name}: {e}")
        else:
            print(f"   ⏭️  EXISTS  — leads.{col_name}")
            skipped.append(col_name)

    print(f"\n{'='*50}")
    print(f"✅ Done! Added: {len(added)} | Skipped: {len(skipped)}")
    print(f"\n🚀 Ab run karo: python index.py")
    print(f"{'='*50}\n")

    cursor.close()
    conn.close()

except Exception as e:
    print(f"\n❌ Error: {e}\n")
