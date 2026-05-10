"""
whatsapp_sender.py
──────────────────
Multi-provider WhatsApp message sender for HCP ERP.

Supported providers:
  - UltraMsg  (default — easy signup, free trial at ultramsg.com)
  - Twilio    (enterprise-grade)

Usage:
    from whatsapp_sender import send_whatsapp, WhatsAppConfig

    cfg = WhatsAppConfig(
        provider   = 'ultramsg',
        instance_id= 'instance12345',   # UltraMsg Instance ID
        api_token  = 'your-token-here', # UltraMsg token
    )
    result = send_whatsapp(to='+919876543210', message='Hello!', config=cfg)
    # result → {'ok': True,  'message_id': '...'} or
    # result → {'ok': False, 'error': '...'}

Config is loaded from npd_whatsapp_config table (managed via Admin UI).
"""

import re
import json
import logging
import requests
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Config dataclass
# ─────────────────────────────────────────────────────────────

@dataclass
class WhatsAppConfig:
    provider:    str   = 'ultramsg'     # 'ultramsg' | 'twilio'
    enabled:     bool  = False

    # UltraMsg credentials  (https://ultramsg.com → My Instances)
    instance_id: str   = ''             # e.g. 'instance12345'
    api_token:   str   = ''             # UltraMsg token

    # Twilio credentials
    account_sid: str   = ''
    auth_token:  str   = ''
    from_number: str   = ''             # e.g. 'whatsapp:+14155238886'

    # Sending rules
    country_code:str   = '+91'          # Prepended to bare 10-digit numbers
    send_time:   str   = '21:00'        # HH:MM — daily auto-send time
    send_to_manager: bool = True
    send_to_employees: bool = True
    manager_numbers: list = field(default_factory=list)  # Extra manager numbers

    @classmethod
    def from_db(cls):
        """Load config from npd_whatsapp_config table."""
        try:
            from models.npd_daily_report import NPDWhatsAppConfig as _Model
            row = _Model.query.first()
            if not row:
                return cls()
            return cls(
                provider        = row.provider or 'ultramsg',
                enabled         = bool(row.is_enabled),
                instance_id     = row.instance_id or '',
                api_token       = row.api_token or '',
                account_sid     = row.twilio_account_sid or '',
                auth_token      = row.twilio_auth_token or '',
                from_number     = row.twilio_from_number or '',
                country_code    = row.country_code or '+91',
                send_time       = row.send_time or '21:00',
                send_to_manager = bool(row.send_to_manager),
                send_to_employees=bool(row.send_to_employees),
                manager_numbers = json.loads(row.manager_numbers or '[]'),
            )
        except Exception as e:
            logger.warning(f'WhatsApp config load error: {e}')
            return cls()


# ─────────────────────────────────────────────────────────────
# Number formatter
# ─────────────────────────────────────────────────────────────

def _format_number(raw: str, country_code: str = '+91') -> Optional[str]:
    """
    Normalise a mobile number to E.164 format.
    '9876543210'   → '+919876543210'
    '09876543210'  → '+919876543210'
    '+919876543210'→ '+919876543210'
    Returns None if number looks invalid.
    """
    if not raw:
        return None
    digits = re.sub(r'[^\d]', '', raw)
    if len(digits) == 10:
        return country_code + digits
    if len(digits) == 11 and digits.startswith('0'):
        return country_code + digits[1:]
    if len(digits) == 12 and digits.startswith('91'):
        return '+' + digits
    if len(digits) == 13 and digits.startswith('091'):
        return '+' + digits[1:]
    if raw.startswith('+') and len(digits) >= 10:
        return '+' + digits
    logger.warning(f'Could not normalise number: {raw!r}')
    return None


# ─────────────────────────────────────────────────────────────
# Provider implementations
# ─────────────────────────────────────────────────────────────

def _send_ultramsg(to: str, message: str, cfg: WhatsAppConfig) -> dict:
    """
    Send via UltraMsg API.
    Docs: https://docs.ultramsg.com/api/post/messages/chat
    """
    if not cfg.instance_id or not cfg.api_token:
        return {'ok': False, 'error': 'UltraMsg instance_id / api_token not configured'}

    url = f'https://api.ultramsg.com/{cfg.instance_id}/messages/chat'
    payload = {
        'token':   cfg.api_token,
        'to':      to,              # '+919876543210'
        'body':    message,
        'priority': 1,
    }

    try:
        resp = requests.post(url, data=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        # UltraMsg returns {"sent":"true","id":"..."}
        if str(data.get('sent', '')).lower() == 'true':
            return {'ok': True, 'message_id': data.get('id', ''), 'provider': 'ultramsg'}
        return {'ok': False, 'error': data.get('error', str(data)), 'provider': 'ultramsg'}
    except requests.exceptions.Timeout:
        return {'ok': False, 'error': 'UltraMsg API timeout', 'provider': 'ultramsg'}
    except Exception as e:
        return {'ok': False, 'error': str(e), 'provider': 'ultramsg'}


def _send_twilio(to: str, message: str, cfg: WhatsAppConfig) -> dict:
    """Send via Twilio WhatsApp API."""
    if not cfg.account_sid or not cfg.auth_token or not cfg.from_number:
        return {'ok': False, 'error': 'Twilio credentials not configured'}

    url = f'https://api.twilio.com/2010-04-01/Accounts/{cfg.account_sid}/Messages.json'
    payload = {
        'From': cfg.from_number,       # 'whatsapp:+14155238886'
        'To':   f'whatsapp:{to}',
        'Body': message,
    }

    try:
        resp = requests.post(url, data=payload,
                             auth=(cfg.account_sid, cfg.auth_token), timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if data.get('sid'):
            return {'ok': True, 'message_id': data['sid'], 'provider': 'twilio'}
        return {'ok': False, 'error': data.get('message', str(data)), 'provider': 'twilio'}
    except Exception as e:
        return {'ok': False, 'error': str(e), 'provider': 'twilio'}


# ─────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────

def send_whatsapp(to: str, message: str, config: WhatsAppConfig = None) -> dict:
    """
    Send a WhatsApp message to `to` (raw number or E.164).
    Returns {'ok': True, 'message_id': ...} or {'ok': False, 'error': ...}
    """
    cfg = config or WhatsAppConfig.from_db()

    if not cfg.enabled:
        return {'ok': False, 'error': 'WhatsApp sending is disabled in config'}

    formatted = _format_number(to, cfg.country_code)
    if not formatted:
        return {'ok': False, 'error': f'Invalid number: {to}'}

    if cfg.provider == 'twilio':
        return _send_twilio(formatted, message, cfg)
    else:
        return _send_ultramsg(formatted, message, cfg)


def test_connection(config: WhatsAppConfig, test_number: str) -> dict:
    """
    Send a test message to verify credentials.
    Called from the Admin Config UI.
    """
    msg = ('✅ *HCP ERP — WhatsApp Test*\n\n'
           'Yeh ek test message hai NPD Daily Report module se.\n'
           'Configuration successful hai! 🎉\n\n'
           '_HCP ERP System_')
    return send_whatsapp(to=test_number, message=msg, config=config)
