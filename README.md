# Specs/Process — Always-Toggleable + Per-Sheet Specs Textarea

## Files

```
formulation_routes.py                       ← parser returns plain text for specs
templates/formulation/index.html            ← always-present checkboxes + specs textarea
```

**Koi SQL change nahi.**

## Steps

1. 2 files replace karo
2. Flask restart
3. **Ctrl+Shift+R** (hard refresh)

## Kya badla

### Pehle (galat)
- Agar sheet me Specs nahi mile (jaise STRONG HOLD HAIR WAX me) → Specifications **plain text "—"** dikha — toggle nahi kar sakte
- User confused — "check/uncheck nai ker pa raha hu"

### Ab (sahi)
- **Specs aur Process dono ki checkboxes hamesha rahti hain**, har sheet me — chahe parser ne detect kiya ho ya nahi
- Agar count > 0 → checkbox auto-checked, colored count badge dikhega
- Agar count = 0 → checkbox auto-unchecked, gray "0" badge dikhega
- User chahe to toggle on karke **manually textarea me likh sakta hai**

### Naya — Per-sheet Specs textarea
Pehle sirf Process ka textarea tha. Ab Specs ka bhi alag textarea hai har card me:
- Auto-detected ho to plain text format me dikhega: `"1. Appearance: Opaque Viscous Liquid"`
- Khali ho aur user chahe to **manually likh sake** (`"pH: 5.50-6.50"` jaise lines)
- Checkbox uncheck karoge → textarea gray ho jaayega (visually clear ki include nahi hoga)

### Plain text → HTML conversion
- Auto-detected specs ab clean plain text format me display hote hain (HTML mess nahi)
- Commit pe server automatically HTML table banata hai for storage
- View modal me proper styled table dikhega
- Manual entry bhi same flow — type karo plain text, server converts to table

## Behavior matrix

| Sheet me | Process Checkbox | Specs Checkbox | Textarea |
|---|---|---|---|
| Process AND Specs dono mile (e.g. DE TAN) | ✓ auto-on, 9 | ✓ auto-on, 6 | Both pre-filled |
| Sirf Process mila (e.g. STRONG HOLD) | ✓ auto-on, 4 | ☐ auto-off, 0 | Process pre-filled, Specs empty (toggle on to add) |
| Kuch nahi mila | ☐ off, 0 | ☐ off, 0 | Both empty (toggle on to add manually) |

User puri freedom me hai — har sheet ka apna alag treatment.
