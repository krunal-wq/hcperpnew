"""
rd_seed.py — R&D Department Users Create karo
Run: python rd_seed.py

Creates:
  1. Suraj      — R&D Executive  (role: rd_executive)
  2. Prashant   — R&D Executive  (role: rd_executive)
  3. R&D Manager (role: rd_manager) — sees ALL NPD projects
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from index import app, db
from models import User

USERS_TO_CREATE = [
    {
        'username':  'suraj.rd',
        'email':     'suraj.rd@hcpwellness.com',
        'full_name': 'Suraj Sharma',
        'role':      'rd_executive',
        'password':  'HCP@123',
    },
    {
        'username':  'prashant.rd',
        'email':     'prashant.rd@hcpwellness.com',
        'full_name': 'Prashant Verma',
        'role':      'rd_executive',
        'password':  'HCP@123',
    },
    {
        'username':  'rd.manager',
        'email':     'rdmanager@hcpwellness.com',
        'full_name': 'R&D Manager',
        'role':      'rd_manager',
        'password':  'HCP@123',
    },
]

def run():
    with app.app_context():
        created = []
        skipped = []

        for u_data in USERS_TO_CREATE:
            # Check if already exists
            existing = User.query.filter(
                (User.username == u_data['username']) |
                (User.email    == u_data['email'])
            ).first()

            if existing:
                skipped.append(f"  ⚠️  {u_data['full_name']} already exists (username: {existing.username})")
                continue

            u = User(
                username  = u_data['username'],
                email     = u_data['email'],
                full_name = u_data['full_name'],
                role      = u_data['role'],
                is_active = True,
            )
            u.set_password(u_data['password'])
            db.session.add(u)
            created.append(f"  ✅ {u_data['full_name']} ({u_data['role']}) — {u_data['username']} / {u_data['password']}")

        db.session.commit()

        print("\n" + "="*55)
        print("  R&D USERS SEED")
        print("="*55)

        if created:
            print(f"\n  Created ({len(created)}):")
            for c in created: print(c)
        if skipped:
            print(f"\n  Skipped ({len(skipped)}):")
            for s in skipped: print(s)

        print("\n  R&D Roles:")
        print("    rd_executive — R&D team member (only assigned projects)")
        print("    rd_manager   — R&D Manager (sees ALL NPD/EPD projects)")

        print("\n  Login credentials:")
        print("    suraj.rd     / HCP@123")
        print("    prashant.rd  / HCP@123")
        print("    rd.manager   / HCP@123")
        print("="*55 + "\n")

if __name__ == '__main__':
    run()
