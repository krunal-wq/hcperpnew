from index import app
from models import db
from sqlalchemy import text, inspect
with app.app_context():
    cols = [c['name'] for c in inspect(db.engine).get_columns('materials')]
    for col, defn in [('pm_attribute',"VARCHAR(300) DEFAULT ''"), ('pm_material_type',"VARCHAR(20) DEFAULT ''")]:
        if col not in cols:
            db.session.execute(text(f"ALTER TABLE materials ADD COLUMN {col} {defn}"))
            db.session.commit()
            print(f"✅ {col} added")
        else:
            print(f"✔️  {col} exists")
    print("\n🎉 Done!")
