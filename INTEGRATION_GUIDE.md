# 📋 MODULE ENABLE/DISABLE — INTEGRATION GUIDE
# ================================================
# Yeh guide batata hai ki naye files ko apne existing app mein kaise integrate karein.

## ✅ Step 1 — Route Register karo (app.py mein)

```python
# app.py mein yeh add karo:

from routes.module_settings_routes import module_settings
from context_processors import register_context_processors

# Blueprint register karo
app.register_blueprint(module_settings)

# Context processor register karo (templates ko nav_modules milega)
register_context_processors(app)
```

---

## ✅ Step 2 — base.html mein sidebar include karo

```html
<!-- base.html mein sidebar ke jagah yeh use karo -->
{% include 'partials/sidebar.html' %}
```

---

## ✅ Step 3 — Database mein Module records add karo

```python
# Ek baar run karo (seed_modules.py ya flask shell mein):

from models.permission import Module
from models import db

modules_data = [
    # Top-level modules (parent_id = None)
    {'name': 'crm',      'label': 'CRM',        'icon': '📊', 'url_prefix': '/crm',  'sort_order': 1},
    {'name': 'hr',       'label': 'HR',          'icon': '👥', 'url_prefix': '/hr',   'sort_order': 2},
    {'name': 'npd',      'label': 'NPD',         'icon': '🔬', 'url_prefix': '/npd',  'sort_order': 3},
    {'name': 'masters',  'label': 'Masters',     'icon': '⚙️', 'url_prefix': '/masters', 'sort_order': 4},
]

# Pehle top-level modules add karo
for m in modules_data:
    if not Module.query.filter_by(name=m['name']).first():
        mod = Module(**m, is_active=True)
        db.session.add(mod)

db.session.commit()

# CRM ka id nikalo
crm = Module.query.filter_by(name='crm').first()

# Sub-modules (CRM ke children)
crm_children = [
    {'name': 'crm_dashboard',    'label': 'CRM Dashboard',     'icon': '📈', 'url_prefix': '/crm/dashboard',    'sort_order': 1, 'parent_id': crm.id},
    {'name': 'crm_leads',        'label': 'Leads',             'icon': '📋', 'url_prefix': '/crm/leads',        'sort_order': 2, 'parent_id': crm.id},
    {'name': 'crm_clients',      'label': 'Client Master',     'icon': '👤', 'url_prefix': '/crm/clients',      'sort_order': 3, 'parent_id': crm.id},
    {'name': 'crm_sample_orders','label': 'Sample Orders',     'icon': '📦', 'url_prefix': '/crm/sample-orders','sort_order': 4, 'parent_id': crm.id},
    {'name': 'crm_quotations',   'label': 'Quotations',        'icon': '💼', 'url_prefix': '/crm/quotations',   'sort_order': 5, 'parent_id': crm.id},
    {'name': 'crm_quot_products','label': 'Quot. Product List','icon': '📝', 'url_prefix': '/crm/quot-products','sort_order': 6, 'parent_id': crm.id},
    {'name': 'crm_leaderboard',  'label': 'Leaderboard',       'icon': '🏆', 'url_prefix': '/crm/leaderboard',  'sort_order': 7, 'parent_id': crm.id},
    {'name': 'crm_import',       'label': 'Import',            'icon': '📥', 'url_prefix': '/crm/import',       'sort_order': 8, 'parent_id': crm.id},
]

for m in crm_children:
    if not Module.query.filter_by(name=m['name']).first():
        db.session.add(Module(**m, is_active=True))

db.session.commit()
print("✅ Modules seeded!")
```

---

## ✅ Step 4 — Settings page access karo

```
URL: /settings/modules
Role: Admin only
```

---

## 🔄 How it works (Flow):

```
Admin → /settings/modules page open karta hai
      → Module ka toggle OFF karta hai
      → POST /settings/modules/toggle API call
      → DB mein Module.is_active = False ho jaata hai
      → Sidebar mein context_processor next request par sirf
        is_active=True modules fetch karta hai
      → Disabled module sidebar se hide ho jaata hai ✅
```

---

## 📁 New Files Created:

| File | Purpose |
|------|---------|
| `routes/module_settings_routes.py` | Settings page + Toggle API routes |
| `templates/settings/module_settings.html` | Admin settings UI |
| `templates/partials/sidebar.html` | Sidebar template (active modules only) |
| `context_processors.py` | nav_modules inject karta hai har template mein |
| `INTEGRATION_GUIDE.md` | Yeh file |
