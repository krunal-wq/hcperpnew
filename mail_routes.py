"""
mail_routes.py
──────────────
Blueprint: mail at /mail

Routes:
  GET  /mail/master              — List all email templates
  GET  /mail/master/<code>/edit  — Edit template form
  POST /mail/master/<code>/edit  — Save template
  POST /mail/leads/<id>/send-npd — Send NPD email to lead
  GET  /mail/leads/<id>/preview-npd — Preview NPD email (modal)
"""

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from datetime             import datetime

from flask       import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app
from flask_login import login_required, current_user
from models      import db, Lead, EmailTemplate
from audit_helper import audit

mail_bp = Blueprint('mail', __name__, url_prefix='/mail')


# ── Default NPD template body ──
NPD_DEFAULT_BODY = """<div>Hello {client_name},</div><br /><br />
<div>I hope this email finds you well. I wanted to take this opportunity to provide you with important information and resources regarding our New Product Development (NPD) services at HCP Wellness Pvt. Ltd. We believe these details will be valuable to you.<br /><br />
You will find our comprehensive NPD Charges Chart. This chart outlines the costs associated with our various product development services. It will help you gain a clear understanding of the pricing structure and make informed decisions regarding your specific requirements.</div>
<br />
<div><strong>NPD Charges Chart &amp; Workings</strong></div><br />
<div>You will find our comprehensive NPD Charges Chart. This chart outlines the costs associated with our various product development services. It will help you gain a clear understanding of the pricing structure and make informed decisions regarding your specific requirements.</div>
<br />
<div>*Terms &amp; conditions will remain the same for all the products.</div>
<table style="border:solid 1px;border-collapse:collapse;" width="60%">
  <tr>
    <th style="border:solid 1px;padding:6px 8px;">Sr. No.</th>
    <th style="border:solid 1px;padding:6px 8px;">Particulars</th>
    <th style="border:solid 1px;padding:6px 8px;">Rate</th>
  </tr>
  <tr><td style="border:solid 1px;padding:6px 8px;"><strong>PLAN - 01</strong></td><td style="border:solid 1px;padding:6px 8px;">NPD Charge for R&amp;D of Single Product / Project / Sample Development with 1 Trial only.</td><td style="border:solid 1px;padding:6px 8px;"><strong>Rs. 3000/-</strong></td></tr>
  <tr><td style="border:solid 1px;padding:6px 8px;">Revision</td><td style="border:solid 1px;padding:6px 8px;">Revision of product/project/sample (As per T&amp;C Clause No. 2).</td><td style="border:solid 1px;padding:6px 8px;"><strong>Rs. 1000/-</strong></td></tr>
  <tr><td style="border:solid 1px;padding:6px 8px;"><strong>PLAN - 02</strong></td><td style="border:solid 1px;padding:6px 8px;">NPD Charge for R&amp;D of Single Product / Project / Sample Development with 5 Trials only.</td><td style="border:solid 1px;padding:6px 8px;"><strong>Rs. 8000/-</strong></td></tr>
  <tr><td style="border:solid 1px;padding:6px 8px;">Revision</td><td style="border:solid 1px;padding:6px 8px;">Revision of product/project/sample (As per T&amp;C Clause No. 2)</td><td style="border:solid 1px;padding:6px 8px;"><strong>Rs. 1000/-</strong></td></tr>
  <tr><td style="border:solid 1px;padding:6px 8px;">Extra Sample</td><td style="border:solid 1px;padding:6px 8px;">Additional Sample Cost (As per T&amp;C Clause No. 2)</td><td style="border:solid 1px;padding:6px 8px;"><strong>Rs. 300/-</strong></td></tr>
  <tr><td style="border:solid 1px;padding:6px 8px;">Lab Visit</td><td style="border:solid 1px;padding:6px 8px;">Working charges at the factory R&amp;D laboratory per person - per day.</td><td style="border:solid 1px;padding:6px 8px;"><strong>Rs. 3000/-</strong></td></tr>
  <tr><td style="border:solid 1px;padding:6px 8px;">Barcode</td><td style="border:solid 1px;padding:6px 8px;">Barcode Charges per product. (If Required)</td><td style="border:solid 1px;padding:6px 8px;"><strong>Rs. 2000/-</strong></td></tr>
  <tr><td style="border:solid 1px;padding:6px 8px;">FDA Permission</td><td style="border:solid 1px;padding:6px 8px;">FDA Product permission charge per product (Cosmetic)</td><td style="border:solid 1px;padding:6px 8px;"><strong>Rs. 2000/-</strong></td></tr>
  <tr><td style="border:solid 1px;padding:6px 8px;">Packing Design</td><td style="border:solid 1px;padding:6px 8px;">Depends on Design</td><td style="border:solid 1px;padding:6px 8px;"><strong>Rs. 5,000/- to Rs. 15,000/-</strong></td></tr>
  <tr><td style="border:solid 1px;padding:6px 8px;">Video Shooting</td><td style="border:solid 1px;padding:6px 8px;">Per Day Video Shoot</td><td style="border:solid 1px;padding:6px 8px;"><strong>Rs. 25000/-</strong></td></tr>
  <tr><td style="border:solid 1px;padding:6px 8px;">Courier Charges</td><td style="border:solid 1px;padding:6px 8px;">Inside India: Free of Cost<br/>Outside India: As per DHL / FedEx</td><td style="border:solid 1px;padding:6px 8px;"><strong>Rs. 2000/-</strong></td></tr>
</table>
<br />
<div>= = = = = = = = = = = = = = = = = = = = = = = = = = =</div><br />
<div><strong>Payment Links</strong></div><br />
<div>To facilitate a seamless payment process, we have provided payment links below: <a href="https://www.hcpwellness.in/our-bank-detail/"><strong>₹ Payment Link</strong></a> (Click to pay through Online / UPI / QR Code / Bank Details)</div>
<br />
<div>= = = = = = = = = = = = = = = = = = = = = = = = = = =</div><br />
<div><strong><u>Terms &amp; Conditions:</u></strong></div><br />
<div><strong>01. If any changes in NPD:</strong> Once the client submits the NPD form if the client needs to make any changes then it needs to be informed to the <strong>Client coordinator within 24hrs.</strong></div><br />
<div><strong>02. Sample Size &amp; Quantity:</strong> NPD product/project sample will be given only one (1) piece of 10gm/ml to 100gm/ml quantity. Extra quantity for every sample will be charged extra from the client.</div><br />
<div><strong>03. Payment terms &amp; method:</strong> The client has to pay the amount in <strong>advance via UPI / online</strong> before every process.</div><br />
<div><strong>04. Rates &amp; Costing:</strong> Rates may be shared before finalizing the product. The final rate is valid only for Thirty (30) days.</div><br />
<div><strong>05. Raw Material (RM):</strong> If any ingredients lead time to procure is high, NPD time might vary and it might also affect the commercial batch.</div><br />
<div><strong>06. Packaging Material (PM):</strong> Once the costing is confirmed, the client has to confirm whether the PM will be issued from their hand. Design cost may vary from <strong>Rs. 5,000/- to Rs. 15,000/-</strong></div><br />
<div><strong>07. Trademark:</strong> The client has to provide the trademark copy via mail. HCP Wellness will not be liable for any trademark issues.</div><br />
<div><strong>08. Formulation Ownership:</strong> We do not provide formulation information including percentages until a commercial order has been placed.</div><br />
<div><strong>09.</strong> All disputes shall be governed by the laws of the Court of Ahmedabad, Gujarat.</div><br /><br />
<div>We hope these resources will assist you in understanding our NPD services better. If you have any inquiries, please feel free to reach out to us.</div><br /><br />
<div>Thank you for your interest in HCP Wellness Pvt. Ltd. We appreciate the opportunity to serve you and look forward to potentially working together.</div><br /><br />
<div><strong>HCP Wellness Pvt. Ltd.</strong><br />
📱 <a href="https://wa.me/+919723455627"><strong>WhatsApp for quick communication</strong></a><br />
✉ info@hcpwellness.in | 🌐 www.hcpwellness.in</div>"""

