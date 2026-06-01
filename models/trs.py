"""
models/trs.py — Testing Requisition Slip (TRS)
"""

from datetime import datetime, date
from models import db


# ── Dropdown choice lists ─────────────────────────────────────────────
PHYSICAL_STATES = [
    'Solid', 'Liquid', 'Powder', 'Flakes',
    'Granules', 'Crystals', 'Pellets', 'Paste', 'Other',
]

APPEARANCES = [
    'White', 'Off-white', 'Yellow', 'Pale-yellow',
    'Brown', 'Colourless', 'Flakes', 'Powder',
    'Crystals', 'Liquid', 'Other',
]

ODOURS = [
    'Pleasant', 'Odourless', 'Pungent',
    'Characteristic', 'Aromatic', 'Mild', 'Strong', 'Other',
]

NEW_OLD = ['NEW', 'OLD']
YES_NO  = ['YES', 'NO']

# ── QC Status workflow (Phase 3) ──────────────────────────────────────
QC_STATUS_PENDING        = 'Pending'
QC_STATUS_UNDER_TESTING  = 'Under Testing'
QC_STATUS_APPROVED       = 'Approved'
QC_STATUS_REJECTED       = 'Rejected'
QC_STATUS_HOLD           = 'Hold'

QC_STATUSES = [
    QC_STATUS_PENDING,
    QC_STATUS_UNDER_TESTING,
    QC_STATUS_APPROVED,
    QC_STATUS_REJECTED,
    QC_STATUS_HOLD,
]


class TrsMaster(db.Model):
    """One TRS row per GRN-item."""
    __tablename__ = 'tbl_trs_master'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Numbering — TRS No is GRN_no/item_seq  (e.g. RM/0468/26-27/1)
    trs_no          = db.Column(db.String(80),  unique=True, nullable=False, index=True)
    trs_date        = db.Column(db.Date,        nullable=False, default=date.today)

    # Source GRN + Item
    grn_id          = db.Column(db.Integer,     nullable=False, index=True)
    grn_no          = db.Column(db.String(60),  default='')
    grn_date        = db.Column(db.Date,        nullable=True)
    grn_item_id     = db.Column(db.Integer,     nullable=False, index=True)
    item_seq        = db.Column(db.Integer,     default=1)

    department      = db.Column(db.String(100), default='R M STORE')

    # Sample info
    sample_name     = db.Column(db.String(300), default='')
    batch_no        = db.Column(db.String(100), default='')
    no_of_packets   = db.Column(db.Numeric(14, 3), default=0)
    total_qty       = db.Column(db.Numeric(14, 3), default=0)
    uom             = db.Column(db.String(20),  default='KG')

    # User-captured
    physical_state  = db.Column(db.String(50),  default='')
    sample_qty      = db.Column(db.Numeric(14, 3), default=0)

    # Manufacturer / supplier
    mfg_name        = db.Column(db.String(200), default='')
    mfg_date        = db.Column(db.Date,        nullable=True)
    supplier_name   = db.Column(db.String(200), default='')
    expiry_date     = db.Column(db.Date,        nullable=True)

    previous_supplier = db.Column(db.String(200), default='')
    new_old_material  = db.Column(db.String(10),  default='OLD')

    # Physical verification
    appearance      = db.Column(db.String(50),  default='')
    odour           = db.Column(db.String(50),  default='')
    coa_available   = db.Column(db.String(5),   default='NO')

    # Verification audit
    verified_by_id   = db.Column(db.Integer,    nullable=True)
    verified_by_name = db.Column(db.String(150), default='')
    verified_at      = db.Column(db.DateTime,   nullable=True)

    # ─── PHASE 3: QC Status workflow ──────────────────────────────────
    qc_status            = db.Column(db.String(30),  default=QC_STATUS_PENDING, index=True)
    qc_remarks           = db.Column(db.Text,        default='')
    qc_approved_at       = db.Column(db.DateTime,    nullable=True)
    qc_approved_by_id    = db.Column(db.Integer,     nullable=True)
    qc_approved_by_name  = db.Column(db.String(150), default='')
    qc_rejected_at       = db.Column(db.DateTime,    nullable=True)
    qc_rejected_by_name  = db.Column(db.String(150), default='')
    # Tracks whether the Approve action's stock-impact has been applied
    # (so re-clicking Approve does not double-stock; reject can reverse it).
    stock_impact_applied = db.Column(db.Boolean,     default=False, nullable=False)
    stock_ledger_ref     = db.Column(db.Integer,     nullable=True)

    # Standard audit
    is_deleted      = db.Column(db.Boolean,     default=False)
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime,    default=datetime.utcnow,
                                onupdate=datetime.utcnow)
    created_by_id   = db.Column(db.Integer,     nullable=True)
    created_by_name = db.Column(db.String(150), default='')
    updated_by_name = db.Column(db.String(150), default='')

    def to_dict(self):
        return {
            'id': self.id,
            'trs_no': self.trs_no,
            'trs_date': self.trs_date.strftime('%Y-%m-%d') if self.trs_date else '',
            'grn_id': self.grn_id,
            'grn_no': self.grn_no,
            'grn_item_id': self.grn_item_id,
            'item_seq': self.item_seq,
            'department': self.department or '',
            'sample_name': self.sample_name or '',
            'batch_no': self.batch_no or '',
            'no_of_packets': float(self.no_of_packets or 0),
            'total_qty': float(self.total_qty or 0),
            'uom': self.uom or '',
            'physical_state': self.physical_state or '',
            'sample_qty': float(self.sample_qty or 0),
            'mfg_name': self.mfg_name or '',
            'mfg_date': self.mfg_date.strftime('%Y-%m-%d') if self.mfg_date else '',
            'supplier_name': self.supplier_name or '',
            'expiry_date': self.expiry_date.strftime('%Y-%m-%d') if self.expiry_date else '',
            'previous_supplier': self.previous_supplier or '',
            'new_old_material': self.new_old_material or 'OLD',
            'appearance': self.appearance or '',
            'odour': self.odour or '',
            'coa_available': self.coa_available or 'NO',
            'verified_by_name': self.verified_by_name or '',
            'verified_at': self.verified_at.strftime('%Y-%m-%d %H:%M') if self.verified_at else '',
            'qc_status': self.qc_status or QC_STATUS_PENDING,
            'qc_remarks': self.qc_remarks or '',
            'qc_approved_at': self.qc_approved_at.strftime('%Y-%m-%d %H:%M') if self.qc_approved_at else '',
            'qc_approved_by_name': self.qc_approved_by_name or '',
            'qc_rejected_at': self.qc_rejected_at.strftime('%Y-%m-%d %H:%M') if self.qc_rejected_at else '',
            'qc_rejected_by_name': self.qc_rejected_by_name or '',
            'stock_impact_applied': bool(self.stock_impact_applied),
        }


class QcStatusHistory(db.Model):
    """Audit trail of every QC status change."""
    __tablename__ = 'tbl_qc_status_history'

    id            = db.Column(db.Integer, primary_key=True, autoincrement=True)
    trs_id        = db.Column(db.Integer, nullable=False, index=True)
    from_status   = db.Column(db.String(30), default='')
    to_status     = db.Column(db.String(30), nullable=False)
    remarks       = db.Column(db.Text, default='')
    actor_id      = db.Column(db.Integer, nullable=True)
    actor_name    = db.Column(db.String(150), default='')
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    # Stock impact tracking (informational)
    stock_action  = db.Column(db.String(20), default='')   # 'stock_in' / 'sample_out' / 'reverse'
    stock_qty     = db.Column(db.Numeric(14, 3), default=0)
