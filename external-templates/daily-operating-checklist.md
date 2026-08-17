# Hooze Outbound — Daily Operating Checklist

Source: `docs/10-outreach-sop.md` §7. This is the same six items, expanded
with what to actually look at/click for each one — meant to be kept open
in a tab (or printed) while running the daily routine, not read once and
memorized.

**Date:** _______________

---

### 1. ☐ Check the error monitor (WF-15)

- Check the Telegram channel/chat WF-15 posts to for anything from the
  last 24h — pipeline errors and stuck-lead warnings both land there.
- If nothing came through, no action needed (WF-15 only notifies on new
  errors or leads stuck 7+ days — silence means clean).
- If something did come through: open `error_log` (via the dashboard, or
  directly in Supabase) and read the `error_message` + `payload` for
  context before deciding whether it needs a fix or was expected
  (e.g. "no website on record" for a company you know has none isn't a
  real problem).

### 2. ☐ Review the REVIEW queue

- Open `dashboard/index.html` → **Review Queue** tab.
- Cards are already sorted A → B → C by `lead_scores.priority` — work
  top to bottom.
- For each card: read the score reason line, skim the evidence list
  (each claim is a link to its source — spot-check a couple), read the
  drafted message.
- **Approve** if it's accurate and on-tone as-is.
- **Edit** then **Approve** if it needs a tweak — the original AI draft
  is preserved automatically (`outreach.draft_history`), you're not
  losing anything by editing.
- **Reject** if it's not salvageable — you'll be asked for a reason.
  Use one of the categories in `rejection-reason-categories.md` where it
  fits, so these stay easy to aggregate later.

### 3. ☐ Send all APPROVED messages

- Open the **Send Queue** tab (same dashboard) — these are the messages
  you just approved (or approved on a previous day and haven't sent yet).
- For each: actually send it via WhatsApp Web/Business app or Gmail,
  copying the message text shown.
- Don't send from this step directly — the dashboard doesn't send
  anything on your behalf, it's just showing you what's ready
  (`docs/10-outreach-sop.md` §4).

### 4. ☐ Mark sent messages as SENT

- Immediately after actually sending each message (don't batch this to
  the end — do it right after each send so you don't lose track of
  which ones went out), click **Mark as Sent** on that card in the Send
  Queue.
- This is what schedules the first follow-up and flips the company to
  CONTACTED — skipping it means the follow-up scheduler won't know to
  follow up.

### 5. ☐ Check REPLIED leads

- Open the **Replied** tab.
- For each card: read the reply and the classification the system
  assigned. If it looks wrong, that's worth a note for classifier
  tuning (not something to fix in this dashboard directly in V1).
- **INTERESTED / MEETING / PRICE** replies are the ones to act on
  *immediately*, not just log — these are also the ones that trigger a
  Telegram notification the moment they come in (WF-12), so you may
  already know about them before this step. Move them to the right
  opportunity stage from the card.

### 6. ☐ Weekly only: check analytics

- Not a daily item — `docs/15-analytics-spec.md` §8 is explicit that this
  is a weekly check, not a daily distraction. Skip this box on days that
  aren't your weekly review day.
- When you do check it: look at the funnel snapshot first, then anything
  flagged at the top (unsubscribe rate spike, rejection rate spike) before
  the full campaign comparison table.

---

**Notes / anything unusual today:**

_______________________________________________
_______________________________________________
_______________________________________________
