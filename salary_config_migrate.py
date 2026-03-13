"""
salary_config_migrate.py
Run once to create the salary_config table.
Add this to your existing migrate.py or run standalone.
"""
from app import app, db  # adjust import to your app factory

SALARY_CONFIG_SQL = """
CREATE TABLE IF NOT EXISTS salary_config (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    `key`       VARCHAR(50) NOT NULL UNIQUE,
    value       VARCHAR(50) NOT NULL,
    label       VARCHAR(100),
    updated_by  VARCHAR(100),
    updated_at  DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
"""

SEED_SQL = """
INSERT IGNORE INTO salary_config (`key`, value, label) VALUES
  ('basic_pct',    '40',    'Basic Salary % of Monthly CTC'),
  ('hra_pct',      '50',    'HRA % of Basic'),
  ('da_pct',       '10',    'DA % of Basic'),
  ('ta_fixed',     '1600',  'Transport Allow. Fixed ₹'),
  ('med_fixed',    '1250',  'Medical Allow. Fixed ₹'),
  ('pf_emp_pct',   '12',    'PF Employee % of Basic'),
  ('pf_er_pct',    '12',    'PF Employer % of Basic'),
  ('esic_emp_pct', '0.75',  'ESIC Employee % of Gross'),
  ('esic_er_pct',  '3.25',  'ESIC Employer % of Gross'),
  ('esic_limit',   '21000', 'ESIC Applicable Gross Limit ₹'),
  ('pt_fixed',     '200',   'Professional Tax Fixed ₹/month');
"""

with app.app_context():
    db.session.execute(db.text(SALARY_CONFIG_SQL))
    db.session.execute(db.text(SEED_SQL))
    db.session.commit()
    print("✅ salary_config table created and seeded!")
