# HCP Wellness ERP — Purchase Order Module

Complete Tally-style Purchase Order system for the existing Flask HCP ERP.
All files generated for the project's existing stack (Flask + SQLAlchemy + reportlab + Jinja + Bootstrap/Select2/DataTables/flatpickr).

---

## 1. Files in this package

```
po_module/
├── models/
│   └── purchase_order.py           # 7 SQLAlchemy models
├── purchase_order_routes.py        # Flask blueprint (40+ endpoints incl. PDF/email/WhatsApp/reports)
├── add_purchase_order_module.py    # one-time migration + seeder + sidebar registrar
├── templates/
│   └── purchase_order/
│       ├── index.html              # PO listing (DataTable, filters, bulk actions)
│       ├── form.html               # Create / Edit PO  (full Tally form, real-time GST)
│       ├── view.html               # Tally-style PO preview + activity timeline + actions
│       ├── print.html              # Print-friendly HTML mirror of PDF
│       ├── dashboard.html          # 8 status tiles + doughnut + by-type bars
│       ├── reports.html            # 5 report tiles
│       ├── report_view.html        # generic report renderer + Excel/PDF export
│       ├── terms_master.html       # editable default terms grid
│       └── company_settings.html   # company info (Bill-To / Ship-To) form
└── README_INTEGRATION.md           # this file
```

---

## 2. Integration steps

1. **Copy model**
   ```
   cp models/purchase_order.py  hcperp/models/purchase_order.py
   ```

2. **Register model** — add to `hcperp/models/__init__.py`:
   ```python
   from .purchase_order import (
       PurchaseOrder, PurchaseOrderItem, PurchaseOrderTerm,
       PurchaseOrderApprovalLog, PurchaseOrderStatusLog,
       PoDefaultTerm, CompanySettings,
   )
   ```

3. **Copy routes & templates**
   ```
   cp purchase_order_routes.py        hcperp/purchase_order_routes.py
   cp -r templates/purchase_order     hcperp/templates/purchase_order
   ```

4. **Register blueprint** — in `hcperp/index.py`:
   ```python
   from purchase_order_routes import po_bp
   app.register_blueprint(po_bp)
   ```

5. **Set up the database** — pick **one** of:

   **Option A — Python migration** (recommended; uses SQLAlchemy, creates tables + seeds + sidebar):
   ```
   cp add_purchase_order_module.py hcperp/
   cd hcperp
   python add_purchase_order_module.py
   ```

   **Option B — Raw SQL** (for phpMyAdmin / MySQL Workbench / command-line MySQL):
   ```
   mysql -u root -p erpdb < po_module.sql
   ```
   The `po_module.sql` file is idempotent — safe to re-run. It creates all 7
   tables, seeds 15 default T&C rows, seeds the HCP Wellness company row, and
   adds 9 sidebar entries under Procurement.

6. **Restart Flask** → open `/purchase-order/` in the browser.

---

## 3. What was built — feature checklist (vs the spec you sent)

| Spec | Status |
|---|---|
| 4 PO Types (RM / PM / Corrugation / Sleeves) | ✓ |
| Auto-numbered PO — Tally style `HCP/RM/PO-0001/26-27` + short `RMPO-2026-0001` | ✓ (both, yearly-incrementing, Indian FY) |
| Header / Company / Delivery / Items / Amount Summary / Terms | ✓ |
| Dynamic item rows, auto-fetch, GST auto-calc, grand-total auto | ✓ (real-time, both client + server) |
| Intrastate (CGST+SGST) vs Interstate (IGST) auto-detection | ✓ (supplier state vs company state) |
| Amount in words (Indian Crore/Lakh) | ✓ (Python + JS) |
| Default editable T&C master, grouped GENERAL/DISPATCH/PAYMENT/OTHER | ✓ |
| Workflow: Draft → Pending → Approved → Rejected, plus Partial / Complete / Cancelled | ✓ (7 statuses, full approval + status logs) |
| Tally-style PDF (reportlab — drop-in for TCPDF) + Download / Print / Email / Save Path | ✓ |
| Email PDF to supplier | ✓ (uses project's mail_routes if available, else stdlib SMTP) |
| WhatsApp-ready structure | ✓ (uses whatsapp_sender if available, else returns wa.me link) |
| Listing page — DataTable + filters + row actions | ✓ |
| Dashboard counts | ✓ (8 tiles + Chart.js doughnut + by-type bars) |
| Validation (qty>0, supplier required, GST, numeric) | ✓ (server + client) |
| 5 reports + Excel/PDF export | ✓ (openpyxl for xlsx, reportlab landscape for PDF) |
| Audit logging, soft-delete | ✓ (via project's existing `audit_helper`) |
| Bootstrap / Select2 / DataTables / jQuery AJAX | ✓ (matches existing supplier module conventions) |

---

## 4. PO number format — note

The spec asked for the short form `RMPO-2026-0001`, but your reference PDF uses the Tally form `HCP/RM/PO-0264/26-27`. **Both are generated and stored** on every PO:
- `po_number`        → Tally form (shown on PDF / view / lists)
- `po_number_short`  → short form (used in filenames, URLs, search)

Both auto-increment yearly by PO type. Indian FY (April–March) is used for the `26-27` portion.

---

## 5. Quick tour after install

- `/purchase-order/`                    — all POs (use the Type tabs to filter)
- `/purchase-order/dashboard`           — counts + chart
- `/purchase-order/new?type=RM`         — create a new RM PO (or PM / COR / SLV)
- `/purchase-order/<id>/view`           — Tally-style preview + action bar
- `/purchase-order/<id>/pdf`            — download PDF
- `/purchase-order/reports`             — 5 report tiles
- `/purchase-order/terms-master`        — edit default T&C
- `/purchase-order/company-settings`    — edit Bill-To / Ship-To

---

## 6. Permissions

Uses the project's existing role helpers (`_role`, `_can`):
- **Purchase User** — create, edit own drafts, submit for approval
- **Purchase Manager** — approve / reject up to a threshold, cancel
- **Director / Admin** — final approval, cancel anything, edit terms master & company settings

Adjust thresholds in `purchase_order_routes.py` (`_can` calls) if your role names differ.
