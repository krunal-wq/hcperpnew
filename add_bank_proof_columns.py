"""
Run this script ONCE to add `bank_proof_base64` and `bank_proof_filename`
columns to the `employees` table in your MySQL database (erpdb).

Usage:
    python add_bank_proof_columns.py

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
        any_added = False

        # bank_proof_base64 — MEDIUMTEXT (~16MB) for base64 image/PDF
        if 'bank_proof_base64' in cols:
            print("ℹ️  bank_proof_base64 already exists — skip.")
        else:
            after = " AFTER `bank_account_holder`" if 'bank_account_holder' in cols else ""
            sql = f"ALTER TABLE `employees` ADD COLUMN `bank_proof_base64` MEDIUMTEXT NULL{after}"
            print(f"🛠  {sql}")
            conn.execute(text(sql))
            any_added = True

        # bank_proof_filename — VARCHAR(200)
        cols2 = [c['name'] for c in inspect(conn).get_columns('employees')]
        if 'bank_proof_filename' in cols2:
            print("ℹ️  bank_proof_filename already exists — skip.")
        else:
            after = " AFTER `bank_proof_base64`" if 'bank_proof_base64' in cols2 else ""
            sql = f"ALTER TABLE `employees` ADD COLUMN `bank_proof_filename` VARCHAR(200) NULL{after}"
            print(f"🛠  {sql}")
            conn.execute(text(sql))
            any_added = True

        if any_added:
            try:
                conn.commit()
            except AttributeError:
                pass
            print("✅ Bank proof columns add ho gaye.")
        else:
            print("ℹ️  Sab columns already mojud hain.")


if __name__ == '__main__':
    migrate()
