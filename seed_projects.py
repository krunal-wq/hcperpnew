"""
seed_projects.py — Dummy NPD & EPD Projects seed karo
Usage: python seed_projects.py
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

G = "\033[92m"; Y = "\033[93m"; R = "\033[91m"; B = "\033[1m"; E = "\033[0m"
def ok(m):   print(f"  {G}✅ {m}{E}")
def warn(m): print(f"  {Y}⚠️  {m}{E}")
def step(m): print(f"\n{B}── {m}{E}")

print(f"\n{'='*55}")
print(f"  {B}DUMMY PROJECT SEED{E}")
print(f"{'='*55}")

try:
    from index import app
    from models import db
except Exception as e:
    print(f"  {R}❌ App load failed: {e}{E}")
    sys.exit(1)

with app.app_context():
    from datetime import datetime, date, timedelta
    from models.npd import NPDProject, MilestoneMaster, NPDMilestoneTemplate

    # Admin user ID
    from models import User
    admin = User.query.filter_by(role='admin').first()
    uid = admin.id if admin else 1

    # Milestone templates
    templates = NPDMilestoneTemplate.query.filter_by(is_active=True)\
                    .order_by(NPDMilestoneTemplate.sort_order).all()

    def add_milestones(proj_id, ptype):
        for tmpl in templates:
            if tmpl.applies_to == 'existing' and ptype == 'npd': continue
            if tmpl.applies_to == 'npd' and ptype == 'existing': continue
            db.session.add(MilestoneMaster(
                project_id=proj_id,
                milestone_type=tmpl.milestone_type,
                title=tmpl.title,
                sort_order=tmpl.sort_order,
                is_selected=tmpl.default_selected,
                status='pending',
                created_by=uid,
            ))

    # ══════════════════════════════════════════════
    # NPD PROJECTS (5 dummy)
    # ══════════════════════════════════════════════
    step("NPD Projects seed kar raha hai...")

    npd_data = [
        {
            'code':             'NPD-0001',
            'project_type':     'npd',
            'status':           'formulation',
            'product_name':     'Vitamin C Face Serum 30ml',
            'product_category': 'Skin Care',
            'product_range':    'Serum',
            'client_name':      'Rahul Sharma',
            'client_company':   'GlowNaturals Pvt. Ltd.',
            'client_email':     'rahul@glownaturals.in',
            'client_phone':     '+91 98765 43210',
            'area_of_application': 'Face',
            'market_level':     'Premium',
            'appearance':       'Clear yellow liquid gel',
            'fragrance':        'Citrus mild',
            'viscosity':        'Low (water-like)',
            'ph_value':         '5.5 - 6.0',
            'priority':         'High',
            'npd_fee_paid':     True,
            'npd_fee_amount':   10000,
            'project_start_date': date.today() - timedelta(days=20),
            'project_end_date':   date.today() + timedelta(days=40),
            'target_sample_date': date.today() + timedelta(days=7),
        },
        {
            'code':             'NPD-0002',
            'project_type':     'npd',
            'status':           'lead_created',
            'product_name':     'Anti-Dandruff Shampoo 200ml',
            'product_category': 'Hair Care',
            'product_range':    'Shampoo',
            'client_name':      'Priya Mehta',
            'client_company':   'HairCare Solutions',
            'client_email':     'priya@haircare.in',
            'client_phone':     '+91 91234 56789',
            'area_of_application': 'Hair',
            'market_level':     'Mass',
            'appearance':       'Opaque white cream',
            'fragrance':        'Mint fresh',
            'viscosity':        'Medium thick',
            'ph_value':         '5.0 - 5.5',
            'priority':         'Normal',
            'npd_fee_paid':     False,
            'npd_fee_amount':   10000,
            'project_start_date': date.today() - timedelta(days=5),
            'project_end_date':   date.today() + timedelta(days=60),
            'target_sample_date': date.today() + timedelta(days=14),
        },
        {
            'code':             'NPD-0003',
            'project_type':     'npd',
            'status':           'sampling',
            'product_name':     'Baby Moisturizing Lotion 100ml',
            'product_category': 'Baby Care',
            'product_range':    'Body Lotion',
            'client_name':      'Sunita Patel',
            'client_company':   'BabySoft India',
            'client_email':     'sunita@babysoft.in',
            'client_phone':     '+91 97890 12345',
            'area_of_application': 'Body',
            'market_level':     'Premium',
            'appearance':       'White creamy lotion',
            'fragrance':        'Baby powder mild',
            'viscosity':        'Medium',
            'ph_value':         '6.0 - 7.0',
            'priority':         'Urgent',
            'npd_fee_paid':     True,
            'npd_fee_amount':   10000,
            'project_start_date': date.today() - timedelta(days=35),
            'project_end_date':   date.today() + timedelta(days=15),
            'target_sample_date': date.today() + timedelta(days=3),
        },
        {
            'code':             'NPD-0004',
            'project_type':     'npd',
            'status':           'complete',
            'product_name':     'Charcoal Face Wash 100ml',
            'product_category': 'Skin Care',
            'product_range':    'Face Cream',
            'client_name':      'Amit Verma',
            'client_company':   'PureSkin Brands',
            'client_email':     'amit@pureskin.in',
            'client_phone':     '+91 99001 23456',
            'area_of_application': 'Face',
            'market_level':     'Mass',
            'appearance':       'Black gel',
            'fragrance':        'Charcoal neutral',
            'viscosity':        'Gel thick',
            'ph_value':         '5.5',
            'priority':         'Normal',
            'npd_fee_paid':     True,
            'npd_fee_amount':   10000,
            'project_start_date': date.today() - timedelta(days=90),
            'project_end_date':   date.today() - timedelta(days=10),
            'target_sample_date': date.today() - timedelta(days=60),
        },
        {
            'code':             'NPD-0005',
            'project_type':     'npd',
            'status':           'client_approved',
            'product_name':     'Kojic Acid Skin Brightening Cream 50g',
            'product_category': 'Skin Care',
            'product_range':    'Face Cream',
            'client_name':      'Neha Joshi',
            'client_company':   'LumaSkin Co.',
            'client_email':     'neha@lumaskin.com',
            'client_phone':     '+91 88765 43210',
            'area_of_application': 'Face',
            'market_level':     'Premium',
            'appearance':       'Off-white smooth cream',
            'fragrance':        'Rose mild',
            'viscosity':        'Medium thick cream',
            'ph_value':         '6.0 - 6.5',
            'priority':         'High',
            'npd_fee_paid':     True,
            'npd_fee_amount':   10000,
            'project_start_date': date.today() - timedelta(days=45),
            'project_end_date':   date.today() + timedelta(days=20),
            'target_sample_date': date.today() - timedelta(days=5),
        },
    ]

    npd_added = 0
    for d in npd_data:
        if NPDProject.query.filter_by(code=d['code']).first():
            warn(f"{d['code']} already exists — skip")
            continue
        proj = NPDProject(
            code=d['code'],
            project_type=d['project_type'],
            status=d['status'],
            product_name=d['product_name'],
            product_category=d.get('product_category',''),
            product_range=d.get('product_range',''),
            client_name=d.get('client_name',''),
            client_company=d.get('client_company',''),
            client_email=d.get('client_email',''),
            client_phone=d.get('client_phone',''),
            area_of_application=d.get('area_of_application',''),
            market_level=d.get('market_level',''),
            appearance=d.get('appearance',''),
            fragrance=d.get('fragrance',''),
            viscosity=d.get('viscosity',''),
            ph_value=d.get('ph_value',''),
            priority=d.get('priority','Normal'),
            npd_fee_paid=d.get('npd_fee_paid', False),
            npd_fee_amount=d.get('npd_fee_amount', 10000),
            project_start_date=d.get('project_start_date'),
            project_end_date=d.get('project_end_date'),
            target_sample_date=d.get('target_sample_date'),
            milestone_master_created=True,
            created_by=uid,
        )
        db.session.add(proj)
        db.session.flush()
        add_milestones(proj.id, 'npd')
        npd_added += 1
        ok(f"{d['code']} — {d['product_name']}")

    db.session.commit()
    ok(f"NPD: {npd_added} projects added!")

    # ══════════════════════════════════════════════
    # EPD PROJECTS (5 dummy)
    # ══════════════════════════════════════════════
    step("EPD Projects seed kar raha hai...")

    epd_data = [
        {
            'code':             'EPD-0001',
            'project_type':     'existing',
            'status':           'sample_sent',
            'product_name':     'Neem Face Wash 100ml (Reformulation)',
            'product_category': 'Skin Care',
            'product_range':    'Face Cream',
            'client_name':      'Vikram Singh',
            'client_company':   'AyurHerb Naturals',
            'client_email':     'vikram@ayurherb.in',
            'client_phone':     '+91 93456 78901',
            'priority':         'Normal',
            'project_start_date': date.today() - timedelta(days=10),
            'project_end_date':   date.today() + timedelta(days=30),
        },
        {
            'code':             'EPD-0002',
            'project_type':     'existing',
            'status':           'lead_created',
            'product_name':     'Protein Hair Conditioner 200ml (New Variant)',
            'product_category': 'Hair Care',
            'product_range':    'Shampoo',
            'client_name':      'Kavita Rao',
            'client_company':   'SilkHair Brands',
            'client_email':     'kavita@silkhair.in',
            'client_phone':     '+91 87654 32109',
            'priority':         'High',
            'project_start_date': date.today() - timedelta(days=3),
            'project_end_date':   date.today() + timedelta(days=45),
        },
        {
            'code':             'EPD-0003',
            'project_type':     'existing',
            'status':           'client_review',
            'product_name':     'Sunscreen SPF 50 Lotion 75ml',
            'product_category': 'Skin Care',
            'product_range':    'Body Lotion',
            'client_name':      'Rohit Gupta',
            'client_company':   'SunShield Cosmetics',
            'client_email':     'rohit@sunshield.in',
            'client_phone':     '+91 96543 21098',
            'priority':         'Urgent',
            'project_start_date': date.today() - timedelta(days=25),
            'project_end_date':   date.today() + timedelta(days=10),
        },
        {
            'code':             'EPD-0004',
            'project_type':     'existing',
            'status':           'complete',
            'product_name':     'Aloe Vera Body Gel 200ml',
            'product_category': 'Skin Care',
            'product_range':    'Body Lotion',
            'client_name':      'Meena Kumari',
            'client_company':   'AloeNature India',
            'client_email':     'meena@aloenature.in',
            'client_phone':     '+91 82345 67890',
            'priority':         'Normal',
            'project_start_date': date.today() - timedelta(days=70),
            'project_end_date':   date.today() - timedelta(days=5),
        },
        {
            'code':             'EPD-0005',
            'project_type':     'existing',
            'status':           'sample_sent',
            'product_name':     'Herbal Toothpaste 100g (New Flavour)',
            'product_category': 'Oral Care',
            'product_range':    'Gel',
            'client_name':      'Suresh Nair',
            'client_company':   'DentaHerb Co.',
            'client_email':     'suresh@dentaherb.in',
            'client_phone':     '+91 78901 23456',
            'priority':         'High',
            'project_start_date': date.today() - timedelta(days=15),
            'project_end_date':   date.today() + timedelta(days=25),
        },
    ]

    epd_added = 0
    for d in epd_data:
        if NPDProject.query.filter_by(code=d['code']).first():
            warn(f"{d['code']} already exists — skip")
            continue
        proj = NPDProject(
            code=d['code'],
            project_type=d['project_type'],
            status=d['status'],
            product_name=d['product_name'],
            product_category=d.get('product_category',''),
            product_range=d.get('product_range',''),
            client_name=d.get('client_name',''),
            client_company=d.get('client_company',''),
            client_email=d.get('client_email',''),
            client_phone=d.get('client_phone',''),
            priority=d.get('priority','Normal'),
            project_start_date=d.get('project_start_date'),
            project_end_date=d.get('project_end_date'),
            milestone_master_created=True,
            advance_paid=True,
            advance_amount=2000,
            created_by=uid,
        )
        db.session.add(proj)
        db.session.flush()
        add_milestones(proj.id, 'existing')
        epd_added += 1
        ok(f"{d['code']} — {d['product_name']}")

    db.session.commit()
    ok(f"EPD: {epd_added} projects added!")

    print(f"\n{'='*55}")
    print(f"  {G}{B}✅ DONE! {npd_added} NPD + {epd_added} EPD projects created!{E}")
    print(f"{'='*55}")
    print(f"\n  Ab /npd/npd-projects aur /npd/epd-projects pe check karo\n")
