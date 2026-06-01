"""
Depreciation Note (DN) Models
═══════════════════════════════════════════════════════════════════════════
Tables:
  1. DepreciationNote      (tbl_depreciation_notes)
  2. DepreciationNoteItem  (tbl_depreciation_note_items)

A DN is auto-created when a GRN is submitted and any item was received in a
lesser physical qty than what the supplier's invoice stated. The DN tracks the
shortage qty and ₹-value so the team can recover from the supplier.
"""
from datetime import datetime, date
from .base import db


# Status constants
DN_STATUS_OPEN     = 'Open'
DN_STATUS_SENT     = 'Sent'
DN_STATUS_RESOLVED = 'Resolved'

DN_STATUSES = [DN_STATUS_OPEN, DN_STATUS_SENT, DN_STATUS_RESOLVED]

DN_STATUS_COLORS = {
    DN_STATUS_OPEN:     '#f59e0b',   # amber
    DN_STATUS_SENT:     '#3b82f6',   # blue
    DN_STATUS_RESOLVED: '#10b981',   # green
}


# ═════════════════════════════════════════════════════════════════════════════
# 1. DEPRECIATION NOTE MASTER
# ═════════════════════════════════════════════════════════════════════════════
class DepreciationNote(db.Model):
    __tablename__ = 'tbl_depreciation_notes'

    id                  = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # Numbering
    dn_number           = db.Column(db.String(60),  nullable=False, unique=True)
    dn_number_short     = db.Column(db.String(60),  default='')
    dn_serial           = db.Column(db.Integer,     default=0)
    dn_fy               = db.Column(db.String(10),  default='')
    dn_year             = db.Column(db.Integer,     default=0)
    dn_date             = db.Column(db.Date,        nullable=False, default=date.today)

    # Source GRN
    grn_id              = db.Column(db.Integer,
                                    db.ForeignKey('tbl_grn_master.id', ondelete='CASCADE'),
                                    nullable=False, index=True)
    grn_number          = db.Column(db.String(60),  default='')
    grn_type            = db.Column(db.String(10),  default='RM')

    # Source PO (may be null for without-PO GRN)
    po_id               = db.Column(db.Integer,     nullable=True)
    po_number           = db.Column(db.String(60),  default='')

    # Supplier snapshot
    supplier_id         = db.Column(db.Integer,     nullable=True, index=True)
    supplier_name       = db.Column(db.String(300), default='')

    # Invoice
    invoice_no          = db.Column(db.String(100), default='')
    invoice_date        = db.Column(db.Date,        nullable=True)

    # Totals
    total_invoice_qty   = db.Column(db.Numeric(14, 3), default=0)
    total_received_qty  = db.Column(db.Numeric(14, 3), default=0)
    total_shortage_qty  = db.Column(db.Numeric(14, 3), default=0)
    total_shortage_value= db.Column(db.Numeric(14, 2), default=0)

    # Status
    status              = db.Column(db.String(30),  nullable=False,
                                    default=DN_STATUS_OPEN, index=True)
    sent_at             = db.Column(db.DateTime,    nullable=True)
    sent_to_email       = db.Column(db.String(255), default='')
    resolved_at         = db.Column(db.DateTime,    nullable=True)
    resolved_by_name    = db.Column(db.String(150), default='')
    resolved_remarks    = db.Column(db.Text,        default='')

    # Files
    pdf_path            = db.Column(db.String(500), default='')

    # Audit
    is_deleted          = db.Column(db.Boolean,     default=False)
    created_by_id       = db.Column(db.Integer,     nullable=True)
    created_by_name     = db.Column(db.String(150), default='')
    created_at          = db.Column(db.DateTime,    default=datetime.utcnow)
    updated_at          = db.Column(db.DateTime,    default=datetime.utcnow,
                                    onupdate=datetime.utcnow)

    # Relationships
    items = db.relationship('DepreciationNoteItem',
                            backref='dn',
                            lazy='dynamic',
                            cascade='all, delete-orphan')

    @property
    def status_color(self):
        return DN_STATUS_COLORS.get(self.status, '#6b7280')

    @property
    def is_editable(self):
        """Only Open DNs can transition; Sent and Resolved are mostly locked."""
        return self.status == DN_STATUS_OPEN

    def to_dict(self):
        return {
            'id': self.id,
            'dn_number': self.dn_number,
            'dn_number_short': self.dn_number_short,
            'dn_date': self.dn_date.strftime('%d-%m-%Y') if self.dn_date else '',
            'grn_id': self.grn_id,
            'grn_number': self.grn_number or '',
            'grn_type': self.grn_type or '',
            'po_number': self.po_number or '',
            'supplier_id': self.supplier_id,
            'supplier_name': self.supplier_name or '',
            'invoice_no': self.invoice_no or '',
            'invoice_date': self.invoice_date.strftime('%d-%m-%Y') if self.invoice_date else '',
            'total_invoice_qty':    float(self.total_invoice_qty    or 0),
            'total_received_qty':   float(self.total_received_qty   or 0),
            'total_shortage_qty':   float(self.total_shortage_qty   or 0),
            'total_shortage_value': float(self.total_shortage_value or 0),
            'status': self.status,
            'status_color': self.status_color,
            'sent_at':     self.sent_at.strftime('%d-%m-%Y %H:%M')     if self.sent_at     else '',
            'resolved_at': self.resolved_at.strftime('%d-%m-%Y %H:%M') if self.resolved_at else '',
            'resolved_remarks': self.resolved_remarks or '',
            'item_count': self.items.count(),
            'created_by': self.created_by_name or '',
            'created_at': self.created_at.strftime('%d-%m-%Y %H:%M') if self.created_at else '',
        }


