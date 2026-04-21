"""
Migration: Add sample approval columns to office_dispatch_items table.
Run once:  python add_sample_approval_columns.py

Works for MySQL (the actual DB used in this project) AND SQLite as a fallback.
Connects through Flask-SQLAlchemy so it picks up DATABASE_URL / config.py
automatically — no need to hardcode credentials here.

Adds:
  - approval_status  VARCHAR(20)  NOT NULL  DEFAULT 'pending'
  - reject_reason    TEXT
  - actioned_by      INT             (FK users.id)
  - actioned_at      DATETIME
"""
import sys
from sqlalchemy import text


def _get_app_and_db():
    """Import the Flask app + db object. Try common entry points in this project."""
    try:
        from index import app
        from models import db
        return app, db
    except Exception:
        pass

    try:
        from setup import app
        from models import db
        return app, db
    except Exception:
        pass

    raise RuntimeError(
        "Could not import the Flask app. Run this script from the project root "
        "(same folder as index.py / config.py)."
    )


def _column_exists(conn, table, col, dialect):
    if dialect.startswith('mysql'):
        sql = text("""
            SELECT COUNT(*) FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME  = :t
              AND COLUMN_NAME = :c
        """)
        return conn.execute(sql, {"t": table, "c": col}).scalar() > 0

    # sqlite fallback
    rows = conn.execute(text(f"PRAGMA table_info({table})")).fetchall()
    return col in [r[1] for r in rows]


def _table_exists(conn, table, dialect):
    if dialect.startswith('mysql'):
        sql = text("""
            SELECT COUNT(*) FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = :t
        """)
        return conn.execute(sql, {"t": table}).scalar() > 0

    row = conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": table}
    ).fetchone()
    return row is not None


def run():
    app, db = _get_app_and_db()

    with app.app_context():
        engine  = db.engine
        dialect = engine.dialect.name.lower()
        try:
            url_str = engine.url.render_as_string(hide_password=True)
        except Exception:
            url_str = str(engine.url)
        print(f"📡 Connected to: {url_str}")
        print(f"🗂  Dialect    : {dialect}")

        with engine.begin() as conn:
            if not _table_exists(conn, "office_dispatch_items", dialect):
                print("❌ Table 'office_dispatch_items' not found in this database.")
                print("   → Start the Flask app once so SQLAlchemy creates all tables, "
                      "then re-run this migration.")
                sys.exit(1)

            if dialect.startswith("mysql"):
                col_defs = [
                    ("approval_status",
                     "ALTER TABLE office_dispatch_items "
                     "ADD COLUMN approval_status VARCHAR(20) NOT NULL DEFAULT 'pending'"),
                    ("reject_reason",
                     "ALTER TABLE office_dispatch_items "
                     "ADD COLUMN reject_reason TEXT NULL"),
                    ("actioned_by",
                     "ALTER TABLE office_dispatch_items "
                     "ADD COLUMN actioned_by INT NULL"),
                    ("actioned_at",
                     "ALTER TABLE office_dispatch_items "
                     "ADD COLUMN actioned_at DATETIME NULL"),
                ]
            else:
                col_defs = [
                    ("approval_status",
                     "ALTER TABLE office_dispatch_items "
                     "ADD COLUMN approval_status TEXT NOT NULL DEFAULT 'pending'"),
                    ("reject_reason",
                     "ALTER TABLE office_dispatch_items ADD COLUMN reject_reason TEXT"),
                    ("actioned_by",
                     "ALTER TABLE office_dispatch_items ADD COLUMN actioned_by INTEGER"),
                    ("actioned_at",
                     "ALTER TABLE office_dispatch_items ADD COLUMN actioned_at DATETIME"),
                ]

            added = 0
            for name, ddl in col_defs:
                if _column_exists(conn, "office_dispatch_items", name, dialect):
                    print(f"✓ Column already exists: {name}")
                    continue
                conn.execute(text(ddl))
                print(f"✅ Added column: {name}")
                added += 1

            # Defensive backfill — any legacy NULL rows get 'pending'
            conn.execute(text(
                "UPDATE office_dispatch_items "
                "SET approval_status = 'pending' "
                "WHERE approval_status IS NULL OR approval_status = ''"
            ))

            # ─────────────────────────────────────────────────────────
            # Create sample_approval_logs table (audit trail)
            # ─────────────────────────────────────────────────────────
            if not _table_exists(conn, "sample_approval_logs", dialect):
                if dialect.startswith("mysql"):
                    conn.execute(text("""
                        CREATE TABLE sample_approval_logs (
                            id              INT AUTO_INCREMENT PRIMARY KEY,
                            item_id         INT NULL,
                            project_id      INT NULL,
                            action          VARCHAR(20) NOT NULL,
                            reason          TEXT NULL,
                            user_id         INT NULL,
                            whatsapp_sent   TINYINT(1) NOT NULL DEFAULT 0,
                            created_at      DATETIME NOT NULL,
                            prev_project_status VARCHAR(50) NULL,
                            prev_assigned_rd    INT NULL,
                            INDEX idx_sal_item    (item_id),
                            INDEX idx_sal_project (project_id),
                            INDEX idx_sal_created (created_at)
                        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                    """))
                else:
                    conn.execute(text("""
                        CREATE TABLE sample_approval_logs (
                            id              INTEGER PRIMARY KEY AUTOINCREMENT,
                            item_id         INTEGER,
                            project_id      INTEGER,
                            action          TEXT NOT NULL,
                            reason          TEXT,
                            user_id         INTEGER,
                            whatsapp_sent   INTEGER NOT NULL DEFAULT 0,
                            created_at      DATETIME NOT NULL,
                            prev_project_status TEXT,
                            prev_assigned_rd    INTEGER
                        )
                    """))
                print("✅ Created table: sample_approval_logs")
                added += 1
            else:
                print("✓ Table already exists: sample_approval_logs")

            # ─────────────────────────────────────────────────────────
            # Seed NPDStatus rows for 'sent_to_client' and 'rejected'
            # (only if they don't exist — preserves user-defined color/icon)
            # ─────────────────────────────────────────────────────────
            if _table_exists(conn, "npd_statuses", dialect):
                seed_rows = [
                    # (slug, name, color, icon, sort_order)
                    ('sent_to_client', 'Sent to Client', '#0ea5e9', '📤', 70),
                    ('rejected',       'Rejected',       '#dc2626', '❌', 90),
                ]
                from datetime import datetime as _dt
                now = _dt.now()
                for slug, name, color, icon, sort_order in seed_rows:
                    exists = conn.execute(
                        text("SELECT COUNT(*) FROM npd_statuses WHERE slug = :s"),
                        {"s": slug}
                    ).scalar() > 0
                    if exists:
                        print(f"✓ NPDStatus already exists: {slug}")
                        continue
                    conn.execute(text("""
                        INSERT INTO npd_statuses (name, slug, color, icon, sort_order, is_active, created_at)
                        VALUES (:name, :slug, :color, :icon, :sort_order, :is_active, :created_at)
                    """), {
                        "name": name, "slug": slug, "color": color,
                        "icon": icon, "sort_order": sort_order,
                        "is_active": True, "created_at": now
                    })
                    print(f"✅ Seeded NPDStatus: {slug} ({name})")
                    added += 1
            else:
                print("⚠️  Table 'npd_statuses' not found — skipping status seed.")

        if added == 0:
            print("🎉 Nothing to do — schema is already up to date.")
        else:
            print(f"🎉 Migration complete — {added} column(s) added.")


if __name__ == "__main__":
    run()
