-- Seed data — Campaign 001 + two sample leads, for pipeline testing.
-- See docs/09-campaign-spec.md and docs/06-scoring-engine.md §6 worked examples.
--
-- Two companies are seeded so python/scoring/engine.py (and tests/scoring/)
-- have a realistic HIGH-scoring lead and a realistic LOW-scoring lead to run
-- against, per the README build order: "ICP scoring (WF-06) — build this
-- early against seed data even before research is fully automated."
--
-- NOTE on docs/06-scoring-engine.md §6 worked examples: those examples show
-- ICP scores like "23/25" and "18/25" which aren't reachable under the literal
-- point rule in §2.1 (four flat conditions worth 10/5/5/5 — any achievable
-- total is one of 0/5/10/15/20/25, never 23 or 18). This seed reproduces the
-- worked examples' EVIDENCE profile faithfully; the actual scores your
-- engine computes from this data will differ slightly from the doc's
-- illustrative numbers for that reason. See BUILD_LOG.md item #3.

with campaign as (
  insert into campaigns (name, industry, target_location, offer, pain, proof, cta, status)
  values (
    'CAMPAIGN 001 — Abuja Real Estate WhatsApp Automation',
    'Real Estate',
    'Abuja',
    'Hooze CRM — WhatsApp AI sales + lead qualification + inspection booking automation',
    'Manual/slow WhatsApp inquiry handling, no automated qualification or inspection booking',
    'Praise Dynasty Realty (PDR) deployment',
    'Offer a short (15-min) demonstration',
    'ACTIVE'
  )
  returning id
),

-- ---------------------------------------------------------------------
-- Lead A: "Prime Estate" — intended to land Tier A (high score), evidence
-- deliberately mirrors docs/06-scoring-engine.md §6 "high score" example.
-- ---------------------------------------------------------------------
company_a as (
  insert into companies (name, normalized_name, industry, location, whatsapp, website, source, source_url, status)
  values (
    'Prime Estate',
    'prime estate',
    'Real Estate',
    'Abuja',
    '+2348000000000',
    'https://example-prime-estate.com',
    'manual',
    'https://example-prime-estate.com',
    'RESEARCHED'
  )
  returning id
),
contact_a as (
  insert into contacts (company_id, name, job_title, email, linkedin, contact_source, confidence)
  select id, 'Mr. Sunday', 'Managing Director', 'sunday@example-prime-estate.com',
         'https://linkedin.com/company/prime-estate-example',
         'Named on LinkedIn company page + site About page', 'HIGH'
  from company_a
  returning company_id
),
research_a as (
  insert into research (
    company_id, website_summary, services, target_market, whatsapp_present,
    booking_process, lead_capture_process, observed_problem, pain_signals,
    buying_signals, proof, research_score
  )
  select
    id,
    'Real estate agency site listing 40+ residential and commercial properties across Abuja, WhatsApp click-to-chat button on every listing page.',
    ARRAY['Property sales', 'Property rentals', 'Inspection scheduling'],
    'Middle-to-high income home buyers and renters in Abuja',
    true,
    'Inquiries route directly to a phone number; no booking widget observed',
    'WhatsApp click-to-chat button on listing pages; no visible form or chatbot',
    'WhatsApp inquiries may require repeated manual qualification before an inspection is booked, since there is no automated flow between "chat with us" and a scheduled visit',
    ARRAY['whatsapp_primary_manual', 'no_automated_qualification', 'high_listing_volume_vs_team_size'],
    ARRAY['hiring_customer_service', 'multiple_branches'],
    '40+ active listings across 2 branches (Wuse II, Gwarinpa)',
    90
  from company_a
  returning company_id
)
insert into research_evidence (company_id, claim, source_url, confidence)
select company_a.id, e.claim, e.source_url, e.confidence
from company_a, (values
  ('WhatsApp contact button visible on every listing page', 'https://example-prime-estate.com/listings', 'HIGH'),
  ('40+ active property listings across the site', 'https://example-prime-estate.com/listings', 'HIGH'),
  ('No visible automated qualification or booking flow — inquiries go to a phone number', 'https://example-prime-estate.com/contact', 'MEDIUM'),
  ('Two branch locations listed (Wuse II, Gwarinpa)', 'https://example-prime-estate.com/about', 'HIGH'),
  ('LinkedIn job post for "Customer Service / WhatsApp Inquiries Officer" posted within last 30 days', 'https://linkedin.com/company/prime-estate-example/jobs', 'HIGH'),
  ('Named Managing Director (Mr. Sunday) listed on About page and LinkedIn', 'https://example-prime-estate.com/about', 'HIGH')
) as e(claim, source_url, confidence);

-- ---------------------------------------------------------------------
-- Lead B: "Random Realty Page" — intended to land DONT_CONTACT (low score),
-- mirrors docs/06-scoring-engine.md §6 "below threshold" example.
-- ---------------------------------------------------------------------
with company_b as (
  insert into companies (name, normalized_name, industry, location, whatsapp, source, status)
  values (
    'Random Realty Page',
    'random realty page',
    'Real Estate',
    'Abuja',
    '+2348011111111',
    'instagram',
    'RESEARCHED'
  )
  returning id
),
contact_b as (
  insert into contacts (company_id, name, job_title, email, contact_source, confidence)
  select id, null, null, 'info@randomrealty.example',
         'Generic inbox in Instagram bio, no named contact found', 'LOW'
  from company_b
  returning company_id
),
research_b as (
  insert into research (
    company_id, website_summary, services, target_market, whatsapp_present,
    booking_process, lead_capture_process, observed_problem, pain_signals,
    buying_signals, proof, research_score
  )
  select
    id,
    null,
    ARRAY['Property listings (Instagram only, no website)'],
    'Unclear — Instagram page only, no site',
    false,
    null,
    'DMs on Instagram, no structure observed',
    'Instagram-only presence with infrequent posting may mean inquiries are handled ad hoc, but there is little evidence to confirm a specific bottleneck',
    ARRAY['no_crm_evidence'],
    ARRAY[]::text[],
    null,
    25
  from company_b
  returning company_id
)
insert into research_evidence (company_id, claim, source_url, confidence)
select company_b.id, e.claim, e.source_url, e.confidence
from company_b, (values
  ('No booking/CRM tool links visible in Instagram bio or posts', 'https://instagram.com/randomrealtypage.example', 'LOW')
) as e(claim, source_url, confidence);

-- Note: both leads intentionally stop at RESEARCHED (not pre-scored) so
-- WF-06 / python/scoring/engine.py can be run against them end-to-end
-- rather than the seed pre-computing lead_scores rows itself.
