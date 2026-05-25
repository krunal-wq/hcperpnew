# Packing Material BOM Module — Install Guide

Naya feature: ek FG (Finished Good) ke liye Packing Material BOM. Har FG ka
sirf ek BOM — phir se save karne pe items overwrite ho jate hain.

## Files in this package

| File in this package         | Where it goes on server                                | New / Patched |
|------------------------------|--------------------------------------------------------|---------------|
| `models_packing_bom.py`      | `models/packing_bom.py`                                | **NEW**       |
| `packing_bom_routes.py`      | `packing_bom_routes.py` (project root)                 | **NEW**       |
| `templates/packing_bom/index.html` | `templates/packing_bom/index.html`                | **NEW**       |
| `add_packing_bom_module.py`  | `add_packing_bom_module.py` (project root)             | **NEW**       |
| `models_init.py`             | `models/__init__.py`  (replace whole file)             | patched       |
| `index.py`                   | `index.py`  (replace whole file)                       | patched       |
| `permissions.py`             | `permissions.py`  (replace whole file)                 | patched       |
| `base.html`                  | `templates/base.html`  (replace whole file)            | patched       |

## Install steps

1. Copy each file from the table above to its target path on the server.
2. Run the migration once to create the two new tables:
   ```bash
   python add_packing_bom_module.py
   ```
   Output should show `packing_boms` and `packing_bom_items` created.
3. Restart the Flask server.
4. Login as **admin** — the new menu item **📦 Packing BOM** appears
   inside the **Packing Material** group in the sidebar.
5. To allow other roles to use it, go to *User Management → Role
   Permissions → Packing BOM* and tick `view / add / edit / delete`
   as needed.

## Feature walkthrough

- **List page** (`/packing-bom`) – search by FG name / code / brand,
  filter by Active / Deleted / All.
- **＋ New Packing BOM** opens the create modal:
  - **FG Item** dropdown (all materials with type=FG).
  - **FG Qty** + **UOM** (FG units this BOM is calibrated for —
    e.g. "100 boxes").
  - **Packing Items** table — each row has Item Name (dropdown of all
    PM / Corrugation / Sleeve items), Qty, UOM. The **＋ Add More**
    button appends a new row. UOM auto-fills from the selected item.
- If a BOM already exists for the chosen FG, a yellow warning banner
  appears: *"Saving will overwrite the existing items."*
- **View** (eye icon) shows the BOM with item rows.
- **Edit** (pencil icon) opens the same form pre-filled.
- **Delete** (trash icon) soft-deletes — restore from the
  `Status → Deleted` filter (admin / edit perm needed).

## Data model

```
PackingBOM
  ├─ id
  ├─ fg_material_id  (FK Material, UNIQUE — one BOM per FG)
  ├─ fg_qty, fg_uom
  ├─ notes
  ├─ is_active, is_deleted, deleted_at
  ├─ created_by, updated_by, created_at, updated_at
  └─ items → PackingBOMItem (cascade delete)

PackingBOMItem
  ├─ id
  ├─ packing_bom_id  (FK PackingBOM)
  ├─ sr_no
  ├─ material_id     (FK Material)
  ├─ qty
  └─ item_name_snap, uom_snap  (snapshots, so display survives renames)
```

## API summary

| Method | Path                               | Purpose                                  |
|--------|------------------------------------|------------------------------------------|
| GET    | `/packing-bom/`                    | List page (HTML)                         |
| GET    | `/packing-bom/api/list`            | JSON list, supports `search`, `status`   |
| GET    | `/packing-bom/api/<id>`            | View one BOM with items                  |
| GET    | `/packing-bom/api/by-fg/<fg_id>`   | Look up by FG (used by the warn banner)  |
| POST   | `/packing-bom/api/save`            | Create or upsert by `fg_material_id`     |
| DELETE | `/packing-bom/api/<id>`            | Soft delete                              |
| POST   | `/packing-bom/api/<id>/restore`    | Undo soft delete                         |
| GET    | `/packing-bom/api/fg-list`         | All FG materials (for dropdown)          |
| GET    | `/packing-bom/api/pm-list`         | All PM/Corrugation/Sleeves materials     |
|        | `   ?cat=Corrugation`             | Optional filter by sub-category          |
