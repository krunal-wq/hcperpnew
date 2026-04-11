"""
update_qr_codes.py
==================
SABHI employees ka QR code employee_code se regenerate karta hai.
Purane QR (jo employee_id se bane the) bhi overwrite ho jayenge.

Usage:
    python update_qr_codes.py

Requirements:
    pip install qrcode[pil] sqlalchemy pymysql
"""

import sys, os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

try:
    from config import Config
    DB_URI = Config.SQLALCHEMY_DATABASE_URI
except Exception:
    DB_URI = 'mysql+pymysql://root:Krunal%402424@localhost:3306/erpdb'

print(f"[INFO] DB: {DB_URI.split('@')[-1]}")


def generate_qr_base64(text: str) -> str:
    import qrcode, base64, io
    text = str(text).strip()
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=8,
        border=3,
    )
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    b64 = base64.b64encode(buf.getvalue()).decode()
    return f'data:image/png;base64,{b64}'


def main():
    try:
        import qrcode
    except ImportError:
        print("[ERROR] Run karo: pip install qrcode[pil]")
        sys.exit(1)

    from sqlalchemy import create_engine, text

    engine = create_engine(DB_URI, pool_pre_ping=True)

    with engine.connect() as conn:
        # SABHI employees fetch karo jinka employee_code hai
        result = conn.execute(text("""
            SELECT id, employee_code
            FROM employees
            WHERE employee_code IS NOT NULL
              AND employee_code != ''
        """))
        rows = result.fetchall()

        if not rows:
            print("[!] Koi employee nahi mila.")
            return

        print(f"[INFO] {len(rows)} employees ka QR regenerate ho raha hai...\n")

        updated = 0
        failed  = 0

        for row in rows:
            emp_id   = row[0]
            emp_code = row[1]
            try:
                qr_b64 = generate_qr_base64(emp_code)
                conn.execute(text("""
                    UPDATE employees
                    SET qr_code_base64 = :qr
                    WHERE id = :id
                """), {"qr": qr_b64, "id": emp_id})
                print(f"  [OK] ID={emp_id}  Code={emp_code}")
                updated += 1
            except Exception as e:
                print(f"  [FAIL] ID={emp_id}  Code={emp_code}  Error: {e}")
                failed += 1

        conn.commit()

    print(f"\n[DONE] Updated: {updated} | Failed: {failed} | Total: {len(rows)}")


if __name__ == '__main__':
    main()
