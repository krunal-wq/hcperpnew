# NPD WhatsApp Auto-Report — Installation Guide

## Overview

Yeh module daily NPD report automatically employees ke WhatsApp pe bhejta hai:
- **Har employee** ko unka **personal performance report** milta hai
- **NPD Manager** ko **poori team ka summary** milta hai
- **Scheduled** — configured time pe automatically send hota hai (e.g. 9 PM IST)
- **Manual trigger** bhi possible hai dashboard se

---

## Step 1 — Files Copy Karo

```
whatsapp_sender.py              → <erp_root>/whatsapp_sender.py
npd_whatsapp_auto.py            → <erp_root>/npd_whatsapp_auto.py
npd_whatsapp_routes.py          → <erp_root>/npd_whatsapp_routes.py
add_npd_whatsapp_tables.py      → <erp_root>/add_npd_whatsapp_tables.py
models/npd_whatsapp_models.py   → append contents to <erp_root>/models/npd_daily_report.py
templates/npd/daily_report/
  whatsapp_config.html          → <erp_root>/templates/npd/daily_report/whatsapp_config.html
```

### models/npd_daily_report.py mein append karo:

`models/npd_whatsapp_models.py` ke dono classes (`NPDWhatsAppConfig` aur `NPDWhatsAppSendLog`)
ko copy karke `models/npd_daily_report.py` ke END mein paste karo.

---

## Step 2 — models/__init__.py Update Karo

```python
from .npd_daily_report import (
    NPDWorkActivityLog, NPDTaskTimeTracking,
    NPDEmployeeProductivity, NPDDailyReport,
    NPDWhatsAppConfig, NPDWhatsAppSendLog,   # ← ADD THESE
)
```

---

## Step 3 — APScheduler Install Karo

```bash
pip install apscheduler
```

---

## Step 4 — index.py Update Karo

```python
# ── Existing imports ──
from npd_daily_report_routes import npd_report_bp, register_activity_hooks

# ── ADD these new imports ──
from npd_whatsapp_routes import *     # registers routes on npd_report_bp
from npd_whatsapp_auto import start_whatsapp_scheduler

# ── After app.register_blueprint(npd_report_bp) ──
app.register_blueprint(npd_report_bp)

# ── After register_activity_hooks(app) ──
register_activity_hooks(app)

# ── ADD at the end, before if __name__ == '__main__' ──
with app.app_context():
    scheduler = start_whatsapp_scheduler(app)
    app._npd_wa_scheduler = scheduler    # Store for runtime reschedule
```

Full diff in index.py:
```python
# After db.init_app(app):
register_activity_hooks(app)

# After all app.register_blueprint() calls:
app.register_blueprint(npd_report_bp)

# At end of file (before if __name__):
with app.app_context():
    try:
        _sched = start_whatsapp_scheduler(app)
        app._npd_wa_scheduler = _sched
    except Exception as _e:
        print(f'[NPD WA] Scheduler start failed: {_e}')
```

---

## Step 5 — Database Migration

```bash
python add_npd_whatsapp_tables.py
```

Expected:
```
  [1/2] ✅  npd_whatsapp_config
  [2/2] ✅  npd_whatsapp_send_logs
```

---

## Step 6 — Sidebar Link Add Karo (base.html)

```html
<!-- NPD section ke andar add karo -->
<a class="nav-a {% if _pg == 'npd_wa_config' %}active{% endif %}"
   href="/npd/whatsapp-config">
    <span class="nav-ic">📱</span>
    <span class="nav-txt">WhatsApp Config</span>
</a>
```

Route ko `npd_whatsapp_routes.py` mein add karo:
```python
@npd_report_bp.route('/whatsapp-config')
@login_required
def whatsapp_config_page():
    return render_template('npd/daily_report/whatsapp_config.html',
                           _pg='npd_wa_config', _mod='npd')
```

---

## Step 7 — UltraMsg Setup (5 minutes)

