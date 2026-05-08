# Personal & KYC Tab — Change Pack

Replaces the **Personal & KYC** tab in `Add / Edit Employee` per the
field-level spec from the screenshot brief.

## Files included

```
hcperp-personal-kyc-update/
├── add_election_card_column.py            ← run ONCE (DB migration)
├── hr_routes.py                            ← drop-in replacement
├── models/
│   └── employee.py                         ← drop-in replacement
└── templates/hr/employees/
    ├── form.html                           ← drop-in replacement
    └── view.html                           ← drop-in replacement
```

## How to deploy

1. **Backup** your existing files and `erp.db` (very important).
2. Copy each file from this pack on top of the corresponding file in your
   project, preserving the directory structure.
3. Run the migration once to add the new DB column:
   ```
   python add_election_card_column.py
   ```
4. Restart the Flask app and hard-refresh the browser (`Ctrl + Shift + R`)
   so the updated `form.html` JS reloads.

## What changed (Personal & KYC tab only)

### 👤 Personal Info
- `Nationality`, `Religion`, `Caste Category` → **Required** (with `*` marker
  and inline error messages).

### 🪪 KYC Documents
- `Aadhaar Number`, `PAN Number` → **Required**.
- **NEW** `Election Card No.` field (Required) — added right after PAN.
  Backed by new column `employees.election_card_no VARCHAR(30)`.
- `UAN Number (PF)` → **moved out** of this section, now lives in PF block.
- `ESIC / Passport / Passport Expiry / DL / DL Expiry` — unchanged
  (remain optional).

### 🚨 Emergency Contact
- `Contact Name`, `Relationship`, `Contact Phone`, `Contact Address`
  → **Required**.

### 🏦 PF (Provident Fund)
- `PF Number` field replaced with **`UAN Number`**
  (mapped to existing `employees.uan_number` column — same field that used to
  live in KYC Documents).
- **Conditional rule** — when `PF Applicable = Yes`:
  - `EPS Applicable` is auto-flipped to `Yes` (cascading default).
  - `ESIC Applicable` is auto-flipped to `Yes` (cascading default).
  - `UAN Number` becomes **Required**.
- **Removed** `Previous PF Transfer?` and `Previous PF Number`
  (form-only — DB columns retained for legacy / Excel-import data).

### 🏥 ESIC Details
- **Conditional rule** — when `ESIC Applicable = Yes`, the following become
  **Required**: `Nominee Name`, `Nominee Relation`, `Dispensary`.
- **Removed** `Family Details`
  (form-only — DB column retained).

### 💸 TDS / Income Tax
- **Removed** `Proof Submission Status` and `Investment Declaration`
  (form-only — DB columns retained).

### ⚖️ Statutory Compliance
- Unchanged.

## Behavioural notes

- Validation runs both on **Save Tab** (AJAX per-tab flow) and on full-form
  submit, with the same `_setEmpErr` / `_clearEmpErr` UX used by the other
  tabs (red border + shake + inline message + auto-scroll to first error).
- The auto-flip of `EPS / ESIC` is **only** triggered when the user changes
  `PF Applicable` to `Yes` during this session. Existing employees being
  edited will keep whatever values were saved earlier — i.e. flipping is
  not retroactive on page-load, which avoids unintentional data overwrites.
- All five form-removed fields (`previous_pf_transfer`, `previous_pf_number`,
  `esic_family_details`, `investment_declaration`, `proof_submission_status`)
  are still preserved on the model and read by the Excel **bulk-import** and
  **bulk-export** code paths, so historical data is not lost.

## Rollback

Restore the four backed-up files. The new DB column is harmless — it can stay
or be dropped with:

```sql
-- SQLite >= 3.35
ALTER TABLE employees DROP COLUMN election_card_no;
```
