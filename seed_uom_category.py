"""
seed_uom_category.py
Run: python seed_uom_category.py
UOM Master aur Category Master mein default data add karta hai.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app
from models import db
from models.master import UOMMaster, CategoryMaster

UOM_DATA = [
    ('ml',   'Milliliter'),
    ('L',    'Liter'),
    ('g',    'Gram'),
    ('kg',   'Kilogram'),
    ('mg',   'Milligram'),
    ('pcs',  'Pieces'),
    ('nos',  'Numbers'),
    ('box',  'Box'),
    ('pkt',  'Packet'),
    ('btl',  'Bottle'),
    ('tube', 'Tube'),
    ('sachet','Sachet'),
    ('strip','Strip'),
    ('vial', 'Vial'),
    ('pouch','Pouch'),
]

CATEGORY_DATA = [
    'Skin Care',
    'Hair Care',
    'Body Care',
    'Oral Care',
    'Baby Care',
    'Eye Care',
    'Cosmetics',
    'Pharma - OTC',
    'Pharma - Prescription',
    'Nutraceutical',
    'Food Supplement',
    'Veterinary',
    'Ayurvedic / Herbal',
    'Industrial',
]

with app.app_context():
    added_uom = 0
    for i, (code, name) in enumerate(UOM_DATA, 1):
        if not UOMMaster.query.filter_by(code=code).first():
            db.session.add(UOMMaster(
                code=code, name=name,
                status=True, is_deleted=False
            ))
            added_uom += 1

    added_cat = 0
    for i, name in enumerate(CATEGORY_DATA, 1):
        if not CategoryMaster.query.filter_by(name=name).first():
            db.session.add(CategoryMaster(
                name=name,
                status=True, is_deleted=False
            ))
            added_cat += 1

    db.session.commit()
    print(f"✅ UOM: {added_uom} added | Category: {added_cat} added")
    print("Done! Refresh Masters page to see the data.")
