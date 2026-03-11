"""Run once — adds all new HRMS columns to employees table."""
import sys; sys.path.insert(0, '.')
from index import app
from models import db
from sqlalchemy import text

NEW_COLS = [
    "ALTER TABLE employees ADD COLUMN aadhar_number VARCHAR(20)",
    "ALTER TABLE employees ADD COLUMN pan_number VARCHAR(20)",
    "ALTER TABLE employees ADD COLUMN passport_number VARCHAR(30)",
    "ALTER TABLE employees ADD COLUMN passport_expiry DATE",
    "ALTER TABLE employees ADD COLUMN driving_license VARCHAR(30)",
    "ALTER TABLE employees ADD COLUMN dl_expiry DATE",
    "ALTER TABLE employees ADD COLUMN uan_number VARCHAR(20)",
    "ALTER TABLE employees ADD COLUMN esic_number VARCHAR(20)",
    "ALTER TABLE employees ADD COLUMN nationality VARCHAR(50) DEFAULT 'Indian'",
    "ALTER TABLE employees ADD COLUMN religion VARCHAR(50)",
    "ALTER TABLE employees ADD COLUMN caste VARCHAR(50)",
    "ALTER TABLE employees ADD COLUMN physically_handicapped TINYINT(1) DEFAULT 0",
    "ALTER TABLE employees ADD COLUMN emergency_name VARCHAR(150)",
    "ALTER TABLE employees ADD COLUMN emergency_relation VARCHAR(50)",
    "ALTER TABLE employees ADD COLUMN emergency_phone VARCHAR(20)",
    "ALTER TABLE employees ADD COLUMN emergency_address TEXT",
    "ALTER TABLE employees ADD COLUMN bank_name VARCHAR(150)",
    "ALTER TABLE employees ADD COLUMN bank_account_number VARCHAR(50)",
    "ALTER TABLE employees ADD COLUMN bank_ifsc VARCHAR(20)",
    "ALTER TABLE employees ADD COLUMN bank_branch VARCHAR(150)",
    "ALTER TABLE employees ADD COLUMN bank_account_type VARCHAR(30)",
    "ALTER TABLE employees ADD COLUMN bank_account_holder VARCHAR(150)",
    "ALTER TABLE employees ADD COLUMN salary_ctc DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_basic DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_hra DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_da DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_ta DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_special_allow DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_medical_allow DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_pf_employee DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_pf_employer DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_esic_employee DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_esic_employer DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_professional_tax DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_tds DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_net DECIMAL(12,2)",
    "ALTER TABLE employees ADD COLUMN salary_mode VARCHAR(30)",
    "ALTER TABLE employees ADD COLUMN salary_effective_date DATE",
    "ALTER TABLE employees ADD COLUMN pay_grade VARCHAR(50)",
    "ALTER TABLE employees ADD COLUMN shift VARCHAR(50)",
    "ALTER TABLE employees ADD COLUMN work_hours_per_day DECIMAL(4,1) DEFAULT 8.0",
    "ALTER TABLE employees ADD COLUMN weekly_off VARCHAR(50)",
    "ALTER TABLE employees ADD COLUMN notice_period_days INT DEFAULT 30",
    "ALTER TABLE employees ADD COLUMN confirmation_date DATE",
    "ALTER TABLE employees ADD COLUMN resignation_date DATE",
    "ALTER TABLE employees ADD COLUMN last_working_date DATE",
    "ALTER TABLE employees ADD COLUMN rehire_eligible TINYINT(1) DEFAULT 1",
    "ALTER TABLE employees ADD COLUMN highest_qualification VARCHAR(100)",
    "ALTER TABLE employees ADD COLUMN university VARCHAR(200)",
    "ALTER TABLE employees ADD COLUMN passing_year INT",
    "ALTER TABLE employees ADD COLUMN specialization VARCHAR(100)",
    "ALTER TABLE employees ADD COLUMN prev_company VARCHAR(200)",
    "ALTER TABLE employees ADD COLUMN prev_designation VARCHAR(100)",
    "ALTER TABLE employees ADD COLUMN prev_from_date DATE",
    "ALTER TABLE employees ADD COLUMN prev_to_date DATE",
    "ALTER TABLE employees ADD COLUMN prev_leaving_reason TEXT",
    "ALTER TABLE employees ADD COLUMN total_experience_yrs DECIMAL(4,1)",
    "ALTER TABLE employees ADD COLUMN documents_json TEXT",
]

with app.app_context():
    with db.engine.connect() as conn:
        ok, skip = 0, 0
        for sql in NEW_COLS:
            try:
                conn.execute(text(sql)); conn.commit()
                col = sql.split('ADD COLUMN ')[1].split(' ')[0]
                print(f"  ✅ {col}")
                ok += 1
            except Exception as ex:
                skip += 1
        print(f"\nDone: {ok} added, {skip} skipped (already exist).")
        print("Restart Flask server.")
