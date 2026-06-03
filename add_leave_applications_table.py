"""
Run ONCE to create the `hr_leave_applications` table in MySQL (erpdb).
This powers Leave Apply + Approve/Reject workflow.

Usage:
    python add_leave_applications_table.py
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


CREATE_SQL = """
CREATE TABLE IF NOT EXISTS `hr_leave_applications` (
  `id` INT NOT NULL AUTO_INCREMENT,
  `employee_id` INT NOT NULL,
  `leave_type` VARCHAR(10) NOT NULL,
  `from_date` DATE NOT NULL,
  `to_date` DATE NOT NULL,
  `days` DECIMAL(5,1) NOT NULL DEFAULT 1,
  `half_day` TINYINT(1) DEFAULT 0,
  `reason` TEXT,
  `status` VARCHAR(20) DEFAULT 'pending',
  `applied_by` VARCHAR(100),
  `applied_at` DATETIME,
  `decided_by` VARCHAR(100),
  `decided_at` DATETIME,
  `decision_note` TEXT,
  `balance_deducted` TINYINT(1) DEFAULT 0,
  PRIMARY KEY (`id`),
  KEY `idx_emp` (`employee_id`),
  KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""


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
        if 'hr_leave_applications' in insp.get_table_names():
            print("ℹ️  hr_leave_applications table already exists — skip.")
            return
        print("🛠  Creating hr_leave_applications ...")
        conn.execute(text(CREATE_SQL))
        try:
            conn.commit()
        except AttributeError:
            pass
        print("✅ hr_leave_applications table ban gayi.")


if __name__ == '__main__':
    migrate()
