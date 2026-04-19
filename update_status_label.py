"""
update_status_label.py
Run: python update_status_label.py
'in_progress' status ka label → 'Sample Inprocess'
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from index import app
    from models import db
except Exception as e:
    print(f"Error: {e}"); sys.exit(1)

with app.app_context():
    import pymysql
    uri = db.engine.url
    con = pymysql.connect(
        host=str(uri.host), port=int(uri.port or 3306),
        user=str(uri.username), password=str(uri.password),
        database=str(uri.database), charset='utf8mb4'
    )
    cur = con.cursor()
    cur.execute("UPDATE `npd_statuses` SET `name` = 'Sample Inprocess' WHERE `slug` = 'in_progress'")
    con.commit()
    print(f"✅ Done! {cur.rowcount} row updated — 'in_progress' → 'Sample Inprocess'")
    cur.close()
    con.close()
