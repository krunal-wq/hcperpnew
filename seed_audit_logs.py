"""
seed_audit_logs.py — Real DB records se JSON snapshot audit logs seed karta hai
Run: python seed_audit_logs.py
"""
import sys, os, json, random
sys.path.insert(0, os.path.dirname(__file__))

from index import app
from models import db, AuditLog, Lead, ClientMaster, Employee, Contractor, User
from audit_helper import model_to_dict
from datetime import datetime, timedelta

IST = timedelta(hours=5, minutes=30)

def now_ist():
    return datetime.utcnow() + IST

def rand_time(days_back=90):
    return now_ist() - timedelta(
        days=random.randint(0, days_back),
        hours=random.randint(8, 20),
        minutes=random.randint(0, 59),
        seconds=random.randint(0, 59)
    )

def add(module, action, uid, uname, urole, rec_id, label, payload, when, ip):
    db.session.add(AuditLog(
        user_id      = uid,
        username     = uname,
        user_role    = urole,
        module       = module,
        action       = action,
        record_id    = rec_id,
        record_label = str(label)[:299],
        detail       = json.dumps(payload, ensure_ascii=False, default=str)[:8000],
        ip_address   = ip,
        created_at   = when,
    ))

def make_update_payload(rec_dict, fields_to_change):
    """Simulate an update — pick some fields and make fake 'before' values."""
    changes = {}
    current = dict(rec_dict)
    fake_befores = {
        'status':        ['open','in_process','close','cancel'],
        'priority':      ['low','medium','high'],
        'source':        ['Email','Phone','Reference','Website','Cold Call'],
        'category':      ['General','Retail','Industrial','Export'],
        'city':          ['Mumbai','Delhi','Surat','Ahmedabad','Pune'],
        'state':         ['Gujarat','Maharashtra','Delhi','Rajasthan'],
        'client_type':   ['regular','premium','vip'],
        'designation':   ['Manager','Executive','Sr. Executive','Officer'],
        'department':    ['Sales','Marketing','Operations','Finance','HR'],
        'role':          ['user','manager','admin'],
    }
    for field in fields_to_change:
        cur_val = rec_dict.get(field)
        if field in fake_befores:
            opts = [x for x in fake_befores[field] if x != str(cur_val)]
            if opts:
                old_val = random.choice(opts)
                changes[field] = {'before': old_val, 'after': cur_val}
        elif cur_val is not None and str(cur_val).strip():
            changes[field] = {'before': str(cur_val) + ' (old)', 'after': cur_val}
    return {
        'changes':        changes,
        'current_record': current,
        'summary':        f'Updated {len(changes)} field(s)'
    }

