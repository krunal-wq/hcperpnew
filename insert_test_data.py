"""
NPD Sample Ready — Test Data Script
====================================
Run karo: python insert_test_data.py

Yeh script 5 NPD projects banayega with status='sample_ready'
Testing ke liye.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, date, timedelta

try:
    from index import app
    from models import db, NPDProject, User
    print("✅ App imported")
except Exception as e:
    print(f"❌ Import error: {e}")
    sys.exit(1)

TEST_PROJECTS = [
    {
        "code"             : "NPD-TEST-01",
        "product_name"     : "Vitamin C Face Serum",
        "client_name"      : "John Doe",
        "client_company"   : "ABC Corp",
        "product_category" : "Skin Care",
        "area_of_application": "Face",
        "priority"         : "High",
        "reference_brand"  : "Minimalist",
        "project_start_date": date.today() - timedelta(days=10),
        "target_sample_date": date.today() + timedelta(days=5),
        "no_of_samples"    : 3,
        "moq"              : "5000 units",
        "product_size"     : "30ml",
        "description"      : "Brightening face serum with 15% Vitamin C",
        "npd_fee_paid"     : True,
        "npd_fee_amount"   : 10000,
    },
    {
        "code"             : "NPD-TEST-02",
        "product_name"     : "Hyaluronic Acid Moisturizer",
        "client_name"      : "Priya Shah",
        "client_company"   : "Glow Beauty",
        "product_category" : "Skin Care",
        "area_of_application": "Face",
        "priority"         : "Urgent",
        "reference_brand"  : "Dot & Key",
        "project_start_date": date.today() - timedelta(days=15),
        "target_sample_date": date.today() + timedelta(days=3),
        "no_of_samples"    : 2,
        "moq"              : "10000 units",
        "product_size"     : "50ml",
        "description"      : "Deep hydrating moisturizer with HA complex",
        "npd_fee_paid"     : True,
        "npd_fee_amount"   : 10000,
    },
    {
        "code"             : "NPD-TEST-03",
        "product_name"     : "Keratin Hair Shampoo",
        "client_name"      : "Raj Patel",
        "client_company"   : "HairCare India",
        "product_category" : "Hair Care",
        "area_of_application": "Hair",
        "priority"         : "Normal",
        "reference_brand"  : "Mamaearth",
        "project_start_date": date.today() - timedelta(days=20),
        "target_sample_date": date.today() + timedelta(days=7),
        "no_of_samples"    : 2,
        "moq"              : "20000 units",
        "product_size"     : "200ml",
        "description"      : "Sulfate-free keratin shampoo for frizzy hair",
        "npd_fee_paid"     : False,
        "npd_fee_amount"   : 10000,
    },
    {
        "code"             : "NPD-TEST-04",
        "product_name"     : "SPF 50 Sunscreen Lotion",
        "client_name"      : "Meera Joshi",
        "client_company"   : "SunSafe Ltd",
        "product_category" : "Sun Care",
        "area_of_application": "Face & Body",
        "priority"         : "High",
        "reference_brand"  : "Re'equil",
        "project_start_date": date.today() - timedelta(days=8),
        "target_sample_date": date.today() + timedelta(days=10),
        "no_of_samples"    : 4,
        "moq"              : "15000 units",
        "product_size"     : "100ml",
        "description"      : "Broad spectrum SPF 50 PA++++ sunscreen",
        "npd_fee_paid"     : True,
        "npd_fee_amount"   : 10000,
    },
    {
        "code"             : "NPD-TEST-05",
        "product_name"     : "Niacinamide Body Lotion",
        "client_name"      : "Arjun Mehta",
        "client_company"   : "DermaCare",
        "product_category" : "Body Care",
        "area_of_application": "Body",
        "priority"         : "Normal",
        "reference_brand"  : "Pilgrim",
        "project_start_date": date.today() - timedelta(days=5),
        "target_sample_date": date.today() + timedelta(days=14),
        "no_of_samples"    : 2,
        "moq"              : "8000 units",
        "product_size"     : "250ml",
        "description"      : "10% Niacinamide body lotion for even skin tone",
        "npd_fee_paid"     : True,
        "npd_fee_amount"   : 10000,
    },
]

with app.app_context():
    # Get first admin/user
    admin = User.query.filter_by(role='admin').first() or User.query.first()
    if not admin:
        print("❌ Koi user nahi mila DB mein. Pehle migrate.py run karo.")
        sys.exit(1)

    print(f"  Using user: {admin.full_name} (id={admin.id})")
    created = 0
    skipped = 0

    for td in TEST_PROJECTS:
        # Already exists?
        existing = NPDProject.query.filter_by(code=td['code']).first()
        if existing:
            # Sirf status update karo sample_ready mein
            existing.status = 'sample_ready'
            db.session.commit()
            print(f"  ↺  {td['code']} already exists — status → sample_ready")
            skipped += 1
            continue

        # First employee ko RD member banao
        from models.employee import Employee
        first_emp = Employee.query.filter_by(is_deleted=False).first()
        rd_emp_id = str(first_emp.id) if first_emp else ''

        proj = NPDProject(
            code                = td['code'],
            project_type        = 'npd',
            status              = 'sample_ready',
            product_name        = td['product_name'],
            client_name         = td['client_name'],
            client_company      = td['client_company'],
            product_category    = td['product_category'],
            area_of_application = td['area_of_application'],
            priority            = td['priority'],
            reference_brand     = td['reference_brand'],
            project_start_date  = td['project_start_date'],
            target_sample_date  = td['target_sample_date'],
            no_of_samples       = td['no_of_samples'],
            moq                 = td['moq'],
            product_size        = td['product_size'],
            description         = td['description'],
            npd_fee_paid        = td['npd_fee_paid'],
            npd_fee_amount      = td['npd_fee_amount'],
            assigned_members    = str(admin.id),
            assigned_sc         = admin.id,
            assigned_rd_members = rd_emp_id,
            started_at          = datetime.now(),
            created_at          = datetime.now(),
        )
        db.session.add(proj)
        db.session.commit()
        print(f"  ✅ Created: {td['code']} — {td['product_name']} ({td['client_name']})")
        created += 1

    print(f"\n{'='*50}")
    print(f"  Done! Created: {created}  |  Updated: {skipped}")
    print(f"  Ab /npd/sample-ready kholo — 5 projects dikhenge")
    print(f"{'='*50}\n")
