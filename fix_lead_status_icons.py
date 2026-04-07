"""
fix_lead_status_icons.py — lead_statuses table mein icons fix karo
Run: python fix_lead_status_icons.py
"""
import sys, os, re
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

G = "\033[92m"; R = "\033[91m"; B = "\033[1m"; E = "\033[0m"
def ok(m):  print(f"  {G}✅ {m}{E}")
def err(m): print(f"  {R}❌ {m}{E}")

try:
    from config import Config
    import pymysql
    from urllib.parse import unquote_plus
    url = Config.SQLALCHEMY_DATABASE_URI
    m = re.match(r'mysql\+pymysql://([^:]+):([^@]+)@([^:/]+):?(\d+)?/(.+)', url)
    DB_USER, DB_PASS_ENC, DB_HOST, DB_PORT, DB_NAME = m.groups()
    DB_PASS = unquote_plus(DB_PASS_ENC)
    DB_PORT = int(DB_PORT or 3306)
except Exception as e:
    print(f"Config error: {e}"); sys.exit(1)

con = pymysql.connect(
    host=DB_HOST, port=DB_PORT, user=DB_USER,
    password=DB_PASS, database=DB_NAME,
    charset='utf8mb4', autocommit=True
)
cur = con.cursor()

print(f"\n{B}── Fixing lead_statuses icons...{E}\n")

# First fix the column charset to support emojis
try:
    cur.execute("ALTER TABLE `lead_statuses` MODIFY `icon` VARCHAR(20) CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    ok("lead_statuses.icon column charset fixed to utf8mb4")
except Exception as e:
    print(f"  Column alter: {e}")

# Fix each status icon + color
statuses = [
    ("open",             "✉️",  "#6366f1"),
    ("in_process",       "⚙️",  "#1e3a5f"),
    ("close",            "✅",  "#059669"),
    ("cancel",           "❌",  "#dc2626"),
    ("NPD Project",      "🧪",  "#8b5cf6"),
    ("Existing Project", "📦",  "#0ea5e9"),
]

for name, icon, color in statuses:
    try:
        cur.execute(
            "UPDATE `lead_statuses` SET `icon`=%s, `color`=%s WHERE `name`=%s",
            (icon, color, name)
        )
        if cur.rowcount > 0:
            ok(f"{name} → {icon} {color}")
        else:
            # Insert if not exists
            cur.execute(
                "INSERT IGNORE INTO `lead_statuses` (name, icon, color, sort_order, is_active) VALUES (%s,%s,%s,%s,1)",
                (name, icon, color, statuses.index((name,icon,color))+1)
            )
            ok(f"{name} → inserted with {icon}")
    except Exception as e:
        print(f"  {name}: {e}")

# Show final state
cur.execute("SELECT name, icon, color FROM lead_statuses ORDER BY sort_order")
rows = cur.fetchall()
print(f"\n  Current lead_statuses:")
for name, icon, color in rows:
    print(f"     {icon}  {name}  ({color})")

cur.close()
con.close()

print(f"\n{G}{B}✅ Done! Server restart karo.{E}\n")
