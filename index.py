from flask import Flask, render_template, redirect, url_for, request, flash
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
from audit_helper import audit
from models import db, User, LoginLog, Lead, ClientMaster, LeadReminder, Employee, WishLog
from config import Config

from crm_routes  import crm
from master_routes import masters
from hr_routes   import hr
from user_routes import users_bp
from approval_routes import approval_bp
from mail_routes import mail_bp
from npd_routes  import npd
from rd_routes   import rd
from attendance_routes import attendance_bp
from hr_master_routes import hr_masters
from late_rule_routes import late_rules_bp
from hr_rules_routes import hr_rules_bp

app = Flask(__name__)
app.config.from_object(Config)
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024
import json as _json
app.jinja_env.filters['from_json'] = lambda s: _json.loads(s) if s else []   # 100MB — base64 photos + docs
db.init_app(app)

# ── Jinja filter: safe base64 encode for JS embedding ──
import base64 as _b64
@app.template_filter('b64encode')
def b64encode_filter(s):
    if s is None: s = ''
    return _b64.b64encode(str(s).encode('utf-8')).decode('ascii')

@app.template_filter('map_audit_data')
def map_audit_data_filter(logs):
    """Convert logs queryset to JSON array safe for embedding."""
    import json
    result = []
    for log in logs:
        result.append({
            'id':     log.id,
            'action': log.action or '',
            'module': log.module or '',
            'record': log.record_label or '',
            'time':   log.created_at.strftime('%d-%m-%Y %H:%M:%S') if log.created_at else '',
            'user':   log.username or '',
            'data':   log.detail or '',
        })
    return json.dumps(result, ensure_ascii=False, default=str)

app.register_blueprint(crm)
app.register_blueprint(masters)
app.register_blueprint(hr)
app.register_blueprint(users_bp)
app.register_blueprint(approval_bp)
app.register_blueprint(mail_bp)
app.register_blueprint(npd)
app.register_blueprint(rd)
app.register_blueprint(attendance_bp)
app.register_blueprint(hr_masters)
app.register_blueprint(late_rules_bp)
app.register_blueprint(hr_rules_bp)

# ── get_perm as Jinja2 global — template mein use ho sakta hai ──
from permissions import get_perm as _get_perm
app.jinja_env.globals['get_perm'] = _get_perm
from permissions import get_sub_perm as _get_sub_perm
app.jinja_env.globals['get_sub_perm'] = _get_sub_perm

# Seed HR master defaults
with app.app_context():
    try:
        from hr_master_routes import seed_defaults
        seed_defaults()
    except Exception:
        pass
    try:
        from permissions import seed_permissions
        seed_permissions()
    except Exception:
        pass

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'warning'

