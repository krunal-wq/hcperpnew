# R&D Sample Log — Complete Patch

This patch adds multi-select + Sample Code persistence + Send-to-Office
to the R&D Sample Log module. Dispatched records show up in the
**existing `/npd/sample-history`** page — no duplicate listing page.

## Folder structure of this zip

```
hcperpnew/
├── INSTALL.md                                    ← you are reading this
├── database_changes.sql                          ← run ONCE in MySQL
├── models/
│   └── npd.py                                    ← REPLACE (columns added on 2 tables)
├── rd_sample_log_routes.py                       ← REPLACE (new endpoints + redirect)
└── templates/
    └── rd/
        └── sample_log.html                       ← REPLACE (checkbox UI + A4 preview modal)
```

> **Note:** there is no `sent_to_office.html` template anymore — R&D
> dispatches are stored as `OfficeDispatchToken`/`OfficeDispatchItem`
> records which render automatically on the existing `/npd/sample-history`
> page.

## Installation (3 steps)

### Step 1 — Run the SQL changes

Open phpMyAdmin / MySQL Workbench / CLI, select your ERP database, and
run `database_changes.sql` — or paste these ALTER queries directly:

```sql
-- On rd_sub_assignments
ALTER TABLE rd_sub_assignments
    ADD COLUMN sample_code VARCHAR(500) NULL AFTER variant_code;

ALTER TABLE rd_sub_assignments
    ADD COLUMN send_to_office_date DATETIME NULL AFTER total_seconds;

ALTER TABLE rd_sub_assignments
    ADD COLUMN sent_to_office_by INT NULL AFTER send_to_office_date;

ALTER TABLE rd_sub_assignments
    ADD CONSTRAINT fk_rd_sub_sent_by
    FOREIGN KEY (sent_to_office_by) REFERENCES users(id)
    ON DELETE SET NULL;

CREATE INDEX idx_rd_sub_assignments_sent_date ON rd_sub_assignments (send_to_office_date);
CREATE INDEX idx_rd_sub_assignments_status    ON rd_sub_assignments (status);

-- On office_dispatch_items
ALTER TABLE office_dispatch_items
    ADD COLUMN rd_sub_assignment_id INT NULL AFTER submitted_by;

ALTER TABLE office_dispatch_items
    ADD CONSTRAINT fk_odi_rd_sub_assignment
    FOREIGN KEY (rd_sub_assignment_id) REFERENCES rd_sub_assignments(id)
    ON DELETE SET NULL;

CREATE INDEX idx_odi_rd_sub_assignment ON office_dispatch_items (rd_sub_assignment_id);
```

### Step 2 — Replace the 3 files

Extract the zip at your project root:

- `models/npd.py`                    (adds `sample_code`, `send_to_office_date`, `sent_to_office_by`, `rd_sub_assignment_id`)
- `rd_sample_log_routes.py`          (4 new endpoints, imports `OfficeDispatchToken`)
- `templates/rd/sample_log.html`     (checkbox UI + A4 preview modal + custom confirm modal)

> **Tip:** back up your current 3 files before extracting.

### Step 3 — Restart Flask

Visit `/rd/sample-log` — you should see the **📋 Sample History** button
beside the Print buttons, which opens `/npd/sample-history`.

---

## End-to-end flow

1. Go to `/rd/sample-log`
2. Tick checkboxes on the rows you want to dispatch
3. Click **📄 Print Full List (A4)** → A4 preview modal opens with editable
   Sample Code and Handover To fields for each selected row
