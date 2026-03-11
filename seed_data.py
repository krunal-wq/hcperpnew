"""
Dummy Data Seeder — Run once: python seed_data.py
Adds 30 leads + 8 clients with realistic data so all dashboard graphs populate
"""
import sys, os
sys.path.insert(0, os.path.dirname(__file__))

from index import app
from models import db, User, ClientMaster, ClientBrand, Lead
from datetime import datetime, timedelta
import random

SOURCES  = ['HCP Website','India Mart','Just Dial','Referral','Cold Call','Exhibition','Social Media','WhatsApp','Trade India','Pharma Hopper']
STATUSES = ['open','in_process','close','cancel']
STAT_W   = [8, 8, 9, 5]
CATS     = ['Skin Care','Hair Care','Body Care','Oral Care','Baby Care','Cosmetics','Pharmaceuticals']
RANGES   = ['Economy','Standard','Premium','Luxury']
CITIES   = ['Mumbai','Delhi','Ahmedabad','Pune','Surat','Bangalore','Chennai','Hyderabad','Jaipur','Kolkata']
STATES   = ['Maharashtra','Delhi','Gujarat','Karnataka','Rajasthan','Tamil Nadu','Telangana','West Bengal']
PRODUCTS = ['Face Cream','Hair Oil','Body Lotion','Shampoo','Conditioner','Serum','Gel','Tablet','Syrup','Baby Wash','Toothpaste','Lip Balm','Sunscreen','Moisturizer']
COMPANIES= ['Glowveda Pharma','NatureCure Labs','SkinBliss Corp','HairLux Industries','PureLife Healthcare',
            'AyuMed Formulations','MedGlow Solutions','BioHerb Labs','VitalCare Pvt Ltd','Radiance Pharma',
            'HerbSync Corp','CosmoVeda Ltd','PharmaPlus Inc','SkinRite Solutions','HealthFirst Labs']
NAMES    = ['Rajesh Kumar','Priya Sharma','Amit Patel','Sunita Verma','Rohit Singh','Meena Joshi',
            'Vikram Chauhan','Anita Desai','Suresh Mehta','Pooja Nair','Deepak Gupta','Kavita Shah',
            'Manish Agarwal','Rekha Pillai','Ajay Tiwari','Neha Srivastava','Arun Mishra','Smita Jain',
            'Kiran Bhat','Rahul Yadav','Sanjay Dubey','Geeta Singh','Mohit Sharma','Divya Kapoor']

def rand_date(days_ago_max=180):
    delta = random.randint(1, days_ago_max)
    return datetime.utcnow() - timedelta(days=delta)

