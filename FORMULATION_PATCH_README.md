# Formulation Module — Patch for HCP ERP

This patch adds a **Formulation** menu under Raw Material with:
- List view, search & filter (by brand, source/linked)
- **Create New** — manual entry of ingredients with `%` or `Qty` mode
- **Link to Existing** — share ingredients with a source formulation
- **Import Excel** — multi-sheet, one formulation per sheet
- **Export Excel** — single or all formulations, in your existing template format

## Files in this zip

### New files
```
models/formulation.py                       # Formulation + FormulationIngredient models
formulation_routes.py                       # Flask blueprint (CRUD + Import + Export)
templates/formulation/index.html            # Main page + 3 modals (Create/Link/Import)
add_formulation_module.py                   # One-time migration script
```

### Modified files (drop-in replacements)
```
index.py                                    # Register blueprint
models/__init__.py                          # Export new models
permissions.py                              # Add 'formulation' module entry
templates/base.html                         # Add 🧪 Formulation link under Raw Material
```

## Install steps

1. **Back up** your existing `index.py`, `models/__init__.py`, `permissions.py`,
   and `templates/base.html`.
2. **Copy** all files from this zip over your existing project, preserving paths.
3. **Run the migration once**:
   ```
   python add_formulation_module.py
   ```
   This creates the two new tables and the Module/permission rows. It is idempotent.
4. **Restart Flask**.
5. **Grant access** in Admin → Access Control Panel for non-admin users
   (admin already has full rights).
6. Visit **`/formulation`** or click 🧪 Formulation under Purchase → Raw Material.

## Excel import parsing rule

Per worksheet, the parser:
- Scans rows 1–30 for the column header (row containing `Sr. No.` in Col A
  AND `Ingredients` in Col B), then reads from the row below.
- Falls back to **row 13** if no header is found (matches your template).
- Body row mapping: **Col A = Sr.No → Col B = Ingredient → Col C = Supplier
  → Col D = % w/w → Col E = Qty KG**.
- **Stops at the first empty Col A** after data has started.
- Auto-skips any "Total" row.
- Pulls **Product Name** and **Batch Size** from the top of the sheet.
- The **sheet name becomes the formulation name** (you can rename per-sheet
  before committing the import).

Verified against your `BEARDO_PRODUCTS_COSTING.xlsx` —
12 ingredients parsed from "DE TAN FACE WASH", 6 from "STRONG HOLD HAIR WAX".

## API surface

```
GET    /formulation                      → list page
GET    /formulation/api/list             → JSON list (search, brand, link filter)
GET    /formulation/api/<id>             → JSON one (with resolved ingredients)
GET    /formulation/api/sources          → JSON sources for "Link to Existing"
POST   /formulation/api/create           → manual create
POST   /formulation/api/link             → link to existing source
PUT    /formulation/api/<id>             → update
DELETE /formulation/api/<id>             → soft delete
POST   /formulation/api/import/preview   → upload XLSX → parse & preview
POST   /formulation/api/import/commit    → commit selected sheets
GET    /formulation/api/export/<id>      → download one as XLSX
GET    /formulation/api/export-all       → download all as XLSX (optional ?brand=…)
```

## Data model notes

`source_id` (nullable FK to `formulations.id`) is the only thing that distinguishes
a **linked** formulation from a **source**:
- Source rows store their own `formulation_ingredients` rows.
- Linked rows store **no ingredients of their own** — they always read through
  `source.ingredients`. Edits to the source propagate automatically.
- Linked rows still hold their own `batch_size`, `product_code`, `brand`, and
  `manufacturing_process`.
- You cannot delete a source that has live linked formulations — the route
  blocks it with a clear error.