MAX_ATTEMPTS = 5
LOCK_MINUTES = 15


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
@login_required
def dashboard():
    from models import Employee
    is_admin = current_user.role in ('admin', 'manager')
    uid_str  = str(current_user.id)

    def lq():
        q = Lead.query
        if not is_admin:
            q = q.filter(
                Lead.team_members.like(f'%{uid_str}%') |
                (Lead.created_by == current_user.id)
            )
        return q

    lead_counts = {
        'open':       lq().filter_by(status='open').count(),
        'in_process': lq().filter_by(status='in_process').count(),
        'close':      lq().filter_by(status='close').count(),
        'cancel':     lq().filter_by(status='cancel').count(),
        'total':      lq().count(),
    }
    total_clients  = ClientMaster.query.count()
    total_employees= Employee.query.filter_by(status='active').count()
    recent_leads   = lq().order_by(Lead.created_at.desc()).limit(5).all()

    upcoming_reminders = LeadReminder.query.filter(
        LeadReminder.is_done == False,
        LeadReminder.remind_at >= datetime.utcnow()
    ).order_by(LeadReminder.remind_at).limit(5).all()

    return render_template('dashboard.html',
        active_page='dashboard',
        lead_counts=lead_counts,
        total_clients=total_clients,
        total_employees=total_employees,
        recent_leads=recent_leads,
        upcoming_reminders=upcoming_reminders,
        is_admin=is_admin,
        now=datetime.utcnow())


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        identifier = request.form.get('username', '').strip()
        password   = request.form.get('password', '')
        remember   = bool(request.form.get('remember'))
        ip_address = request.remote_addr

        # ── 3-way login: username OR email OR employee_code ──
        user = (
            User.query.filter_by(username=identifier).first() or
            User.query.filter(User.email.ilike(identifier)).first()
        )

        # Try by employee code — case-insensitive
        if not user:
            emp = Employee.query.filter(
                Employee.employee_code.ilike(identifier)
            ).first()
            if emp:
                # First try linked user_id
                if emp.user_id:
                    user = User.query.get(emp.user_id)
                # Fallback: try username derived from employee code
                if not user:
                    derived_username = emp.employee_code.lower().replace('-', '').replace(' ', '')
                    user = User.query.filter_by(username=derived_username).first()
                # Fallback: try employee email
                if not user and emp.email:
                    user = User.query.filter(User.email.ilike(emp.email)).first()

        if not user:
            _log(None, identifier, ip_address, 'failed')
            flash('Invalid username / email / employee code!', 'danger')
            return render_template('login.html')

        if user.is_locked():
            remaining = int((user.locked_until - datetime.utcnow()).total_seconds() / 60) + 1
            _log(user.id, identifier, ip_address, 'locked')
            flash(f'Account locked! Try again in {remaining} minute(s).', 'danger')
            return render_template('login.html')

        if not user.is_active:
            flash('Account disabled. Contact admin.', 'danger')
            return render_template('login.html')

        if not user.check_password(password):
            user.login_attempts += 1
            if user.login_attempts >= MAX_ATTEMPTS:
                user.locked_until = datetime.utcnow() + timedelta(minutes=LOCK_MINUTES)
                db.session.commit()
                flash(f'Too many attempts! Locked for {LOCK_MINUTES} min.', 'danger')
            else:
                db.session.commit()
                flash(f'Wrong password! {MAX_ATTEMPTS - user.login_attempts} attempt(s) left.', 'danger')
            _log(user.id, identifier, ip_address, 'failed')
            return render_template('login.html')

        user.login_attempts = 0
        user.locked_until   = None
        user.last_login     = datetime.utcnow()
        db.session.commit()
        _log(user.id, identifier, ip_address, 'success')
        audit('auth','LOGIN', user.id, user.username, f'Login from {ip_address}', commit=True)
        login_user(user, remember=remember)
        flash(f'Welcome, {user.full_name or user.username}!', 'success')
        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    audit('auth','LOGOUT', current_user.id, current_user.username, '', commit=True)
    logout_user()
    flash('Logged out.', 'info')
    return redirect(url_for('login'))


@app.route('/seed-modules')
def seed_modules():
    """Seed missing modules without full setup — call once after adding new modules."""
    from permissions import seed_permissions
    try:
        seed_permissions()
        return '✅ Modules seeded successfully! New modules added to DB.'
    except Exception as e:
        return f'❌ Error: {e}', 500

@app.route('/setup')
def setup():
    from permissions import seed_permissions
    db.create_all()
    seed_permissions()

    if not User.query.filter_by(username='admin').first():
        admin = User(username='admin', email='admin@hcp.com',
                     full_name='Administrator', role='admin', is_active=True)
        admin.set_password('HCP@123')
        db.session.add(admin)
        db.session.commit()
        msg = '✅ Setup complete! <br>Username: <b>admin</b> | Password: <b>HCP@123</b>'
    else:
        msg = '✅ Tables synced & permissions seeded!'

    return f'''<div style="font-family:sans-serif;padding:2rem;max-width:600px;">
        <h2 style="color:green;">{msg}</h2>
        <p style="margin-top:1rem;"><a href="/login" style="color:#2563eb;">→ Go to Login</a></p>
    </div>'''


def _log(user_id, username, ip, status):
    try:
        db.session.add(LoginLog(user_id=user_id, username=username,
                                ip_address=ip, status=status))
        db.session.commit()
    except Exception:
        db.session.rollback()


if __name__ == '__main__':
    app.run(debug=True)