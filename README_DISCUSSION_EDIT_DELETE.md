# NPD Discussion Board — Edit & Delete Patch

Adds **Edit** and **Delete** options to comments on the NPD Project View's
Discussion Board AND Internal Discussion Board.

## What this patch does

- A small "✏️ Edit" and "🗑 Delete" button is shown next to each comment.
- Buttons are **only visible to the comment's author or to an admin**
  (`current_user.role == 'admin'`). Other users do not see them.
- **Edit** → opens a full rich-text editor (same toolbar as the compose box:
  **B**, *I*, U, • bullets, 1≡ ordered list, 🖼 inline image, 📎 file attach)
  with Save / Cancel buttons.
- **Inline images** pasted/dropped/uploaded into the edit area are embedded
  as base64 in the comment HTML — no reload needed.
- **File attachment** (📎) during edit *replaces* the existing attached file.
  The old file is removed from disk. After a file replacement the page
  reloads automatically so the new chip/image shows correctly.
- Text-only edits update the comment **in place** without a page reload.
- **Delete** → asks for confirmation, then deletes the comment AND its
  attached file (if any). Page reloads to the same tab.
- An `(edited)` tag is shown next to the timestamp once a comment is edited,
  with the edit time visible on hover.
- Every edit/delete is recorded in the **NPD Activity Log**.

## Files in this patch

| File in this patch                            | Goes to (in your project)            | Action  |
| --------------------------------------------- | ------------------------------------ | ------- |
| `npd_model.py`                                | `models/npd.py`                      | Replace |
| `npd_routes.py`                               | `npd_routes.py`                      | Replace |
| `project_view.html`                           | `templates/npd/project_view.html`    | Replace |
| `add_npd_comment_edited_column.py`            | project root                         | New     |

## Installation steps

1. **Back up** these three files first (just in case):
   - `models/npd.py`
   - `npd_routes.py`
   - `templates/npd/project_view.html`

2. **Copy the patched files** from this zip into your project, overwriting
   the originals.

3. **Run the migration** to add the `edited_at` column to the
   `npd_comments` table (MySQL — uses the same credential pattern as
   `add_milestone_key_column.py`):

   ```bash
   python add_npd_comment_edited_column.py
   ```

   If your MySQL credentials differ from the defaults in `config.py`
   (`root` / `Krunal@2424` / `erpdb`), edit `DB_USER`, `DB_PASS`, `DB_NAME`
   at the top of the script before running.

4. **Restart the app** (Flask / gunicorn / your dev server).

5. Open any NPD project → Discussion Board → you should now see Edit / Delete
   buttons next to your own comments.

## Notes

- Admins (`role == 'admin'`) can edit/delete any comment, not just their own.
- The print view (`🖨️ Print`) excludes the Edit/Delete buttons automatically.
- Edited comments still show original `created_at`; the `(edited)` tag carries
  the most recent edit time in its tooltip.
- This patch is additive — no existing data is modified or removed, and
  existing comments simply gain the new option.
