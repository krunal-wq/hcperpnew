"""
Migration: Add RDTestParameter table for Test Parameter Master
Run: python migrate_rd_parameters.py
"""

from app import app, db  # adjust import as per your project structure

# ── Model Definition ──────────────────────────────────────────────────────────
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, Text, ForeignKey
from datetime import datetime

class RDTestParameter(db.Model):
    __tablename__ = 'rd_test_parameters'

    id           = Column(Integer, primary_key=True)
    name         = Column(String(120), nullable=False)          # e.g. "Appearance"
    default_val  = Column(String(200), default='')              # default result value
    unit         = Column(String(50),  default='')              # e.g. "cP", "mPa·s"
    sort_order   = Column(Integer,     default=0)               # display order
    is_active    = Column(Boolean,     default=True)            # soft-disable
    created_at   = Column(DateTime,    default=datetime.utcnow)
    updated_at   = Column(DateTime,    default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id':          self.id,
            'name':        self.name,
            'default_val': self.default_val or '',
            'unit':        self.unit or '',
            'sort_order':  self.sort_order,
            'is_active':   self.is_active,
        }

# ── Default seed data ─────────────────────────────────────────────────────────
DEFAULT_PARAMETERS = [
    {'name': 'Appearance',    'default_val': '',               'unit': '',      'sort_order': 1},
    {'name': 'Color',         'default_val': '',               'unit': '',      'sort_order': 2},
    {'name': 'Odour',         'default_val': '',               'unit': '',      'sort_order': 3},
    {'name': 'Transparency',  'default_val': '',               'unit': '',      'sort_order': 4},
    {'name': 'pH',            'default_val': '',               'unit': '',      'sort_order': 5},
    {'name': 'Viscosity',     'default_val': '',               'unit': 'cP',    'sort_order': 6},
    {'name': 'Spindle No.',   'default_val': '',               'unit': '',      'sort_order': 7},
    {'name': 'RPM',           'default_val': '',               'unit': 'rpm',   'sort_order': 8},
]

# ── Migration runner ──────────────────────────────────────────────────────────
def run_migration():
    with app.app_context():
        # 1. Create table if not exists
        db.create_all()
        print("✅ Table 'rd_test_parameters' created (or already exists)")

        # 2. Seed default parameters only if table is empty
        existing = RDTestParameter.query.count()
        if existing == 0:
            for p in DEFAULT_PARAMETERS:
                db.session.add(RDTestParameter(**p))
            db.session.commit()
            print(f"✅ Seeded {len(DEFAULT_PARAMETERS)} default parameters")
        else:
            print(f"ℹ️  Table already has {existing} parameters — skipping seed")

        # 3. Show current state
        params = RDTestParameter.query.order_by(RDTestParameter.sort_order).all()
        print("\n📋 Current Parameters:")
        for p in params:
            status = "✅" if p.is_active else "❌"
            print(f"  {status} [{p.sort_order}] {p.name:<20} unit={p.unit or '—':<8} default={p.default_val or '—'}")

if __name__ == '__main__':
    run_migration()
