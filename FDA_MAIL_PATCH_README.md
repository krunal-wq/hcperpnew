# FDA Request-Mail Gating — Patch Notes

## Kya badla hai

Jab NPD form me **FDA** milestone select hota hai aur user uss milestone ko
project view me kholta hai, ab do steps dikhte hain:

1. **Step 1 — Send FDA Request Mail** (naya)
   - To (required, comma-separated multiple allowed)
   - CC (optional)
   - Subject (auto pre-filled: `Request for FDA | <company> | <product>`,
     fully editable)
   - Body (pre-filled starter template, fully editable)
   - Attachments (multiple files, chip-style list with remove buttons)
   - **Send FDA Request Mail** button
2. **Step 2 — FDA Entries** (existing UI)
   - `+ Add FDA` button + per-doc-type uploads
   - **Locked tab tak** jab tak Step 1 ka mail bhej nahi diya

Mail send hone ke baad Step 1 ek green "✅ FDA REQUEST MAIL SENT" banner ban
jaata hai (sent_by, sent_at, To, CC, subject, body preview, attachment links
ke saath), aur Step 2 ka lock hat jaata hai.

## Files (sirf 2 files replace karni hain)

| File | Original path |
|------|---------------|
| `npd_routes.py` | project root |
| `project_view.html` | `templates/npd/project_view.html` |

## Database

**Koi migration zaroori nahi.** Sab kuch existing `npd_projects.npd_milestone_data`
column (TEXT, JSON) me save hota hai, naye key `fda_mail` ke andar:

```json
{
  "fda_mail": {
    "sent": true,
    "sent_at": "23-05-2026 14:30",
    "sent_by": "Sneha Dagar",
    "to": "dipika@hcpwellness.in, shital@hcpwellness.in",
    "cc": "anushka@hcpwellness.in",
    "subject": "Request for FDA | Xiva Pharmaceuticals | Noni Toothpaste",
    "body": "...",
    "attachments": [
      {"file": "20260523143012_NONI_TOOTHPASTE.pdf",
       "original_name": "NONI TOOTHPASTE.pdf"}
    ]
  },
  "fda_entries": [ ... ]
}
```

## SMTP

Existing `config.py` ki settings hi use hoti hain:

- `MAIL_SERVER`
- `MAIL_PORT`
- `MAIL_USE_TLS`
- `MAIL_USERNAME`
- `MAIL_PASSWORD`

Mail ka **From** automatically `current_user.full_name <MAIL_USERNAME>` hota
hai. SMTP credentials missing hone par send route 500 return karta hai with
clear error message.

## Naye routes (sirf reference ke liye)

| Method | Path | Function |
|--------|------|----------|
| GET    | `/npd/<pid>/fda/mail/status` | `fda_mail_status` |
| POST   | `/npd/<pid>/fda/mail/send`   | `fda_mail_send`   |

Dono `@login_required` hain aur existing FDA permission check ke saath chalein.

## Attachments storage

Send route har attachment ko `static/uploads/npd/` me save karta hai (saath me
timestamp prefix taaki collision na ho — `save_upload()` helper use hota hai).
Bad me banner se woh files clickable links hote hain.

## Frontend safeguards

1. **Visual lock overlay** FDA Entries pe (`#fda-entries-lock`).
2. **`+ Add FDA` button disabled** + opacity dim jab mail pending ho.
3. **`openFdaForm()` me JS guard**: `window._fdaMailSent === false` hone par
   alert + return — agar koi user DOM tweak karke overlay hata bhi de, fir
   bhi entry form open nahi hoga.
4. **Fail-safe lock**: agar `/fda/mail/status` API call fail ho jaaye, default
   locked state aata hai (better to block than allow).

## Mark-as-Done behaviour

FDA milestone ka existing **Mark as Done** flow bilkul wesa hi hai. Mail send
karna `milestone.status` ko apne aap "done" nahi karta — user ko manually
ya FDA entries complete karke "Mark as Done" karna hota hai. Yeh design
deliberate hai: mail sirf gating step hai, FDA process ka final step nahi.

## Edge cases handled

- Multiple recipients: To / CC dono `,` ya `;` se split hote hain.
- Invalid email format → 400 with clear message.
- File size: SMTP server pe dependent — koi explicit cap nahi (jaise existing
  `_send_smtp` me bhi nahi tha).
- Body: HTML tags milein to as-is, plain text milein to `\n` → `<br>`
  conversion ke saath safe HTML escape.
- After send, Step 1 banner show karta hai jo user ne send kiya (body preview
  collapsible details me).

## Testing checklist

- [ ] FDA milestone open karo → "Loading FDA mail status..." dikhe → fir compose form aaye.
- [ ] FDA Entries pe lock overlay (🔒 FDA Request Mail Pending) dikhe.
- [ ] `+ Add FDA` button disabled ho (40% opacity, not-allowed cursor).
- [ ] To blank rakhke send karo → "To: email required" error.
- [ ] Subject blank rakhke send karo → "Subject required" error.
- [ ] Invalid email type karo (`foo`) → "Invalid email: foo" error.
- [ ] Multiple recipients (comma-separated) + 1-2 attachments ke saath send karo → success.
- [ ] Page refresh karo → ab green "✅ FDA REQUEST MAIL SENT" banner dikhe + Entries unlocked.
- [ ] Recipients ke inbox me mail aaya ho with attachments.
- [ ] `+ Add FDA` button click karo → form khule normally.
