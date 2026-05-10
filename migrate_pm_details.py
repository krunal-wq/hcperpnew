from index import app
from models import db
from sqlalchemy import text, inspect
with app.app_context():
    cols = [c['name'] for c in inspect(db.engine).get_columns('materials')]
    new_cols = {
        'corrugation_ply': "VARCHAR(20) DEFAULT ''",
        'dim_length': "DECIMAL(10,2) NULL",
        'dim_width':  "DECIMAL(10,2) NULL",
        'dim_height': "DECIMAL(10,2) NULL",
        'pm_attribute': "VARCHAR(300) DEFAULT ''",
    }
    for col, defn in new_cols.items():
        if col not in cols:
            db.session.execute(text(f"ALTER TABLE materials ADD COLUMN {col} {defn}"))
            db.session.commit()
            print(f"✅ {col} added")
        else:
            print(f"✔️  {col} exists")
    print("\n🎉 Done!")
