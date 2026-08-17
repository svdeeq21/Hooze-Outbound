# New Campaign Intake — [CAMPAIGN NAME]

Fill this in completely, top to bottom, before setting `campaigns.status`
to `ACTIVE`. Source: `docs/09-campaign-spec.md` §5 ("Adding a new
campaign") — this is that 5-step process turned into a fillable template so
each new campaign (002, 003, ...) starts from the same shape Campaign 001
did, instead of skipping a step under time pressure.

Copy this file to `campaign-XXX-[short-name].md` per new campaign, fill it
in, then use it as the source for the actual `campaigns` table insert.

---

## Step 1 — ICP section

Reference (or write, if new): `docs/02-icp-spec.md` §_____

- **Industry:** _______________________________________________
- **Location:** _______________________________________________
- **Firmographic signals that qualify a company for this ICP** (bullet
  list — what makes a company "in scope" before you even look at pain
  signals):
  -
  -
  -
- **Disqualifiers specific to this ICP** (beyond the global ones in
  `docs/02-icp-spec.md` §2.2, if any):
  -

If this is a genuinely new vertical (like the planned CAMPAIGN 003 /
Nigerian clinics), don't skip this step — write the full ICP section in
`docs/02-icp-spec.md` first and reference it here. Reusing Campaign 001's
ICP language for a different industry produces a scoring engine that
silently doesn't fit the new vertical.

## Step 2 — `campaigns` row (insert with `status = 'DRAFT'`)

```sql
insert into campaigns (name, industry, target_location, offer, pain, proof, cta, status)
values (
  'CAMPAIGN 0__ — [name]',
  '[industry — must exactly match companies.industry values you expect to score against]',
  '[target_location — must exactly match companies.location values]',
  '[offer — one sentence, what Hooze is selling]',
  '[pain — the specific problem this campaign targets]',
  '[proof — a real deployment/case study, or NULL if none yet]',
  '[cta — the single ask, e.g. "Offer a short (15-min) demonstration"]',
  'DRAFT'
);
```

Fill in the bracketed values above, then run it against Supabase.
**`industry` and `target_location` must match `companies` values exactly**
(case-sensitive string match in `python/campaign/matcher.py`) — this is the
single most common way a new campaign silently matches zero leads.

## Step 3 — Personalization prompt override (only if needed)

Does this campaign's pain/hook pattern differ meaningfully from Campaign
001's? (New industry almost always → yes. Same industry, different
geography → usually no.)

- ☐ No — Campaign 001's `prompts/personalizer.md` applies as-is.
- ☐ Yes — write the override below, then save it as
  `prompts/personalizer-campaign-0__.md` and note here that
  `python/personalization/generator.py`'s `_PROMPT_PATH` needs a
  per-campaign lookup added (it currently loads one fixed prompt file —
  see that module's docstring; this is a real code change, not just a
  new file, if you check this box).

Override notes:
_______________________________________________
_______________________________________________

## Step 4 — Test against sample leads

- ☐ Manually identified 3–5 real companies fitting this ICP
- ☐ Ran them through the pipeline (or scored/personalized them manually)
  and read the output for accuracy and tone
- ☐ Evidence quality looked sufficient (not mostly LOW confidence)
- ☐ Draft messages didn't need heavy editing to sound right

List the 3–5 test companies and a one-line verdict on each:

| Company | Verdict |
|---|---|
| | |
| | |
| | |

Do not proceed to Step 5 if fewer than 3 of your 3–5 test leads passed.

## Step 5 — Activate

```sql
update campaigns set status = 'ACTIVE' where name = 'CAMPAIGN 0__ — [name]';
```

- **Activated by:** _______________________
- **Date:** _______________________

Once ACTIVE, this campaign starts competing for matches in WF-07
(`python/campaign/matcher.py`) alongside every other ACTIVE campaign whose
industry/location overlaps — double-check you're not accidentally creating
a conflict with an existing campaign for the same industry+location
combination (matching logic picks one deterministically per
`docs/09-campaign-spec.md` §4, but two campaigns silently splitting the
same leads is usually not what you intended).
