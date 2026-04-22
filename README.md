# Phase 7 — Configurable HCP Salary Rules

## What changed

Phase 6 mein HCP rules **hardcoded** the JavaScript mein (30K threshold, 21K ESIC limit, 15K fixed Basic, 50%/40%/30% percentages, etc.). Ab **sab configurable hain** Salary Configuration page se.

**Admin jo settings karega wahan — turant sab jagah apply ho jayega:**
- Employee Add/Edit form (Salary tab)
- My Profile page (Salary tab)

Koi code change nahi chahiye future mein — policy change karne ke liye sirf UI use karo.

## New Salary Config Section

`/hr/salary-config/page` pe jao — **"🏭 HCP Salary Policy Rules"** card dikhega (blue border) with:

| Setting | Default | Meaning |
|---|---|---|
| ✅ Enable HCP Rules | ON | Uncheck to disable (fallback to legacy CTC calc) |
| High Gross Threshold | ₹30,000 | Gross ≥ this → % formula; below → fixed Basic |
| ESIC Limit (HO only) | ₹21,000 | Gross ≤ this → ESIC applies in HO |
| Low-Gross Fixed Basic | ₹15,000 | Basic+DA when Gross < threshold |
| High-Gross Basic % | 50% | Basic = this % of Gross (high branch) |
| HRA % | 40% | of Basic+DA |
| Conveyance % | 30% | of Basic+DA (high branch) |
| Medical Fixed | ₹1,200 | (high branch) |
| Bonus % | 8.33% | of Gross |
| PT Threshold | ₹12,000 | Gross ≥ this → PT applies |
| PT Amount | ₹200 | Fixed PT |
| PF Employee % | 12% | of Basic+DA |
| PF Employer % | 13% | of Basic+DA (incl admin + EDLI) |
| ESIC Employee % | 0.75% | of Gross |
| ESIC Employer % | 3.25% | of Gross |

**Business rules hardcoded (NOT configurable) — these are by design:**
- "Plant = FACTORY/WORKER, ESIC never applicable" — per your policy document
- "HO = OFFICE/WFH, ESIC applies only if Gross ≤ ESIC limit"
- CTC = (Gross + PF Er + ESIC Er + Bonus) × 12

Agar in rules ko bhi change karna hai future mein, bolo — bana denge editable.

## Files to replace (5 files)

| File | Path | Kya change |
|---|---|---|
| `employee.py` | `hcperp/models/employee.py` | `SalaryConfig._DEFAULTS` mein 15 new HCP keys |
| `hr_routes.py` | `hcperp/hr_routes.py` | `salary_config_save` route HCP keys allow |
| `salary_config.html` | `hcperp/templates/hr/salary_config.html` | Naya "HCP Salary Policy Rules" card + save payload |
| `form.html` | `hcperp/templates/hr/employees/form.html` | HCP JS ab `/hr/salary-config` se fetch karta hai |
| `profile.html` | `hcperp/templates/admin/profile.html` | Same — config-fetched calc |

**Database migration NOT needed** — `salary_config` table kv-store hai, new keys automatically save honge jab admin save karega (agle GET par defaults se populated mil jayenge).

## Installation

```bash
# Backup
cp hcperp/models/employee.py hcperp/models/employee.py.bak-p6
cp hcperp/hr_routes.py hcperp/hr_routes.py.bak-p6
cp hcperp/templates/hr/salary_config.html hcperp/templates/hr/salary_config.html.bak-p6
cp hcperp/templates/hr/employees/form.html hcperp/templates/hr/employees/form.html.bak-p6
cp hcperp/templates/admin/profile.html hcperp/templates/admin/profile.html.bak-p6

# Replace
cp employee.py hcperp/models/employee.py
cp hr_routes.py hcperp/hr_routes.py
cp salary_config.html hcperp/templates/hr/salary_config.html
cp form.html hcperp/templates/hr/employees/form.html
cp profile.html hcperp/templates/admin/profile.html

# Restart Flask
```

