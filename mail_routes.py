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


# ── Default Sample Order template body ──
SAMPLE_ORDER_DEFAULT_BODY = """\
<div style="font-family:Arial,sans-serif;font-size:14px;color:#222;">

<p>Dear <strong>{client_name}</strong>,</p>

<p>I hope this email finds you well. Thank you for choosing <strong>HCP Wellness Private Limited</strong> for your product needs.<br>
Please find the attached Sample Order <strong>{order_number}</strong> for your reference.</p>

{items_table}

<p>Please find the Sample Order PDF attached to this email.<br>
If you have any questions, feel free to reply to this email.</p>

<p>Thank you for your business!</p>

<p><strong>Warm regards,</strong><br>
{sender_name}<br>
HCP Wellness Private Limited</p>

</div>"""

SAMPLE_ORDER_DEFAULT_SUBJECT = "{company} - Sample Order #{order_number}"


# ── Default Quotation Email template ──
QUOTATION_DEFAULT_SUBJECT = "Final Quote for {company} - {quot_number}"

QUOTATION_DEFAULT_BODY = """<div style="font-family:Arial,sans-serif;font-size:14px;color:#333;">

<p>Dear <b>{client_name}</b>,</p>

<p>Hope this email finds you well.</p>

<p>Kindly find below the <b>final cost</b> for quote for {subject}.</p>

{items_table}

<b>Key highlights of the quotation:</b>
<ul style="margin:6px 0 12px 0;padding-left:20px;">
  <li><b>Exclusions:</b> The quoted price does not include <b>GST, and transportation charges.</b> These will be billed separately.</li>
  <li><b>Validity:</b> This quotation remains valid for 30 days from the date of this email.</li>
  <li><b>Note:-</b> We have considered PM rates based upon specs shared, any change in specs will lead to change in PM rates which eventually leads to change in final rates.</li>
</ul>

<p>Let me know in case of any query. Looking forward for your valuable order.</p>

<p><b>Warm Regards,</b><br/>
<b>{sender_name}</b><br/>
<b>HCP Wellness Pvt. Ltd.</b></p>

<hr style="border:none;border-top:1px solid #ccc;margin:16px 0;">
<span style="font-size:11px;color:#cc0000;"><b>IMPORTANT NOTICE:</b> This email and any attachments may contain information that is confidential and privileged. It is intended to be received only by persons entitled to receive the information. If you are not the intended recipient, please delete it from your system and notify the sender. You should not copy it or use it for any purpose nor disclose or distribute its contents to any other person.</span>

</div>"""


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


def _get_or_create_sample_order_template():
    """Get Sample Order template from DB. Always sync body/subject with latest default."""
    t = EmailTemplate.query.filter_by(code='sample_order').first()
    if not t:
        t = EmailTemplate(
            code       = 'sample_order',
            name       = 'Sample Order Confirmation Email',
            subject    = SAMPLE_ORDER_DEFAULT_SUBJECT,
            body       = SAMPLE_ORDER_DEFAULT_BODY,
            from_email = 'info@hcpwellness.in',
            from_name  = 'HCP Wellness Pvt. Ltd.',
            is_active  = True,
        )
        db.session.add(t)
        db.session.commit()
    else:
        # Force update body and subject to latest template
        t.body    = SAMPLE_ORDER_DEFAULT_BODY
        t.subject = SAMPLE_ORDER_DEFAULT_SUBJECT
        db.session.commit()
    return t


def _get_or_create_quotation_template():
    """Get Quotation template from DB. Always sync with latest default."""
    t = EmailTemplate.query.filter_by(code='quotation').first()
    if not t:
        t = EmailTemplate(
            code       = 'quotation',
            name       = 'Quotation Email',
            subject    = QUOTATION_DEFAULT_SUBJECT,
            body       = QUOTATION_DEFAULT_BODY,
            from_email = 'info@hcpwellness.in',
            from_name  = 'HCP Wellness Pvt. Ltd.',
            is_active  = True,
        )
        db.session.add(t)
        db.session.commit()
    else:
        t.body    = QUOTATION_DEFAULT_BODY
        t.subject = QUOTATION_DEFAULT_SUBJECT
        db.session.commit()
    return t


