"""
migrate_addresses.py
Run this ONCE to create client_addresses table.
Usage: python migrate_addresses.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from index import app
from models import db

SQL = """
CREATE TABLE IF NOT EXISTS `client_addresses` (
  `id`         int(11)      NOT NULL AUTO_INCREMENT,
  `client_id`  int(11)      NOT NULL,
  `title`      varchar(100) NOT NULL DEFAULT 'Address',
  `addr_type`  varchar(20)           DEFAULT 'billing',
  `address`    text                  DEFAULT NULL,
  `city`       varchar(100)          DEFAULT NULL,
  `state`      varchar(100)          DEFAULT NULL,
  `country`    varchar(100)          DEFAULT 'India',
  `zip_code`   varchar(10)           DEFAULT NULL,
  `is_default` tinyint(1)            DEFAULT 0,
  `created_at` datetime              DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `fk_ca_client` (`client_id`),
  CONSTRAINT `fk_ca_client` FOREIGN KEY (`client_id`)
    REFERENCES `client_masters` (`id`) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

with app.app_context():
    with db.engine.connect() as conn:
        conn.execute(db.text(SQL))
        conn.commit()
    print("✅ client_addresses table created (or already exists)")
    print("🚀 Now run: python index.py")
