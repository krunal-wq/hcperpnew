"""
Create Department + Designation master tables and seed default data
Run: python create_dept_desig.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app, db
from sqlalchemy import text

DEPARTMENTS = [
    'Administration', 'Accounts', 'HR', 'Production', 'Quality',
    'Sales', 'R&D', 'IT', 'Stores', 'Purchase', 'Marketing',
]

DESIGNATIONS = [
    'Director', 'Manager', 'Assistant Manager', 'Executive',
    'Senior Executive', 'Officer', 'Supervisor', 'Technician',
    'Worker', 'Intern', 'Trainee',
]

with app.app_context():
    with db.engine.connect() as conn:

        # Create department_master table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS `department_master` (
                `id`         INT AUTO_INCREMENT PRIMARY KEY,
                `name`       VARCHAR(100) NOT NULL UNIQUE,
                `code`       VARCHAR(20),
                `sort_order` INT DEFAULT 0,
                `is_active`  TINYINT(1) DEFAULT 1,
                `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `created_by` INT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))

        # Create designation_master table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS `designation_master` (
                `id`         INT AUTO_INCREMENT PRIMARY KEY,
                `name`       VARCHAR(100) NOT NULL UNIQUE,
                `department` VARCHAR(100),
                `sort_order` INT DEFAULT 0,
                `is_active`  TINYINT(1) DEFAULT 1,
                `created_at` DATETIME DEFAULT CURRENT_TIMESTAMP,
                `created_by` INT
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """))
        conn.commit()

        # Seed Departments
        print("\n── Departments ──")
        for i, name in enumerate(DEPARTMENTS):
            res = conn.execute(text("SELECT COUNT(*) FROM department_master WHERE name=:n"), {'n': name})
            if res.scalar() == 0:
                conn.execute(text(
                    "INSERT INTO department_master (name, sort_order, is_active) VALUES (:n, :s, 1)"
                ), {'n': name, 's': i})
                print(f"  ✅ {name}")
            else:
                print(f"  ⏭  {name}")

        # Seed Designations
        print("\n── Designations ──")
        for i, name in enumerate(DESIGNATIONS):
            res = conn.execute(text("SELECT COUNT(*) FROM designation_master WHERE name=:n"), {'n': name})
            if res.scalar() == 0:
                conn.execute(text(
                    "INSERT INTO designation_master (name, sort_order, is_active) VALUES (:n, :s, 1)"
                ), {'n': name, 's': i})
                print(f"  ✅ {name}")
            else:
                print(f"  ⏭  {name}")

        conn.commit()

    print("\n✅ Done! Server restart karo.\n")
