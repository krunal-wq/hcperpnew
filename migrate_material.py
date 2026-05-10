"""
migrate_material.py  (MySQL version)
Run: python migrate_material.py
"""
import pymysql

# Config se same credentials
HOST     = 'localhost'
PORT     = 3306
USER     = 'root'
PASSWORD = 'Krunal@2424'
DATABASE = 'erpdb'

conn = pymysql.connect(host=HOST, port=PORT, user=USER,
                       password=PASSWORD, database=DATABASE)
cur  = conn.cursor()

def col_exists(table, col):
    cur.execute("""SELECT COUNT(*) FROM information_schema.columns
                   WHERE table_schema=%s AND table_name=%s AND column_name=%s""",
                (DATABASE, table, col))
    return cur.fetchone()[0] > 0

def tbl_exists(table):
    cur.execute("""SELECT COUNT(*) FROM information_schema.tables
                   WHERE table_schema=%s AND table_name=%s""",
                (DATABASE, table))
    return cur.fetchone()[0] > 0

print("[1] materials table:")
for col, definition in [
    ('code',        "VARCHAR(100) DEFAULT ''"),
    ('inci_name',   "VARCHAR(300) DEFAULT ''"),
    ('brand',       "VARCHAR(200) DEFAULT ''"),
    ('category',    "VARCHAR(200) DEFAULT ''"),
    ('per_box_qty', "INT DEFAULT 0"),
]:
    if col_exists('materials', col):
        print(f"  ✓ {col} exists")
    else:
        cur.execute(f"ALTER TABLE materials ADD COLUMN {col} {definition}")
        conn.commit()
        print(f"  ✅ Added: {col}")

print("\n[2] item_categories table:")
if tbl_exists('item_categories'):
    print("  ✓ exists")
else:
    cur.execute("""CREATE TABLE item_categories (
        id            INT AUTO_INCREMENT PRIMARY KEY,
        category_name VARCHAR(150) NOT NULL UNIQUE,
        description   TEXT,
        is_active     TINYINT(1) DEFAULT 1,
        created_at    DATETIME,
        updated_at    DATETIME,
        created_by    VARCHAR(100) DEFAULT ''
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4""")
    conn.commit()
    print("  ✅ Created")

cur.close()
conn.close()
print("\n✅ Done! Server restart karo.")

# Run extra: add is_deleted + deleted_at columns
import pymysql
conn2 = pymysql.connect(host='localhost', port=3306, user='root', password='Krunal@2424', database='erpdb')
cur2  = conn2.cursor()

def col_exists2(col):
    cur2.execute("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='erpdb' AND table_name='materials' AND column_name=%s", (col,))
    return cur2.fetchone()[0] > 0

print("\n[3] Soft delete columns:")
if col_exists2('is_deleted'):
    print("  ✓ is_deleted exists")
else:
    cur2.execute("ALTER TABLE materials ADD COLUMN is_deleted TINYINT(1) DEFAULT 0")
    conn2.commit()
    print("  ✅ Added: is_deleted")

if col_exists2('deleted_at'):
    print("  ✓ deleted_at exists")
else:
    cur2.execute("ALTER TABLE materials ADD COLUMN deleted_at DATETIME")
    conn2.commit()
    print("  ✅ Added: deleted_at")

cur2.close(); conn2.close()

# Add is_deleted + deleted_at to material_types, material_groups, item_categories
import pymysql
conn3 = pymysql.connect(host='localhost', port=3306, user='root', password='Krunal@2424', database='erpdb')
cur3  = conn3.cursor()

def col_ok(tbl, col):
    cur3.execute("SELECT COUNT(*) FROM information_schema.columns WHERE table_schema='erpdb' AND table_name=%s AND column_name=%s",(tbl,col))
    return cur3.fetchone()[0]>0

print("\n[4] Soft delete columns for Types/Groups/Categories:")
for tbl in ['material_types','material_groups','item_categories']:
    for col,typ in [('is_deleted','TINYINT(1) DEFAULT 0'),('deleted_at','DATETIME DEFAULT NULL')]:
        if col_ok(tbl,col): print(f"  ✓ {tbl}.{col}")
        else:
            cur3.execute(f"ALTER TABLE {tbl} ADD COLUMN {col} {typ}")
            conn3.commit()
            print(f"  ✅ Added {tbl}.{col}")

cur3.close(); conn3.close()
print("\n✅ All migrations done!")
