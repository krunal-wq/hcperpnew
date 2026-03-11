"""
migrate_masters.py — Create master tables and seed default data
Run: python migrate_masters.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from index import app
from models import db, LeadStatus, LeadSource, LeadCategory, ProductRange

TABLES_SQL = [
    """CREATE TABLE IF NOT EXISTS `lead_statuses` (
      `id` int AUTO_INCREMENT PRIMARY KEY,
      `name` varchar(100) NOT NULL UNIQUE,
      `color` varchar(20) DEFAULT '#6b7280',
      `icon` varchar(10) DEFAULT '🔵',
      `sort_order` int DEFAULT 0,
      `is_active` tinyint(1) DEFAULT 1,
      `created_at` datetime DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    """CREATE TABLE IF NOT EXISTS `lead_sources` (
      `id` int AUTO_INCREMENT PRIMARY KEY,
      `name` varchar(100) NOT NULL UNIQUE,
      `icon` varchar(10) DEFAULT '📌',
      `sort_order` int DEFAULT 0,
      `is_active` tinyint(1) DEFAULT 1,
      `created_at` datetime DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    """CREATE TABLE IF NOT EXISTS `lead_categories` (
      `id` int AUTO_INCREMENT PRIMARY KEY,
      `name` varchar(100) NOT NULL UNIQUE,
      `icon` varchar(10) DEFAULT '🏷️',
      `sort_order` int DEFAULT 0,
      `is_active` tinyint(1) DEFAULT 1,
      `created_at` datetime DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",

    """CREATE TABLE IF NOT EXISTS `product_ranges` (
      `id` int AUTO_INCREMENT PRIMARY KEY,
      `name` varchar(100) NOT NULL UNIQUE,
      `icon` varchar(10) DEFAULT '📦',
      `sort_order` int DEFAULT 0,
      `is_active` tinyint(1) DEFAULT 1,
      `created_at` datetime DEFAULT CURRENT_TIMESTAMP
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;""",
]

DEFAULT_DATA = {
    LeadStatus: [
        {'name':'Open',       'color':'#3b82f6','icon':'🔵','sort_order':1},
        {'name':'In Process', 'color':'#f59e0b','icon':'🟡','sort_order':2},
        {'name':'Close',      'color':'#22c55e','icon':'🟢','sort_order':3},
        {'name':'Cancel',     'color':'#ef4444','icon':'🔴','sort_order':4},
    ],
    LeadSource: [
        {'name':'HCP Website', 'icon':'🌐','sort_order':1},
        {'name':'Pharma Hopper','icon':'💊','sort_order':2},
        {'name':'Just Dial',   'icon':'📞','sort_order':3},
        {'name':'India Mart',  'icon':'🛒','sort_order':4},
        {'name':'Trade India', 'icon':'📊','sort_order':5},
        {'name':'Referral',    'icon':'🤝','sort_order':6},
        {'name':'Cold Call',   'icon':'📱','sort_order':7},
        {'name':'Exhibition',  'icon':'🎪','sort_order':8},
        {'name':'Social Media','icon':'📣','sort_order':9},
        {'name':'WhatsApp',    'icon':'💬','sort_order':10},
        {'name':'Email',       'icon':'📧','sort_order':11},
        {'name':'Other',       'icon':'📌','sort_order':12},
    ],
    LeadCategory: [
        {'name':'Skin Care',      'icon':'✨','sort_order':1},
        {'name':'Hair Care',      'icon':'💆','sort_order':2},
        {'name':'Body Care',      'icon':'🧴','sort_order':3},
        {'name':'Oral Care',      'icon':'🦷','sort_order':4},
        {'name':'Baby Care',      'icon':'👶','sort_order':5},
        {'name':'Cosmetics',      'icon':'💄','sort_order':6},
        {'name':'Pharmaceuticals','icon':'💊','sort_order':7},
        {'name':'Other',          'icon':'📦','sort_order':8},
    ],
    ProductRange: [
        {'name':'Economy', 'icon':'💰','sort_order':1},
        {'name':'Standard','icon':'⭐','sort_order':2},
        {'name':'Premium', 'icon':'💎','sort_order':3},
        {'name':'Luxury',  'icon':'👑','sort_order':4},
    ],
}

with app.app_context():
    with db.engine.connect() as conn:
        for sql in TABLES_SQL:
            try:
                conn.execute(db.text(sql))
                print(f"  ✅ Table created")
            except Exception as e:
                print(f"  ℹ️  {e}")
        conn.commit()

    # Seed defaults
    for Model, rows in DEFAULT_DATA.items():
        for row in rows:
            if not Model.query.filter_by(name=row['name']).first():
                db.session.add(Model(**row))
                print(f"  ➕ {Model.__name__}: {row['name']}")
            else:
                print(f"  ✓  {Model.__name__}: {row['name']} (exists)")
    db.session.commit()

print("\n✅ Masters migration complete!")
print("🚀 Now run: python index.py")