## How it works

### Flow
1. User Salary tab opens → JS calls `GET /hr/salary-config` → backend returns current HCP values from DB (or defaults if never saved)
2. JS caches config for the session (one fetch per page load)
3. User enters Gross → `hcpAutoFromGross()` uses cached config to calculate all fields
4. Banner shows current policy dynamically (e.g. "Plant — Gross ≥ 30K" or admin's custom threshold)

### Admin workflow
1. Go to `/hr/salary-config/page`
2. Scroll to **"🏭 HCP Salary Policy Rules"** section
3. Change any threshold/percentage
4. Click **Save Config** — backend stores in `salary_config` table
5. Next time any user opens Employee/Profile Salary tab, **new rules apply automatically**

### Enable/Disable toggle
- "Enable HCP Rules" checkbox → when OFF, banner warns "HCP rules are DISABLED" with link to config page
- Old CTC-based `autoCalcSalary` still works for edge cases

## Testing

### Test 1: Default values match Excel
1. Open `/hr/employees/add`
2. Employee Type: HCP OFFICE, Gross: **30000**
3. Verify: Basic=15000, HRA=6000, Conv=4500, Med=1200, PF Emp=1800, Net=28000 ✅

### Test 2: Change threshold live
1. Go to `/hr/salary-config/page`
2. Change **High Gross Threshold** from 30000 → **25000**
3. Save
4. Reload Add Employee form
5. Enter Gross 25000 with HCP OFFICE
6. Verify: Now Gross ≥ new threshold → Basic = 50% × 25000 = 12500 (high branch)
7. Enter Gross 24999 → Basic = 15000 (low branch fixed)

### Test 3: Change ESIC limit
1. Salary Config → ESIC Limit: 21000 → 25000
2. HO Gross 22000 → previously ESIC=0 (> 21K), now ESIC applicable (22000 ≤ 25000)
3. ESIC Emp = 22000 × 0.75% = 165

### Test 4: Change percentages
1. Salary Config → HRA % of Basic: 40 → 50
2. HCP OFFICE Gross 30000 → Basic=15000, **HRA=7500** (50% of Basic) ✅

### Test 5: Disable HCP
1. Uncheck "Enable HCP Rules" in config → Save
2. Open Salary tab → Banner shows warning, calculation doesn't run
3. User must re-enable to use HCP rules

## Design rationale

### Why cache config in session?
Multiple `fetch()` calls per Gross keystroke would be wasteful. Config rarely changes — cached once per page load is sufficient.

### Why not move business logic to server?
- Client-side = instant feedback (no network round-trip per keystroke)
- Server-side validation still happens in route handlers (emp_add, emp_edit, etc.)
- Config fetched from server ensures consistency

### Why keep old CTC-based calc?
- Backward compatibility (existing employees with CTC-only data)
- Legacy generic formula still works if HCP disabled
- `salary_components` table + earnings/deductions CRUD still functional

## Limitations

1. **Plant vs HO detection** uses string match: `FACTORY`/`WORKER` → Plant, `OFFICE`/`HO`/`WFH` → HO. If your Employee Type Master has different naming, update master or logic in JS (2 lines).

2. **Config cached per page load** — admin must refresh Employee form after changing config (browser tab reload).

3. **No audit log** for config changes beyond `updated_by` + `updated_at`. Future: add to `audit` table.

## Rollback

```bash
cp hcperp/models/employee.py.bak-p6 hcperp/models/employee.py
cp hcperp/hr_routes.py.bak-p6 hcperp/hr_routes.py
cp hcperp/templates/hr/salary_config.html.bak-p6 hcperp/templates/hr/salary_config.html
cp hcperp/templates/hr/employees/form.html.bak-p6 hcperp/templates/hr/employees/form.html
cp hcperp/templates/admin/profile.html.bak-p6 hcperp/templates/admin/profile.html
```

DB rows (new keys in `salary_config`) can be safely left as-is — they won't affect anything.