def _build_quotation_items_table(quot):
    """Build HTML items table from quotation items_json for email."""
    import json as _json
    try:
        items = _json.loads(quot.items_json or '[]')
    except Exception:
        items = []

    th = 'style="border:1px solid #999;padding:7px 12px;background:#f1f1f1;font-weight:bold;text-align:{a};"'
    td = 'style="border:1px solid #ccc;padding:6px 10px;text-align:{a};"'
    tdb = 'style="border:1px solid #ccc;padding:6px 10px;text-align:{a};font-weight:bold;"'

    rows = ''
    for it in items:
        def _v(k, fmt='str'):
            val = it.get(k, '')
            if fmt == 'num':
                try: v = float(val); return f'{v:,.2f} INR' if v else '—'
                except: return '—'
            if fmt == 'int':
                try: return str(int(float(val))) if val else '—'
                except: return '—'
            return str(val) if val else '—'
        rows += (
            f'<tr>'
            f'<td {td.format(a="left")}>{_v("name")}</td>'
            f'<td {td.format(a="center")}>{(_v("size") + " " + _v("uom")).strip() if (_v("size") != "—" or _v("uom") != "—") else "—"}</td>'
            f'<td {td.format(a="left")}>{_v("code")}</td>'
            f'<td {td.format(a="center")}>{_v("moq","int")}</td>'
            f'<td {tdb.format(a="right")}>{_v("final_cost","num")}</td>'
            f'</tr>'
        )

    return (
        f'<table style="border-collapse:collapse;font-size:13px;font-family:Arial,sans-serif;width:auto;">'
        f'<thead><tr>'
        f'<th {th.format(a="left")}>Product Name</th>'
        f'<th {th.format(a="center")}>Size</th>'
        f'<th {th.format(a="left")}>Product Code</th>'
        f'<th {th.format(a="center")}>Moq</th>'
        f'<th {th.format(a="right")}>Final Cost (INR)</th>'
        f'</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table><br/>'
    )


def _render_quot_template_vars(text, quot, sender_name='Administrator'):
    """Replace {variables} in quotation email template."""
    lead = quot.lead
    return (text
        .replace('{client_name}',  quot.bill_company or (lead.contact_name if lead else '') or 'Sir/Madam')
        .replace('{company}',      quot.bill_company or (lead.company_name if lead else '') or '')
        .replace('{quot_number}',  quot.quot_number  or '')
        .replace('{subject}',      quot.subject      or quot.bill_company or 'your requirement')
        .replace('{sender_name}',  sender_name)
        .replace('{items_table}',  _build_quotation_items_table(quot))
    )


def _build_items_table(so):
    """Build HTML items table from so.items_json for email."""
    import json as _json
    try:
        items = _json.loads(so.items_json or '[]')
    except Exception:
        items = []

    th = 'style="background:#1e3a5f;color:#fff;padding:8px 12px;text-align:{align};border:1px solid #1e3a5f;"'
    td = 'style="padding:8px 12px;border:1px solid #ddd;text-align:{align};"'

    rows = ''
    for item in items:
        name   = item.get('name', '')
        rate   = float(item.get('rate', 0) or 0)
        qty    = float(item.get('qty',  0) or 0)
        amount = float(item.get('amount', rate * qty) or 0)
        rows += f"""<tr>
          <td {td.format(align='left')}>{name}</td>
          <td {td.format(align='right')}>Rs.{rate:,.2f}</td>
          <td {td.format(align='center')}>{qty:g}</td>
          <td {td.format(align='right')}>Rs.{amount:,.2f}</td>
        </tr>"""

    sub   = float(so.sub_total    or 0)
    gst   = float(so.gst_amount   or 0)
    total = float(so.total_amount or 0)
    gst_pct = float(so.gst_pct or 18)

    table = f"""<table style="border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:14px;">
      <thead><tr>
        <th {th.format(align='left')}>Product Details</th>
        <th {th.format(align='right')}>Rate</th>
        <th {th.format(align='center')}>Quantity</th>
        <th {th.format(align='right')}>Amount</th>
      </tr></thead>
      <tbody>{rows}
        <tr>
          <td colspan="2" style="border:none;"></td>
          <td style="padding:6px 12px;border:1px solid #ddd;font-weight:600;">Sub Total</td>
          <td style="padding:6px 12px;border:1px solid #ddd;text-align:right;">Rs.{sub:,.2f}</td>
        </tr>
        <tr>
          <td colspan="2" style="border:none;"></td>
          <td style="padding:6px 12px;border:1px solid #ddd;font-weight:600;">GST ({gst_pct:.0f}%)</td>
          <td style="padding:6px 12px;border:1px solid #ddd;text-align:right;">Rs.{gst:,.2f}</td>
        </tr>
        <tr>
          <td colspan="2" style="border:none;"></td>
          <td style="padding:6px 12px;border:1px solid #1e3a5f;background:#f0f4ff;font-weight:700;">Total Amount</td>
          <td style="padding:6px 12px;border:1px solid #1e3a5f;background:#f0f4ff;text-align:right;font-weight:700;">Rs.{total:,.2f}</td>
        </tr>
      </tbody>
    </table>"""
    return table


