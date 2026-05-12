"""
GRN (Goods Receipt Note) Models
═══════════════════════════════════════════════════════════════════════════
Tables:
  1. GrnMaster          (tbl_grn_master)
  2. GrnItem            (tbl_grn_items)
  3. GrnStatusLog       (tbl_grn_status_logs)
  4. GrnApprovalLog     (tbl_grn_approval_logs)
  5. GrnStockLedger     (tbl_grn_stock_ledger)
  6. GrnBatchStock      (tbl_grn_batch_stock)
"""
from datetime import datetime, date
from .base import db


# ═════════════════════════════════════════════════════════════════════════════
# Status & Type constants  (No approval workflow — direct Draft → Completed)
# ═════════════════════════════════════════════════════════════════════════════
GRN_STATUS_DRAFT     = 'Draft'
GRN_STATUS_COMPLETED = 'Completed'
GRN_STATUS_CANCEL    = 'Cancelled'

# Kept for backward compat with existing DB rows; not used in new workflow
GRN_STATUS_PENDING   = 'Pending Approval'
GRN_STATUS_APPROVED  = 'Approved'
GRN_STATUS_REJECTED  = 'Rejected'

GRN_STATUSES = [GRN_STATUS_DRAFT, GRN_STATUS_COMPLETED, GRN_STATUS_CANCEL]

GRN_STATUS_COLORS = {
    GRN_STATUS_DRAFT:     '#3b82f6',  # blue
    GRN_STATUS_COMPLETED: '#10b981',  # green
    GRN_STATUS_CANCEL:    '#6b7280',  # gray
    GRN_STATUS_PENDING:   '#f59e0b',  # legacy (amber)
    GRN_STATUS_APPROVED:  '#10b981',  # legacy (green)
    GRN_STATUS_REJECTED:  '#dc2626',  # legacy (red)
}

GRN_TYPES = {
    'RM':  'Raw Material',
    'PM':  'Packing Material',
    'COR': 'Corrugation',
    'SLV': 'Sleeves',
    'FG':  'Finish Goods',
}

DELIVERY_TYPES = ['Road', 'Rail', 'Air', 'Courier', 'Hand Delivery', 'Self Pickup']


