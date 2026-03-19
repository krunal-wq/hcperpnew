"""
audit_helper.py — Central audit logging with full JSON snapshots
"""
import json
from datetime import datetime
from flask import request as flask_request
from flask_login import current_user
from models import db, AuditLog


def _get_ip():
    try:
        return flask_request.remote_addr or 'unknown'
    except Exception:
        return 'unknown'


def _get_user_info():
    try:
        if current_user and current_user.is_authenticated:
            return current_user.id, current_user.username, getattr(current_user, 'role', '')
    except Exception:
        pass
    return None, 'system', ''


def _to_str(val):
    if val is None:
        return None
    if isinstance(val, datetime):
        return val.strftime('%d-%m-%Y %H:%M:%S')
    try:
        from decimal import Decimal
        if isinstance(val, Decimal):
            return float(val)
    except Exception:
        pass
    return str(val) if not isinstance(val, (int, float, bool, str)) else val


def model_to_dict(obj, exclude=('password_hash', 'qr_code_base64')):
    """Convert SQLAlchemy model instance to clean dict."""
    d = {}
    try:
        for col in obj.__table__.columns:
            if col.name in exclude:
                continue
            d[col.name] = _to_str(getattr(obj, col.name, None))
    except Exception:
        pass
    return d


def audit(module, action, record_id=None, record_label='', detail='',
          commit=False, obj=None, old_dict=None, new_dict=None):
    uid, uname, urole = _get_user_info()
    payload = {}

    if action == 'DELETE' and obj is not None:
        payload['deleted_record'] = model_to_dict(obj)
    elif action == 'INSERT' and obj is not None:
        payload['created_record'] = model_to_dict(obj)
    elif action == 'UPDATE':
        if old_dict and new_dict:
            changes = {}
            for k in new_dict:
                ov = str(old_dict.get(k, '') or '')
                nv = str(new_dict.get(k, '') or '')
                if ov != nv:
                    changes[k] = {'before': old_dict.get(k), 'after': new_dict.get(k)}
            payload['changes'] = changes
            if not detail and changes:
                detail = ', '.join(f"{k}: {v['before']} → {v['after']}" for k, v in list(changes.items())[:5])
        if obj is not None:
            payload['current_record'] = model_to_dict(obj)
    elif action == 'VIEW' and obj is not None:
        payload['viewed_record'] = model_to_dict(obj)
    elif obj is not None:
        payload['record'] = model_to_dict(obj)

    if detail:
        payload['summary'] = str(detail)

    detail_json = json.dumps(payload, ensure_ascii=False, default=str) if payload else str(detail)

    log = AuditLog(
        user_id      = uid,
        username     = uname,
        user_role    = urole,
        module       = module,
        action       = action,
        record_id    = record_id,
        record_label = str(record_label)[:299],
        detail       = detail_json[:8000],
        ip_address   = _get_ip(),
        created_at   = datetime.now(),
    )
    db.session.add(log)
    # Always commit audit log immediately in its own transaction
    try:
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        # Try again with a fresh session
        try:
            db.session.add(log)
            db.session.commit()
        except Exception:
            db.session.rollback()


def snapshot(obj, fields):
    parts = []
    for f in fields:
        val = getattr(obj, f, None)
        if val is not None:
            parts.append(f'{f}: {val}')
    return ' | '.join(parts)


def diff(old_dict, new_dict):
    changes = []
    for k in new_dict:
        ov = old_dict.get(k)
        nv = new_dict.get(k)
        if str(ov) != str(nv):
            changes.append(f'{k}: {ov} → {nv}')
    return ' | '.join(changes) if changes else 'No changes'
