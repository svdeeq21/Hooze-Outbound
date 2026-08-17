# external-templates/

Everything in this folder is a document *outside* the codebase that the
system depends on — mostly the Google Sheets staging area WF-01 reads from
(`docs/13-n8n-architecture.md` WF-01). None of this is optional scaffolding;
WF-01 will fail to import without a real sheet built from these templates.

## 1. `staging-leads-template.csv` — the "Staging" tab

This is where leads get typed or pasted in before WF-01 imports them into
`companies`. Columns match the `companies` table's input fields exactly
(everything except system-generated columns like `id`, `normalized_name`,
`status`) — see `database/migrations/001_companies.sql`.

**Setup:**
1. Create a new Google Sheet (or reuse an existing one for the whole
   pipeline — WF-01 and WF-15 both need Sheets/Gmail OAuth either way).
2. Rename the first tab to exactly `Staging` (WF-01's Read node is
   configured to look for a tab named `Staging` — see
   `n8n/WF-01-lead-import.json`, node "Read Staging Sheet").
3. Import `staging-leads-template.csv` into that tab (File → Import → Upload
   → Replace current sheet), or just copy the header row and start typing.
4. Delete the two example rows before real use — they're there to show the
   expected shape, not real leads.

**Column notes:**
- `name` is the only required column (`docs/03-data-dictionary.md`) — a row
  with an empty name gets logged to `import_errors` and skipped, per WF-01's
  error path.
- `source` must be one of: `google_maps`, `linkedin`, `website`, `youtube`,
  `instagram`, `directory`, `referral`, `manual` (matches the `companies.source`
  check constraint in the schema — anything else will fail the insert).
- `phone`/`email`/`website` etc. are all optional at import time — WF-02
  (cleaning) and WF-04 (enrichment) fill gaps and normalize formats
  downstream. Don't pre-format phone numbers; `python/enrichment/normalize.py`
  handles that.
- `whatsapp`: only fill this in if you've *already* confirmed a WhatsApp
  number exists (e.g. you found a click-to-chat link). Otherwise leave it
  blank — WF-05 (research) will confirm and populate it from the site itself
  if present, rather than guessing from the phone number.

## 2. `import-errors-template.csv` — the "import_errors" tab

Where WF-01 logs rows it couldn't import, instead of silently dropping them
(`docs/13-n8n-architecture.md` WF-01 error path).

**Setup:**
1. Add a second tab to the same Google Sheet, named exactly `import_errors`
   (matches `n8n/WF-01-lead-import.json`, node "Log to import_errors tab").
2. Import `import-errors-template.csv`'s header row (delete the example row
   after — same as above).
3. This tab is append-only from WF-01's side; you don't need to do anything
   with it day-to-day except glance at it if a batch import looks smaller
   than expected. It feeds WF-15's "check for failed workflow runs" step
   indirectly (`docs/10-outreach-sop.md` §7) — worth a look during your
   daily checklist if you've just done a big import.

## 3. Wiring the Sheet ID into n8n

After creating the sheet, copy its ID from the URL
(`https://docs.google.com/spreadsheets/d/THIS_PART_IS_THE_ID/edit`) and
paste it into:
- `n8n/WF-01-lead-import.json` → "Read Staging Sheet" node → Document ID
- `n8n/WF-01-lead-import.json` → "Log to import_errors tab" node → Document ID

Both nodes currently have a placeholder value `GOOGLE_SHEET_ID` — either
edit the JSON directly before importing into n8n, or set it in the n8n
editor's node parameters after import (either works; editing in the n8n
UI is easier if you're not comfortable hand-editing the JSON).

## 4. Other documents in this folder

- `daily-operating-checklist.md` — Hooze's own daily routine
  (`docs/10-outreach-sop.md` §7), formatted as an actual checklist you can
  print or keep open, not just a doc reference.
- `new-campaign-intake-template.md` — a fill-in-the-blanks version of
  `docs/09-campaign-spec.md` §5's "Adding a new campaign" steps, so
  Campaign 002/003 (or any future campaign) starts from a consistent
  template instead of a blank page.
- `rejection-reason-categories.md` — a short standard taxonomy for the
  `outreach.rejection_reason` free-text field, so rejection reasons stay
  categorizable for the monthly review `docs/15-analytics-spec.md` §3
  calls for, instead of every rejection being a one-off sentence that's
  hard to aggregate later.

None of these three are referenced by name in any n8n workflow (they're
paper/process documents, not system inputs) — they exist because the specs
*describe* a checklist, an intake process, and a reason taxonomy without
ever actually writing one down as a standalone, usable document.