NPD_DEFAULT_SUBJECT = "{company} - Request for proposal (RFP) for Skincare products"


def _get_or_create_npd_template():
    """Get NPD template from DB, create default if not exists."""
    t = EmailTemplate.query.filter_by(code='npd_project').first()
    if not t:
        t = EmailTemplate(
            code       = 'npd_project',
            name       = 'NPD Project Email',
            subject    = NPD_DEFAULT_SUBJECT,
            body       = NPD_DEFAULT_BODY,
            from_email = 'info@hcpwellness.in',
            from_name  = 'HCP Wellness Pvt. Ltd.',
            is_active  = True,
        )
        db.session.add(t)
        db.session.commit()
    return t


def _render_template_vars(text, lead):
    """Replace {variables} in subject/body with lead data."""
    return (text
        .replace('{client_name}',  lead.contact_name or '')
        .replace('{company}',      lead.company_name  or lead.contact_name or '')
        .replace('{email}',        lead.email         or '')
        .replace('{phone}',        lead.phone         or '')
        .replace('{product}',      lead.product_name  or '')
        .replace('{city}',         lead.city          or '')
        .replace('{lead_code}',    getattr(lead, 'code', '') or '')
    )


def _send_smtp(to_email, subject, html_body, from_email, from_name):
    """Send email via SMTP. Returns (success, error_msg)."""
    try:
        cfg = current_app.config
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From']    = f'{from_name} <{from_email}>'
        msg['To']      = to_email
        msg['Reply-To']= from_email
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        server = smtplib.SMTP(cfg['MAIL_SERVER'], cfg['MAIL_PORT'], timeout=15)
        server.ehlo()
        if cfg.get('MAIL_USE_TLS'):
            server.starttls()
        if cfg.get('MAIL_USERNAME') and cfg.get('MAIL_PASSWORD'):
            server.login(cfg['MAIL_USERNAME'], cfg['MAIL_PASSWORD'])
        server.sendmail(from_email, [to_email], msg.as_string())
        server.quit()
        return True, None
    except Exception as e:
        return False, str(e)


