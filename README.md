# Client Dispatch Module — Complete Deployment Guide

Naya module: **"Send Approved Samples to Client"** — once project is
`approved_by_office`, operator can select samples, fill tracking, and
trigger Email + WhatsApp dispatch.

---

## 📁 File Placement

| File from outputs                  | Place at                                            |
|------------------------------------|-----------------------------------------------------|
| `index.py`                         | project root (replaces existing)                    |
| `models_npd.py`                    | `models/npd.py` (replace — adds `ClientDispatch`)   |
| `rd_routes.py`                     | project root (replace)                              |
| `rd_sample_log_routes.py`          | project root (replace)                              |
| `npd_routes.py`                    | project root (replace)                              |
| `client_dispatch_routes.py`        | project root (NEW file)                             |
| `base.html`                        | `templates/base.html` (replace — adds menu link)    |
| `client_dispatch_index.html`       | `templates/client_dispatch/index.html`  (NEW)       |
| `client_dispatch_history.html`     | `templates/client_dispatch/history.html` (NEW)      |
| `client_dispatch_schema.sql`       | run via mysql                                       |

> Note: `templates/client_dispatch/` directory create karna padega.

---

## 🚀 Deploy Steps

### 1. Backup
```bash
cp -r /path/to/project /path/to/project.bak.$(date +%F)
```

### 2. SQL migration
```bash
mysql -u root -p erpdb < client_dispatch_schema.sql
```
Ye:
- `client_dispatch` table create karta hai
- `office_dispatch_items` me 2 columns add karta hai (`client_dispatch_id`, `sent_to_client_at`)
- `npd_statuses` me `sent_to_client` slug ensure karta hai

### 3. Files replace + create
```bash
cd /path/to/project

# Existing files replace
cp /downloads/index.py .
cp /downloads/models_npd.py models/npd.py
cp /downloads/rd_routes.py .
cp /downloads/rd_sample_log_routes.py .
cp /downloads/npd_routes.py .
cp /downloads/base.html templates/base.html

# New files
cp /downloads/client_dispatch_routes.py .
mkdir -p templates/client_dispatch
cp /downloads/client_dispatch_index.html   templates/client_dispatch/index.html
cp /downloads/client_dispatch_history.html templates/client_dispatch/history.html
```

### 4. Restart Flask app

---

## 🎯 End-to-End Workflow

### User Flow

1. **NPD Sample History page** pe office user samples ko ✓ Approve karta hai
2. Project status auto-derive: jab **sare samples approved** hote hain → **`Approved By Office`**
3. User **"Client Dispatch"** menu pe ja ke us project ko select kare
4. Approved samples list dikhe — checkboxes ke saath
5. Select samples + fill **Courier Name / Tracking No.** + Notes
6. Email override / channel toggle (Email + WhatsApp)
7. **"📤 Send to Client"** click → backend:
   - `client_dispatch` token row create
   - Items pe `client_dispatch_id` + `sent_to_client_at` stamp
   - Project `status = 'sent_to_client'`
   - Email send (agar checked + email available)
   - WhatsApp URL return (browser me click karke send)

### Email Format (auto-generated)

**Subject:** `Sample Dispatch Details – NPD-0001`

**Body (HTML):**
```
Dear Krunal Chandi,

Greetings from HCP Wellness.

We have dispatched the samples for the above-mentioned project.
Please find the tracking details below:

Tracking Details: 1234567890 (BlueDart)

Samples Dispatched:
┌──────────────────┬──────────────┬──────────────────┐
│ NPD Project Code │ Sample Code  │ Product Name     │
├──────────────────┼──────────────┼──────────────────┤
│ NPD-0001         │ NPD-0001/V1  │ Neem Face Wash   │
│ NPD-0001         │ NPD-0001/V2  │ Neem Face Wash   │
└──────────────────┴──────────────┴──────────────────┘

We request you to kindly acknowledge receipt of the samples upon
delivery and share your feedback at the earliest to help us
proceed further.

— HCP Wellness Pvt. Ltd.
```

### WhatsApp Format (wa.me URL)

```
Dear Krunal Chandi,

Your samples for project *NPD-0001* have been dispatched.

*Tracking Details:* 1234567890 (BlueDart)

*Samples:*
• NPD-0001/V1 – Neem Face Wash
• NPD-0001/V2 – Neem Face Wash

Kindly confirm once received. Thank you!

— HCP Wellness
```

Phone normalization:
- 10-digit Indian number → auto prepend `91`
- Empty / invalid → opens WhatsApp **contact picker**

---

## 🧪 Test Checklist

- [ ] **SQL migration** runs cleanly — `client_dispatch` table exists, `office_dispatch_items` has 2 new columns
- [ ] **Sidebar menu** "📤 Client Dispatch" visible (NPD section, after Sample History)
- [ ] `/client-dispatch/` page loads — shows projects with approved-but-unsent items
- [ ] Click project → samples list dikhe with checkboxes
- [ ] **"Select All"** toggle works
- [ ] Without tracking input → button error
- [ ] Send → dispatch saved, token like `CDT-0001` shown
- [ ] **Email** delivered (check inbox) — proper HTML formatting
- [ ] **WhatsApp link** opens with pre-filled message
- [ ] After dispatch → project disappears from list (since items are now sent)
- [ ] Project status → **`Sent to Client`**
- [ ] **History page** (`/client-dispatch/history`) shows past dispatches with all metadata

---

## 🛠 Tech Notes

### Project Status Aggregator Update

`_recompute_project_status()` me `sent_to_client` ko **MANUAL_TERMINAL**
me add kiya — taaki agle approve/reject calls ye status overwrite na karein.

### Email Configuration

Email send karne ke liye `Config` me ye chahiye (existing CRM jo use karta hai):
```python
MAIL_SERVER   = 'smtp.gmail.com'
MAIL_PORT     = 587
MAIL_USE_TLS  = True
MAIL_USERNAME = 'info@hcpwellness.in'
MAIL_PASSWORD = '<app password>'
```

Agar mail config nahi hai to dispatch save ho jayega lekin email skip
hoga — UI me clearly "⚠️ Email failed" dikhayega user ko.

### Permissions / Access Control

Abhi `@login_required` enough hai. Agar specific permission chahiye
future me, ek `cd_send` sub-perm add kar sakte ho `permissions.py` me.

---

## 📊 Schema Diagram

```
NPDProject                                                            ┐
   │                                                                  │
   └─→ OfficeDispatchToken (R&D dispatch to office)                   │
        │                                                             │
        └─→ OfficeDispatchItem (per sample row)                       │
              │ approval_status: 'pending'/'approved'/'rejected'      │
              │ client_dispatch_id  ←─── NEW                          │
              │ sent_to_client_at   ←─── NEW                          │
              │                                                       │
              └─→ ClientDispatch (NEW)  ──── one batch ───────────────┤
                    token_no, tracking_no, courier_name, notes        │
                    email_sent_to/at, whatsapp_sent                   │
                    dispatched_by/at                                  │
                                                                      │
   project.status: not_started → sample_inprocess → sample_ready →    │
                   sent_to_office → approved_by_office →              │
                   **sent_to_client** ←── this stage ──────────────── ┘
```

Done! Bhai, deploy kar lo aur ek test dispatch try karo. Email + WhatsApp dono test karna mat bhulo.
