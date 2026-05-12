"""
models/purchase_order.py
────────────────────────
Purchase Order Module – complete Tally-style PO system.

Tables created
──────────────
1. tbl_purchase_order              (PurchaseOrder)
2. tbl_purchase_order_items        (PurchaseOrderItem)
3. tbl_purchase_order_terms        (PurchaseOrderTerm)
4. tbl_purchase_order_approval_logs(PurchaseOrderApprovalLog)
5. tbl_purchase_order_status_logs  (PurchaseOrderStatusLog)
6. tbl_po_terms_master             (PoDefaultTerm)            ← saved default terms
7. tbl_company_settings            (CompanySettings)          ← Company info on PDF

PO Types  : RM | PM | COR (Corrugation) | SLV (Sleeves)
Statuses  : Draft | Pending Approval | Approved | Rejected
            Partial Received | Completed | Cancelled

PO Number Formats supported
───────────────────────────
• Tally style  →  HCP/RM/PO-0001/26-27   (matches existing PDF)
• Short style  →  RMPO-2026-0001         (as per spec)

Both are stored; `po_number` is the canonical (Tally style) and
`po_number_short` is the short style for filenames/URLs.
"""
from datetime import datetime, date
from decimal import Decimal
from .base import db


# ── Status constants (single source of truth) ────────────────────────────────
PO_STATUS_DRAFT    = 'Draft'
PO_STATUS_PENDING  = 'Pending Approval'
PO_STATUS_APPROVED = 'Approved'
PO_STATUS_REJECTED = 'Rejected'
PO_STATUS_PARTIAL  = 'Partial Received'
PO_STATUS_COMPLETE = 'Completed'
PO_STATUS_CANCEL   = 'Cancelled'

PO_STATUSES = [
    PO_STATUS_DRAFT, PO_STATUS_PENDING, PO_STATUS_APPROVED,
    PO_STATUS_REJECTED, PO_STATUS_PARTIAL, PO_STATUS_COMPLETE,
    PO_STATUS_CANCEL,
]

PO_STATUS_COLORS = {
    PO_STATUS_DRAFT   : '#64748b',
    PO_STATUS_PENDING : '#f59e0b',
    PO_STATUS_APPROVED: '#16a34a',
    PO_STATUS_REJECTED: '#dc2626',
    PO_STATUS_PARTIAL : '#0ea5e9',
    PO_STATUS_COMPLETE: '#7c3aed',
    PO_STATUS_CANCEL  : '#94a3b8',
}

PO_TYPES = {
    'RM' : 'Raw Material',
    'PM' : 'Packing Material',
    'COR': 'Corrugation',
    'SLV': 'Sleeves',
}

# Short prefixes (per spec)
PO_TYPE_PREFIX_SHORT = {
    'RM' : 'RMPO',
    'PM' : 'PMPO',
    'COR': 'CORPO',
    'SLV': 'SLVPO',
}


