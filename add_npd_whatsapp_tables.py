"""
add_npd_whatsapp_tables.py
──────────────────────────
Migration: Create WhatsApp config and send log tables.

Run AFTER add_npd_daily_report_module.py:
    python add_npd_whatsapp_tables.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app
from models import db

DDL = [

    # ── npd_whatsapp_config ──────────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS `npd_whatsapp_config` (
        `id`                  INT          NOT NULL AUTO_INCREMENT,
        `provider`            VARCHAR(30)  NOT NULL DEFAULT 'ultramsg',
        `is_enabled`          TINYINT(1)   NOT NULL DEFAULT 0,
        `instance_id`         VARCHAR(100) DEFAULT NULL,
        `api_token`           VARCHAR(200) DEFAULT NULL,
        `twilio_account_sid`  VARCHAR(50)  DEFAULT NULL,
        `twilio_auth_token`   VARCHAR(50)  DEFAULT NULL,
        `twilio_from_number`  VARCHAR(30)  DEFAULT NULL,
        `country_code`        VARCHAR(10)  NOT NULL DEFAULT '+91',
        `send_time`           VARCHAR(8)   NOT NULL DEFAULT '21:00',
        `send_to_manager`     TINYINT(1)   NOT NULL DEFAULT 1,
        `send_to_employees`   TINYINT(1)   NOT NULL DEFAULT 1,
        `manager_numbers`     TEXT         DEFAULT NULL,
        `updated_at`          DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP
                                              ON UPDATE CURRENT_TIMESTAMP,
        `updated_by`          INT          DEFAULT NULL,
        PRIMARY KEY (`id`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,

    # ── npd_whatsapp_send_logs ───────────────────────────────────────────
    """
    CREATE TABLE IF NOT EXISTS `npd_whatsapp_send_logs` (
        `id`              INT          NOT NULL AUTO_INCREMENT,
        `send_date`       DATE         NOT NULL,
        `recipient_type`  VARCHAR(20)  NOT NULL DEFAULT 'employee',
        `recipient_name`  VARCHAR(150) DEFAULT NULL,
        `mobile_number`   VARCHAR(25)  DEFAULT NULL,
        `user_id`         INT          DEFAULT NULL,
        `message_type`    VARCHAR(30)  NOT NULL DEFAULT 'personal_report',
        `status`          VARCHAR(20)  NOT NULL DEFAULT 'pending',
        `error_message`   VARCHAR(500) DEFAULT NULL,
        `message_id`      VARCHAR(100) DEFAULT NULL,
        `triggered_by`    INT          DEFAULT NULL,
        `created_at`      DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,
        PRIMARY KEY (`id`),
        KEY `ix_nwsl_date`   (`send_date`),
        KEY `ix_nwsl_status` (`status`)
    ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
    """,
]


def run():
    print('=' * 55)
    print('NPD WhatsApp Tables — Migration')
    print('=' * 55)
    with app.app_context():
        from sqlalchemy import text
        for i, stmt in enumerate(DDL, 1):
            tbl = stmt.strip().split('`')[1]
            try:
                db.session.execute(text(stmt.strip()))
                db.session.commit()
                print(f'  [{i}/{len(DDL)}] ✅  {tbl}')
            except Exception as e:
                db.session.rollback()
                print(f'  [{i}/{len(DDL)}] ❌  {tbl}: {e}')
                raise
    print('\nDone. Now install APScheduler:')
    print('  pip install apscheduler')
    print('And follow INSTALL_WHATSAPP.md for index.py changes.')

if __name__ == '__main__':
    run()
