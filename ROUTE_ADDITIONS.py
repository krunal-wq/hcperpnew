"""
HOW TO ADD wa_share PAGE ROUTE — append to npd_daily_report_routes.py
or npd_whatsapp_routes.py

Add this route anywhere in npd_daily_report_routes.py:
"""

# ── Add this route to npd_daily_report_routes.py ──────────────────────────

# @npd_report_bp.route('/wa-share')
# @login_required
# def wa_share_page():
#     return render_template('npd/daily_report/wa_share.html',
#                            _pg='npd_wa_share', _mod='npd')


# ── Add to base.html NPD sidebar section ──────────────────────────────────
"""
<a class="nav-a {% if _pg == 'npd_wa_share' %}active{% endif %}"
   href="/npd/wa-share">
    <span class="nav-ic">📱</span>
    <span class="nav-txt">WA Report Share</span>
</a>
"""


# ── Or add a button in existing dashboard.html ────────────────────────────
"""
Existing dashboard ke header mein yeh button add karo:

<a href="/npd/wa-share"
   class="btn-wa"
   style="display:inline-flex;align-items:center;gap:.45rem;
          background:#25d366;color:#fff;border-radius:8px;
          padding:.45rem .95rem;font-size:.8rem;font-weight:700;
          text-decoration:none;">
  📋 Detail Report Share
</a>
"""

# ── Import npd_wa_web_report.py in index.py ───────────────────────────────
"""
Add to index.py (after npd_daily_report_routes import):

import npd_wa_web_report   # registers /npd/api/wa-detail-report on npd_report_bp
"""