### 7a. Account banao
1. **ultramsg.com** → Sign Up (free)
2. Dashboard pe "Create Instance" click karo
3. QR code scan karo apne WhatsApp se (jaise WhatsApp Web)
4. Instance CONNECTED ho jayega

### 7b. Credentials copy karo
- **Instance ID**: e.g. `instance12345`
- **Token**: Dashboard → Settings → Token

### 7c. ERP mein configure karo
1. `/npd/whatsapp-config` pe jao
2. Provider: **UltraMsg** select karo
3. Instance ID aur Token daalo
4. Country Code: **+91** (India)
5. Send Time: **21:00** (ya jo time chahiye)
6. "Config Save Karo" click karo
7. Test number daalke "Test Send" karo
8. **Enable karo** aur fir save

---

## How It Works (Flow Diagram)

```
Every Day at Configured Time (e.g. 9 PM IST)
           ↓
  APScheduler triggers send_daily_reports()
           ↓
  Report generate hoti hai (agar nahi hai to)
           ↓
  ┌─────────────────────────────────────────┐
  │  Employee loop (NPD dept. employees)    │
  │  • Mobile number fetch from Employee    │
  │  • Personal stats fetch karo            │
  │  • build_employee_message() call        │
  │  • send_whatsapp() → UltraMsg API       │
  │  • Log in npd_whatsapp_send_logs        │
  └─────────────────────────────────────────┘
           ↓
  ┌─────────────────────────────────────────┐
  │  Manager loop                           │
  │  • NPD Manager/Admin users find karo   │
  │  • build_manager_summary() call         │
  │  • send_whatsapp() → UltraMsg API       │
  │  • Log result                           │
  └─────────────────────────────────────────┘
           ↓
  Dashboard → Send Logs mein dikhega
```

---

## Employee Ko Aisa Message Milega:

```
📋 *NPD Daily Report — 09 May 2026*
━━━━━━━━━━━━━━━━━━━━━
👤 *Rahul Sharma*

✅ Tasks Completed:   *5*
🔄 Tasks Updated:     *3*
🎯 Milestones Done:   *2*
💬 Comments Added:    *4*
⏱️ Time Active:       *6h 30m*
📊 Productivity Score: *88/100*
━━━━━━━━━━━━━━━━━━━━━
🥇 *Team Rank: #1*
🏆 Outstanding performance! Keep it up!
━━━━━━━━━━━━━━━━━━━━━
_HCP ERP — NPD Module_
```

## Manager Ko Aisa Message Milega:

```
📋 *NPD Daily Report — 09 May 2026*
━━━━━━━━━━━━━━━━━━━━━
📊 Total Worked:  *12*
✅ Completed:     *7*
⏳ Pending:       *45*
👥 Active Team:   *5*
⏱️ Team Time:     *28h 15m*
━━━━━━━━━━━━━━━━━━━━━
👤 *Team Performance:*
  🥇 Rahul → 5 done (score: 88)
  🥈 Neha → 4 done (score: 76)
  🥉 Amit → 2 done, 3 updated (score: 52)
━━━━━━━━━━━━━━━━━━━━━
_HCP ERP — NPD Module_
```

---

## Troubleshooting

**Q: "WhatsApp sending disabled" error**
A: Config page pe "Enable" toggle on karo aur save karo.

**Q: Messages send ho rahe hain but nahi mile**
A: UltraMsg mein apna WhatsApp instance connected hai? Dashboard check karo.
   Country code sahi hai? +91 hona chahiye India ke liye.

**Q: APScheduler error on startup**
A: `pip install apscheduler` karo. Bina iske scheduled send nahi hoga —
   but "Send Now" button se manual send ho sakta hai.

**Q: Test message milti hai but scheduled send nahi hota**
A: Server restart karo — scheduler app startup pe initialize hota hai.
   `app._npd_wa_scheduler` check karo ki None nahi hai.

**Q: Employees ko message nahi jaa raha**
A: `/npd/api/whatsapp-recipients` check karo — employees ko
   `department` field mein 'NPD' hona chahiye AND `mobile` field filled hona chahiye.
