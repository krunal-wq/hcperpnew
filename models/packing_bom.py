"""
models/packing_bom.py
─────────────────────
Packing Material BOM master.

One BOM row per FG (unique fg_material_id).  Each BOM lists the
packing materials (from PM / Corrugation / Sleeves) needed to pack a
given quantity of the finished good.

    PackingBOM   ──┐
                   ├─ owns ─→  PackingBOMItem  (one row per line item)
"""
from datetime import datetime
from .base import db


class PackingBOM(db.Model):
    __tablename__ = 'packing_boms'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # The FG this BOM applies to (one BOM per FG)
    fg_material_id  = db.Column(db.Integer,
                                db.ForeignKey('materials.id'),
                                nullable=False, unique=True, index=True)
    fg              = db.relationship('Material', foreign_keys=[fg_material_id], lazy=True)

    # The qty of FG units this BOM is calibrated for (e.g. 100 boxes)
    fg_qty          = db.Column(db.Numeric(14, 3), default=0)
    fg_uom          = db.Column(db.String(20),     default='PCS')

    notes           = db.Column(db.Text, nullable=True)

    # Soft delete
    is_active       = db.Column(db.Boolean,  default=True)
    is_deleted      = db.Column(db.Boolean,  default=False)
    deleted_at      = db.Column(db.DateTime, nullable=True)

    created_by      = db.Column(db.String(100), default='')
    updated_by      = db.Column(db.String(100), default='')
    created_at      = db.Column(db.DateTime,    default=datetime.utcnow)
    updated_at      = db.Column(db.DateTime,    default=datetime.utcnow,
                                                onupdate=datetime.utcnow)

    items           = db.relationship(
        'PackingBOMItem',
        backref='bom',
        cascade='all, delete-orphan',
        order_by='PackingBOMItem.sr_no',
        lazy='dynamic',
    )

    def item_count(self):
        return self.items.count()

    def to_dict(self, include_items=False):
        d = {
            'id'               : self.id,
            'fg_material_id'   : self.fg_material_id,
            'fg_name'          : self.fg.material_name if self.fg else '',
            'fg_code'          : self.fg.code if self.fg else '',
            'fg_brand'         : self.fg.brand if self.fg else '',
            'fg_image'         : self.fg.image_data if self.fg else '',
            'fg_qty'           : float(self.fg_qty or 0),
            'fg_uom'           : self.fg_uom or 'PCS',
            'notes'            : self.notes or '',
            'is_active'        : self.is_active,
            'is_deleted'       : self.is_deleted,
            'item_count'       : self.item_count(),
            'created_by'       : self.created_by or '',
            'updated_by'       : self.updated_by or '',
            'created_at'       : self.created_at.strftime('%d-%m-%Y %H:%M')
                                   if self.created_at else '',
            'updated_at'       : self.updated_at.strftime('%d-%m-%Y %H:%M')
                                   if self.updated_at else '',
        }
        if include_items:
            d['items'] = [i.to_dict() for i in self.items.all()]
        return d


class PackingBOMItem(db.Model):
    __tablename__ = 'packing_bom_items'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    packing_bom_id  = db.Column(db.Integer,
                                db.ForeignKey('packing_boms.id', ondelete='CASCADE'),
                                nullable=False, index=True)

    sr_no           = db.Column(db.Integer, default=0)

    material_id     = db.Column(db.Integer,
                                db.ForeignKey('materials.id'),
                                nullable=False)
    material        = db.relationship('Material', foreign_keys=[material_id], lazy=True)

    qty             = db.Column(db.Numeric(14, 4), default=0)

    # Snapshot fields (so display works even if the source material's
    # name / UOM later changes)
    item_name_snap  = db.Column(db.String(300), default='')
    uom_snap        = db.Column(db.String(30),  default='')

    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        m = self.material
        return {
            'id'             : self.id,
            'packing_bom_id' : self.packing_bom_id,
            'sr_no'          : self.sr_no or 0,
            'material_id'    : self.material_id,
            'item_name'      : (m.material_name if m else '') or self.item_name_snap,
            'item_code'      : m.code if m else '',
            'category'       : (m.category if m else '') or '',
            'qty'            : float(self.qty or 0),
            'uom'            : (m.uom if m else '') or self.uom_snap or 'PCS',
        }