# ═════════════════════════════════════════════════════════════════════════════
# 1. GRN MASTER
# ═════════════════════════════════════════════════════════════════════════════
class GrnMaster(db.Model):
    __tablename__ = 'tbl_grn_master'

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Numbering
    grn_type            = db.Column(db.String(10),  nullable=False, default='RM')
    grn_number          = db.Column(db.String(60),  nullable=False, unique=True)
    grn_number_short    = db.Column(db.String(60),  default='', index=True)
    grn_serial          = db.Column(db.Integer,     default=0)
    grn_fy              = db.Column(db.String(10),  default='')
    grn_year            = db.Column(db.Integer,     default=0)
    grn_date            = db.Column(db.Date,        nullable=False, default=date.today)

    # Source PO
    po_id               = db.Column(db.Integer,     nullable=True, index=True)
    po_number           = db.Column(db.String(60),  default='')
    po_date             = db.Column(db.Date,        nullable=True)

    # Supplier
    supplier_id         = db.Column(db.Integer,     nullable=True, index=True)
    supplier_name       = db.Column(db.String(300), default='')
    supplier_address    = db.Column(db.Text,        default='')

    # Invoice
    invoice_no          = db.Column(db.String(100), default='')
    invoice_date        = db.Column(db.Date,        nullable=True)
    invoice_file        = db.Column(db.String(500), default='')   # Uploaded invoice (PDF/image)

    # Receive location
    receive_location_id = db.Column(db.Integer,     nullable=True)
    receive_location_name = db.Column(db.String(150), default='')
    receive_location_address = db.Column(db.Text,   default='')

    # Gate inward
    gate_inward_no      = db.Column(db.String(50),  default='')
    gate_inward_date    = db.Column(db.Date,        nullable=True)
    gate_inward_time    = db.Column(db.Time,        nullable=True)
    unloading_time      = db.Column(db.Time,        nullable=True)

    # Logistics
    lr_no               = db.Column(db.String(50),  default='')
    lr_date             = db.Column(db.Date,        nullable=True)
    logistics_name      = db.Column(db.String(200), default='')
    delivery_type       = db.Column(db.String(50),  default='')
    driver_name         = db.Column(db.String(150), default='')
    driver_contact      = db.Column(db.String(30),  default='')
    vehicle_no          = db.Column(db.String(30),  default='')
    supervisor_name     = db.Column(db.String(150), default='')

    # Quality checklist
    qc_test_certificate   = db.Column(db.Boolean, default=False)
    qc_batch_on_product   = db.Column(db.Boolean, default=False)
    qc_physical_condition = db.Column(db.Boolean, default=False)
    qc_expiry_date        = db.Column(db.Boolean, default=False)
    qc_label_checked      = db.Column(db.Boolean, default=False)
    rejection_remarks     = db.Column(db.Text,    default='')

    # Totals
    total_ordered_qty   = db.Column(db.Numeric(14, 3), default=0)
    total_received_qty  = db.Column(db.Numeric(14, 3), default=0)
    total_accepted_qty  = db.Column(db.Numeric(14, 3), default=0)
    total_rejected_qty  = db.Column(db.Numeric(14, 3), default=0)
    total_box_qty       = db.Column(db.Integer,        default=0)
    total_amount        = db.Column(db.Numeric(14, 2), default=0)

    # Remarks
    supplier_remarks    = db.Column(db.Text, default='')
    internal_remarks    = db.Column(db.Text, default='')

    # Status
    status              = db.Column(db.String(30), nullable=False, default=GRN_STATUS_DRAFT, index=True)
    is_locked           = db.Column(db.Boolean,    default=False)

    # Approval audit
    submitted_by_id     = db.Column(db.Integer,    nullable=True)
    submitted_by_name   = db.Column(db.String(150), default='')
    submitted_at        = db.Column(db.DateTime,   nullable=True)
    approved_by_id      = db.Column(db.Integer,    nullable=True)
    approved_by_name    = db.Column(db.String(150), default='')
    approved_at         = db.Column(db.DateTime,   nullable=True)
    rejected_by_id      = db.Column(db.Integer,    nullable=True)
    rejected_by_name    = db.Column(db.String(150), default='')
    rejected_at         = db.Column(db.DateTime,   nullable=True)
    rejection_reason    = db.Column(db.Text,       default='')
    cancelled_by_id     = db.Column(db.Integer,    nullable=True)
    cancelled_by_name   = db.Column(db.String(150), default='')
    cancelled_at        = db.Column(db.DateTime,   nullable=True)
    cancel_reason       = db.Column(db.Text,       default='')

    # Soft delete + audit
    is_deleted          = db.Column(db.Boolean,    default=False)
    deleted_at          = db.Column(db.DateTime,   nullable=True)
    deleted_by_name     = db.Column(db.String(150), default='')
    created_by_id       = db.Column(db.Integer,    nullable=True)
    created_by_name     = db.Column(db.String(150), default='')
    updated_by_name     = db.Column(db.String(150), default='')
    created_at          = db.Column(db.DateTime,   default=datetime.utcnow)
    updated_at          = db.Column(db.DateTime,   default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships (no order_by so .delete() works)
    items = db.relationship('GrnItem',
                            backref='grn',
                            lazy='dynamic',
                            cascade='all, delete-orphan')
    status_logs = db.relationship('GrnStatusLog',
                                  backref='grn',
                                  lazy='dynamic',
                                  cascade='all, delete-orphan')
    approval_logs = db.relationship('GrnApprovalLog',
                                    backref='grn',
                                    lazy='dynamic',
                                    cascade='all, delete-orphan')

    @property
    def is_editable(self):
        """Editable in Draft only (no approval workflow)."""
        return (self.status == GRN_STATUS_DRAFT and not self.is_locked)

    @property
    def can_complete(self):
        """Can submit/complete from Draft only."""
        return self.status == GRN_STATUS_DRAFT

    @property
    def can_cancel(self):
        return self.status not in (GRN_STATUS_CANCEL,)

    @property
    def status_color(self):
        return GRN_STATUS_COLORS.get(self.status, '#6b7280')

    @property
    def grn_type_label(self):
        return GRN_TYPES.get(self.grn_type, self.grn_type)

    def to_dict(self):
        return {
            'id': self.id,
            'grn_number': self.grn_number,
            'grn_number_short': self.grn_number_short,
            'grn_type': self.grn_type,
            'grn_type_label': self.grn_type_label,
            'grn_date': self.grn_date.strftime('%d-%m-%Y') if self.grn_date else '',
            'po_number': self.po_number or '',
            'po_date': self.po_date.strftime('%d-%m-%Y') if self.po_date else '',
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier_name or '',
            'invoice_no': self.invoice_no or '',
            'invoice_date': self.invoice_date.strftime('%d-%m-%Y') if self.invoice_date else '',
            'invoice_file': self.invoice_file or '',
            'total_received_qty': float(self.total_received_qty or 0),
            'total_accepted_qty': float(self.total_accepted_qty or 0),
            'total_rejected_qty': float(self.total_rejected_qty or 0),
            'total_amount': float(self.total_amount or 0),
            'status': self.status,
            'status_color': self.status_color,
            'is_editable': self.is_editable,
            'is_locked': self.is_locked,
            'created_by': self.created_by_name or '',
            'created_at': self.created_at.strftime('%d-%m-%Y %H:%M') if self.created_at else '',
        }


# ═════════════════════════════════════════════════════════════════════════════
# 2. GRN ITEMS
# ═════════════════════════════════════════════════════════════════════════════
class GrnItem(db.Model):
    __tablename__ = 'tbl_grn_items'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    grn_id          = db.Column(db.Integer,
                                db.ForeignKey('tbl_grn_master.id', ondelete='CASCADE'),
                                nullable=False, index=True)
    sr_no           = db.Column(db.Integer, default=1)

    # PO link
    po_item_id      = db.Column(db.Integer, nullable=True, index=True)
    po_number       = db.Column(db.String(60), default='')

    # Item snapshot
    material_id     = db.Column(db.Integer, nullable=True, index=True)
    item_code       = db.Column(db.String(100), default='')
    item_name       = db.Column(db.String(300), nullable=False)
    description     = db.Column(db.Text,        default='')
    category        = db.Column(db.String(200), default='')
    manufacturer    = db.Column(db.String(200), default='')
    hsn_code        = db.Column(db.String(20),  default='')
    uom             = db.Column(db.String(30),  default='KG')

    # Batch
    batch_no        = db.Column(db.String(100), default='', index=True)
    mfg_date        = db.Column(db.Date, nullable=True)
    expiry_date     = db.Column(db.Date, nullable=True)

    # Quantities
    no_of_boxes        = db.Column(db.Integer,       default=0)
    per_box_qty        = db.Column(db.Numeric(14, 3), default=0)
    ordered_qty        = db.Column(db.Numeric(14, 3), default=0)
    already_received_qty = db.Column(db.Numeric(14, 3), default=0)
    remaining_qty      = db.Column(db.Numeric(14, 3), default=0)
    received_qty       = db.Column(db.Numeric(14, 3), default=0)
    accepted_qty       = db.Column(db.Numeric(14, 3), default=0)
    rejected_qty       = db.Column(db.Numeric(14, 3), default=0)

    # Rate
    rate            = db.Column(db.Numeric(14, 4), default=0)
    gst_pct         = db.Column(db.Numeric(5, 2),  default=0)
    amount          = db.Column(db.Numeric(14, 2), default=0)

    # Storage
    storage_location_id   = db.Column(db.Integer, nullable=True)
    storage_location_name = db.Column(db.String(150), default='')

    # Quality
    qc_passed        = db.Column(db.Boolean, default=True)
    rejection_reason = db.Column(db.Text, default='')
    remarks          = db.Column(db.Text, default='')

    # Files
    coa_file         = db.Column(db.String(500), default='')
    invoice_file     = db.Column(db.String(500), default='')

    created_at       = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at       = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'sr_no': self.sr_no,
            'po_item_id': self.po_item_id,
            'po_number': self.po_number or '',
            'material_id': self.material_id,
            'item_code': self.item_code or '',
            'item_name': self.item_name or '',
            'manufacturer': self.manufacturer or '',
            'category': self.category or '',
            'hsn_code': self.hsn_code or '',
            'uom': self.uom or 'KG',
            'batch_no': self.batch_no or '',
            'mfg_date': self.mfg_date.strftime('%Y-%m-%d') if self.mfg_date else '',
            'expiry_date': self.expiry_date.strftime('%Y-%m-%d') if self.expiry_date else '',
            'no_of_boxes': int(self.no_of_boxes or 0),
            'per_box_qty': float(self.per_box_qty or 0),
            'ordered_qty': float(self.ordered_qty or 0),
            'already_received_qty': float(self.already_received_qty or 0),
            'remaining_qty': float(self.remaining_qty or 0),
            'received_qty': float(self.received_qty or 0),
            'accepted_qty': float(self.accepted_qty or 0),
            'rejected_qty': float(self.rejected_qty or 0),
            'rate': float(self.rate or 0),
            'gst_pct': float(self.gst_pct or 0),
            'amount': float(self.amount or 0),
            'storage_location_id': self.storage_location_id,
            'storage_location_name': self.storage_location_name or '',
            'qc_passed': self.qc_passed,
            'rejection_reason': self.rejection_reason or '',
            'remarks': self.remarks or '',
            'coa_file': self.coa_file or '',
            'invoice_file': self.invoice_file or '',
        }


