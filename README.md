# QC Re-open / Change Decision (galti se Approve/Reject undo)

## Naya kya hai
Agar QC ne galti se **Approve** (ya Reject) kar diya, ab use change kar sakte hain:

- QC Review form pe, approved/rejected hone ke baad neeche
  **"✏️ Change Decision / Re-open"** button aata hai.
- Click → confirm modal → confirm karne pe:
  - Agar stock move hua tha (RM stock-in / PM sample-out), woh **reverse** ho jaata hai
    (ledger me reverse entry banti hai).
  - TRS status wapas **Pending** ho jaata hai, approve/reject stamps clear.
  - Form dobara editable — ab sahi decision (Approved/Rejected) le sakte ho.
- Upar bar me bhi **"✏️ Edit TRS Data"** link (jab locked nahi hai) — TRS slip ke
  fields (qty, dates, etc.) edit karne ke liye.

Saari confirmations ab styled **modal popup** me hain (browser ka default alert nahi).

## Install (2 files, overwrite)

| Source                          | Destination                                  |
|---------------------------------|----------------------------------------------|
| `qc_routes.py`                  | `D:\hcperpnew\qc_routes.py`                  |
| `templates/qc/trs_review.html`  | `D:\hcperpnew\templates\qc\trs_review.html`  |

Phir Flask restart (`python .\index.py`) + browser **Ctrl + F5**.
(qc_routes.py me naya endpoint hai isliye restart zaroori hai.)

## Flow
1. QC Department → RM/PM TRS List → 🔬 Review.
2. Galti se Approve ho gaya? → neeche **Change Decision / Re-open** → confirm.
3. Stock reverse ho jayega, status Pending → ab dobara Approved/Rejected karo.

> Koi DB migration nahi chahiye — sirf maujooda tables use hote hain.
