import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'erp-super-secret-key-2024'

    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'mysql+pymysql://root:Krunal%402424@localhost/erpdb'

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    MAX_CONTENT_LENGTH = 100 * 1024 * 1024  # 100MB — needed for base64 photos+docs
    MAX_FORM_MEMORY_SIZE = 100 * 1024 * 1024  # Werkzeug form memory limit
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_recycle': 280,
        'pool_pre_ping': True,
    }

    WTF_CSRF_ENABLED = True
    SESSION_COOKIE_SECURE = False
    SESSION_COOKIE_HTTPONLY = True
    PERMANENT_SESSION_LIFETIME = 1800
