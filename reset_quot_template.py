"""
reset_quot_template.py
Run: python reset_quot_template.py
Quotation email template DB se delete karta hai — 
next mail send par fresh template auto-create hogi.
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app
from models import db, EmailTemplate

with app.app_context():
    t = EmailTemplate.query.filter_by(code='quotation').first()
    if t:
        db.session.delete(t)
        db.session.commit()
        print("✅ Quotation template deleted — fresh template will be created on next mail send")
    else:
        print("ℹ️ No quotation template found in DB")
