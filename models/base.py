"""
models/base.py
──────────────
SQLAlchemy db instance.
Sabse pehle import hota hai taaki circular import na ho.
"""

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
