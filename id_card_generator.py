"""
id_card_generator.py  —  100mm × 70mm HCP Employee ID Card
"""
import io, base64, os
from datetime import date
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.lib.utils import ImageReader

W = 100 * mm
H = 70  * mm

BLACK  = colors.HexColor('#000000')
WHITE  = colors.HexColor('#FFFFFF')
YELLOW = colors.HexColor('#F2C200')
GRAY   = colors.HexColor('#666666')

FONT_REG  = 'Helvetica'
FONT_BOLD = 'Helvetica-Bold'
LOGO_PATH = os.path.join(os.path.dirname(__file__), 'static', 'images', 'icons', 'hcp-logo.png')


def _b64_to_reader(b64_str):
    try:
        if ',' in b64_str:
            b64_str = b64_str.split(',', 1)[1]
        return ImageReader(io.BytesIO(base64.b64decode(b64_str)))
    except Exception:
        return None


def generate_id_card_pdf(employee) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(W, H))
    c.setTitle(f'ID Card - {employee.employee_code}')

    def yt(mm_val):
        """mm from top  →  pts from bottom"""
        return H - mm_val * mm

    # ── WHITE BG ────────────────────────────────────────────────
    c.setFillColor(WHITE)
    c.rect(0, 0, W, H, fill=1, stroke=0)

    # ── HEADER  0–14 mm ─────────────────────────────────────────
    # black corner triangle
    tri = c.beginPath()
    tri.moveTo(W - 9*mm, H); tri.lineTo(W, H); tri.lineTo(W, H - 9*mm); tri.close()
    c.setFillColor(BLACK); c.drawPath(tri, fill=1, stroke=0)

    # logo
    if os.path.exists(LOGO_PATH):
        c.drawImage(LOGO_PATH, 2*mm, yt(13.5),
                    width=19*mm, height=12.5*mm,
                    preserveAspectRatio=True, mask='auto')

    # company name
    c.setFillColor(BLACK)
    c.setFont(FONT_BOLD, 10.5)
    c.drawString(22.5*mm, yt(5.8), 'HCP WELLNESS PVT. LTD.')

    c.setFont(FONT_REG, 4.8)
    c.drawString(22.5*mm, yt(9.2),
                 '#8, Ozone Industrial Park, Nr. Kerala GIDC, Bhayla, Bavla, Ahmedabad')
    c.drawString(22.5*mm, yt(11.6),
                 '382220, Gujarat, India.  www.hcpwellness.in  |  Email: info@hcpwellness.in')

    c.setStrokeColor(BLACK); c.setLineWidth(0.4)
    c.line(0, yt(14), W, yt(14))

    # ── BLACK BAR  14–25 mm ─────────────────────────────────────
    c.setFillColor(BLACK)
    c.rect(0, yt(25), W, 11*mm, fill=1, stroke=0)

    div_x = 40 * mm
    c.setFillColor(WHITE)

    c.setFont(FONT_BOLD, 5.5)
    c.drawString(3*mm, yt(18.5), 'EMPLOYEE ID')
    c.setFont(FONT_BOLD, 11.5)
    c.drawString(3*mm, yt(24.2), employee.employee_code or '')

    c.setStrokeColor(WHITE); c.setLineWidth(0.5)
    c.line(div_x, yt(15), div_x, yt(24.5))

    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 5.5)
    c.drawString(div_x + 3*mm, yt(18.5), 'DEPARTMENT')
    c.setFont(FONT_BOLD, 11.5)
    c.drawString(div_x + 3*mm, yt(24.2), (employee.department or '').upper())

    # ── BODY  26–61 mm ──────────────────────────────────────────
    # Avatar
    av_sz = 22 * mm
    av_x  = 3  * mm
    av_yb = yt(26 + 22)          # top of avatar = 26mm, height = 22mm

    if employee.profile_photo:
        reader = _b64_to_reader(employee.profile_photo)
        if reader:
            c.drawImage(reader, av_x, av_yb, width=av_sz, height=av_sz,
                        preserveAspectRatio=False, mask='auto')
        else:
            _yellow_box(c, av_x, av_yb, av_sz, employee)
    else:
        _yellow_box(c, av_x, av_yb, av_sz, employee)

    # Details — tightly spaced to fit in body area
    dx     = av_x + av_sz + 4*mm
    line_h = 5.5   # mm between lines

    row = 29.5  # first row: Name

    # Name
    c.setFillColor(BLACK)
    c.setFont(FONT_BOLD, 9)
    c.drawString(dx, yt(row), employee.full_name)
    row += line_h

    # Gender
    c.setFont(FONT_BOLD, 7.5)
    c.drawString(dx, yt(row), (employee.gender or '').capitalize())
    row += line_h

    # Date of Joining  (was date_of_birth — now joining date)
    if employee.date_of_joining:
        c.setFont(FONT_BOLD, 7.5)
        c.drawString(dx, yt(row),
                     employee.date_of_joining.strftime('%d-%m-%Y'))
    row += line_h + 1.5   # extra gap before issue info

    # Issue Date
    c.setFont(FONT_REG, 7)
    today_str = date.today().strftime('%d-%m-%Y')
    c.drawString(dx, yt(row), f'Issue Date : {today_str}')
    row += 4.5

    # Issue By
    c.drawString(dx, yt(row), 'Issue By : HR HCP')

    # QR code — use stored qr_code_base64, fallback: generate from employee_code
    qr_sz = 19 * mm
    qr_x  = W - qr_sz - 3*mm
    qr_yb = yt(26 + 20)

    qr_reader = None

    # Get QR base64 — stored in DB or generate fresh
    qr_b64 = employee.qr_code_base64
    if not qr_b64 and employee.employee_code:
        try:
            from qr_generator import generate_qr_base64
            qr_b64 = generate_qr_base64(employee.employee_code)
        except Exception:
            pass

    if qr_b64:
        try:
            b64 = qr_b64.split(',', 1)[1] if ',' in qr_b64 else qr_b64
            raw = base64.b64decode(b64)
            from PIL import Image as PilImage
            pil_img = PilImage.open(io.BytesIO(raw)).convert('RGB')
            rgb_buf = io.BytesIO()
            pil_img.save(rgb_buf, 'PNG')
            rgb_buf.seek(0)
            qr_reader = ImageReader(rgb_buf)
        except Exception:
            qr_reader = None

    if qr_reader:
        c.drawImage(qr_reader, qr_x, qr_yb, width=qr_sz, height=qr_sz,
                    preserveAspectRatio=True)

    # ── DISCLAIMER  ~58mm ───────────────────────────────────────
    c.setFont(FONT_REG, 4.5)
    c.setFillColor(GRAY)
    c.drawString(3*mm, yt(59.5),
                 "This Card is System Generated, Doesn't Require Signature")

    # ── BOTTOM BAR  62–70mm ─────────────────────────────────────
    foot_h = 8 * mm
    c.setFillColor(BLACK)
    c.rect(0, 0, W, foot_h, fill=1, stroke=0)

    label = 'HCP WELLNESS PVT. LTD.'
    c.setFillColor(WHITE)
    c.setFont(FONT_BOLD, 8.5)
    lw = c.stringWidth(label, FONT_BOLD, 8.5)
    c.drawString((W - lw)/2, foot_h/2 - 3, label)

    # ── BORDER ──────────────────────────────────────────────────
    c.setStrokeColor(BLACK); c.setLineWidth(0.6)
    c.rect(0, 0, W, H, fill=0, stroke=1)

    c.save()
    return buf.getvalue()


def _yellow_box(c, x, y_pos, size, employee):
    c.setFillColor(YELLOW)
    c.rect(x, y_pos, size, size, fill=1, stroke=0)
    initial = (employee.first_name or '?')[0].upper()
    fs = size * 0.58
    c.setFillColor(WHITE)
    c.setFont('Helvetica-Bold', fs)
    tw = c.stringWidth(initial, 'Helvetica-Bold', fs)
    c.drawString(x + (size - tw)/2, y_pos + (size - fs * 0.72)/2, initial)