# ═════════════════════════════════════════════════════════════════════════════
# 1. PURCHASE ORDER  (header / master)
# ═════════════════════════════════════════════════════════════════════════════
class PurchaseOrder(db.Model):
    __tablename__ = 'tbl_purchase_order'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # ── Identification ──────────────────────────────────────────────────────
    po_type         = db.Column(db.String(10),  nullable=False, default='RM')   # RM/PM/COR/SLV
    po_number       = db.Column(db.String(60),  nullable=False, unique=True)    # HCP/RM/PO-0001/26-27
    po_number_short = db.Column(db.String(60),  default='', index=True)         # RMPO-2026-0001
    po_serial       = db.Column(db.Integer,     default=0)                      # yearly running serial
    po_fy           = db.Column(db.String(10),  default='')                     # 26-27
    po_year         = db.Column(db.Integer,     default=0)                      # 2026
    po_date         = db.Column(db.Date,        nullable=False, default=date.today)

    # ── Supplier (Bill-from) ────────────────────────────────────────────────
    supplier_id     = db.Column(db.Integer, db.ForeignKey('suppliers.id'), nullable=False)
    supplier_name   = db.Column(db.String(300), default='')
    supplier_address= db.Column(db.Text,        default='')
    supplier_gst    = db.Column(db.String(20),  default='')
    supplier_pan    = db.Column(db.String(20),  default='')
    supplier_state  = db.Column(db.String(100), default='')
    supplier_state_code = db.Column(db.String(10), default='')
    supplier_country = db.Column(db.String(100), default='India')
    supplier_contact_person = db.Column(db.String(200), default='')
    supplier_mobile = db.Column(db.String(30),  default='')
    supplier_email  = db.Column(db.String(200), default='')

    # ── Company (Invoice-to) ────────────────────────────────────────────────
    company_name    = db.Column(db.String(300), default='HCP Wellness Pvt Ltd')
    company_gst     = db.Column(db.String(20),  default='')
    company_pan     = db.Column(db.String(20),  default='')
    company_address = db.Column(db.Text,        default='')
    company_state   = db.Column(db.String(100), default='Gujarat')
    company_state_code = db.Column(db.String(10), default='24')

    # ── Delivery (Consignee / Ship-to) ──────────────────────────────────────
    delivery_address    = db.Column(db.Text,    default='')
    expected_delivery   = db.Column(db.Date,    nullable=True)
    transport_mode      = db.Column(db.String(100), default='')   # Road / Rail / Air / Courier
    dispatched_through  = db.Column(db.String(200), default='')
    destination         = db.Column(db.String(200), default='')
    reference_no        = db.Column(db.String(100), default='')
    reference_date      = db.Column(db.Date, nullable=True)
    other_references    = db.Column(db.String(200), default='')

    # ── Payment ─────────────────────────────────────────────────────────────
    payment_terms       = db.Column(db.String(200), default='')   # e.g. "30 DAYS"
    credit_days         = db.Column(db.Integer,     default=30)

    # ── Amount summary (header totals — also stored for reporting speed) ────
    basic_total         = db.Column(db.Numeric(14,2), default=0)
    discount_total      = db.Column(db.Numeric(14,2), default=0)
    taxable_amount      = db.Column(db.Numeric(14,2), default=0)
    cgst_total          = db.Column(db.Numeric(14,2), default=0)
    sgst_total          = db.Column(db.Numeric(14,2), default=0)
    igst_total          = db.Column(db.Numeric(14,2), default=0)
    round_off           = db.Column(db.Numeric(8,2),  default=0)
    grand_total         = db.Column(db.Numeric(14,2), default=0)
    amount_in_words     = db.Column(db.String(500),   default='')
    total_quantity      = db.Column(db.Numeric(14,3), default=0)

    # GST mode — intra-state (CGST+SGST) OR inter-state (IGST)
    is_interstate       = db.Column(db.Boolean,       default=False)

    # ── Workflow ────────────────────────────────────────────────────────────
    status              = db.Column(db.String(30),  default=PO_STATUS_DRAFT, index=True)
    is_locked           = db.Column(db.Boolean,     default=False)   # locked after approve

    # Approval (level 1 — Purchase Manager)
    submitted_at        = db.Column(db.DateTime, nullable=True)
    submitted_by_id     = db.Column(db.Integer,  nullable=True)
    submitted_by_name   = db.Column(db.String(150), default='')

    approved_by_id      = db.Column(db.Integer,  nullable=True)
    approved_by_name    = db.Column(db.String(150), default='')
    approved_at         = db.Column(db.DateTime, nullable=True)

    # Level 2 — Director final
    director_approved_by_id    = db.Column(db.Integer,  nullable=True)
    director_approved_by_name  = db.Column(db.String(150), default='')
    director_approved_at       = db.Column(db.DateTime, nullable=True)

    rejected_by_id      = db.Column(db.Integer,  nullable=True)
    rejected_by_name    = db.Column(db.String(150), default='')
    rejected_at         = db.Column(db.DateTime, nullable=True)
    rejection_reason    = db.Column(db.Text,     default='')

    cancelled_by_id     = db.Column(db.Integer,  nullable=True)
    cancelled_by_name   = db.Column(db.String(150), default='')
    cancelled_at        = db.Column(db.DateTime, nullable=True)
    cancel_reason       = db.Column(db.Text,     default='')

    # ── Communication ──────────────────────────────────────────────────────
    pdf_path            = db.Column(db.String(500), default='')
    email_sent          = db.Column(db.Boolean,     default=False)
    email_sent_at       = db.Column(db.DateTime, nullable=True)
    email_sent_to       = db.Column(db.String(500), default='')
    whatsapp_sent       = db.Column(db.Boolean,     default=False)
    whatsapp_sent_at    = db.Column(db.DateTime, nullable=True)

    # ── Receiving progress (for Partial / Completed) ────────────────────────
    received_qty        = db.Column(db.Numeric(14,3), default=0)
    received_amount     = db.Column(db.Numeric(14,2), default=0)

    # ── Free-form ──────────────────────────────────────────────────────────
    declaration         = db.Column(db.Text, default='')
    narration           = db.Column(db.Text, default='')

    # ── Meta ────────────────────────────────────────────────────────────────
    is_deleted          = db.Column(db.Boolean,     default=False)
    deleted_at          = db.Column(db.DateTime,    nullable=True)
    deleted_by_name     = db.Column(db.String(150), default='')
    created_by_id       = db.Column(db.Integer,     nullable=True)
    created_by_name     = db.Column(db.String(150), default='')
    updated_by_name     = db.Column(db.String(150), default='')
    created_at          = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at          = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # ── Relationships ───────────────────────────────────────────────────────
    items       = db.relationship('PurchaseOrderItem', backref='po', lazy='dynamic',
                                  cascade='all, delete-orphan',
                                  order_by='PurchaseOrderItem.sr_no')
    terms       = db.relationship('PurchaseOrderTerm', backref='po', lazy='dynamic',
                                  cascade='all, delete-orphan',
                                  order_by='PurchaseOrderTerm.sort_order')
    approval_logs = db.relationship('PurchaseOrderApprovalLog', backref='po', lazy='dynamic',
                                    cascade='all, delete-orphan',
                                    order_by='PurchaseOrderApprovalLog.created_at')
    status_logs   = db.relationship('PurchaseOrderStatusLog', backref='po', lazy='dynamic',
                                    cascade='all, delete-orphan',
                                    order_by='PurchaseOrderStatusLog.created_at')

    def __repr__(self):
        return f'<PO {self.po_number} – {self.supplier_name} – {self.status}>'

    # ── helpers ────────────────────────────────────────────────────────────
    @property
    def status_color(self):
        return PO_STATUS_COLORS.get(self.status, '#64748b')

    @property
    def type_label(self):
        return PO_TYPES.get(self.po_type, self.po_type)

    @property
    def is_editable(self):
        """POs can be edited until they're Approved by a manager.
        Editable states: Draft, Rejected, Cancelled, Pending Approval.
        Locked states: Approved, Partial, Completed."""
        return (self.status in (PO_STATUS_DRAFT, PO_STATUS_REJECTED,
                                PO_STATUS_CANCEL, PO_STATUS_PENDING)
                and not self.is_locked)

    @property
    def can_approve(self):
        return self.status == PO_STATUS_PENDING

    @property
    def can_cancel(self):
        return self.status not in (PO_STATUS_COMPLETE, PO_STATUS_CANCEL)

    def to_dict(self):
        return {
            'id'             : self.id,
            'po_type'        : self.po_type,
            'type_label'     : self.type_label,
            'po_number'      : self.po_number,
            'po_number_short': self.po_number_short,
            'po_date'        : self.po_date.strftime('%d-%m-%Y') if self.po_date else '',
            'supplier_id'    : self.supplier_id,
            'supplier_name'  : self.supplier_name or '',
            'supplier_gst'   : self.supplier_gst or '',
            'supplier_mobile': self.supplier_mobile or '',
            'supplier_email' : self.supplier_email or '',
            'grand_total'    : float(self.grand_total or 0),
            'total_quantity' : float(self.total_quantity or 0),
            'status'         : self.status,
            'status_color'   : self.status_color,
            'is_editable'    : self.is_editable,
            'is_locked'      : self.is_locked,
            'created_by'     : self.created_by_name or '',
            'created_at'     : self.created_at.strftime('%d-%m-%Y %H:%M') if self.created_at else '',
            'approved_by'    : self.approved_by_name or '',
            'item_count'     : self.items.count(),
            'expected_delivery': self.expected_delivery.strftime('%d-%m-%Y') if self.expected_delivery else '',
            'payment_terms'  : self.payment_terms or '',
            'email_sent'     : self.email_sent or False,
        }


