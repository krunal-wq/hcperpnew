import os
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, send_file
from flask_login import login_required, current_user
from datetime import datetime, date
from werkzeug.utils import secure_filename
from models import (db, User, ClientMaster, ClientBrand, ClientAddress,
                    Lead, LeadDiscussion, LeadAttachment,
                    LeadReminder, LeadNote, LeadActivityLog,
                    Customer, CustomerAddress,
                    LeadStatus, LeadSource, LeadCategory, ProductRange)

from permissions import get_perm, get_grid_columns, save_grid_columns
from audit_helper import audit, snapshot, diff

LEAD_COLS_DEFAULT = ['code','created_at','name','company','email','mobile','product','team','status','last_contact']
LEAD_COLS_ALL = {
    'code':          'Lead Code',
    'created_at':    'Created Date',
    'name':          'Name',
    'company':       'Company',
    'email':         'Email',
    'mobile':        'Mobile',
    'product':       'Product',
    'category':      'Category',
    'source':        'Source',
    'city':          'City',
    'assigned_to':   'Assigned To',
    'team':          'Team',
    'follow_up':     'Follow Up Date',
    'status':        'Status',
    'last_contact':  'Last Contact',
    'priority':      'Priority',
    'expected_value':'Expected Value',
}

UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'static', 'uploads')
ALLOWED_EXTENSIONS = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'xls', 'xlsx', 'txt'}

crm = Blueprint('crm', __name__, url_prefix='/crm')


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def gen_code(model, prefix):
    last = model.query.order_by(model.id.desc()).first()
    num  = (last.id + 1) if last else 1
    return f"{prefix}-{num:04d}"


def log_activity(lead_id, action, user_id=None):
    uid = user_id or (current_user.id if current_user.is_authenticated else None)
    db.session.add(LeadActivityLog(lead_id=lead_id, user_id=uid, action=action))


# ══════════════════════════════════════
# CLIENT MASTER ROUTES
# ══════════════════════════════════════

@crm.route('/clients')
@login_required
def clients():
    search      = request.args.get('search', '')
    city        = request.args.get('city', '')
    state       = request.args.get('state', '')
    client_type = request.args.get('client_type', '')
    status_f    = request.args.get('status_f', '')
    sort_by     = request.args.get('sort_by', 'created_at')
    sort_dir    = request.args.get('sort_dir', 'desc')

    query = ClientMaster.query

    if search:
        query = query.filter(
            ClientMaster.company_name.ilike(f'%{search}%') |
            ClientMaster.contact_name.ilike(f'%{search}%') |
            ClientMaster.mobile.ilike(f'%{search}%') |
            ClientMaster.email.ilike(f'%{search}%')
        )
    if city:        query = query.filter(ClientMaster.city.ilike(f'%{city}%'))
    if state:       query = query.filter(ClientMaster.state.ilike(f'%{state}%'))
    if client_type: query = query.filter_by(client_type=client_type)
    if status_f:    query = query.filter_by(status=status_f)

    sort_col = getattr(ClientMaster, sort_by, ClientMaster.created_at)
    if sort_dir == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    all_clients = query.all()

    all_cities = [r[0] for r in db.session.query(ClientMaster.city).distinct().all() if r[0]]
    all_states = [r[0] for r in db.session.query(ClientMaster.state).distinct().all() if r[0]]

    return render_template('crm/clients/clients.html',
        clients=all_clients, search=search,
        city=city, state=state, client_type=client_type, status_f=status_f,
        sort_by=sort_by, sort_dir=sort_dir,
        all_cities=all_cities, all_states=all_states,
        active_page='clients')


@crm.route('/clients/add', methods=['GET', 'POST'])
@login_required
def client_add():
    if request.method == 'POST':
        c = ClientMaster(
            code             = gen_code(ClientMaster, 'CLT'),
            contact_name     = request.form.get('contact_name', '').strip(),
            position         = request.form.get('position', '').strip(),
            company_name     = request.form.get('company_name', '').strip(),
            email            = request.form.get('email', '').strip(),
            website          = request.form.get('website', '').strip(),
            mobile           = request.form.get('mobile', '').strip(),
            alternate_mobile = request.form.get('alternate_mobile', '').strip(),
            gstin            = request.form.get('gstin', '').strip().upper(),
            client_type      = request.form.get('client_type', 'regular'),
            status           = request.form.get('status', 'active'),
            notes            = request.form.get('notes', '').strip(),
            created_by       = current_user.id
        )
        db.session.add(c)
        db.session.flush()

        # Save addresses (multiple)
        addr_titles  = request.form.getlist('addr_title[]')
        addr_types   = request.form.getlist('addr_type[]')
        addr_streets = request.form.getlist('addr_street[]')
        addr_cities  = request.form.getlist('addr_city[]')
        addr_states  = request.form.getlist('addr_state[]')
        addr_countries = request.form.getlist('addr_country[]')
        addr_zips    = request.form.getlist('addr_zip[]')
        addr_defaults= request.form.getlist('addr_default[]')
        for i, title in enumerate(addr_titles):
            if title.strip() or (addr_streets[i] if i < len(addr_streets) else '').strip():
                db.session.add(ClientAddress(
                    client_id  = c.id,
                    title      = title.strip() or 'Address',
                    addr_type  = addr_types[i]    if i < len(addr_types)    else 'billing',
                    address    = addr_streets[i]  if i < len(addr_streets)  else '',
                    city       = addr_cities[i]   if i < len(addr_cities)   else '',
                    state      = addr_states[i]   if i < len(addr_states)   else '',
                    country    = addr_countries[i] if i < len(addr_countries) else 'India',
                    zip_code   = addr_zips[i]     if i < len(addr_zips)     else '',
                    is_default = (str(i) in addr_defaults),
                ))

        # Save brands
        brand_names = request.form.getlist('brand_name[]')
        brand_cats  = request.form.getlist('brand_category[]')
        brand_descs = request.form.getlist('brand_description[]')
        for i, bname in enumerate(brand_names):
            if bname.strip():
                db.session.add(ClientBrand(
                    client_id   = c.id,
                    brand_name  = bname.strip(),
                    category    = brand_cats[i] if i < len(brand_cats) else '',
                    description = brand_descs[i] if i < len(brand_descs) else '',
                ))

        db.session.commit()
        flash(f'Client {c.contact_name} added! (Code: {c.code})', 'success')
        return redirect(url_for('crm.clients'))

    return render_template('crm/clients/client_form.html', client=None, brands=[], active_page='clients')