# ═════════════════════════════════════════════════════════════════════════════
# 3. STATUS LOG
# ═════════════════════════════════════════════════════════════════════════════
class GrnStatusLog(db.Model):
    __tablename__ = 'tbl_grn_status_logs'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    grn_id      = db.Column(db.Integer,
                            db.ForeignKey('tbl_grn_master.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    from_status = db.Column(db.String(30), default='')
    to_status   = db.Column(db.String(30), default='')
    actor_id    = db.Column(db.Integer,    nullable=True)
    actor_name  = db.Column(db.String(150), default='')
    note        = db.Column(db.Text, default='')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


# ═════════════════════════════════════════════════════════════════════════════
# 4. APPROVAL LOG
# ═════════════════════════════════════════════════════════════════════════════
class GrnApprovalLog(db.Model):
    __tablename__ = 'tbl_grn_approval_logs'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    grn_id      = db.Column(db.Integer,
                            db.ForeignKey('tbl_grn_master.id', ondelete='CASCADE'),
                            nullable=False, index=True)
    level       = db.Column(db.String(50), default='Manager')
    action      = db.Column(db.String(30), default='SUBMITTED')
    actor_id    = db.Column(db.Integer,    nullable=True)
    actor_name  = db.Column(db.String(150), default='')
    actor_role  = db.Column(db.String(80),  default='')
    comment     = db.Column(db.Text, default='')
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)


# ═════════════════════════════════════════════════════════════════════════════
# 5. STOCK LEDGER
# ═════════════════════════════════════════════════════════════════════════════
class GrnStockLedger(db.Model):
    __tablename__ = 'tbl_grn_stock_ledger'

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    txn_date     = db.Column(db.DateTime, default=datetime.utcnow)
    txn_type     = db.Column(db.String(30), default='GRN_IN')
    txn_ref_type = db.Column(db.String(30), default='GRN')
    txn_ref_id   = db.Column(db.Integer, nullable=False, index=True)
    txn_ref_no   = db.Column(db.String(60), default='')

    material_id  = db.Column(db.Integer, nullable=False, index=True)
    item_code    = db.Column(db.String(100), default='')
    item_name    = db.Column(db.String(300), default='')
    batch_no     = db.Column(db.String(100), default='', index=True)

    location_id  = db.Column(db.Integer, nullable=True)
    location_name = db.Column(db.String(150), default='')

    qty_in       = db.Column(db.Numeric(14, 3), default=0)
    qty_out      = db.Column(db.Numeric(14, 3), default=0)
    uom          = db.Column(db.String(30), default='KG')
    rate         = db.Column(db.Numeric(14, 4), default=0)
    amount       = db.Column(db.Numeric(14, 2), default=0)

    remarks      = db.Column(db.Text, default='')
    actor_name   = db.Column(db.String(150), default='')
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)