def run():
    with app.app_context():
        # ── Check existing seed ──
        existing = AuditLog.query.count()
        if existing > 0:
            print(f"⚠️  {existing} audit logs already exist.")
            ans = input("Clear existing logs and re-seed? (y/N): ").strip().lower()
            if ans != 'y':
                print("Aborted.")
                return
            AuditLog.query.delete()
            db.session.commit()
            print("✅ Cleared existing logs.")

        leads       = Lead.query.all()
        clients     = ClientMaster.query.all()
        employees   = Employee.query.all()
        contractors = Contractor.query.all()
        users       = User.query.all()

        if not users:
            print("❌ No users found. Run migrate_v7.py and /setup first.")
            return

        upool = [{'id':u.id,'name':u.username,'role':u.role or 'user'} for u in users]
        admins = [u for u in upool if u['role']=='admin'] or [upool[0]]
        ips   = ['192.168.1.101','192.168.1.102','192.168.1.103','10.0.0.15','10.0.0.22','172.16.0.5']
        total = 0

        print(f"\n📊 Found: {len(leads)} leads, {len(clients)} clients, {len(employees)} employees, {len(contractors)} contractors, {len(users)} users")

        # ══════════════════════════════════
        # 1. AUTH — Login/Logout
        # ══════════════════════════════════
        print("\n⏳ Auth logs...")
        for u in upool:
            for _ in range(random.randint(4, 15)):
                ip = random.choice(ips)
                lt = rand_time(60)
                add('auth','LOGIN', u['id'], u['name'], u['role'],
                    u['id'], u['name'],
                    {'summary': f"Login from {ip}", 'user': {'id': u['id'], 'username': u['name'], 'role': u['role']}},
                    lt, ip)
                add('auth','LOGOUT', u['id'], u['name'], u['role'],
                    u['id'], u['name'],
                    {'summary': 'Session ended'},
                    lt + timedelta(minutes=random.randint(10,480)), ip)
                total += 2

        # ══════════════════════════════════
        # 2. LEADS — full snapshots
        # ══════════════════════════════════
        print("⏳ Lead logs...")
        disc_msgs = [
            'Called customer — interested in bulk order.',
            'Sent product catalogue via email.',
            'Follow-up done — customer reviewing samples.',
            'Customer asked for revised quote. Sent revised price list.',
            'Meeting scheduled for next week at customer office.',
            'Shared product specification sheet. Decision pending.',
            'Price negotiation done. Final offer sent via email.',
            'Customer confirmed intent to place order.',
            'Technical team visit arranged for site inspection.',
            'Customer requested credit terms — checking with finance.',
        ]
        note_msgs = [
            'High-value customer — handle with priority.',
            'Reference from existing client Sharma Industries.',
            'Budget constraint mentioned — target closing in Q2.',
            'Decision maker is MD directly. Avoid middle management.',
            'Customer competes with XYZ Ltd — highlight our USP.',
        ]
        reminder_titles = [
            'Follow-up call', 'Send quotation', 'Site visit', 'Demo scheduled',
            'Payment follow-up', 'Contract renewal', 'Feedback call'
        ]

        for lead in leads:
            rec   = model_to_dict(lead)
            label = f"{lead.code or 'LD-?'} / {lead.contact_name}"
            u     = random.choice(upool)
            ip    = random.choice(ips)
            ct    = lead.created_at or rand_time(120)

            # INSERT — full record
            add('leads','INSERT', u['id'], u['name'], u['role'],
                lead.id, label,
                {'created_record': rec, 'summary': f'New lead created. Status:{lead.status} | Company:{lead.company_name}'},
                ct, ip)
            total += 1

            # 1-4 UPDATEs with field diffs
            update_field_sets = [
                ['status'],
                ['priority', 'expected_value'],
                ['source', 'category'],
                ['city', 'state', 'status'],
                ['product_name', 'order_quantity'],
                ['assigned_to', 'follow_up_date'],
            ]
            for i in range(random.randint(1, 4)):
                t   = ct + timedelta(days=random.randint(1,20), hours=random.randint(0,8))
                u2  = random.choice(upool)
                flds = random.choice(update_field_sets)
                payload = make_update_payload(rec, flds)
                add('leads','UPDATE', u2['id'], u2['name'], u2['role'],
                    lead.id, label, payload, t, random.choice(ips))
                total += 1

            # VIEW — full snapshot
            for _ in range(random.randint(1, 5)):
                uv = random.choice(upool)
                add('leads','VIEW', uv['id'], uv['name'], uv['role'],
                    lead.id, label,
                    {'viewed_record': rec, 'summary': f'Record viewed by {uv["name"]}'},
                    rand_time(30), random.choice(ips))
                total += 1

            # Kanban drag (40% chance)
            if random.random() < 0.4:
                statuses = ['open','in_process','close','cancel']
                old_s, new_s = random.sample(statuses, 2)
                add('leads','KANBAN', u['id'], u['name'], u['role'],
                    lead.id, label,
                    {'changes': {'status': {'before': old_s, 'after': new_s}},
                     'current_record': rec,
                     'summary': f'Kanban drag: {old_s} → {new_s}'},
                    rand_time(20), ip)
                total += 1

            # Discussions
            for _ in range(random.randint(1, 4)):
                ud  = random.choice(upool)
                msg = random.choice(disc_msgs)
                add('leads','DISCUSSION', ud['id'], ud['name'], ud['role'],
                    lead.id, label,
                    {'summary': msg, 'record': {'lead_id': lead.id, 'comment': msg, 'user': ud['name']}},
                    rand_time(50), random.choice(ips))
                total += 1

            # Notes
            for _ in range(random.randint(0, 2)):
                un  = random.choice(upool)
                msg = random.choice(note_msgs)
                add('leads','NOTE', un['id'], un['name'], un['role'],
                    lead.id, label,
                    {'summary': msg, 'record': {'lead_id': lead.id, 'note': msg, 'user': un['name']}},
                    rand_time(60), random.choice(ips))
                total += 1

            # Reminders
            for _ in range(random.randint(0, 2)):
                ur    = random.choice(upool)
                title = random.choice(reminder_titles)
                add('leads','REMINDER', ur['id'], ur['name'], ur['role'],
                    lead.id, label,
                    {'summary': f'Reminder set: {title}',
                     'record': {'lead_id': lead.id, 'title': title, 'user': ur['name']}},
                    rand_time(40), random.choice(ips))
                total += 1

        # ══════════════════════════════════
        # 3. CLIENTS — full snapshots
        # ══════════════════════════════════
        print("⏳ Client logs...")
        for client in clients:
            rec   = model_to_dict(client)
            label = f"{client.code or 'CL-?'} / {client.contact_name}"
            u     = random.choice(upool)
            ip    = random.choice(ips)
            ct    = client.created_at or rand_time(120)

            add('clients','INSERT', u['id'], u['name'], u['role'],
                client.id, label,
                {'created_record': rec, 'summary': f'New client. Type:{client.client_type}'},
                ct, ip)
            total += 1

            for i in range(random.randint(0, 3)):
                t   = ct + timedelta(days=random.randint(1,30))
                u2  = random.choice(upool)
                fld = random.choice([['client_type'],['status'],['city','state'],['notes']])
                payload = make_update_payload(rec, fld)
                add('clients','UPDATE', u2['id'], u2['name'], u2['role'],
                    client.id, label, payload, t, random.choice(ips))
                total += 1

            # DELETE simulation (10% chance — just the log, not actual delete)
            if random.random() < 0.1:
                add('clients','DELETE', random.choice(admins)['id'],
                    random.choice(admins)['name'], 'admin',
                    client.id, label,
                    {'deleted_record': rec, 'summary': 'Record deleted by admin'},
                    rand_time(10), random.choice(ips))
                total += 1

            for _ in range(random.randint(1, 3)):
                add('clients','VIEW', u['id'], u['name'], u['role'],
                    client.id, label,
                    {'viewed_record': rec},
                    rand_time(20), random.choice(ips))
                total += 1

        # ══════════════════════════════════
        # 4. EMPLOYEES — full snapshots
        # ══════════════════════════════════
        print("⏳ Employee logs...")
        for emp in employees:
            rec   = model_to_dict(emp, exclude=('password_hash','qr_code_base64'))
            full  = f"{emp.first_name} {emp.last_name}"
            label = f"{emp.employee_code or emp.id} / {full}"
            u     = random.choice(upool)
            ip    = random.choice(ips)
            ct    = emp.created_at or rand_time(180)

            add('employees','INSERT', u['id'], u['name'], u['role'],
                emp.id, label,
                {'created_record': rec, 'summary': f'Employee added. Dept:{getattr(emp,"department","N/A")}'},
                ct, ip)
            total += 1

            for i in range(random.randint(1, 4)):
                t   = ct + timedelta(days=random.randint(5, 60))
                u2  = random.choice(upool)
                fld = random.choice([['department'],['designation'],['status'],['department','designation']])
                payload = make_update_payload(rec, fld)
                add('employees','UPDATE', u2['id'], u2['name'], u2['role'],
                    emp.id, label, payload, t, random.choice(ips))
                total += 1

            for _ in range(random.randint(1, 3)):
                add('employees','VIEW', u['id'], u['name'], u['role'],
                    emp.id, label,
                    {'viewed_record': rec},
                    rand_time(30), random.choice(ips))
                total += 1

        # ══════════════════════════════════
        # 5. CONTRACTORS
        # ══════════════════════════════════
        print("⏳ Contractor logs...")
        for cont in contractors:
            rec   = model_to_dict(cont)
            label = f"{cont.contract_id} / {cont.company_name}"
            u     = random.choice(upool)
            ip    = random.choice(ips)

            add('contractors','INSERT', u['id'], u['name'], u['role'],
                cont.id, label,
                {'created_record': rec, 'summary': f'Contractor added. Supply:{cont.supply}'},
                rand_time(120), ip)
            total += 1

            if random.random() < 0.6:
                payload = make_update_payload(rec, ['status'])
                add('contractors','UPDATE', u['id'], u['name'], u['role'],
                    cont.id, label, payload, rand_time(30), ip)
                total += 1

        # ══════════════════════════════════
        # 6. USERS
        # ══════════════════════════════════
        print("⏳ User management logs...")
        for u in upool:
            admin = random.choice(admins)
            ip    = random.choice(ips)
            urec  = {'id': u['id'], 'username': u['name'], 'role': u['role']}

            add('users','INSERT', admin['id'], admin['name'], admin['role'],
                u['id'], u['name'],
                {'created_record': urec, 'summary': f'User created. Role:{u["role"]}'},
                rand_time(120), ip)
            total += 1

            if random.random() < 0.5:
                payload = make_update_payload(urec, ['role'])
                add('users','UPDATE', admin['id'], admin['name'], admin['role'],
                    u['id'], u['name'], payload, rand_time(60), ip)
                total += 1

        # ══════════════════════════════════
        # 7. MASTERS
        # ══════════════════════════════════
        print("⏳ Masters logs...")
        master_samples = [
            ('LeadStatus','Status','New Status','Converted'),
            ('LeadSource','Source','Trade Show','Cold Call'),
            ('LeadCategory','Category','Bulk Order','Sample'),
            ('ProductRange','Product Range','Industrial','Retail'),
        ]
        for mname, mtype, v1, v2 in master_samples:
            adm = random.choice(admins)
            add('masters','INSERT', adm['id'], adm['name'], adm['role'],
                None, mname,
                {'created_record': {'name': v1, 'type': mtype, 'is_active': True},
                 'summary': f'{mtype} "{v1}" added'},
                rand_time(90), random.choice(ips))
            add('masters','UPDATE', adm['id'], adm['name'], adm['role'],
                None, mname,
                {'changes': {'name': {'before': v1+' (draft)', 'after': v1}},
                 'summary': f'{mtype} name finalized'},
                rand_time(60), random.choice(ips))
            total += 2

        # Commit
        db.session.commit()
        final = AuditLog.query.count()
        print(f"\n✅ Done! {total} entries inserted. Total in DB: {final}")
        print("→ http://localhost:5000/admin/audit-logs")

if __name__ == '__main__':
    run()
