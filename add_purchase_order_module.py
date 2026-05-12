"""
add_purchase_order_module.py
────────────────────────────
Run this ONCE to set up the Purchase Order system.

What it does
────────────
1. Creates all PO tables (header / items / terms / approval-log / status-log /
   terms-master / company-settings).
2. Seeds default Terms & Conditions per PO type.
3. Seeds default CompanySettings row (HCP Wellness Pvt Ltd) — pulled from the
   reference Tally PDF.
4. Registers the Purchase Order module in the sidebar (under Procurement).

Usage
─────
    python add_purchase_order_module.py
"""
from index import app
from models import db
from models.purchase_order import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderTerm,
    PurchaseOrderApprovalLog, PurchaseOrderStatusLog,
    PoDefaultTerm, CompanySettings,
)

try:
    from models.permission import Module
except Exception:
    Module = None


def seed_default_terms():
    """Insert the default Tally-style Terms & Conditions if none exist."""
    if PoDefaultTerm.query.count() > 0:
        print("  ↪ Default terms already exist — skipped.")
        return

    defaults = [
        # General
        ('ALL', 'GENERAL', 1,
         'PLEASE ALWAYS SEND COA, MSDS, TDS AND MICRO REPORT (IF NOT SENT PREVIOUSLY) FOR ALL THE MATERIAL YOU DISPATCH ON A STRICT NOTE.'),
        ('ALL', 'GENERAL', 2,
         'WE MAY REJECT AND SEND THE MATERIAL BACK TO YOU, IF THE MATERIAL DOESN\'T COMPLY AS PER OUR SPECIFICATION. WE MAY SEND MATERIAL ALONG WITH A DEBIT NOTE AND DEBIT NOTE MAY CONTAIN FREIGHT CHARGES.'),
        ('ALL', 'GENERAL', 3,
         'IT IS MANDATORY TO SEND AN INVOICE COPY AND COA OF THE PRODUCT ON EMAIL ALONG WITH DISPATCH DETAILS WHILE DISPATCHING.'),
        ('ALL', 'GENERAL', 4,
         'WE DO NOT ACCEPT MATERIALS LESS THAN 6 MONTH EXPIRY DATE.'),
        ('ALL', 'GENERAL', 5,
         'Material should be as per approved specification.'),
        ('ALL', 'GENERAL', 6,
         'GST invoice mandatory.'),
        ('ALL', 'GENERAL', 7,
         'Quantity variation allowed +/-5%.'),

        # Dispatch
        ('ALL', 'DISPATCH', 1,
         'OUR 1ST PRIORITY LOGISTIC PARTNERS ARE KALPATARU EXPRESS (TBB), V-TRANS (TBB), ACPL CARGO.'),
        ('ALL', 'DISPATCH', 2,
         'DOOR DELIVERY IS ACCEPTED ONLY AT THE FACTORY ADDRESS ONLY IF THE MATERIAL IS DISPATCHED THROUGH LOGISTICS AND MORE QUANTITY THEN 20 KG.'),
        ('ALL', 'DISPATCH', 3,
         'NEVER DISPATCH MATERIAL THROUGH BHAVNA ROADWAYS, DTDC COURIER, TRACKON COURIER AND MARUTI COURIERS. KINDLY DISPATCH MATERIALS BY ANJANI COURIER. IF SENT MATERIAL THROUGH THESE LOGISTIC PARTNERS WE WILL NOT ACCEPT MATERIAL.'),
        ('ALL', 'DISPATCH', 4,
         'WE WILL NOT BARE DEMURRAGE CHARGES IN CASE THE DISPATCH DETAILS ARE NOT SHARED ON TIME.'),
        ('ALL', 'DISPATCH', 5,
         'IF THE MATERIAL IS DISPATCHED ON GODOWN DELIVERY TERMS, KINDLY DISPATCH TO SARKHEJ OR CHANGODAR GODOWN ONLY.'),

        # Payment
        ('ALL', 'PAYMENT', 1,
         'PAYMENT CREDIT TERMS WILL BE CONSIDERED FROM THE DATE OF MATERIAL RECEIPT AT OUR END.'),
        ('ALL', 'PAYMENT', 2,
         'Payment terms as agreed.'),
        ('ALL', 'PAYMENT', 3,
         'Subject to Ahmedabad jurisdiction.'),
    ]

    for po_type, section, sort_order, text in defaults:
        db.session.add(PoDefaultTerm(
            po_type=po_type, section=section,
            sort_order=sort_order, text=text,
            is_active=True, created_by='system',
        ))
    db.session.commit()
    print(f"  ✅ Inserted {len(defaults)} default term rows.")