4. Two options:
   - **🖨️ Print Only** → saves sample codes + prints A4 sheet. Rows stay in main list.
   - **📤 Send to Office + Print** → custom confirm modal asks; on OK:
     - Saves sample codes to `rd_sub_assignments.sample_code`
     - Sets `status='sent_to_office'` + `send_to_office_date` + `sent_to_office_by`
     - Creates (or reuses today's) `OfficeDispatchToken` record
     - Creates `OfficeDispatchItem` per row, linked back via `rd_sub_assignment_id`
     - Rows disappear from Sample Log
     - Prints A4 sheet
5. Dispatched records now appear on `/npd/sample-history` (existing page) —
   same UI, tokens, filters, export buttons, everything.
6. To revert: on `/npd/sample-history`, delete an item or an entire token
   (existing buttons). For items linked to an R&D row, that row's status
   flips back to `finished` automatically via the FK cascade and the
   existing `/npd/sample-history/item/<id>/delete` endpoint.

---

## Status lifecycle (RDSubAssignment)

```
 not_started → in_progress → finished → sent_to_office
                                ↑              │
                                │              │ (delete item on Sample
                                └──────────────┘  History OR hit API revert)
```

Main Sample Log page shows: `not_started`, `in_progress`, `finished`
(excludes `sent_to_office`).

---

## Data recovery (if Sample Log looks empty)

If `/rd/sample-log` shows "No sample logs found" but you know records
should exist, use these URLs to diagnose and fix:

### Step 1 — Diagnose

Open this in your browser while logged in:

```
http://your-host/rd/sample-log/api/diagnose
```

You'll get a JSON report like:

```json
{
  "current_user": { "id": 7, "bucket": "employee" },
  "raw_totals": {
    "total_rd_sub_assignments": 15,
    "active_rows": 10,
    "sent_to_office_rows": 5
  },
  "my_rows": { "total": 3, "active": 2, "sent_to_office": 1 },
  "sample_log_visible_count": 2,
  "hint": "..."
}
```

Look at `hint` — it tells you exactly why rows are hidden.

### Step 2 — Activate

If you just want everything to show up on the sample log page:

**Restore YOUR own rows** (any logged-in user):
```bash
curl -X POST -b cookies.txt http://your-host/rd/sample-log/api/activate?scope=mine
```

Or open DevTools → Console on the sample log page and run:
```javascript
fetch('/rd/sample-log/api/activate?scope=mine', { method: 'POST', credentials: 'same-origin' })
  .then(r => r.json()).then(d => { console.log(d); location.reload(); })
```

**Restore ALL rows** (admin/manager only):
```javascript
fetch('/rd/sample-log/api/activate?scope=all', { method: 'POST', credentials: 'same-origin' })
  .then(r => r.json()).then(d => { console.log(d); location.reload(); })
```

What activate does:
- Sets `is_active = TRUE` on every affected row
- Reverts `sent_to_office` → `finished` + clears dispatch metadata
- Removes linked `OfficeDispatchItem` records (so Sample History is consistent)
- Drops any token left with zero items

---

## API reference (R&D Sample Log)

All under `/rd/sample-log/`.

| Endpoint | Method | Purpose |
|---|---|---|
| `/api/save-sample-codes` | POST | Save codes only (Print Only button) |
| `/api/send-to-office` | POST | Save codes + create dispatch token/item + flip status |
| `/api/revert/<id>` | POST | Revert a single RD row back to `finished`; removes linked dispatch item(s) |
| `/api/generate-codes` | POST | Server-side unique code suggester (only fills blanks) |
| `/sent-to-office` | GET | Redirects to `/npd/sample-history` (with date filters preserved) |
| `/api/list`, `/api/debug` | GET | Pre-existing, unchanged |
| `/api/diagnose` | GET | Self-diagnosis: tells you exactly why rows are hidden |
| `/api/activate?scope=mine` | POST | Restore YOUR rows to visible state (revert sent_to_office + clear is_active=0) |
| `/api/activate?scope=all` | POST | Same, for ALL rows (admin/manager only) |

### Send-to-Office request shape

```json
{
  "rows": [
    {"id": 12, "codes": "SMP001,SMP002"},
    {"id": 13, "codes": "SMP003"}
  ],
  "handover_to":  {"12": "Sneha Dagar", "13": "Anushka"},
  "submitted_by": {"12": "Aaquib", "13": "Mayuri"}
}
```

Response:
```json
{
  "ok": true,
  "saved": 2,
  "rows": [...],
  "token_no": "ODT-0042",
  "dispatched_at": "18-04-2026 14:32"
}
```

---

## Rollback

```sql
ALTER TABLE office_dispatch_items DROP FOREIGN KEY fk_odi_rd_sub_assignment;
ALTER TABLE office_dispatch_items DROP COLUMN rd_sub_assignment_id;
DROP INDEX idx_odi_rd_sub_assignment ON office_dispatch_items;

ALTER TABLE rd_sub_assignments DROP FOREIGN KEY fk_rd_sub_sent_by;
ALTER TABLE rd_sub_assignments DROP COLUMN sent_to_office_by;
ALTER TABLE rd_sub_assignments DROP COLUMN send_to_office_date;
ALTER TABLE rd_sub_assignments DROP COLUMN sample_code;
DROP INDEX idx_rd_sub_assignments_sent_date ON rd_sub_assignments;
DROP INDEX idx_rd_sub_assignments_status    ON rd_sub_assignments;

UPDATE rd_sub_assignments SET status='finished' WHERE status='sent_to_office';
```

Then restore your 3 original files from backup.