# ═════════════════════════════════════════════════════════════════════════════
# 6. BATCH STOCK (current state)
# ═════════════════════════════════════════════════════════════════════════════
class GrnBatchStock(db.Model):
    __tablename__ = 'tbl_grn_batch_stock'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    material_id     = db.Column(db.Integer, nullable=False, index=True)
    item_code       = db.Column(db.String(100), default='')
    item_name       = db.Column(db.String(300), default='')
    batch_no        = db.Column(db.String(100), nullable=False, default='')
    location_id     = db.Column(db.Integer, nullable=True)
    location_name   = db.Column(db.String(150), default='')

    mfg_date        = db.Column(db.Date, nullable=True)
    expiry_date     = db.Column(db.Date, nullable=True)

    qty_on_hand     = db.Column(db.Numeric(14, 3), default=0)
    qty_reserved    = db.Column(db.Numeric(14, 3), default=0)
    qty_available   = db.Column(db.Numeric(14, 3), default=0)

    uom             = db.Column(db.String(30),  default='KG')
    avg_rate        = db.Column(db.Numeric(14, 4), default=0)

    last_inward_at  = db.Column(db.DateTime, nullable=True)
    last_outward_at = db.Column(db.DateTime, nullable=True)

    is_qc_hold      = db.Column(db.Boolean, default=False)
    qc_hold_qty     = db.Column(db.Numeric(14, 3), default=0)

    created_at      = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        db.UniqueConstraint('material_id', 'batch_no', 'location_id',
                            name='uq_batch_loc'),
    )