def seed_company_settings():
    """Insert default HCP Wellness company info if missing."""
    if CompanySettings.query.count() > 0:
        print("  ↪ Company settings already exist — skipped.")
        return

    cs = CompanySettings(
        is_default=True,
        company_name='HCP Wellness Pvt Ltd',
        short_code='HCP',
        gst_number='24AAFCH7246H1ZK',
        pan_number='AAFCH7246H',
        state='Gujarat',
        state_code='24',
        bill_address=('403 Maruti Vertex Elanza, Opp. Global Hospital, '
                      'Nr. GTPL House, Sindhubhavan Road, Bodakdev, '
                      'Ahmedabad-380054'),
        ship_address=('Plot No. 8, Ozone Industrial Estate, Beside Kerala '
                      'GIDC, Bavla-Bagodara Road, Bhayla, Bavla-382220, '
                      'Gujarat, India.'),
        phone='',
        email='',
        website='',
        declaration_text=('IF DISPATCHING THE MATERIAL THROUGH LOGISTIC '
                          'GODOWN DELIVERY, PLEASE DISPATCH TO SARKHEJ '
                          'OR CHANGODAR (1ST PRIORITY) GODOWN ONLY'),
        jurisdiction='Ahmedabad',
    )
    db.session.add(cs)
    db.session.commit()
    print("  ✅ Inserted HCP Wellness default company settings.")


def register_sidebar_module():
    if Module is None:
        print("  ↪ permission.Module not available — sidebar registration skipped.")
        return

    # Locate the existing "Procurement" parent (created by add_procurement_modules.py)
    proc = Module.query.filter_by(name='procurement').first()
    if not proc:
        print("  ⚠️  'procurement' parent module not found — running parent setup first…")
        proc = Module(name='procurement', label='Procurement', icon='🛒',
                      url_prefix='', sort_order=19, is_active=True, parent_id=None)
        db.session.add(proc)
        db.session.flush()

    # Purchase Order parent (child of Procurement)
    po_parent = Module.query.filter_by(name='purchase_order').first()
    if not po_parent:
        po_parent = Module(
            name       = 'purchase_order',
            label      = 'Purchase Order',
            icon       = '📄',
            url_prefix = '/purchase-order',
            sort_order = 25,
            is_active  = True,
            parent_id  = proc.id,
        )
        db.session.add(po_parent)
        db.session.flush()
        print(f"  ✅ Created 'purchase_order' sidebar entry (id={po_parent.id})")
    else:
        po_parent.parent_id = proc.id
        po_parent.is_active = True
        po_parent.label     = 'Purchase Order'
        po_parent.icon      = '📄'
        po_parent.url_prefix= '/purchase-order'
        po_parent.sort_order= 25
        print(f"  ✔️  'purchase_order' already exists (id={po_parent.id}) — updated")

    # Sub-modules per PO type (URL-driven so we can route directly)
    submods = [
        ('po_rm',  'RM PO',          '🧪', '/purchase-order?po_type=RM',  26),
        ('po_pm',  'PM PO',          '📦', '/purchase-order?po_type=PM',  27),
        ('po_cor', 'Corrugation PO', '🟫', '/purchase-order?po_type=COR', 28),
        ('po_slv', 'Sleeves PO',     '🎯', '/purchase-order?po_type=SLV', 29),
        ('po_dashboard', 'PO Dashboard', '📊', '/purchase-order/dashboard', 30),
        ('po_reports',   'PO Reports',   '📈', '/purchase-order/reports',   31),
        ('po_terms',     'PO Terms Master', '📋', '/purchase-order/terms-master', 32),
        ('po_company_settings', 'Company Settings', '⚙️', '/purchase-order/company-settings', 33),
    ]
    for name, label, icon, url, order in submods:
        m = Module.query.filter_by(name=name).first()
        if not m:
            m = Module(name=name, label=label, icon=icon,
                       url_prefix=url, sort_order=order,
                       is_active=True, parent_id=po_parent.id)
            db.session.add(m)
            print(f"     ➕ {label}")
        else:
            m.parent_id = po_parent.id
            m.is_active = True
            m.url_prefix= url
            m.label     = label
            m.icon      = icon
            m.sort_order= order

    db.session.commit()


def main():
    with app.app_context():
        print("🔧 Setting up Purchase Order Module…\n")

        print("[1/4] Creating tables…")
        db.create_all()
        # Verify
        from sqlalchemy import inspect
        insp = inspect(db.engine)
        for tbl in ['tbl_purchase_order', 'tbl_purchase_order_items',
                    'tbl_purchase_order_terms', 'tbl_purchase_order_approval_logs',
                    'tbl_purchase_order_status_logs', 'tbl_po_terms_master',
                    'tbl_company_settings']:
            exists = insp.has_table(tbl)
            print(f"     {'✅' if exists else '❌'} {tbl}")

        print("\n[2/4] Seeding default Terms & Conditions…")
        seed_default_terms()

        print("\n[3/4] Seeding Company Settings…")
        seed_company_settings()

        print("\n[4/4] Registering sidebar entries…")
        register_sidebar_module()

        print("\n🎉 Purchase Order Module setup complete!\n")
        print("Next steps:")
        print("  1. Add to index.py:")
        print("       from purchase_order_routes import po_bp")
        print("       app.register_blueprint(po_bp)")
        print("  2. Restart the Flask app.")
        print("  3. Open  /purchase-order  in the browser.\n")


if __name__ == '__main__':
    main()