# ═════════════════════════════════════════════════════════════════════════════
# 2. PURCHASE ORDER ITEM (line items)
# ═════════════════════════════════════════════════════════════════════════════
class PurchaseOrderItem(db.Model):
    __tablename__ = 'tbl_purchase_order_items'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    po_id           = db.Column(db.Integer, db.ForeignKey('tbl_purchase_order.id', ondelete='CASCADE'),
                                nullable=False, index=True)

    sr_no           = db.Column(db.Integer, default=1)

    # Material link (optional — items may be free-text for misc purchases)
    material_id     = db.Column(db.Integer, db.ForeignKey('materials.id'), nullable=True)
    item_code       = db.Column(db.String(100), default='')
    item_name       = db.Column(db.String(300), nullable=False)
    description     = db.Column(db.Text,        default='')
    category        = db.Column(db.String(200), default='')
    hsn_code        = db.Column(db.String(20),  default='')
    uom             = db.Column(db.String(30),  default='KG')

    # Quantities & money
    quantity        = db.Column(db.Numeric(14,3), default=0)
    rate            = db.Column(db.Numeric(14,4), default=0)
    discount_pct    = db.Column(db.Numeric(6,2),  default=0)
    discount_amt    = db.Column(db.Numeric(14,2), default=0)
    gst_pct         = db.Column(db.Numeric(5,2),  default=0)
    amount          = db.Column(db.Numeric(14,2), default=0)   # qty * rate
    taxable_amount  = db.Column(db.Numeric(14,2), default=0)   # amount – discount
    cgst_amount     = db.Column(db.Numeric(14,2), default=0)
    sgst_amount     = db.Column(db.Numeric(14,2), default=0)
    igst_amount     = db.Column(db.Numeric(14,2), default=0)
    tax_amount      = db.Column(db.Numeric(14,2), default=0)
    total_amount    = db.Column(db.Numeric(14,2), default=0)   # taxable + tax

    # Due / delivery (per line — matches the Tally PDF "Due On" column)
    due_date        = db.Column(db.Date, nullable=True)

    remark          = db.Column(db.Text, default='')

    # Receiving (for partial / completed tracking)
    received_qty    = db.Column(db.Numeric(14,3), default=0)
    pending_qty     = db.Column(db.Numeric(14,3), default=0)

    def __repr__(self):
        return f'<POItem PO={self.po_id} {self.item_name} qty={self.quantity}>'

    def to_dict(self):
        return {
            'id'           : self.id,
            'sr_no'        : self.sr_no,
            'material_id'  : self.material_id,
            'item_code'    : self.item_code or '',
            'item_name'    : self.item_name or '',
            'description'  : self.description or '',
            'category'     : self.category or '',
            'hsn_code'     : self.hsn_code or '',
            'uom'          : self.uom or '',
            'quantity'     : float(self.quantity or 0),
            'rate'         : float(self.rate or 0),
            'discount_pct' : float(self.discount_pct or 0),
            'discount_amt' : float(self.discount_amt or 0),
            'gst_pct'      : float(self.gst_pct or 0),
            'amount'       : float(self.amount or 0),
            'taxable_amount': float(self.taxable_amount or 0),
            'cgst_amount'  : float(self.cgst_amount or 0),
            'sgst_amount'  : float(self.sgst_amount or 0),
            'igst_amount'  : float(self.igst_amount or 0),
            'tax_amount'   : float(self.tax_amount or 0),
            'total_amount' : float(self.total_amount or 0),
            'due_date'     : self.due_date.strftime('%d-%m-%Y') if self.due_date else '',
            'remark'       : self.remark or '',
            'received_qty' : float(self.received_qty or 0),
            'pending_qty'  : float(self.pending_qty or 0),
        }


