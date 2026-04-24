# NPD/EPD Gate Flow — Patch Summary

Implements the "Check Client Mapping → Open Client Form OR Open Project Form" flow
when the user clicks **NPD Project** or **EPD Project** from the Lead detail page.

---

## Files changed

Replace your existing files with the ones in this archive. Nothing else needs to move.

```
npd_routes.py                            (modified)
crm_routes.py                            (modified)
templates/crm/leads/lead_view.html       (modified)
templates/crm/clients/client_form.html   (modified)
templates/npd/epd_form.html              (modified)
```

No DB migrations needed. No new dependencies.

---

## What changed, per file

### 1. `npd_routes.py`

**Added a new gate route** — this is the single entry point for the new flow:

```
GET /npd/start/<lead_id>/<npd|epd>   →  start_from_lead(lead_id, project_type)
```

Behavior:
- Fetches the lead, checks `lead.client_id`.
- **Client linked** → redirects to `GET /npd/npd-new?lead_id=…&client_id=…`
  (or `/npd/epd-new` for EPD). Client ID, Client Name, and Lead ID land pre-filled.
- **No client** → redirects to `GET /crm/clients/add` with `lead_id`, `next_action=npd|epd`,
  and lead-derived prefill params. On save, `client_add` handles the final hop to the
  project form.

**Added `client_id` validation** to both `npd_new` and `epd_new` POST handlers —
projects can no longer be created without a client.

**Legacy route** `POST /npd/convert-lead/<lead_id>/<npd|existing>` is untouched.
Anything else that still calls it keeps working.

### 2. `crm_routes.py`

**`client_add`** now recognizes a `next_action` param (`npd` or `epd`).
When present alongside `lead_id_link`, after the client is saved & mapped to the lead,
the user is redirected to the NPD/EPD project creation form with `lead_id` and the
newly created `client_id`. AJAX clients receive the redirect URL in the JSON response.

The existing client-lead linking code (`lead_id_link` / `proj_id_link`) is unchanged.

### 3. `templates/crm/leads/lead_view.html`

The **NPD Project** and **EPD Project** buttons now open a confirmation modal
whose Confirm button navigates to `/npd/start/<lead_id>/<npd|epd>` (the new gate route).
The modal body and step list reflect the new two-step flow, and the sub-label under
each button now reads "Client linked → Project Form" or "Create Client → Project Form".

A short loader message (`"✅ Client already exists. Redirecting to project creation…"`
or `"ℹ️ No client found. Opening client creation form first…"`) is shown inside the
modal between click and navigation, per the spec's optional enhancement.

The old hidden POST forms (`form-npd-convert`, `form-epd-convert`) are left in place
so any other JS hooks aren't broken, but they're no longer submitted by the UI.

### 4. `templates/crm/clients/client_form.html`

- Adds a hidden `<input name="next_action">` that carries `npd` or `epd` through
  the POST so `crm.client_add` knows where to redirect after save.
- Top banner is now context-aware — when `next_action` is present it reads
  *"Step 1 of 2 — Create Client for NPD/EPD Project"*.

### 5. `templates/npd/epd_form.html`

- Adds a hidden `<input name="client_id">` so EPD submissions actually carry the FK.
  (The NPD form already had this.)
- Shows a small green banner when client is pre-filled from the gate flow so the
  user sees which client the project is being linked to.
- Client Name field becomes `readonly` when a client is pre-filled (prevents the
  user from editing the client name out of sync with the actual `client_id`).

---

## End-to-end user flow (matches spec)

**Case A — lead already has a client:**

1. User clicks **NPD Project** / **EPD Project** on `/crm/leads/<id>`.
2. Modal opens: *"Client already linked. Open NPD Project Form."*
3. User clicks Confirm → loader shows *"✅ Client already exists. Redirecting…"*
4. Browser navigates to `/npd/start/<lead_id>/npd`.
5. `start_from_lead` sees `lead.client_id`, redirects to `/npd/npd-new?lead_id=…&client_id=…`.
6. NPD form renders with Client ID, Client Name, Company, Email, Phone, and Lead
   all pre-filled. Client Name field is the same read-only style as today.
7. User edits product details, clicks Save → project created, linked to existing client.

**Case B — lead has no client:**

1. User clicks **NPD Project** / **EPD Project**.
2. Modal opens: *"No client mapped. Client form opens first, then project form."*
3. User clicks Confirm → loader shows *"ℹ️ No client found. Opening client creation form first…"*
4. Browser navigates to `/npd/start/<lead_id>/npd`.
5. `start_from_lead` sees `lead.client_id is None`, redirects to
   `/crm/clients/add?lead_id=…&next_action=npd&contact_name=…&company_name=…&email=…`.
6. Client form renders with the *"Step 1 of 2"* banner and all lead fields pre-filled.
7. User saves → existing `client_add` logic: client row created, lead.client_id
   updated, activity logged.
8. **New**: because `next_action=npd` was present, `client_add` redirects to
   `/npd/npd-new?lead_id=…&client_id=<new_id>` instead of `/crm/clients/<id>`.
9. NPD form renders with all client + lead fields pre-filled. User saves → project
   created, linked to the newly created client.

---

## Validation rules enforced

| Rule | Where |
|---|---|
| Project cannot be created without a client | `npd_new` & `epd_new` POST — rejects if `client_id` empty |
| One lead → one mapped client | Existing `Lead.client_id` single FK; `client_add` only overwrites if gate flow explicitly requests it |
| No duplicate client creation for a lead that already has one | `start_from_lead` routes straight to project form, never to client form, when `lead.client_id` is set |

---

## Rollback

Revert these 5 files. The old `POST /npd/convert-lead/...` path is still live,
so reverting `lead_view.html` alone is enough to fall back to the previous behavior.
