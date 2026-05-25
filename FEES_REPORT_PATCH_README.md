# NPD Fees Report — Patch Notes

## Kya feature ban gaya

Jab user NPD form me **"NPD Fee Received (₹10,000)"** checkbox tick karke
project save karta hai, ab woh fee automatically ek dedicated **NPD Fees
Report** page pe track ho jaati hai. Page pe:

- 💰 Saari paid NPD fees ki list (newest pehle).
- 📅 **From Date / To Date** filter — fee received date pe.
- ⚡ Quick range buttons — Today / This Week / This Month / Last Month / This Year.
- 🔍 Search — project code, product, client name, ya company.
- 🧮 **Total amount** band upar bhi + table footer me bhi.
- ⬇️ **Export CSV** button — filtered list ke saath total.
- 📎 Receipt file ka direct view link.
- ↗ Project view ka quick link.

Access: **Sidebar → NPD → 💰 NPD Fees Report** ya direct URL `/npd/fees-report`.

---

## Files (5 total — 1 new template, 1 migration, 3 modified)

| File | Original path | Status |
|------|--------------|--------|
| `npd_routes.py` | project root | **MODIFY (replace)** |
| `npd_model.py` | `models/npd.py` | **MODIFY (replace as `models/npd.py`)** |
| `base.html` | `templates/base.html` | **MODIFY (replace)** |
| `fees_report.html` | `templates/npd/fees_report.html` | **NEW** |
| `add_npd_fee_paid_at_column.py` | project root | **NEW (run once)** |

> Note: `npd_model.py` in this folder is the file that goes to `models/npd.py`.
> Renamed only because two `npd.py` files in one folder is confusing.

---

## Setup steps

```bash
# 1. Copy files
cp npd_routes.py                       <project-root>/
cp npd_model.py                        <project-root>/models/npd.py
cp base.html                           <project-root>/templates/base.html
cp fees_report.html                    <project-root>/templates/npd/fees_report.html
cp add_npd_fee_paid_at_column.py       <project-root>/

# 2. Run the migration ONCE — adds npd_fee_paid_at column + backfills
cd <project-root>
python add_npd_fee_paid_at_column.py

# 3. Restart Flask app
```

Migration output should look like:

```
🔧 Adding npd_fee_paid_at column to npd_projects table...

  ✅ Added column: npd_fee_paid_at
  ✅ Backfilled N existing paid row(s) with created_at

🎉 Done. NPD Fees Report available at /npd/fees-report
```

---

## What changed in code (high-level)

### 1. `models/npd.py`
New column on `NPDProject`:
```python
npd_fee_paid_at = db.Column(db.DateTime, nullable=True)
```

### 2. `npd_routes.py` — 4 changes

**(a) Create route** (`/npd/projects/new`, around line 535): stamps
`proj.npd_fee_paid_at = datetime.now()` if checkbox was ticked at create-time.

**(b) Edit route** (`/npd/projects/<pid>/edit`, around line 1207): tracks
transition unpaid → paid. **Re-checking an already-paid project does NOT
reset the original timestamp** — important for audit accuracy.

**(c) Third create variant** (the "existing→NPD" code path around line 3334):
same stamp logic as (a).

**(d) New route** `/npd/fees-report` (~ line 2520, before `/npd-projects`):
list with date filter + total + CSV export.

### 3. `templates/base.html` — 3 small additions

- Sidebar nav link "💰 NPD Fees Report" in 2 places (primary accordion + secondary nav).
- Entry in global search registry so users can find it by typing "fees", "fee",
  "payment", "receipt", etc.

### 4. `templates/npd/fees_report.html` — NEW

Standalone page that follows existing NPD theme (purple primary, monospace
project codes, ecdf5 totals band).

---

## Date column logic

`npd_fee_paid_at` is set **only when the checkbox transitions from unchecked
→ checked**. This is deliberate:

| Scenario | Behavior |
|----------|----------|
| New project, fee ticked at create | `paid_at = now()` |
| New project, fee unticked, edit later & tick | `paid_at = now()` (transition) |
| Already-paid project, edited (other fields) | `paid_at` unchanged |
| Already-paid project, fee unticked & re-ticked | `paid_at` resets to new `now()` |
| Legacy data (pre-migration, paid_at NULL) | report **coalesces to `created_at`** so nothing disappears |

The migration script backfills all existing paid rows with their `created_at`,
so even before-migration entries show up in the report immediately.

---

## Permissions

The new route piggybacks on existing **`npd` module permission** (`can_view`).
If you want only Accounts/Finance to see this, you can later split it out as
a new permission key — but for now any NPD viewer can see this page.

Also, **per-user project visibility filter** applies — same as
`/npd/npd-projects`. So a non-manager only sees fees for projects they're
assigned to. Accounts/managers who should see ALL paid fees need
`npd_manager` or `admin` role.

---

## Filter behavior

- **From Date / To Date**: inclusive. Date format auto-handled (HTML5 native
  `YYYY-MM-DD` OR `DD-MM-YYYY` strings both accepted server-side).
- **To-date** is treated as end-of-day (23:59:59), so picking the same
  from-date and to-date shows everything paid that day.
- **Quick range buttons** auto-populate dates and submit immediately.
- **Reset** button clears all filters → shows everything.

---

## CSV export

URL: `/npd/fees-report?from_date=...&to_date=...&q=...&export=csv`

Columns: Sr. | Project Code | Product | Client | Company | Amount | Fee
Received On | Receipt

Last row: blank then `... TOTAL <amount>`.

---

## Testing checklist

- [ ] Migration runs without error.
- [ ] Existing project (already paid) → entry visible immediately in report.
- [ ] Create new NPD project with checkbox ticked → entry appears with today's date.
- [ ] Create new project unticked → no entry. Edit project, tick checkbox, save → entry now appears with today's date.
- [ ] Edit existing paid project's other fields → `paid_at` unchanged in report.
- [ ] From/To date filter excludes outside-range entries.
- [ ] Quick "This Month" button correctly filters this calendar month.
- [ ] Search by project code / product / client → matches.
- [ ] Total amount band matches sum of visible rows.
- [ ] CSV export downloads with filtered rows + total at the end.
- [ ] Receipt file link opens the uploaded PDF/image.
- [ ] Project view (↗ Open) opens correct project.
- [ ] Sidebar link highlights "active" when on the page.
- [ ] Global search ("fees", "payment") shows this page in results.
- [ ] Non-manager user sees only their assigned projects' fees.
