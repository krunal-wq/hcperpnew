# R&D Sample Log — Integration Guide

This package adds a new **"R&D Sample Log"** menu under the R&D module, with
role-based + project-based access control, without modifying any existing
tables or breaking any existing feature.

---

## What you get

| File | Destination | Purpose |
|---|---|---|
| `rd_sample_log_routes.py` | project root (next to `rd_routes.py`) | Flask blueprint — list page + JSON API |
| `sample_log.html` | `templates/rd/sample_log.html` | Jinja template for the listing page |
| `add_rd_sample_log_menu.py` | project root | One-time DB migration to register the menu |

Plus two tiny patches to apply — shown below.

---

## Step 1 — Drop the files into place

```
your_project/
├── rd_sample_log_routes.py           ← new (root)
├── add_rd_sample_log_menu.py         ← new (root)
└── templates/
    └── rd/
        └── sample_log.html           ← new
```

## Step 2 — Register the blueprint in `index.py`

**File:** `index.py`

Find the R&D blueprint import (around line 15):

```python
from rd_routes   import rd
```

Add one line **below** it:

```python
from rd_routes   import rd
from rd_sample_log_routes import rd_sample_log_bp   # ← NEW
```

Then find where `rd` is registered (around line 63):

```python
app.register_blueprint(rd)
```

Add one line **below** it:

```python
app.register_blueprint(rd)
app.register_blueprint(rd_sample_log_bp)            # ← NEW
```

## Step 3 — Add the sidebar link in `templates/base.html`

**File:** `templates/base.html`

### 3a) Register the page key (around line 85)

Find the R&D page-list block:

```jinja
{% elif _pg in ('npd_dashboard','npd_projects','npd_reports','npd_milestone_master',
                'npd_npd_dashboard','npd_npd_projects','npd_epd_dashboard','npd_epd_projects',
                'npd_status_master','milestone_status_master','npd_category_master',
                'rd_dashboard','rd_projects','rd_executives','rd_performance',
                'rd_discussion','rd_param_master',
                'rd_sample_ready','rd_sample_history') %}
    {% set _mod = 'rd' %}
```

Add `'rd_sample_log'` to the tuple:

```jinja
                'rd_sample_ready','rd_sample_history','rd_sample_log') %}
```

### 3b) Add the sidebar link (around line 383)

Find the R&D section block (near line 377):

```jinja
<a class="nav-a {% if _pg == 'rd_sample_history' %}active{% endif %}" href="/rd/sample-history"><span class="nav-ic">📋</span><span class="nav-txt">Sample History</span></a>
```

Add a new line **below** it:

```jinja
<a class="nav-a {% if _pg == 'rd_sample_history' %}active{% endif %}" href="/rd/sample-history"><span class="nav-ic">📋</span><span class="nav-txt">Sample History</span></a>
<a class="nav-a {% if _pg == 'rd_sample_log' %}active{% endif %}" href="/rd/sample-log"><span class="nav-ic">🧪</span><span class="nav-txt">R&amp;D Sample Log</span></a>
```

## Step 4 — Run the menu migration (one time)

```bash
python add_rd_sample_log_menu.py
```

Expected output:

```
===========================================
  R&D SAMPLE LOG — MENU MIGRATION
===========================================
  ✅ R&D parent module found (id=…)
  ✅ 'R&D Sample Log' module created (id=…) ✓
  ✅ RolePermission rows seeded: 8 new, 0 refreshed

  ✅ DONE — restart the server to see the menu.
```

## Step 5 — Restart the server

```bash
python index.py
```

Visit: **http://localhost:5000/rd/sample-log**

---

## Access-control behaviour

The blueprint enforces these rules automatically — no config needed.

| Role(s) | Sees |
|---|---|
| `admin`, `manager`, `npd_manager`, `rd_manager` | **All** sample logs across **all** projects & **all** members |
| `rd_executive`, `sales`, `lead`, `team_lead`, `hr`, `npd` | **All** sample logs on projects **assigned to them** (cannot see unassigned projects) |
| `user` / any other | **Only their own** sample log rows on projects **assigned to them** |

A user is considered "assigned" to a project if **any** of the following is true:
- `NPDProject.assigned_rd == user.id`
- `NPDProject.assigned_sc == user.id`
- `NPDProject.npd_poc == user.id`
- `NPDProject.created_by == user.id`
- `user.id` appears in `NPDProject.assigned_members` (CSV)
- `user.id` appears in `NPDProject.assigned_rd_members` (CSV)
- The user has an active `RDSubAssignment` on the project

This exactly matches how the existing R&D Team Log section in
`templates/npd/project_view.html` determines visibility, so behaviour
stays consistent across both surfaces.

---

## API endpoint

The same data is also exposed as JSON (same scoping applied automatically):

```
GET /rd/sample-log/api/list
```

Returns:

```json
{
  "ok": true,
  "count": 12,
  "bucket": "project",
  "rows": [
    {
      "id": 42,
      "project_id": 7,
      "project_code": "NPD-0007",
      "product_name": "Vitamin-C Serum",
      "member_id": 11,
      "member_name": "Raj Thakkar",
      "variant_code": "V1",
      "started_at": "16-04-2026 16:58",
      "finished_at": "16-04-2026 17:04",
      "duration_sec": 364,
      "status": "finished"
    }
  ]
}
```

---

## Rollback

If you ever need to remove it, run this in a Python shell with the app context:

```python
from index import app, db
from models.permission import Module, RolePermission, UserPermission

with app.app_context():
    mod = Module.query.filter_by(name='rd_sample_log').first()
    if mod:
        RolePermission.query.filter_by(module_id=mod.id).delete()
        UserPermission.query.filter_by(module_id=mod.id).delete()
        db.session.delete(mod)
        db.session.commit()
        print("Removed rd_sample_log menu.")
```

Then delete the three new files and remove the two blueprint lines in `index.py`
and the sidebar snippet in `base.html`.