# ══════════════════════════════════════
# MAIL MASTER — List & Edit templates
# ══════════════════════════════════════

@mail_bp.route('/master')
@login_required
def mail_master():
    _get_or_create_npd_template()   # ensure default exists
    templates = EmailTemplate.query.order_by(EmailTemplate.name).all()
    return render_template('mail/master.html',
        templates=templates, active_page='mail_master')


@mail_bp.route('/master/<code>/edit', methods=['GET', 'POST'])
@login_required
def mail_template_edit(code):
    t = EmailTemplate.query.filter_by(code=code).first_or_404()

    if request.method == 'POST':
        t.name       = request.form.get('name', t.name).strip()
        t.subject    = request.form.get('subject', t.subject).strip()
        t.body       = request.form.get('body', t.body)
        t.from_email = request.form.get('from_email', t.from_email).strip()
        t.from_name  = request.form.get('from_name',  t.from_name).strip()
        t.is_active  = request.form.get('is_active') == '1'
        t.updated_by = current_user.id
        t.updated_at = datetime.utcnow()
        db.session.commit()
        audit('mail', 'EDIT', t.id, f'Template: {t.code}', obj=None)
        flash(f'✅ Template "{t.name}" saved successfully!', 'success')
        return redirect(url_for('mail.mail_master'))

    return render_template('mail/template_edit.html',
        t=t, active_page='mail_master')


# ══════════════════════════════════════
# SEND NPD EMAIL — from Lead
# ══════════════════════════════════════

@mail_bp.route('/leads/<int:id>/preview-npd')
@login_required
def lead_npd_preview(id):
    """Return rendered subject + body for modal preview."""
    lead = Lead.query.get_or_404(id)
    t    = _get_or_create_npd_template()
    return jsonify(
        subject    = _render_template_vars(t.subject, lead),
        body       = _render_template_vars(t.body,    lead),
        to_email   = lead.email or '',
        from_email = t.from_email,
        from_name  = t.from_name,
        template_name = t.name,
    )


@mail_bp.route('/leads/<int:id>/send-npd', methods=['POST'])
@login_required
def lead_send_npd(id):
    """Send NPD email to lead."""
    from models import LeadActivityLog
    lead = Lead.query.get_or_404(id)

    to_email   = request.form.get('to_email', '').strip()
    subject    = request.form.get('subject',  '').strip()
    body       = request.form.get('body',     '').strip()
    from_email = request.form.get('from_email', 'info@hcpwellness.in').strip()
    from_name  = request.form.get('from_name',  'HCP Wellness Pvt. Ltd.').strip()

    if not to_email:
        flash('❌ Email address required!', 'danger')
        return redirect(url_for('crm.lead_view', id=id))

    success, err = _send_smtp(to_email, subject, body, from_email, from_name)

    if success:
        db.session.add(LeadActivityLog(
            lead_id  = id,
            user_id  = current_user.id,
            action   = f'NPD Email sent to {to_email}',
        ))
        db.session.commit()
        audit('mail', 'SEND', id, f'NPD → {to_email}', obj=None)
        flash(f'✅ NPD Email sent successfully to {to_email}!', 'success')
    else:
        flash(f'❌ Email failed: {err}', 'danger')

    return redirect(url_for('crm.lead_view', id=id))
