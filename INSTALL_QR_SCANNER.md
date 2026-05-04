# QR Scanner Feature — Installation Guide

QR Code Attendance Scanner — kiosk-style page jisme external USB/Bluetooth
QR scanner ya mobile/system camera se employee QR scan karte hi:

  📷 Photo · 👤 Name · 🆔 Employee Code · 🕐 Time In · 🕐 Time Out

…sab kuch turant display ho jata hai.


## 📦 Files (3 changes total)

```
hcperpnew/
├── qr_scan_routes.py                            ← NEW (drop-in)
├── templates/hr/attendance/qr_scan.html         ← NEW (drop-in)
├── index.py                                     ← MODIFY (2 lines)
└── templates/base.html                          ← MODIFY (1 link)
```


## 🔧 Step 1: Drop-in NEW files

Bas zip se ye 2 files apne project root mein copy kar do:

```
qr_scan_routes.py             →  <project_root>/qr_scan_routes.py
templates/hr/attendance/...   →  <project_root>/templates/hr/attendance/qr_scan.html
```


## 🔧 Step 2: index.py mein 2 lines add karo

Apne `index.py` kholo. Iss line ke aas-paas dhundo (line ~22):

```python
from attendance_routes import attendance_bp
```

Uske theek **niche** ye line add karo:

```python
from qr_scan_routes import qr_scan_bp     # ← NEW: QR scanner kiosk
```

Phir line ~85-90 ke aas-paas dhundo:

```python
app.register_blueprint(attendance_bp)
```

Uske theek **niche** ye line add karo:

```python
app.register_blueprint(qr_scan_bp)        # ← NEW: QR scanner kiosk
```

Bas itna hi backend mein.


## 🔧 Step 3: Sidebar mein link add karo (optional but recommended)

`templates/base.html` kholo. Line ~571-573 ke aas-paas ye block dhundo:

```html
<a class="nav-a nav-sub {% if _pg == 'my_attendance' %}active{% endif %}" href="/hr/attendance/my">
    <span class="nav-ic">👤</span><span class="nav-txt">My Attendance</span>
</a>
```

Uske theek **upar** ye block add karo:

```html
<a class="nav-a nav-sub {% if _pg == 'qr_scan' %}active{% endif %}" href="/hr/attendance/qr-scan">
    <span class="nav-ic">📷</span><span class="nav-txt">QR Scanner</span>
</a>
```

Aur same file mein line 92 wala lamba `_pg in (...)` list dhundo, usme
`'qr_scan'` add karo (taaki sidebar HR menu open rahe is page pe):

```python
{% elif _pg in ('hr_emp_dashboard',...,'my_attendance', 'qr_scan', 'hr_masters',...) %}
```


## 🚀 Step 4: Server restart karo

```bash
# Gunicorn / Flask jo bhi use kar rahe ho
sudo systemctl restart hcperp        # ya jaisa bhi setup hai
```

Phir browser mein kholo:

```
http://<your-server>/hr/attendance/qr-scan
```


## 🎮 Use kaise karein

### External USB / Bluetooth Scanner (recommended for kiosk):
1. Page khulta hi **External Scanner** mode default ON hai.
2. Scanner ko USB/Bluetooth se connect karo (zyadatar HID-keyboard mode).
3. Bas QR scan karo — code automatic type ho ke Enter dab jayega.
4. Employee ka card 8 second tak dikhega, phir auto-clear.

### Camera Mode (mobile / laptop webcam):
1. **📸 Camera Mode** button click karo.
2. Browser camera permission maango → allow karo.
3. QR code camera ke saamne lao.

### Fullscreen Kiosk:
- **⛶ Fullscreen** button click karo — sidebar/topbar hide ho jayega.
- Pure kiosk display ban jayega ek tablet/screen pe.


## 🔒 QR code mein kya ho — sab handle ho jata hai

Backend in sab formats ko parse kar sakta hai:
- Plain text:     `HCP001`
- JSON:           `{"emp_code":"HCP001"}`
- URL:            `https://hcperp.in/emp/HCP001`
- Numeric ID:     `1001`

Lookup ka order: `employee_code` → `employee_id` (biometric) → numeric `id`.


## 📡 API Reference

```
POST /hr/attendance/qr-lookup
Form-data:  code=HCP001

Success (200):
{
  "success": true,
  "employee": {
    "id": 42,
    "code": "HCP001",
    "employee_id": "1001",
    "name": "Krunal Sharma",
    "department": "R&D",
    "designation": "Manager",
    "photo": "data:image/jpeg;base64,..."
  },
  "attendance": {
    "date":        "04-May-2026",
    "time_in":     "09:12 AM",
    "time_out":    "06:48 PM",
    "total_hours": "9h 36m",
    "status":      "Present"
  },
  "scanned_at": "11:42:08"
}

Not found (404):
{ "success": false, "error": "Employee nahi mila ...", "scanned": "XYZ" }
```


## 🛠️ Aage agar Punch IN/OUT bhi register karna ho

Ye version sirf **STATUS DISPLAY** karta hai — punch nahi maarta.
Agar scan pe attendance bhi mark karni ho (RawPunchLog mein punch
insert + auto-detect IN ya OUT), to bata dena — `/qr-lookup` endpoint
ko ya alag `/qr-punch` endpoint banakar 5-10 lines mein add ho jayega.