def seed():
    with app.app_context():
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            print("❌ No admin user found. Run http://localhost:5000/setup first.")
            return

        # ── CLIENTS ──────────────────────────────────────────────
        existing_clients = ClientMaster.query.count()
        if existing_clients < 5:
            print("Adding clients...")
            clients_data = [
                ('Rajesh Kumar',   'Glowveda Pharma',    'Mumbai',    'Maharashtra', 'regular',     [('GlowVeda Face Cream','Skin Care'),('GlowVeda SPF50','Cosmetics')]),
                ('Priya Sharma',   'NatureCure Labs',    'Delhi',     'Delhi',       'vip',         [('NatHair Oil','Hair Care'),('NatHair Serum','Hair Care')]),
                ('Amit Patel',     'SkinBliss Corp',     'Ahmedabad', 'Gujarat',     'dealer',      [('SkinBliss Lotion','Skin Care')]),
                ('Sunita Verma',   'HairLux Industries', 'Pune',      'Maharashtra', 'regular',     [('HairLux Shampoo','Hair Care'),('HairLux Conditioner','Hair Care')]),
                ('Vikram Chauhan', 'PureLife Healthcare','Bangalore', 'Karnataka',   'vip',         [('PureLife Baby Wash','Baby Care'),('PureLife Powder','Baby Care')]),
                ('Meena Joshi',    'AyuMed Formulations','Surat',     'Gujarat',     'regular',     [('AyuMed Tablets','Pharmaceuticals')]),
                ('Rohit Singh',    'MedGlow Solutions',  'Chennai',   'Tamil Nadu',  'dealer',      [('MedGlow Gel','Skin Care'),('MedGlow Cream','Cosmetics')]),
                ('Anita Desai',    'BioHerb Labs',       'Hyderabad', 'Telangana',   'distributor', [('BioHerb Extract','Pharmaceuticals'),('BioHerb Syrup','Body Care')]),
            ]
            for i,(cname, company, city, state, ctype, brands) in enumerate(clients_data):
                c = ClientMaster(
                    code         = f'CLT{100+i}',
                    contact_name = cname,
                    company_name = company,
                    mobile       = f'98{random.randint(10000000,99999999)}',
                    email        = f'contact@{company.lower().replace(" ","")}.com',
                    city=city, state=state, country='India',
                    client_type=ctype, status='active',
                    created_by=admin.id,
                    created_at=rand_date(365),
                )
                db.session.add(c)
                db.session.flush()
                for bname, bcat in brands:
                    db.session.add(ClientBrand(client_id=c.id, brand_name=bname, category=bcat, is_active=True))
            db.session.commit()
            print(f"  ✅ Added 8 clients")
        else:
            print(f"  ℹ️  Clients already exist ({existing_clients}), skipping")

        # ── LEADS ────────────────────────────────────────────────
        existing_leads = Lead.query.count()
        if existing_leads < 10:
            print("Adding leads...")
            all_clients = ClientMaster.query.all()
            count = 0
            for i in range(30):
                name     = random.choice(NAMES)
                company  = random.choice(COMPANIES)
                source   = random.choice(SOURCES)
                status   = random.choices(STATUSES, weights=STAT_W, k=1)[0]
                cat      = random.choice(CATS)
                prange   = random.choice(RANGES)
                city     = random.choice(CITIES)
                state    = random.choice(STATES)
                product  = f'{random.choice(PRODUCTS)} ({cat})'
                cdate    = rand_date(180)
                client   = random.choice(all_clients) if all_clients and random.random() > 0.4 else None

                # Build all fields — use direct DB column names
                lead_data = {
                    'contact_name':     name,
                    'title':            f'{product} Requirement',   # ← this was missing!
                    'phone':            f'9{random.randint(100000000,999999999)}',
                    'email':            f'{name.split()[0].lower()}.{i}@{company.lower().replace(" ","")[:12]}.com',
                    'company_name':     company,
                    'position':         random.choice(['Purchase Manager','CEO','MD','Director','Procurement Head','Owner','Partner']),
                    'city':             city,
                    'state':            state,
                    'country':          'India',
                    'source':           source,
                    'status':           status,
                    'priority':         random.choice(['low','medium','high']),
                    'category':         cat,
                    'product_range':    prange,
                    'product_name':     product,
                    'order_quantity':   f'{random.choice([500,1000,2000,5000,10000])} units',
                    'requirement_spec': f'Require {prange.lower()} range {cat.lower()}. GMP certified preferred. Packaging: {random.choice(["50ml","100ml","200ml","500gm","1kg"])}.',
                    'remark':           random.choice(['Urgent','Budget approved','Need samples','Follow up next week','Good prospect','']),
                    'average_cost':     round(random.uniform(50, 2000), 2),
                    'tags':             random.choice(['premium','bulk','urgent','sample','referral','']),
                    'created_at':       cdate,
                    'last_contact':     cdate + timedelta(days=random.randint(0, 10)),
                    'client_id':        client.id if client else None,
                }
                if status == 'cancel':
                    lead_data['lost_reason'] = random.choice(['Price too high','Went to competitor','No budget','Not interested','Quality mismatch'])

                l = Lead(**lead_data)
                db.session.add(l)
                count += 1

            db.session.commit()
            print(f"  ✅ Added {count} leads")

            # Print breakdown
            for s in STATUSES:
                c = Lead.query.filter_by(status=s).count()
                print(f"     {s:12}: {c}")
        else:
            print(f"  ℹ️  Leads already exist ({existing_leads}), skipping")
            print("     To re-seed, delete existing leads from DB first.")

        print(f"\n✅ Done! Leads: {Lead.query.count()}, Clients: {ClientMaster.query.count()}")
        print("   Now open http://localhost:5000/crm/dashboard to see charts!")

if __name__ == '__main__':
    seed()
