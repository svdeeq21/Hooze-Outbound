# Rejection Reason Categories

`docs/10-outreach-sop.md` §3 requires a rejection reason on every REJECT
action, and says it "feeds scoring/research quality improvements."
`docs/15-analytics-spec.md` §3 tracks a rejection rate and expects
rejection reasons "categorized and reviewed monthly." Neither doc actually
defines the categories — this does, so `outreach.rejection_reason` stays
short, consistent, and easy to count instead of every rejection being a
unique freeform sentence.

**Usage:** when rejecting a message in the dashboard, start the reason with
one of these tags, then add a specific note. The dashboard's reject prompt
is freeform text — it will accept anything — but sticking to this format
is what makes the monthly review actually answerable ("how many rejections
were bad evidence this month?") instead of requiring someone to re-read
every rejection line by line.

| Tag | Use when... | Feeds back into |
|---|---|---|
| `BAD_EVIDENCE` | The evidence cited is technically real but doesn't actually support a compelling pain/buying signal, or evidence is thin/generic | `docs/07-research-engine.md` — research engine isn't finding strong enough signal; consider tightening `prompts/researcher.md` or the site-fetch coverage in `python/research/fetcher.py` |
| `WRONG_TONE` | Evidence and targeting are fine, but the message reads off — too salesy, too stiff, doesn't sound like it came from someone who looked at the business | `prompts/personalizer.md` — prompt tuning, not a targeting problem |
| `NOT_ACTUALLY_A_FIT` | On reading the evidence, this company isn't really a fit for the ICP/campaign even though it scored high enough to reach REVIEW | `docs/02-icp-spec.md` / `python/scoring/engine.py` — the scoring rules let something through that shouldn't have qualified; look at whether a disqualifier or ICP condition needs tightening |
| `STALE_EVIDENCE` | The research is accurate but old enough that it might not reflect the business's current state (e.g. site clearly redesigned since research ran) | `docs/07-research-engine.md` §7 rate/freshness — may need a re-research trigger for leads that sit in REVIEW too long |
| `DUPLICATE_OR_ALREADY_CONTACTED` | This company (or a clear duplicate of it) has already been contacted, despite reaching REVIEW again | `python/enrichment/dedup.py` — a dedup match was missed; check why (different phrasing of name, no shared phone/email key) |
| `WRONG_CONTACT` | The named contact is clearly wrong (title doesn't fit, or evidence suggests they've left the company) — separate from a WRONG_PERSON *reply*, this is catching it before send | `python/research/` contact-finding step — confidence scoring on this contact needs revisiting |
| `OTHER` | Doesn't fit any category above | Note the specific reason in full; if `OTHER` starts showing up often, that's a signal this taxonomy needs a new category, not that rejections are unclassifiable |

**Monthly review:** count rejections by tag (`outreach.rejection_reason` in
Supabase can be filtered by prefix), and use `BAD_EVIDENCE` /
`NOT_ACTUALLY_A_FIT` volume as an early warning the way
`docs/15-analytics-spec.md` §9's feedback loop describes — high volume in
either means revisit `docs/02-icp-spec.md` / `docs/06-scoring-engine.md`
before assuming the problem is somewhere else in the pipeline.