def _render_template_vars(text, lead, so=None, sender_name='Administrator'):
    """Replace {variables} in subject/body with lead (and optional sample_order) data."""
    result = (text
        .replace('{client_name}',  lead.contact_name or '')
        .replace('{company}',      lead.company_name  or lead.contact_name or '')
        .replace('{email}',        lead.email         or '')
        .replace('{phone}',        lead.phone         or '')
        .replace('{product}',      lead.product_name  or '')
        .replace('{city}',         lead.city          or '')
        .replace('{lead_code}',    getattr(lead, 'code', '') or '')
        .replace('{sender_name}',  sender_name)
    )
    if so:
        order_date_str = so.order_date.strftime('%d %b %Y') if so.order_date else ''
        result = (result
            .replace('{order_number}',  so.order_number  or '')
            .replace('{order_date}',    order_date_str)
            .replace('{bill_company}',  so.bill_company  or lead.company_name or '')
            .replace('{bill_email}',    so.bill_email    or lead.email or '')
            .replace('{bill_phone}',    so.bill_phone    or lead.phone or '')
            .replace('{total_amount}',  f'{so.total_amount:,.2f}' if so.total_amount else '0.00')
            .replace('{sub_total}',     f'{so.sub_total:,.2f}'    if so.sub_total    else '0.00')
            .replace('{gst_amount}',    f'{so.gst_amount:,.2f}'   if so.gst_amount   else '0.00')
            .replace('{items_table}',   _build_items_table(so))
        )
    return result


def _send_smtp(to_email, subject, html_body, from_email, from_name, attachment_bytes=None, attachment_name=None):
    """Send email via SMTP with optional PDF attachment. Returns (success, error_msg)."""
    from email.mime.base import MIMEBase
    from email import encoders
    try:
        cfg       = current_app.config
        smtp_user = cfg.get('MAIL_USERNAME', '')

        msg = MIMEMultipart('mixed')
        msg['Subject'] = subject
        msg['From']    = f'{from_name} <{from_email}>'
        msg['To']      = to_email
        msg['Reply-To']= from_email

        alt = MIMEMultipart('alternative')
        alt.attach(MIMEText(html_body, 'html', 'utf-8'))
        msg.attach(alt)

        if attachment_bytes and attachment_name:
            part = MIMEBase('application', 'octet-stream')
            part.set_payload(attachment_bytes)
            encoders.encode_base64(part)
            part.add_header('Content-Disposition', f'attachment; filename="{attachment_name}"')
            msg.attach(part)

        server = smtplib.SMTP(cfg['MAIL_SERVER'], cfg['MAIL_PORT'], timeout=15)
        server.ehlo()
        if cfg.get('MAIL_USE_TLS'):
            server.starttls()
        if smtp_user and cfg.get('MAIL_PASSWORD'):
            server.login(smtp_user, cfg['MAIL_PASSWORD'])
        actual_sender = smtp_user or from_email
        server.sendmail(actual_sender, [to_email], msg.as_string())
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
    _get_or_create_npd_template()           # ensure NPD default exists
    _get_or_create_sample_order_template()  # ensure Sample Order default exists
    _get_or_create_quotation_template()     # ensure Quotation default exists
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


# ══════════════════════════════════════
# SEND SAMPLE ORDER EMAIL — from SampleOrder
# ══════════════════════════════════════

@mail_bp.route('/sample-orders/<int:id>/preview')
@login_required
def sample_order_preview(id):
    """Return rendered subject + body for modal preview (Sample Order)."""
    from models import SampleOrder
    so   = SampleOrder.query.get_or_404(id)
    lead = so.lead
    t    = _get_or_create_sample_order_template()
    return jsonify(
        subject       = _render_template_vars(t.subject, lead, so),
        body          = _render_template_vars(t.body,    lead, so),
        to_email      = so.bill_email or lead.email or '',
        from_email    = t.from_email,
        from_name     = t.from_name,
        template_name = t.name,
        order_number  = so.order_number,
    )


