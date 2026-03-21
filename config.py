import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'erp-super-secret-key-2024'

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://root:Krunal%402424@localhost:3306/erpdb'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
    }

    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = 1800

    # ── SMTP / Mail Settings ──────────────────────────────────────────────
    MAIL_SERVER   = os.environ.get('MAIL_SERVER',   'smtp.gmail.com')
    MAIL_PORT     = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS  = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'krunalchandi.hcp@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD', 'qrcfnyawxvlwjgvk')
