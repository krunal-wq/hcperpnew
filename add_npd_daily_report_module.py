"""
add_npd_daily_report_module.py
──────────────────────────────
Migration: Create NPD Daily Work Report Dashboard tables.

Run once:
    python add_npd_daily_report_module.py

Tables created:
  - npd_work_activity_logs
  - npd_task_time_tracking
  - npd_employee_productivity
  - npd_daily_reports
"""

import sys
import os

# ── Ensure project root is on the path ──
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app
from models import db


DDL_STATEMENTS = [

    # ── 1. npd_work_activity_logs ────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS `npd_work_activity_logs` (
        `id`                INT          NOT NULL AUTO_INCREMENT,
        `project_id`        INT          NOT NULL,
        `user_id`           INT          DEFAULT NULL,
        `employee_id`       INT          DEFAULT NULL,
        `action_type`       VARCHAR(50)  NOT NULL DEFAULT 'task_updated',
        `action_detail`     VARCHAR(600) NOT NULL DEFAULT '',
        `old_status`        VARCHAR(50)  DEFAULT NULL,
        `new_status`        VARCHAR(50)  DEFAULT NULL,
        `milestone_id`      INT          DEFAULT NULL,
        `time_spent_seconds` INT         NOT NULL DEFAULT 0,
        `activity_date`     DATE         NOT NULL,
        `created_at`        DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        KEY `ix_npd_wal_date`       (`activity_date`),
        KEY `ix_npd_wal_user_date`  (`user_id`, `activity_date`),
        KEY `ix_npd_wal_proj_date`  (`project_id`, `activity_date`),
        CONSTRAINT `fk_nwal_project` FOREIGN KEY (`project_id`)
            REFERENCES `npd_projects` (`id`) ON DELETE CASCADE,
        CONSTRAINT `fk_nwal_user`    FOREIGN KEY (`user_id`)
            REFERENCES `users` (`id`) ON DELETE SET NULL
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── 2. npd_task_time_tracking ────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS `npd_task_time_tracking` (
        `id`                INT       NOT NULL AUTO_INCREMENT,
        `project_id`        INT       NOT NULL,
        `user_id`           INT       NOT NULL,
        `employee_id`       INT       DEFAULT NULL,
        `session_start`     DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `session_end`       DATETIME  DEFAULT NULL,
        `duration_seconds`  INT       NOT NULL DEFAULT 0,
        `action_type`       VARCHAR(50) NOT NULL DEFAULT 'project_viewed',
        `activity_date`     DATE      NOT NULL,
        `auto_closed`       TINYINT(1) NOT NULL DEFAULT 0,
        `created_at`        DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        KEY `ix_ntt_date`       (`activity_date`),
        KEY `ix_ntt_user_date`  (`user_id`, `activity_date`),
        KEY `ix_ntt_open_sess`  (`user_id`, `project_id`, `activity_date`, `session_end`),
        CONSTRAINT `fk_ntt_project` FOREIGN KEY (`project_id`)
            REFERENCES `npd_projects` (`id`) ON DELETE CASCADE,
        CONSTRAINT `fk_ntt_user`    FOREIGN KEY (`user_id`)
            REFERENCES `users` (`id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── 3. npd_employee_productivity ────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS `npd_employee_productivity` (
        `id`                    INT       NOT NULL AUTO_INCREMENT,
        `user_id`               INT       NOT NULL,
        `employee_id`           INT       DEFAULT NULL,
        `report_date`           DATE      NOT NULL,
        `tasks_created`         INT       NOT NULL DEFAULT 0,
        `tasks_completed`       INT       NOT NULL DEFAULT 0,
        `tasks_updated`         INT       NOT NULL DEFAULT 0,
        `milestones_updated`    INT       NOT NULL DEFAULT 0,
        `comments_added`        INT       NOT NULL DEFAULT 0,
        `status_changes`        INT       NOT NULL DEFAULT 0,
        `total_actions`         INT       NOT NULL DEFAULT 0,
        `total_time_seconds`    INT       NOT NULL DEFAULT 0,
        `active_sessions`       INT       NOT NULL DEFAULT 0,
        `productivity_score`    FLOAT     NOT NULL DEFAULT 0,
        `avg_task_time_seconds` INT       NOT NULL DEFAULT 0,
        `computed_at`           DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP
                                    ON UPDATE CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        UNIQUE KEY `uq_npd_emp_prod` (`user_id`, `report_date`),
        KEY `ix_nep_date`  (`report_date`),
        CONSTRAINT `fk_nep_user` FOREIGN KEY (`user_id`)
            REFERENCES `users` (`id`) ON DELETE CASCADE
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── 4. npd_daily_reports ─────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS `npd_daily_reports` (
        `id`                  INT       NOT NULL AUTO_INCREMENT,
        `report_date`         DATE      NOT NULL,
        `total_tasks_worked`  INT       NOT NULL DEFAULT 0,
        `completed_tasks`     INT       NOT NULL DEFAULT 0,
        `pending_tasks`       INT       NOT NULL DEFAULT 0,
        `late_tasks`          INT       NOT NULL DEFAULT 0,
        `new_tasks_today`     INT       NOT NULL DEFAULT 0,
        `active_employees`    INT       NOT NULL DEFAULT 0,
        `total_time_seconds`  INT       NOT NULL DEFAULT 0,
        `report_data`         LONGTEXT  DEFAULT NULL,
        `is_finalized`        TINYINT(1) NOT NULL DEFAULT 0,
        `generated_at`        DATETIME  NOT NULL DEFAULT CURRENT_TIMESTAMP,
        `finalized_at`        DATETIME  DEFAULT NULL,
        `generated_by`        INT       DEFAULT NULL,
        PRIMARY KEY (`id`),
        UNIQUE KEY `uq_ndr_date` (`report_date`),
        KEY `ix_ndr_date` (`report_date`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]


def run_migration():
    print('=' * 60)
    print('NPD Daily Work Report Module — Database Migration')
    print('=' * 60)

    with app.app_context():
        from sqlalchemy import text

        for i, stmt in enumerate(DDL_STATEMENTS, 1):
            table_name = stmt.strip().split('`')[1]
            try:
                db.session.execute(text(stmt.strip()))
                db.session.commit()
                print(f'  [{i}/{len(DDL_STATEMENTS)}] ✅  Created / verified: {table_name}')
            except Exception as e:
                db.session.rollback()
                print(f'  [{i}/{len(DDL_STATEMENTS)}] ❌  Error on {table_name}: {e}')
                raise

        # ── Register models so SQLAlchemy ORM knows about the tables ──
        try:
            from models.npd_daily_report import (
                NPDWorkActivityLog, NPDTaskTimeTracking,
                NPDEmployeeProductivity, NPDDailyReport
            )
            db.create_all()
            print('\n  ✅  SQLAlchemy ORM synced (db.create_all)')
        except Exception as e:
            print(f'\n  ⚠️   ORM sync note: {e}')

    print('\nMigration complete.')
    print('\nNext steps:')
    print('  1. Add to models/__init__.py:')
    print('       from .npd_daily_report import (NPDWorkActivityLog, NPDTaskTimeTracking,')
    print('                                       NPDEmployeeProductivity, NPDDailyReport)')
    print('  2. Add to index.py (after db.init_app(app)):')
    print('       from npd_daily_report_routes import npd_report_bp, register_activity_hooks')
    print('       app.register_blueprint(npd_report_bp)')
    print('       register_activity_hooks(app)')
    print('  3. Add sidebar link to base.html (see INSTALL.md)')
    print('  4. Set up daily cron:')
    print('       0 22 * * * curl -s -X POST http://localhost:5000/npd/api/generate-daily-report')


if __name__ == '__main__':
    run_migration()
