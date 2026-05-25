"""
models/formulation.py
─────────────────────
Formulation Master under Raw Material.

Two tables:
    • formulations             ─ one row per batch / recipe
    • formulation_ingredients  ─ ingredient lines (child rows)

"Link to Existing":
    A linked formulation has `source_id` pointing to another formulation.
    Linked rows do NOT store their own ingredients — they read from the
    source.  Edits to the source therefore propagate automatically to
    every linked batch.  The linked row still keeps its own batch size,
    product code, brand, name and manufacturing process.
"""
from datetime import datetime
from .base import db


class Formulation(db.Model):
    __tablename__ = 'formulations'

    id                    = db.Column(db.Integer, primary_key=True, autoincrement=True)

    # ── Identity ──────────────────────────────────────────────────
    name                  = db.Column(db.String(300), nullable=False)   # "BEARDO DE TAN FACE WASH"
    product_code          = db.Column(db.String(100), default='', nullable=True)
    batch_size            = db.Column(db.Numeric(14, 3), default=0)     # KG
    batch_uom             = db.Column(db.String(20),  default='KG')

    # ── Branding / Categorisation ─────────────────────────────────
    brand                 = db.Column(db.String(200), default='', nullable=True)

    # ── Production ────────────────────────────────────────────────
    manufacturing_process = db.Column(db.Text, nullable=True)           # printed on production sheet
    specifications        = db.Column(db.Text, nullable=True)           # QC specs (Appearance/Colour/pH/etc.)

    # ── Link-to-existing source (NULL for standalone) ─────────────
    source_id             = db.Column(db.Integer,
                                      db.ForeignKey('formulations.id'),
                                      nullable=True)
    source                = db.relationship('Formulation',
                                            remote_side=[id],
                                            backref='linked_formulations',
                                            foreign_keys=[source_id])

    # ── Audit / soft delete ───────────────────────────────────────
    is_active             = db.Column(db.Boolean, default=True)
    is_deleted            = db.Column(db.Boolean, default=False)
    deleted_at            = db.Column(db.DateTime, nullable=True)

    created_by            = db.Column(db.String(100), default='')
    updated_by            = db.Column(db.String(100), default='')
    created_at            = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at            = db.Column(db.DateTime, default=datetime.utcnow,
                                                   onupdate=datetime.utcnow)

    # Own ingredients (only used when source_id is NULL)
    ingredients           = db.relationship(
        'FormulationIngredient',
        backref='formulation',
        cascade='all, delete-orphan',
        order_by='FormulationIngredient.sr_no',
        lazy='dynamic',
    )

    # ── Helpers ───────────────────────────────────────────────────
    @property
    def is_linked(self):
        return self.source_id is not None

    def resolved_ingredients(self):
        """Always returns the row that actually owns the ingredients —
        the source if linked, else self."""
        if self.source_id and self.source and not self.source.is_deleted:
            return self.source.ingredients.all()
        return self.ingredients.all()

    def resolved_source(self):
        """Return the formulation row that owns the ingredients."""
        if self.source_id and self.source and not self.source.is_deleted:
            return self.source
        return self

    def ingredient_count(self):
        return len(self.resolved_ingredients())

    def to_dict(self, include_ingredients=False):
        d = {
            'id'                   : self.id,
            'name'                 : self.name,
            'product_code'         : self.product_code or '',
            'batch_size'           : float(self.batch_size or 0),
            'batch_uom'            : self.batch_uom or 'KG',
            'brand'                : self.brand or '',
            'manufacturing_process': self.manufacturing_process or '',
            'specifications'       : self.specifications or '',
            'source_id'            : self.source_id,
            'source_name'          : (self.source.name if self.source else ''),
            'is_linked'            : self.is_linked,
            'is_active'            : self.is_active,
            'is_deleted'           : self.is_deleted,
            'ingredient_count'     : self.ingredient_count(),
            'created_by'           : self.created_by or '',
            'updated_by'           : self.updated_by or '',
            'created_at'           : self.created_at.strftime('%d-%m-%Y %H:%M')
                                       if self.created_at else '',
            'updated_at'           : self.updated_at.strftime('%d-%m-%Y %H:%M')
                                       if self.updated_at else '',
        }
        if include_ingredients:
            d['ingredients']          = [i.to_dict() for i in self.resolved_ingredients()]
            d['ingredients_owned_by'] = self.resolved_source().id
        return d


class FormulationIngredient(db.Model):
    __tablename__ = 'formulation_ingredients'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    formulation_id  = db.Column(db.Integer,
                                db.ForeignKey('formulations.id', ondelete='CASCADE'),
                                nullable=False, index=True)

    sr_no           = db.Column(db.Integer, default=0)
    ingredient_name = db.Column(db.String(300), nullable=False)
    supplier_name   = db.Column(db.String(300), default='')

    percentage      = db.Column(db.Numeric(14, 6), default=0)   # % w/w (decimal 0–1 or 0–100, we store as-given)
    qty_kg          = db.Column(db.Numeric(14, 6), default=0)   # absolute qty for the batch

    # ── New: per-row UOM, cost & additional flag ──────────────────
    uom              = db.Column(db.String(20),     default='KG')
    is_additional    = db.Column(db.Boolean,        default=False)
    rm_rate_per_kg   = db.Column(db.Numeric(14, 4), default=0)   # ₹/kg raw material cost
    bulk_rate_per_kg = db.Column(db.Numeric(14, 4), default=0)   # contribution to bulk cost (₹/kg of finished bulk)

    # Optional FK to Material master (RM)
    material_id     = db.Column(db.Integer, db.ForeignKey('materials.id'), nullable=True)
    material        = db.relationship('Material', lazy=True)

    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'id'              : self.id,
            'formulation_id'  : self.formulation_id,
            'sr_no'           : self.sr_no or 0,
            'ingredient_name' : self.ingredient_name or '',
            'supplier_name'   : self.supplier_name or '',
            'percentage'      : float(self.percentage or 0),
            'qty_kg'          : float(self.qty_kg or 0),
            'uom'             : self.uom or 'KG',
            'is_additional'   : bool(self.is_additional),
            'rm_rate_per_kg'  : float(self.rm_rate_per_kg or 0),
            'bulk_rate_per_kg': float(self.bulk_rate_per_kg or 0),
            'material_id'     : self.material_id,
        }
