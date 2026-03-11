╔══════════════════════════════════════════════════════════════╗
║           ERP CRM v7 — SETUP GUIDE                          ║
╚══════════════════════════════════════════════════════════════╝

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 1 — Pehle yeh install karo (ek baar)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  1. Python 3.9+   → https://python.org/downloads
  2. MySQL 8.0+    → https://dev.mysql.com/downloads/mysql/

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 2 — setup.py mein apni DB details daalo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  setup.py file kholo aur upar yeh lines edit karo:

    DB_HOST     = "localhost"
    DB_PORT     = 3306
    DB_NAME     = "erpdb"
    DB_USER     = "root"
    DB_PASSWORD = "apna_mysql_password"

  Admin user bhi change kar sakte ho:
    ADMIN_EMAIL    = "admin@erp.com"
    ADMIN_PASSWORD = "Admin@123"

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 3 — Setup run karo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Terminal/Command Prompt mein:

    cd erp_v7
    python setup.py

  Yeh script automatically karega:
    ✅ Python packages install
    ✅ MySQL database create
    ✅ config.py update
    ✅ Saari tables create
    ✅ Master data seed (statuses, sources, categories)
    ✅ Admin user create
    ✅ Missing columns add

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 STEP 4 — Server start karo
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    python index.py

  Browser mein kholo:
    http://localhost:5000

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 DEFAULT LOGIN
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Email   : admin@erp.com
  Password: Admin@123

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
 TROUBLESHOOTING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  ❌ MySQL connection failed?
     → MySQL service start karo
     → DB_PASSWORD check karo setup.py mein

  ❌ Port 5000 busy?
     → index.py ke last line mein port change karo:
       app.run(debug=True, port=5001)

  ❌ pip error on Python 3.12+?
     → requirements.txt manually install karo:
       pip install flask flask-sqlalchemy flask-login
       pip install pymysql cryptography openpyxl pillow
