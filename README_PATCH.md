# Permission System Patch — User-Only Model

## Kya Badla?

**Pehle:** Role-based fallback (agar user ke liye permission nahi, to role ke hisaab se default milta tha). Isliye "permission diya lekin kaam nahi huva" — role fallback chalta tha.

**Ab:** Sirf user-wise permission. Admin ko automatic full rights. Baaki sab ko kuch bhi nahi jab tak explicitly diya na ho.

## Files To Replace

4 files — apne project mein overwrite karo:

```
patch/permissions.py                                  → <project>/permissions.py
patch/user_routes.py                                  → <project>/user_routes.py
patch/templates/base.html                             → <project>/templates/base.html
patch/templates/admin/permissions/acp_panel.html      → <project>/templates/admin/permissions/acp_panel.html
```

## Deployment Steps

1. Backup current files first:
   ```bash
   cp permissions.py permissions.py.bak
   cp user_routes.py user_routes.py.bak
   cp templates/base.html templates/base.html.bak
   cp templates/admin/permissions/acp_panel.html templates/admin/permissions/acp_panel.html.bak
   ```

2. 4 patch files copy karo proper locations par.

3. Flask server restart karo.

4. Admin user se login karo → sab kuch pehle jaisa dikhega.

5. Non-admin user (e.g. `hcp0286`) ke liye `/admin/acp/<user_id>` pe jao, permission toggle karo, logout-login se verify.

## Important Notes

### RolePermission table
DB mein table rahega (data safe hai) lekin code use nahi karega. Future mein migrate kar ke drop kar sakte ho.

### Admin Auto-Rights
Admin role ka user **automatic full rights** paata hai — UserPermission table mein record nahi chahiye. Safety net: admin ka `can_view` kabhi False nahi ho sakta.

### Non-Admin Default
Non-admin user (role=user/manager/hr/sales/etc.) ko **koi access nahi** jab tak admin ne `/admin/acp/<user_id>` se explicitly permission na di ho. Jo aapne abhi chahiye tha.

### Feature-Level Role Checks (crm_routes.py, rd_routes.py, etc.)
Business logic ke liye route files mein `current_user.role in ('admin','manager')` jaise checks hain (100+ places). Ye **chhod diye** hain — ye data filtering / visibility logic hai, menu nahi. Agar kaam ho raha hai to chhod do. Future mein alag se refactor kar sakte ho.

### Settings & Admin Links
Sidebar mein "Settings" group aur "Users" link sirf admin ko dikhte hain — kyunki ye admin-only config pages hain. Ye design-by-intent hai.

## Testing Checklist

- [ ] Admin login → sab modules dikhen
- [ ] Non-admin login (jiska koi permission nahi) → sirf "Dashboard" dikhe, aur kuch nahi
- [ ] Admin se `/admin/acp/<user_id>` pe jao, CRM → Leads → View toggle ON karo
- [ ] Us non-admin user se login karo → CRM menu aur Leads link dikhna chahiye
- [ ] View OFF karo → wapas gayab ho jaaye
- [ ] Employee code (hcp0286 wagerah) left sidebar aur right header mein dikhe
- [ ] Search mein employee code type karne se user filter ho

## Rollback

Agar kuch galat ho jaaye:
```bash
cp permissions.py.bak permissions.py
cp user_routes.py.bak user_routes.py
cp templates/base.html.bak templates/base.html
cp templates/admin/permissions/acp_panel.html.bak templates/admin/permissions/acp_panel.html
```
Flask restart karo — pehle jaisa ho jayega.