@mail_bp.route('/sample-orders/<int:id>/send', methods=['GET', 'POST'])
@login_required
def sample_order_send(id):
    """Send Sample Order confirmation email.
    GET  — direct one-click send using DB template (no form needed)
    POST — send with optional overrides from modal form
    """
    from models import SampleOrder, LeadActivityLog
    so   = SampleOrder.query.get_or_404(id)
    lead = so.lead
    t    = _get_or_create_sample_order_template()

    # Auto-render from template — works even if form fields are empty
    rendered_subject = _render_template_vars(t.subject, lead, so)
    rendered_body    = _render_template_vars(t.body,    lead, so)

    to_email   = (request.form.get('to_email',   '') or so.bill_email or lead.email or '').strip()
    subject    = (request.form.get('subject',    '') or rendered_subject).strip()
    body       = (request.form.get('body',       '') or rendered_body).strip()
    from_email = (request.form.get('from_email', '') or t.from_email or 'info@hcpwellness.in').strip()
    from_name  = (request.form.get('from_name',  '') or t.from_name  or 'HCP Wellness Pvt. Ltd.').strip()

    # Redirect back to caller page if provided
    redirect_url = request.form.get('redirect_url', '') or request.args.get('redirect_url', '')
    back = redirect(redirect_url) if redirect_url else redirect(url_for('crm.sample_orders_list'))

    if not to_email:
        flash(f'❌ No email found for order {so.order_number}. Please add email to lead/order first.', 'danger')
        return back

    success, err = _send_smtp(to_email, subject, body, from_email, from_name)

    if success:
        db.session.add(LeadActivityLog(
            lead_id = lead.id,
            user_id = current_user.id,
            action  = f'Sample Order email sent ({so.order_number}) to {to_email}',
        ))
        db.session.commit()
        audit('mail', 'SEND', so.id, f'SampleOrder {so.order_number} → {to_email}', obj=None)
        flash(f'✅ Sample Order email sent to {to_email} ({so.order_number})!', 'success')
    else:
        flash(f'❌ Email failed for {so.order_number}: {err}', 'danger')

    return back


# ══════════════════════════════════════
# QUICK SEND — one-click from any page
# GET /mail/sample-orders/<id>/quick-send
# ══════════════════════════════════════

@mail_bp.route('/sample-orders/<int:id>/quick-send')
@login_required
def sample_order_quick_send(id):
    """One-click send: no form needed. Uses DB template + SampleOrder data directly."""
    from models import SampleOrder, LeadActivityLog
    so   = SampleOrder.query.get_or_404(id)
    lead = so.lead
    t    = _get_or_create_sample_order_template()

    to_email   = (so.bill_email or lead.email or '').strip()
    subject    = _render_template_vars(t.subject, lead, so)
    body       = _render_template_vars(t.body,    lead, so)
    from_email = t.from_email or 'info@hcpwellness.in'
    from_name  = t.from_name  or 'HCP Wellness Pvt. Ltd.'

    # Where to go back
    back_url = request.args.get('next', url_for('crm.sample_orders_list'))

    if not to_email:
        flash(f'❌ No email address for order {so.order_number}. Update the lead email first.', 'danger')
        return redirect(back_url)

    success, err = _send_smtp(to_email, subject, body, from_email, from_name)

    if success:
        db.session.add(LeadActivityLog(
            lead_id = lead.id,
            user_id = current_user.id,
            action  = f'Sample Order email sent ({so.order_number}) to {to_email}',
        ))
        db.session.commit()
        audit('mail', 'SEND', so.id, f'SampleOrder {so.order_number} → {to_email}', obj=None)
        flash(f'✅ Sample Order email sent to {to_email}!', 'success')
    else:
        flash(f'❌ Email failed: {err}', 'danger')

    return redirect(back_url)

# ══════════════════════════════════════
# QUOTATION EMAIL — from Quotations list
# ══════════════════════════════════════

@mail_bp.route('/quotations/<int:id>/preview')
@login_required
def quotation_preview(id):
    """Return rendered subject + body for modal preview."""
    from models import Quotation
    quot = Quotation.query.get_or_404(id)
    t    = _get_or_create_quotation_template()
    sender_name = current_user.full_name or 'Administrator'
    return jsonify(
        subject      = _render_quot_template_vars(t.subject, quot, sender_name),
        body         = _render_quot_template_vars(t.body,    quot, sender_name),
        to_email     = quot.bill_email or (quot.lead.email if quot.lead else '') or '',
        from_email   = t.from_email,
        from_name    = t.from_name,
        quot_number  = quot.quot_number,
    )
