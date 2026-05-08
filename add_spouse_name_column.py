"""
Run this script ONCE to add `spouse_name` column to the `employees`
table in your MySQL database (erpdb).

Usage:
    python add_spouse_name_column.py

`config.py` se DB URI automatically uthega.
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
        if 'employees' not in insp.get_table_names():
            print("❌ 'employees' table nahi mili!")
            return

        cols = [c['name'] for c in insp.get_columns('employees')]
        if 'spouse_name' in cols:
            print("ℹ️  spouse_name column already exists — skip.")
            return

        # Place after mother_name if it exists, else just add
        after_clause = " AFTER `mother_name`" if 'mother_name' in cols else ""
        sql = f"ALTER TABLE `employees` ADD COLUMN `spouse_name` VARCHAR(150) NULL{after_clause}"
        print(f"🛠  {sql}")
        conn.execute(text(sql))
        try:
            conn.commit()
        except AttributeError:
            pass
        print("✅ spouse_name column add ho gaya.")


if __name__ == '__main__':
    migrate()
