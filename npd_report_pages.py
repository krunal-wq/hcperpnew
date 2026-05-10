"""
npd_report_pages.py
────────────────────
Yeh file saare missing page routes register karti hai.

index.py mein sirf yeh ek line add karo (baaki sab imports ke saath):
    import npd_report_pages

Bas! Teeno pages kaam karenge:
  /npd/wa-share          → WhatsApp Web share (NPD detail)
  /npd/universal-report  → Universal cross-module share
  /npd/whatsapp-config   → WhatsApp API config (agar use karo to)
"""

from flask import render_template
from flask_login import login_required

# Reuse the existing blueprint — DO NOT create a new one
from npd_daily_report_routes import npd_report_bp

# ── Import API handlers (registers their routes automatically) ──
try:
    import npd_wa_web_report          # registers /npd/api/wa-detail-report
except ImportError:
    pass

try:
    import universal_activity_report  # registers /npd/universal-report + APIs
except ImportError:
    pass

try:
    import npd_whatsapp_routes        # registers /npd/api/whatsapp-* (config, send)
except ImportError:
    pass


# ─────────────────────────────────────────────────────────────
# PAGE ROUTES
# ─────────────────────────────────────────────────────────────

@npd_report_bp.route('/wa-share')
@login_required
def wa_share_page():
    """WhatsApp Web share page — NPD detailed activity."""
    return render_template(
        'npd/daily_report/wa_share.html',
        _pg='npd_wa_share',
        _mod='npd',
    )


@npd_report_bp.route('/whatsapp-config')
@login_required
def whatsapp_config_page():
    """WhatsApp API config admin page."""
    return render_template(
        'npd/daily_report/whatsapp_config.html',
        _pg='npd_wa_config',
        _mod='npd',
    )