# ═════════════════════════════════════════════════════════════════════════════
# 2. DEPRECIATION NOTE ITEMS (only the rows that are short)
# ═════════════════════════════════════════════════════════════════════════════
class DepreciationNoteItem(db.Model):
    __tablename__ = 'tbl_depreciation_note_items'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dn_id           = db.Column(db.Integer,
                                db.ForeignKey('tbl_depreciation_notes.id',
                                              ondelete='CASCADE'),
                                nullable=False, index=True)

    # Source GRN line
    grn_item_id     = db.Column(db.Integer, nullable=True, index=True)
    sr_no           = db.Column(db.Integer, default=1)

    # Item snapshot
    material_id     = db.Column(db.Integer,     nullable=True)
    item_code       = db.Column(db.String(100), default='')
    item_name       = db.Column(db.String(300), nullable=False)
    hsn_code        = db.Column(db.String(20),  default='')
    uom             = db.Column(db.String(30),  default='KG')
    batch_no        = db.Column(db.String(100), default='')

    # Quantities
    invoice_qty     = db.Column(db.Numeric(14, 3), default=0)
    received_qty    = db.Column(db.Numeric(14, 3), default=0)
    shortage_qty    = db.Column(db.Numeric(14, 3), default=0)

    # Money
    rate            = db.Column(db.Numeric(14, 4), default=0)
    shortage_value  = db.Column(db.Numeric(14, 2), default=0)

    remarks         = db.Column(db.Text, default='')
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id, 'sr_no': self.sr_no,
            'grn_item_id': self.grn_item_id,
            'material_id': self.material_id,
            'item_code':   self.item_code or '',
            'item_name':   self.item_name or '',
            'hsn_code':    self.hsn_code  or '',
            'uom':         self.uom       or 'KG',
            'batch_no':    self.batch_no  or '',
            'invoice_qty':    float(self.invoice_qty    or 0),
            'received_qty':   float(self.received_qty   or 0),
            'shortage_qty':   float(self.shortage_qty   or 0),
            'rate':           float(self.rate           or 0),
            'shortage_value': float(self.shortage_value or 0),
            'remarks': self.remarks or '',
        }
