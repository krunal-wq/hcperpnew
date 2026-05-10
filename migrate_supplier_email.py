from index import app
from models import db
from sqlalchemy import text, inspect
with app.app_context():
    cols = [c['name'] for c in inspect(db.engine).get_columns('suppliers')]
    if 'email_list' not in cols:
        db.session.execute(text("ALTER TABLE suppliers ADD COLUMN email_list TEXT NULL"))
        db.session.commit()
        print("✅ email_list column added!")
    else:
        print("✔️  Already exists")
