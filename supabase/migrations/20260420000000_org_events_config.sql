-- Org events config: add events_enabled flag, cascade delete on event price rules

-- 1. Add events_enabled to orgs
ALTER TABLE orgs ADD COLUMN IF NOT EXISTS events_enabled BOOLEAN DEFAULT false;

-- Backfill: RCC already has events
UPDATE orgs SET events_enabled = true WHERE org_code = 'RCC';

-- 2. Add ON DELETE CASCADE to price_rules.event_id FK
-- Drop existing FK and re-add with cascade
ALTER TABLE price_rules DROP CONSTRAINT IF EXISTS price_rules_event_id_fkey;
ALTER TABLE price_rules
  ADD CONSTRAINT price_rules_event_id_fkey
  FOREIGN KEY (event_id) REFERENCES events(id) ON DELETE CASCADE;
