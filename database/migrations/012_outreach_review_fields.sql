-- Migration 012: outreach review-workflow fields
-- Depends on: 006_outreach.sql
-- Reference: docs/10-outreach-sop.md §3
--
-- Added after the initial schema draft: §3 requires (a) preserving the
-- original AI-drafted message when Hooze edits it before approving ("kept
-- in a draft_history note field"), and (b) logging WHY a message was
-- rejected ("A rejection reason is logged... feeds scoring/research
-- quality improvements"). Neither had a column in the v1.0 draft schema —
-- this migration closes that gap. See BUILD_LOG.md item #5.

alter table outreach add column if not exists draft_history text;
alter table outreach add column if not exists rejection_reason text;

comment on column outreach.draft_history is
  'Original AI-generated message text, preserved verbatim if Hooze edits outreach.message before approving (docs/10-outreach-sop.md §3). NULL if never edited.';
comment on column outreach.rejection_reason is
  'Free-text reason logged when outreach.status -> REJECTED (docs/10-outreach-sop.md §3). Feeds scoring/research quality review (docs/15-analytics-spec.md §3 rejection rate).';