@crm.route('/clients/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def client_edit(id):
    c = ClientMaster.query.get_or_404(id)
    if request.method == 'POST':
        c.contact_name     = request.form.get('contact_name', '').strip()
        c.position         = request.form.get('position', '').strip()
        c.company_name     = request.form.get('company_name', '').strip()
        c.email            = request.form.get('email', '').strip()
        c.website          = request.form.get('website', '').strip()
        c.mobile           = request.form.get('mobile', '').strip()
        c.alternate_mobile = request.form.get('alternate_mobile', '').strip()
        c.gstin            = request.form.get('gstin', '').strip().upper()
        c.client_type      = request.form.get('client_type', 'regular')
        c.status           = request.form.get('status', 'active')
        c.notes            = request.form.get('notes', '').strip()
        c.updated_at       = datetime.utcnow()

        # Delete old addresses and re-save
        ClientAddress.query.filter_by(client_id=c.id).delete()
        addr_titles   = request.form.getlist('addr_title[]')
        addr_types    = request.form.getlist('addr_type[]')
        addr_streets  = request.form.getlist('addr_street[]')
        addr_cities   = request.form.getlist('addr_city[]')
        addr_states   = request.form.getlist('addr_state[]')
        addr_countries= request.form.getlist('addr_country[]')
        addr_zips     = request.form.getlist('addr_zip[]')
        addr_defaults = request.form.getlist('addr_default[]')
        for i, title in enumerate(addr_titles):
            if title.strip() or (addr_streets[i] if i < len(addr_streets) else '').strip():
                db.session.add(ClientAddress(
                    client_id  = c.id,
                    title      = title.strip() or 'Address',
                    addr_type  = addr_types[i]     if i < len(addr_types)     else 'billing',
                    address    = addr_streets[i]   if i < len(addr_streets)   else '',
                    city       = addr_cities[i]    if i < len(addr_cities)    else '',
                    state      = addr_states[i]    if i < len(addr_states)    else '',
                    country    = addr_countries[i] if i < len(addr_countries) else 'India',
                    zip_code   = addr_zips[i]      if i < len(addr_zips)      else '',
                    is_default = (str(i) in addr_defaults),
                ))

        # Delete old brands and re-save
        ClientBrand.query.filter_by(client_id=c.id).delete()
        brand_names = request.form.getlist('brand_name[]')
        brand_cats  = request.form.getlist('brand_category[]')
        brand_descs = request.form.getlist('brand_description[]')
        for i, bname in enumerate(brand_names):
            if bname.strip():
                db.session.add(ClientBrand(
                    client_id   = c.id,
                    brand_name  = bname.strip(),
                    category    = brand_cats[i] if i < len(brand_cats) else '',
                    description = brand_descs[i] if i < len(brand_descs) else '',
                ))

        db.session.commit()
        flash('Client updated successfully!', 'success')
        return redirect(url_for('crm.clients'))

    brands = ClientBrand.query.filter_by(client_id=c.id).all()
    return render_template('crm/clients/client_form.html', client=c, brands=brands, active_page='clients')


@crm.route('/clients/<int:id>')
@login_required
def client_view(id):
    c = ClientMaster.query.get_or_404(id)
    brands = ClientBrand.query.filter_by(client_id=c.id).all()
    return render_template('crm/clients/client_view.html', client=c, brands=brands, active_page='clients')


@crm.route('/clients/<int:id>/delete', methods=['POST'])
@login_required
def client_delete(id):
    c = ClientMaster.query.get_or_404(id)
    name = c.contact_name
    db.session.delete(c)
    db.session.commit()
    flash(f'Client "{name}" deleted!', 'success')
    return redirect(url_for('crm.clients'))


# ══════════════════════════════════════
# LEAD ROUTES
# ══════════════════════════════════════

@crm.route('/leads')
@login_required
def leads():
    # Basic filters
    status   = request.args.get('status', '')
    search   = request.args.get('search', '')
    # Advanced filters
    source   = request.args.get('source', '')
    category = request.args.get('category', '')
    p_range  = request.args.get('product_range', '')
    city     = request.args.get('city', '')
    date_from= request.args.get('date_from', '')
    date_to  = request.args.get('date_to', '')
    # Sorting
    sort_by  = request.args.get('sort_by', 'created_at')
    sort_dir = request.args.get('sort_dir', 'desc')

    query = Lead.query

    if status:   query = query.filter_by(status=status)
    if source:   query = query.filter_by(source=source)
    if category: query = query.filter_by(category=category)
    if p_range:  query = query.filter_by(product_range=p_range)
    if city:     query = query.filter(Lead.city.ilike(f'%{city}%'))
    if date_from:
        query = query.filter(Lead.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(Lead.created_at <= datetime.strptime(date_to + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
    if search:
        s = f'%{search}%'
        query = query.filter(
            Lead.contact_name.ilike(s)    |
            Lead.company_name.ilike(s)    |
            Lead.phone.ilike(s)           |
            Lead.alternate_mobile.ilike(s)|
            Lead.email.ilike(s)           |
            Lead.product_name.ilike(s)    |
            Lead.category.ilike(s)        |
            Lead.product_range.ilike(s)   |
            Lead.source.ilike(s)          |
            Lead.city.ilike(s)            |
            Lead.state.ilike(s)           |
            Lead.country.ilike(s)         |
            Lead.zip_code.ilike(s)        |
            Lead.address.ilike(s)         |
            Lead.position.ilike(s)        |
            Lead.title.ilike(s)           |
            Lead.tags.ilike(s)            |
            Lead.remark.ilike(s)          |
            Lead.notes.ilike(s)           |
            Lead.lost_reason.ilike(s)     |
            Lead.requirement_spec.ilike(s)|
            Lead.order_quantity.ilike(s)  |
            Lead.code.ilike(s)
        )

    # Sort
    # Map frontend sort names to actual DB columns
    sort_map = {
        'name':    'contact_name',
        'mobile':  'phone',
        'company': 'company_name',
    }
    actual_sort = sort_map.get(sort_by, sort_by)
    sort_col = getattr(Lead, actual_sort, Lead.created_at)
    if sort_dir == 'asc':
        query = query.order_by(sort_col.asc())
    else:
        query = query.order_by(sort_col.desc())

    all_leads = query.all()

    counts = {
        'open':       Lead.query.filter_by(status='open').count(),
        'in_process': Lead.query.filter_by(status='in_process').count(),
        'close':      Lead.query.filter_by(status='close').count(),
        'cancel':     Lead.query.filter_by(status='cancel').count(),
    }

    # Filter options
    all_sources   = [r[0] for r in db.session.query(Lead.source).distinct().all() if r[0]]
    all_categories= [r[0] for r in db.session.query(Lead.category).distinct().all() if r[0]]
    all_ranges    = [r[0] for r in db.session.query(Lead.product_range).distinct().all() if r[0]]
    all_cities    = [r[0] for r in db.session.query(Lead.city).distinct().all() if r[0]]
    all_users     = User.query.filter_by(is_active=True).all()
    grid_cols     = get_grid_columns('leads', LEAD_COLS_DEFAULT, list(LEAD_COLS_ALL.keys()))

    return render_template('crm/leads/leads.html',
        leads=all_leads, counts=counts, all_users=all_users,
        status=status, search=search,
        source=source, category=category, p_range=p_range,
        city=city, date_from=date_from, date_to=date_to,
        sort_by=sort_by, sort_dir=sort_dir,
        all_sources=all_sources, all_categories=all_categories,
        all_ranges=all_ranges, all_cities=all_cities,
        grid_cols=grid_cols, all_cols=LEAD_COLS_ALL,
        active_page='leads')




@crm.route('/leads/export')
@login_required
def leads_export():
    """Export filtered leads to Excel with ALL fields."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    import io

    # ── Apply same filters as leads list ──
    status   = request.args.get('status', '')
    search   = request.args.get('search', '')
    source   = request.args.get('source', '')
    category = request.args.get('category', '')
    p_range  = request.args.get('product_range', '')
    city     = request.args.get('city', '')
    date_from= request.args.get('date_from', '')
    date_to  = request.args.get('date_to', '')
    sort_by  = request.args.get('sort_by', 'created_at')
    sort_dir = request.args.get('sort_dir', 'desc')

    query = Lead.query
    if status:   query = query.filter_by(status=status)
    if source:   query = query.filter_by(source=source)
    if category: query = query.filter_by(category=category)
    if p_range:  query = query.filter_by(product_range=p_range)
    if city:     query = query.filter(Lead.city.ilike(f'%{city}%'))
    if date_from:
        query = query.filter(Lead.created_at >= datetime.strptime(date_from, '%Y-%m-%d'))
    if date_to:
        query = query.filter(Lead.created_at <= datetime.strptime(date_to + ' 23:59:59', '%Y-%m-%d %H:%M:%S'))
    if search:
        s = f'%{search}%'
        query = query.filter(
            Lead.contact_name.ilike(s)    | Lead.company_name.ilike(s)    |
            Lead.phone.ilike(s)           | Lead.alternate_mobile.ilike(s)|
            Lead.email.ilike(s)           | Lead.product_name.ilike(s)    |
            Lead.category.ilike(s)        | Lead.product_range.ilike(s)   |
            Lead.source.ilike(s)          | Lead.city.ilike(s)            |
            Lead.state.ilike(s)           | Lead.country.ilike(s)         |
            Lead.zip_code.ilike(s)        | Lead.address.ilike(s)         |
            Lead.position.ilike(s)        | Lead.title.ilike(s)           |
            Lead.tags.ilike(s)            | Lead.remark.ilike(s)          |
            Lead.notes.ilike(s)           | Lead.lost_reason.ilike(s)     |
            Lead.requirement_spec.ilike(s)| Lead.order_quantity.ilike(s)  |
            Lead.code.ilike(s)
        )
    sort_map = {'name': 'contact_name', 'mobile': 'phone', 'company': 'company_name'}
    actual_sort = sort_map.get(sort_by, sort_by)
    sort_col = getattr(Lead, actual_sort, Lead.created_at)
    query = query.order_by(sort_col.asc() if sort_dir == 'asc' else sort_col.desc())
    leads_data = query.all()

    # User lookup for assigned_to / created_by
    from models.user import User as UserModel
    users = {u.id: u.full_name for u in UserModel.query.all()}

    # ── Build Excel ──
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Leads"

    # Header style
    hdr_fill = PatternFill("solid", fgColor="1E3A5F")
    hdr_font = Font(bold=True, color="FFFFFF", size=10)
    hdr_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    thin = Side(style="thin", color="D0D7E2")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    # All columns definition: (Header Label, field_getter)
    COLUMNS = [
        ("Lead Code",        lambda l: l.code or ''),
        ("Title",            lambda l: l.title or ''),
        ("Contact Name",     lambda l: l.contact_name or ''),
        ("Company",          lambda l: l.company_name or ''),
        ("Position",         lambda l: l.position or ''),
        ("Email",            lambda l: l.email or ''),
        ("Mobile",           lambda l: l.phone or ''),
        ("Alternate Mobile", lambda l: l.alternate_mobile or ''),
        ("Website",          lambda l: l.website or ''),
        ("Address",          lambda l: l.address or ''),
        ("City",             lambda l: l.city or ''),
        ("State",            lambda l: l.state or ''),
        ("Country",          lambda l: l.country or ''),
        ("Zip Code",         lambda l: l.zip_code or ''),
        ("Source",           lambda l: l.source or ''),
        ("Category",         lambda l: l.category or ''),
        ("Product Range",    lambda l: l.product_range or ''),
        ("Product Name",     lambda l: l.product_name or ''),
        ("Order Quantity",   lambda l: l.order_quantity or ''),
        ("Requirement Spec", lambda l: l.requirement_spec or ''),
        ("Status",           lambda l: (l.status or '').replace('_', ' ').title()),
        ("Priority",         lambda l: (l.priority or '').title()),
        ("Expected Value",   lambda l: float(l.expected_value) if l.expected_value else ''),
        ("Average Cost",     lambda l: float(l.average_cost) if l.average_cost else ''),
        ("Tags",             lambda l: l.tags or ''),
        ("Remark",           lambda l: l.remark or ''),
        ("Notes",            lambda l: l.notes or ''),
        ("Lost Reason",      lambda l: l.lost_reason or ''),
        ("Assigned To",      lambda l: users.get(l.assigned_to, '') if l.assigned_to else ''),
        ("Follow Up Date",   lambda l: l.follow_up_date.strftime('%d-%m-%Y') if l.follow_up_date else ''),
        ("Last Contact",     lambda l: l.last_contact.strftime('%d-%m-%Y %H:%M') if l.last_contact else ''),
        ("Created By",       lambda l: users.get(l.created_by, '') if l.created_by else ''),
        ("Created At",       lambda l: l.created_at.strftime('%d-%m-%Y %H:%M') if l.created_at else ''),
        ("Updated At",       lambda l: l.updated_at.strftime('%d-%m-%Y %H:%M') if l.updated_at else ''),
    ]

    # Write header row
    ws.row_dimensions[1].height = 32
    for col_idx, (label, _) in enumerate(COLUMNS, 1):
        cell = ws.cell(row=1, column=col_idx, value=label)
        cell.font    = hdr_font
        cell.fill    = hdr_fill
        cell.alignment = hdr_align
        cell.border  = border

    # Write data rows
    alt_fill = PatternFill("solid", fgColor="F0F4FA")
    data_font = Font(size=9)
    data_align = Alignment(vertical="center", wrap_text=False)

    for row_idx, lead in enumerate(leads_data, 2):
        row_fill = alt_fill if row_idx % 2 == 0 else None
        ws.row_dimensions[row_idx].height = 18
        for col_idx, (_, getter) in enumerate(COLUMNS, 1):
            try:
                val = getter(lead)
            except Exception:
                val = ''
            cell = ws.cell(row=row_idx, column=col_idx, value=val)
            cell.font      = data_font
            cell.alignment = data_align
            cell.border    = border
            if row_fill:
                cell.fill = row_fill

    # Auto column widths
    for col_idx in range(1, len(COLUMNS) + 1):
        col_letter = get_column_letter(col_idx)
        max_len = 10
        for row in ws.iter_rows(min_col=col_idx, max_col=col_idx):
            for cell in row:
                try:
                    if cell.value:
                        max_len = max(max_len, min(len(str(cell.value)), 40))
                except:
                    pass
        ws.column_dimensions[col_letter].width = max_len + 2

    # Freeze header row
    ws.freeze_panes = "A2"

    # Filter info sheet
    ws2 = wb.create_sheet("Filter Info")
    ws2.column_dimensions['A'].width = 20
    ws2.column_dimensions['B'].width = 40
    info_rows = [
        ("Exported At",    datetime.now().strftime('%d-%m-%Y %H:%M:%S')),
        ("Total Records",  len(leads_data)),
        ("Status Filter",  status or 'All'),
        ("Search",         search or '—'),
        ("Source",         source or 'All'),
        ("Category",       category or 'All'),
        ("Product Range",  p_range or 'All'),
        ("City",           city or 'All'),
        ("Date From",      date_from or '—'),
        ("Date To",        date_to or '—'),
        ("Sort By",        sort_by),
        ("Sort Direction", 'Ascending' if sort_dir == 'asc' else 'Descending'),
    ]
    for r, (k, v) in enumerate(info_rows, 1):
        ws2.cell(row=r, column=1, value=k).font = Font(bold=True)
        ws2.cell(row=r, column=2, value=str(v))

    # Output
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    fname = f"leads_export_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx"
    return send_file(buf, mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                     as_attachment=True, download_name=fname)


@crm.route('/leads/grid-config', methods=['POST'])
@login_required
def lead_grid_config():
    cols = request.json.get('cols', [])
    save_grid_columns('leads', cols)
    return jsonify(success=True)


@crm.route('/leads/<int:id>/update-status', methods=['POST'])
@login_required
def lead_update_status(id):
    """Kanban drag-drop status update"""
    lead = Lead.query.get_or_404(id)
    data = request.get_json()
    new_status = data.get('status', '').strip()
    valid = {'open', 'in_process', 'close', 'cancel'}
    if new_status not in valid:
        return jsonify(success=False, error='Invalid status'), 400
    old_status = lead.status
    lead.status = new_status
    lead.updated_at = datetime.now()
    log_activity(id, f'Status changed: {old_status} → {new_status}')
    audit('leads','KANBAN', id, f'{lead.code} / {lead.contact_name}', f'Kanban: {old_status} → {new_status}')
    lead.modified_by = current_user.id
    db.session.commit()
    return jsonify(success=True, id=id, status=new_status)



@crm.route('/leads/add', methods=['GET', 'POST'])
@login_required
def lead_add():
    if request.method == 'POST':
        # Get team members
        team_ids = request.form.getlist('team_members[]')
        team_str = ','.join(team_ids) if team_ids else ''

        pname = request.form.get('name', '').strip()
        l = Lead(
            code             = gen_code(Lead, 'LD'),
            contact_name     = pname,
            title            = request.form.get('product_name', pname).strip() or pname,
            position         = request.form.get('position', '').strip(),
            email            = request.form.get('email', '').strip(),
            website          = request.form.get('website', '').strip(),
            phone            = request.form.get('mobile', '').strip(),
            alternate_mobile = request.form.get('alternate_mobile', '').strip(),
            company_name     = request.form.get('company', '').strip(),
            address          = request.form.get('address', '').strip(),
            city             = request.form.get('city', '').strip(),
            state            = request.form.get('state', '').strip(),
            country          = request.form.get('country', 'India').strip(),
            zip_code         = request.form.get('zip_code', '').strip(),
            average_cost     = request.form.get('average_cost') or 0,
            product_name     = request.form.get('product_name', '').strip(),
            category         = request.form.get('category', '').strip(),
            product_range    = request.form.get('product_range', '').strip(),
            order_quantity   = request.form.get('order_quantity', '').strip(),
            requirement_spec = request.form.get('requirement_spec', '').strip(),
            tags             = request.form.get('tags', '').strip(),
            remark           = request.form.get('remark', '').strip(),
            source           = request.form.get('source', '').strip(),
            status           = request.form.get('status', 'open'),
            follow_up_date   = datetime.strptime(request.form['follow_up_date'], '%Y-%m-%d').date()
                               if request.form.get('follow_up_date') else None,
            team_members     = team_str,
            client_id        = request.form.get('client_id') or None,
            created_by       = current_user.id
        )
        db.session.add(l)
        db.session.flush()
        log_activity(l.id, 'New Lead Added')
        db.session.commit()
        flash(f'Lead {l.code} added!', 'success')
        return redirect(url_for('crm.lead_view', id=l.id))

    clients      = ClientMaster.query.filter_by(status='active').order_by(ClientMaster.contact_name).all()
    all_users    = User.query.filter_by(is_active=True).all()
    lead_statuses  = LeadStatus.query.filter_by(is_active=True).order_by(LeadStatus.sort_order).all()
    lead_sources   = LeadSource.query.filter_by(is_active=True).order_by(LeadSource.sort_order).all()
    lead_categories= LeadCategory.query.filter_by(is_active=True).order_by(LeadCategory.sort_order).all()
    product_ranges = ProductRange.query.filter_by(is_active=True).order_by(ProductRange.sort_order).all()
    return render_template('crm/leads/lead_form.html', lead=None, clients=clients,
                           all_users=all_users, lead_statuses=lead_statuses,
                           lead_sources=lead_sources, lead_categories=lead_categories,
                           product_ranges=product_ranges, active_page='leads')


@crm.route('/leads/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def lead_edit(id):
    l = Lead.query.get_or_404(id)
    if request.method == 'POST':
        team_ids = request.form.getlist('team_members[]')
        team_str = ','.join(team_ids) if team_ids else ''
        from audit_helper import model_to_dict
        _old_snap = model_to_dict(l)

        l.contact_name     = request.form.get('name', '').strip()
        l.title            = request.form.get('product_name', l.contact_name).strip() or l.contact_name
        l.position         = request.form.get('position', '').strip()
        l.email            = request.form.get('email', '').strip()
        l.website          = request.form.get('website', '').strip()
        l.phone            = request.form.get('mobile', '').strip()
        l.alternate_mobile = request.form.get('alternate_mobile', '').strip()
        l.company_name     = request.form.get('company', '').strip()
        l.address          = request.form.get('address', '').strip()
        l.city             = request.form.get('city', '').strip()
        l.state            = request.form.get('state', '').strip()
        l.country          = request.form.get('country', 'India').strip()
        l.zip_code         = request.form.get('zip_code', '').strip()
        l.average_cost     = request.form.get('average_cost') or 0
        l.product_name     = request.form.get('product_name', '').strip()
        l.category         = request.form.get('category', '').strip()
        l.product_range    = request.form.get('product_range', '').strip()
        l.order_quantity   = request.form.get('order_quantity', '').strip()
        l.requirement_spec = request.form.get('requirement_spec', '').strip()
        l.tags             = request.form.get('tags', '').strip()
        l.remark           = request.form.get('remark', '').strip()
        l.source           = request.form.get('source', '').strip()
        l.status           = request.form.get('status', 'open')
        l.follow_up_date   = None  # removed from form
        l.team_members     = team_str
        l.client_id        = request.form.get('client_id') or None
        l.updated_at       = datetime.utcnow()

        log_activity(l.id, f'Lead Record Updated')
        db.session.commit()
        flash('Lead updated!', 'success')
        return redirect(url_for('crm.lead_view', id=l.id))

    clients        = ClientMaster.query.filter_by(status='active').order_by(ClientMaster.contact_name).all()
    all_users      = User.query.filter_by(is_active=True).all()
    lead_statuses  = LeadStatus.query.filter_by(is_active=True).order_by(LeadStatus.sort_order).all()
    lead_sources   = LeadSource.query.filter_by(is_active=True).order_by(LeadSource.sort_order).all()
    lead_categories= LeadCategory.query.filter_by(is_active=True).order_by(LeadCategory.sort_order).all()
    product_ranges = ProductRange.query.filter_by(is_active=True).order_by(ProductRange.sort_order).all()
    return render_template('crm/leads/lead_form.html', lead=l, clients=clients,
                           all_users=all_users, lead_statuses=lead_statuses,
                           lead_sources=lead_sources, lead_categories=lead_categories,
                           product_ranges=product_ranges, active_page='leads')


@crm.route('/leads/<int:id>/delete', methods=['POST'])
@login_required
def lead_delete(id):
    l = Lead.query.get_or_404(id)
    name = l.contact_name
    db.session.delete(l)
    db.session.commit()
    flash(f'Lead "{name}" deleted!', 'success')
    return redirect(url_for('crm.leads'))


@crm.route('/leads/<int:id>')
@login_required
def lead_view(id):
    l           = Lead.query.get_or_404(id)
    tab         = request.args.get('tab', 'overview')
    discussions = LeadDiscussion.query.filter_by(lead_id=id).order_by(LeadDiscussion.created_at.desc()).all()
    reminders   = LeadReminder.query.filter_by(lead_id=id).order_by(LeadReminder.remind_at).all()
    notes_list  = LeadNote.query.filter_by(lead_id=id, user_id=current_user.id).order_by(LeadNote.created_at.desc()).all()
    activity    = LeadActivityLog.query.filter_by(lead_id=id).order_by(LeadActivityLog.created_at.desc()).all()
    attachments = LeadAttachment.query.filter_by(lead_id=id).order_by(LeadAttachment.created_at.desc()).all()
    team_members = l.get_team_member_objects()
    all_users   = User.query.filter_by(is_active=True).all()
    audit('leads','VIEW', id, f'{l.code} / {l.contact_name}', obj=l)
    return render_template('crm/leads/lead_view.html',
        lead=l, tab=tab,
        discussions=discussions, reminders=reminders,
        notes_list=notes_list, activity=activity,
        attachments=attachments, team_members=team_members,
        all_users=all_users,
        now=datetime.utcnow(),
        active_page='leads')


# ── Discussion Board ──

@crm.route('/leads/<int:id>/discussion/add', methods=['POST'])
@login_required
def lead_discussion_add(id):
    l       = Lead.query.get_or_404(id)
    comment = request.form.get('comment', '').strip()
    if not comment:
        flash('Comment cannot be empty!', 'warning')
        return redirect(url_for('crm.lead_view', id=id, tab='discussion'))

    disc = LeadDiscussion(
        lead_id    = id,
        user_id    = current_user.id,
        comment    = comment,
        created_at = datetime.utcnow()
    )
    db.session.add(disc)
    db.session.flush()

    # Handle file attachments
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    files = request.files.getlist('attachments[]')
    for f in files:
        if f and f.filename and allowed_file(f.filename):
            fname = secure_filename(f.filename)
            fpath = os.path.join(UPLOAD_FOLDER, fname)
            f.save(fpath)
            att = LeadAttachment(
                lead_id       = id,
                discussion_id = disc.id,
                file_name     = fname,
                file_path     = f'uploads/{fname}',
                file_type     = f.content_type,
                uploaded_by   = current_user.id
            )
            db.session.add(att)

    # Update last contact
    l.last_contact = datetime.utcnow()
    log_activity(id, 'New Comment Added in Lead')
    db.session.commit()
    audit('leads','DISCUSSION', id, f'Lead #{id}', f'Comment added by {current_user.username}')
    flash('Comment added!', 'success')
    return redirect(url_for('crm.lead_view', id=id, tab='discussion'))


# ── Reminders (Followup) ──

@crm.route('/leads/<int:id>/reminder/add', methods=['POST'])
@login_required
def lead_reminder_add(id):
    Lead.query.get_or_404(id)
    title      = request.form.get('title', '').strip()
    remind_str = request.form.get('remind_at', '')
    if not title or not remind_str:
        flash('Title and reminder date/time required!', 'warning')
        return redirect(url_for('crm.lead_view', id=id, tab='reminder'))

    try:
        remind_dt = datetime.strptime(remind_str, '%Y-%m-%dT%H:%M')
    except:
        remind_dt = datetime.strptime(remind_str, '%Y-%m-%d %H:%M')

    r = LeadReminder(
        lead_id     = id,
        user_id     = current_user.id,
        title       = title,
        description = request.form.get('description', '').strip(),
        remind_at   = remind_dt
    )
    db.session.add(r)
    log_activity(id, f'Reminder set: {title}')
    db.session.commit()
    audit('leads','REMINDER', id, f'Lead #{id}', f'Reminder set: {title}')
    flash('Reminder added!', 'success')
    return redirect(url_for('crm.lead_view', id=id, tab='reminder'))


@crm.route('/leads/reminder/<int:rid>/done', methods=['POST'])
@login_required
def lead_reminder_done(rid):
    r = LeadReminder.query.get_or_404(rid)
    r.is_done = not r.is_done
    db.session.commit()
    return redirect(url_for('crm.lead_view', id=r.lead_id, tab='reminder'))


@crm.route('/leads/reminder/<int:rid>/delete', methods=['POST'])
@login_required
def lead_reminder_delete(rid):
    r = LeadReminder.query.get_or_404(rid)
    lid = r.lead_id
    db.session.delete(r)
    db.session.commit()
    flash('Reminder deleted!', 'success')
    return redirect(url_for('crm.lead_view', id=lid, tab='reminder'))


# ── Personal Notes ──

@crm.route('/leads/<int:id>/note/add', methods=['POST'])
@login_required
def lead_note_add(id):
    Lead.query.get_or_404(id)
    note_text = request.form.get('note', '').strip()
    if not note_text:
        flash('Note cannot be empty!', 'warning')
        return redirect(url_for('crm.lead_view', id=id, tab='notes'))

    n = LeadNote(lead_id=id, user_id=current_user.id, note=note_text)
    db.session.add(n)
    db.session.commit()
    audit('leads','NOTE', id, f'Lead #{id}', f'Note added by {current_user.username}')
    flash('Note saved!', 'success')
    return redirect(url_for('crm.lead_view', id=id, tab='notes'))


@crm.route('/leads/note/<int:nid>/delete', methods=['POST'])
@login_required
def lead_note_delete(nid):
    n = LeadNote.query.get_or_404(nid)
    lid = n.lead_id
    db.session.delete(n)
    db.session.commit()
    flash('Note deleted!', 'success')
    return redirect(url_for('crm.lead_view', id=lid, tab='notes'))


# ── Status Change ──

@crm.route('/leads/<int:id>/status', methods=['POST'])
@login_required
def lead_status_change(id):
    l = Lead.query.get_or_404(id)
    new_status = request.form.get('status')
    if new_status in ['open', 'in_process', 'close', 'cancel']:
        old = l.status
        l.status = new_status
        log_activity(id, f'Status changed: {old} → {new_status}')
        db.session.commit()
    return redirect(url_for('crm.lead_view', id=id))


# ══════════════════════════════════════
# LEGACY CUSTOMER ROUTES (kept)
# ══════════════════════════════════════

@crm.route('/customers')
@login_required
def customers():
    return redirect(url_for('crm.clients'))


@crm.route('/customers/add')
@login_required
def customer_add():
    return redirect(url_for('crm.client_add'))


# ══════════════════════════════════════
# DASHBOARD API (JSON for Charts)
# ══════════════════════════════════════

@crm.route('/api/dashboard-stats')
@login_required
def dashboard_stats():
    from sqlalchemy import func, extract
    from datetime import datetime, timedelta

    # Monthly lead counts (last 6 months)
    monthly = []
    for i in range(5, -1, -1):
        dt = datetime.utcnow().replace(day=1) - timedelta(days=i*30)
        m, y = dt.month, dt.year
        count = Lead.query.filter(
            extract('month', Lead.created_at) == m,
            extract('year', Lead.created_at) == y
        ).count()
        monthly.append({'month': dt.strftime('%b %Y'), 'count': count})

    # Status distribution
    status_data = [
        {'label': 'Open',       'value': Lead.query.filter_by(status='open').count(),       'color': '#94a3b8'},
        {'label': 'In Process', 'value': Lead.query.filter_by(status='in_process').count(), 'color': '#1e2d5e'},
        {'label': 'Close',      'value': Lead.query.filter_by(status='close').count(),      'color': '#0d9488'},
        {'label': 'Cancel',     'value': Lead.query.filter_by(status='cancel').count(),     'color': '#ef4444'},
    ]

    # Source wise
    sources = db.session.query(Lead.source, func.count(Lead.id)).group_by(Lead.source).all()
    source_data = [{'label': s or 'Unknown', 'value': c} for s, c in sources]

    # Category wise
    cats = db.session.query(Lead.category, func.count(Lead.id)).group_by(Lead.category).all()
    cat_data = [{'label': c or 'N/A', 'value': cnt} for c, cnt in cats]

    # Product range wise
    ranges = db.session.query(Lead.product_range, func.count(Lead.id)).group_by(Lead.product_range).all()
    range_data = [{'label': r or 'N/A', 'value': c} for r, c in ranges]

    # Recent activity - last 7 days leads
    week_data = []
    for i in range(6, -1, -1):
        d = datetime.utcnow().date() - timedelta(days=i)
        c = Lead.query.filter(func.date(Lead.created_at) == d).count()
        week_data.append({'day': d.strftime('%a'), 'count': c})

    return jsonify({
        'monthly': monthly,
        'status': status_data,
        'sources': source_data,
        'categories': cat_data,
        'ranges': range_data,
        'week': week_data,
    })


# ══════════════════════════════════════
# LEAD IMPORT (CSV / Excel)
# ══════════════════════════════════════

@crm.route('/leads/import', methods=['GET', 'POST'])
@login_required
def lead_import():
    if request.method == 'POST':
        import csv, io
        f = request.files.get('import_file')
        if not f or not f.filename:
            flash('Please select a file!', 'warning')
            return redirect(url_for('crm.lead_import'))

        ext = f.filename.rsplit('.', 1)[-1].lower()
        added = 0
        errors = []

        try:
            if ext == 'csv':
                content = f.read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)
            elif ext in ('xls', 'xlsx'):
                import openpyxl
                wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
                ws = wb.active
                headers = [str(c.value).strip() if c.value else '' for c in next(ws.iter_rows(min_row=1, max_row=1))]
                rows = []
                for row in ws.iter_rows(min_row=2, values_only=True):
                    rows.append(dict(zip(headers, [str(v).strip() if v is not None else '' for v in row])))
            else:
                flash('Only CSV and Excel (.xlsx) files allowed!', 'danger')
                return redirect(url_for('crm.lead_import'))

            for i, row in enumerate(rows, 2):
                name = (row.get('name') or row.get('Name') or '').strip()
                if not name:
                    errors.append(f'Row {i}: Name is required')
                    continue
                try:
                    l = Lead(
                        code             = gen_code(Lead, 'LD'),
                        contact_name     = name,
                        position         = row.get('position') or row.get('Position') or '',
                        email            = row.get('email') or row.get('Email') or '',
                        phone            = row.get('mobile') or row.get('Mobile') or '',
                        alternate_mobile = row.get('alternate_mobile') or row.get('Alternate Mobile') or '',
                        company_name     = row.get('company') or row.get('Company') or '',
                        website          = row.get('website') or row.get('Website') or '',
                        city             = row.get('city') or row.get('City') or '',
                        state            = row.get('state') or row.get('State') or '',
                        country          = row.get('country') or row.get('Country') or 'India',
                        zip_code         = row.get('zip_code') or row.get('Zip Code') or '',
                        product_name     = row.get('product_name') or row.get('Product Name') or '',
                        category         = row.get('category') or row.get('Category') or '',
                        product_range    = row.get('product_range') or row.get('Product Range') or '',
                        source           = row.get('source') or row.get('Source') or '',
                        status           = row.get('status') or row.get('Status') or 'open',
                        requirement_spec = row.get('requirement_spec') or row.get('Requirement Specification') or '',
                        remark           = row.get('remark') or row.get('Remark') or '',
                        tags             = row.get('tags') or row.get('Tags') or '',
                        created_by       = current_user.id
                    )
                    # Validate status
                    if l.status.lower() not in ['open','in_process','close','cancel']:
                        l.status = 'open'
                    db.session.add(l)
                    db.session.flush()
                    log_activity(l.id, 'Lead Imported via CSV/Excel')
                    added += 1
                except Exception as e:
                    errors.append(f'Row {i}: {str(e)}')

            db.session.commit()
            flash(f'✅ {added} leads imported successfully!{(" ⚠️ " + str(len(errors)) + " rows had errors.") if errors else ""}', 'success')
            if errors:
                for e in errors[:5]:
                    flash(e, 'warning')

        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}', 'danger')

        return redirect(url_for('crm.leads'))

    return render_template('crm/leads/lead_import.html', active_page='leads')


@crm.route('/leads/import/template')
@login_required
def lead_import_template():
    import csv, io
    from flask import Response
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['name','position','email','mobile','alternate_mobile','company','website',
                     'city','state','country','zip_code','product_name','category',
                     'product_range','source','status','requirement_spec','remark','tags'])
    writer.writerow(['John Doe','CEO','john@example.com','9999999999','','ABC Corp','www.abc.com',
                     'Mumbai','Maharashtra','India','400001','Face Wash','Skin Care','Premium',
                     'HCP Website','open','Vitamin C face wash 500ml','Premium product needed','skincare'])
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=lead_import_template.csv'}
    )


# ══════════════════════════════════════
# CLIENT IMPORT (CSV / Excel)
# ══════════════════════════════════════

@crm.route('/clients/import', methods=['GET', 'POST'])
@login_required
def client_import():
    if request.method == 'POST':
        import csv, io
        f = request.files.get('import_file')
        if not f or not f.filename:
            flash('Please select a file!', 'warning')
            return redirect(url_for('crm.client_import'))

        ext = f.filename.rsplit('.', 1)[-1].lower()
        added = 0
        errors = []

        try:
            if ext == 'csv':
                content = f.read().decode('utf-8-sig')
                reader = csv.DictReader(io.StringIO(content))
                rows = list(reader)
            elif ext in ('xls', 'xlsx'):
                import openpyxl
                wb = openpyxl.load_workbook(f, read_only=True, data_only=True)
                ws = wb.active
                headers = [str(c.value).strip() if c.value else '' for c in next(ws.iter_rows(min_row=1, max_row=1))]
                rows = []
                for row in ws.iter_rows(min_row=2, values_only=True):
                    rows.append(dict(zip(headers, [str(v).strip() if v is not None else '' for v in row])))
            else:
                flash('Only CSV and Excel (.xlsx) files allowed!', 'danger')
                return redirect(url_for('crm.client_import'))

            for i, row in enumerate(rows, 2):
                name = (row.get('contact_name') or row.get('Contact Name') or '').strip()
                if not name:
                    errors.append(f'Row {i}: Contact Name required')
                    continue
                try:
                    c = ClientMaster(
                        code             = gen_code(ClientMaster, 'CLT'),
                        contact_name     = name,
                        position         = row.get('position') or row.get('Position') or '',
                        company_name     = row.get('company_name') or row.get('Company Name') or '',
                        email            = row.get('email') or row.get('Email') or '',
                        phone            = row.get('mobile') or row.get('Mobile') or '',
                        alternate_mobile = row.get('alternate_mobile') or row.get('Alternate Mobile') or '',
                        website          = row.get('website') or row.get('Website') or '',
                        city             = row.get('city') or row.get('City') or '',
                        state            = row.get('state') or row.get('State') or '',
                        country          = row.get('country') or row.get('Country') or 'India',
                        zip_code         = row.get('zip_code') or row.get('Zip Code') or '',
                        gstin            = row.get('gstin') or row.get('GSTIN') or '',
                        client_type      = row.get('client_type') or row.get('Client Type') or 'regular',
                        status           = 'active',
                        created_by       = current_user.id
                    )
                    db.session.add(c)
                    db.session.flush()
                    # Brands from import
                    brands_str = row.get('brands') or row.get('Brands') or ''
                    if brands_str:
                        for b in brands_str.split('|'):
                            b = b.strip()
                            if b:
                                db.session.add(ClientBrand(client_id=c.id, brand_name=b))
                    added += 1
                except Exception as e:
                    errors.append(f'Row {i}: {str(e)}')

            db.session.commit()
            flash(f'✅ {added} clients imported!{(" ⚠️ " + str(len(errors)) + " errors.") if errors else ""}', 'success')

        except Exception as e:
            db.session.rollback()
            flash(f'Import failed: {str(e)}', 'danger')

        return redirect(url_for('crm.clients'))

    return render_template('crm/clients/client_import.html', active_page='clients')


@crm.route('/clients/import/template')
@login_required
def client_import_template():
    import csv, io
    from flask import Response
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['contact_name','position','company_name','email','mobile','alternate_mobile',
                     'website','gstin','city','state','country','zip_code','client_type','brands'])
    writer.writerow(['Jane Doe','CEO','ABC Corp','jane@abc.com','9999999999','','www.abc.com',
                     '27ABCDE1234F1Z5','Mumbai','Maharashtra','India','400001','regular','Brand A|Brand B'])
    return Response(
        output.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=client_import_template.csv'}
    )



# ══════════════════════════════════════
# CRM DASHBOARD
# ══════════════════════════════════════

@crm.route('/dashboard')
@login_required
def crm_dashboard():
    from models import LeadReminder
    lead_counts = {
        'open':       Lead.query.filter_by(status='open').count(),
        'in_process': Lead.query.filter_by(status='in_process').count(),
        'close':      Lead.query.filter_by(status='close').count(),
        'cancel':     Lead.query.filter_by(status='cancel').count(),
        'total':      Lead.query.count(),
    }
    total_clients     = ClientMaster.query.count()
    recent_leads      = Lead.query.order_by(Lead.created_at.desc()).limit(5).all()
    upcoming_reminders = LeadReminder.query.filter(
        LeadReminder.is_done == False,
        LeadReminder.remind_at >= datetime.utcnow()
    ).order_by(LeadReminder.remind_at).limit(5).all()

    return render_template('crm/dashboard/index.html',
        active_page='crm_dashboard',
        lead_counts=lead_counts,
        total_clients=total_clients,
        recent_leads=recent_leads,
        upcoming_reminders=upcoming_reminders,
        now=datetime.utcnow())


# ══════════════════════════════════════
# NOTIFICATION API — Reminder Alerts
# ══════════════════════════════════════

@crm.route('/api/due-reminders')
@login_required
def api_due_reminders():
    """
    Returns reminders due in next 5 min OR overdue (not done yet).
    Uses IST (Asia/Kolkata = UTC+5:30) to match browser local time.
    """
    from datetime import timedelta, timezone
    # IST = UTC + 5:30
    IST = timezone(timedelta(hours=5, minutes=30))
    now    = datetime.now(IST).replace(tzinfo=None)   # naive IST datetime
    window = now + timedelta(minutes=5)

    # Get pending reminders due within next 5 min or already overdue
    reminders = LeadReminder.query.filter(
        LeadReminder.is_done == False,
        LeadReminder.remind_at <= window
    ).all()

    results = []
    for r in reminders:
        lead = r.lead
        if not lead:
            continue

        # Check if current user should be notified
        should_notify = False

        # 1. User who set the reminder
        if r.user_id == current_user.id:
            should_notify = True

        # 2. Lead assigned to current user
        if lead.assigned_to == current_user.id:
            should_notify = True

        # 3. Current user is in team_members
        if lead.team_members:
            try:
                team_ids = [int(x) for x in lead.team_members.split(',') if x.strip()]
                if current_user.id in team_ids:
                    should_notify = True
            except Exception:
                pass

        # Admin sees all
        if current_user.role == 'admin':
            should_notify = True

        if should_notify:
            mins_left = int((r.remind_at - now).total_seconds() / 60)
            results.append({
                'id':        r.id,
                'title':     r.title,
                'lead_code': lead.code or '',
                'lead_name': lead.contact_name or '',
                'company':   lead.company_name or '',
                'remind_at': r.remind_at.strftime('%d %b %Y %I:%M %p'),
                'mins_left': mins_left,
                'overdue':   mins_left < 0,
                'lead_url':  f'/crm/leads/{lead.id}?tab=reminder',
            })

    return jsonify(reminders=results, server_time=now.strftime('%d-%m-%Y %H:%M:%S IST'))


@crm.route('/api/reminder/<int:rid>/snooze', methods=['POST'])
@login_required
def api_reminder_snooze(rid):
    """Snooze reminder by 5 minutes"""
    from datetime import timedelta
    r = LeadReminder.query.get_or_404(rid)
    r.remind_at = r.remind_at + timedelta(minutes=5)
    db.session.commit()
    return jsonify(success=True)


@crm.route('/api/reminder/<int:rid>/done', methods=['POST'])
@login_required
def api_reminder_mark_done(rid):
    """Mark reminder done via notification"""
    r = LeadReminder.query.get_or_404(rid)
    r.is_done = True
    db.session.commit()
    return jsonify(success=True)
