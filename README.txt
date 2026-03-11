╔══════════════════════════════════════════════════════════════╗
║           ERP CRM v7 — SETUP GUIDE                          ║
╚══════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 OPTION A — Fresh Setup (naya PC, koi data nahi)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  1. Python 3.9+ install karo  → https://python.org/downloads
  2. MySQL 8.0+ install karo   → https://dev.mysql.com/downloads/mysql/
  3. setup.py mein apna MySQL password daalo:
       DB_PASSWORD = "apna_mysql_password"
  4. Run: python setup.py
  5. Run: python index.py
  6. Browser: http://localhost:5000
     Login:   admin@erp.com / Admin@123

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 OPTION B — Purane PC ka data naye PC pe laana
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

  PURANE PC PE:
    python export_data.py   ← data_dump.py generate hogi

  NAYE PC PE:
    1. erp_v7.zip extract karo
    2. data_dump.py copy karo erp_v7/ mein
    3. setup.py mein naye PC ka MySQL password daalo
    4. python setup.py        (tables + admin)
    5. python data_dump.py    (saara data restore)
    6. python index.py        (server)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 SCRIPTS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  export_data.py  → Purane PC pe: data_dump.py generate karo
  setup.py        → Naye PC pe: DB + tables + admin create
  data_dump.py    → Data restore (export ke baad milti hai)
  index.py        → Flask server start

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  MySQL error → MySQL service start karo, password check karo
  Port busy   → index.py mein port=5001 karo
  pip error   → pip install flask flask-sqlalchemy flask-login
                pip install pymysql cryptography openpyxl pillow