# ═════════════════════════════════════════════════════════════════════════════
# 3. PURCHASE ORDER TERMS  (per-PO terms & conditions, free-form)
# ═════════════════════════════════════════════════════════════════════════════
class PurchaseOrderTerm(db.Model):
    __tablename__ = 'tbl_purchase_order_terms'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    po_id       = db.Column(db.Integer, db.ForeignKey('tbl_purchase_order.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    section     = db.Column(db.String(80), default='GENERAL')   # GENERAL / DISPATCH / PAYMENT / OTHER
    sort_order  = db.Column(db.Integer,    default=0)
    text        = db.Column(db.Text,       nullable=False)

    def to_dict(self):
        return {
            'id': self.id, 'section': self.section,
            'sort_order': self.sort_order, 'text': self.text or '',
        }


# ═════════════════════════════════════════════════════════════════════════════
# 4. APPROVAL LOG
# ═════════════════════════════════════════════════════════════════════════════
class PurchaseOrderApprovalLog(db.Model):
    __tablename__ = 'tbl_purchase_order_approval_logs'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    po_id       = db.Column(db.Integer, db.ForeignKey('tbl_purchase_order.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    level       = db.Column(db.String(50), default='Manager')   # User / Manager / Director
    action      = db.Column(db.String(30), default='SUBMITTED') # SUBMITTED / APPROVED / REJECTED / RE-SUBMITTED
    actor_id    = db.Column(db.Integer,    nullable=True)
    actor_name  = db.Column(db.String(150), default='')
    actor_role  = db.Column(db.String(80),  default='')
    comment     = db.Column(db.Text,       default='')
    created_at  = db.Column(db.DateTime,   default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'level': self.level, 'action': self.action,
            'actor_name': self.actor_name or '', 'actor_role': self.actor_role or '',
            'comment': self.comment or '',
            'created_at': self.created_at.strftime('%d-%m-%Y %H:%M') if self.created_at else '',
        }


# ═════════════════════════════════════════════════════════════════════════════
# 5. STATUS CHANGE LOG (every status transition)
# ═════════════════════════════════════════════════════════════════════════════
class PurchaseOrderStatusLog(db.Model):
    __tablename__ = 'tbl_purchase_order_status_logs'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    po_id       = db.Column(db.Integer, db.ForeignKey('tbl_purchase_order.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    from_status = db.Column(db.String(30), default='')
    to_status   = db.Column(db.String(30), default='')
    actor_id    = db.Column(db.Integer,    nullable=True)
    actor_name  = db.Column(db.String(150), default='')
    note        = db.Column(db.Text,       default='')
    created_at  = db.Column(db.DateTime,   default=datetime.utcnow)


# ═════════════════════════════════════════════════════════════════════════════
# 6. DEFAULT TERMS MASTER (re-usable templates per PO type)
# ═════════════════════════════════════════════════════════════════════════════
class PoDefaultTerm(db.Model):
    __tablename__ = 'tbl_po_terms_master'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    po_type     = db.Column(db.String(10),  default='ALL')      # RM / PM / COR / SLV / ALL
    section     = db.Column(db.String(80),  default='GENERAL')  # GENERAL / DISPATCH / PAYMENT / OTHER
    sort_order  = db.Column(db.Integer,     default=0)
    text        = db.Column(db.Text,        nullable=False)
    is_active   = db.Column(db.Boolean,     default=True)
    is_deleted  = db.Column(db.Boolean,     default=False)
    created_by  = db.Column(db.String(100), default='')
    created_at  = db.Column(db.DateTime,    default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'po_type': self.po_type,
            'section': self.section, 'sort_order': self.sort_order,
            'text': self.text or '', 'is_active': self.is_active,
        }


# ═════════════════════════════════════════════════════════════════════════════
# 7. COMPANY SETTINGS (used on PDF header / invoice-to)
# ═════════════════════════════════════════════════════════════════════════════
class CompanySettings(db.Model):
    __tablename__ = 'tbl_company_settings'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    is_default      = db.Column(db.Boolean, default=True)
    company_name    = db.Column(db.String(300), default='HCP Wellness Pvt Ltd')
    short_code      = db.Column(db.String(20),  default='HCP')   # for PO number generation
    gst_number      = db.Column(db.String(20),  default='24AAFCH7246H1ZK')
    pan_number      = db.Column(db.String(20),  default='')
    state           = db.Column(db.String(100), default='Gujarat')
    state_code      = db.Column(db.String(10),  default='24')

    # Registered / Invoice-to address
    bill_address    = db.Column(db.Text, default='')
    # Factory / Consignee address
    ship_address    = db.Column(db.Text, default='')

    phone           = db.Column(db.String(50),  default='')
    email           = db.Column(db.String(200), default='')
    website         = db.Column(db.String(200), default='')

    logo_path       = db.Column(db.String(500), default='')
    signature_path  = db.Column(db.String(500), default='')

    declaration_text= db.Column(db.Text, default='')
    jurisdiction    = db.Column(db.String(100), default='Ahmedabad')

    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get_default():
        row = CompanySettings.query.filter_by(is_default=True).first()
        if not row:
            row = CompanySettings.query.first()
        return row

    def to_dict(self):
        return {
            'id': self.id,
            'company_name': self.company_name or '',
            'short_code'  : self.short_code or 'HCP',
            'gst_number'  : self.gst_number or '',
            'pan_number'  : self.pan_number or '',
            'state'       : self.state or '',
            'state_code'  : self.state_code or '',
            'bill_address': self.bill_address or '',
            'ship_address': self.ship_address or '',
            'phone'       : self.phone or '',
            'email'       : self.email or '',
            'website'     : self.website or '',
            'logo_path'   : self.logo_path or '',
            'signature_path': self.signature_path or '',
            'declaration_text': self.declaration_text or '',
            'jurisdiction': self.jurisdiction or 'Ahmedabad',
        }
