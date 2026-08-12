-- Airtable fully retired (2026-07) — the worker's Airtable→Supabase sync has
-- been removed from the codebase. Drop the sync bookkeeping tables.
-- Apply manually (Studio or psql) AFTER the sync-removal branch is merged and
-- deployed, so no running worker still references them.

DROP TABLE IF EXISTS sync_error_log;
DROP TABLE IF EXISTS sync_state;
DROP TABLE IF EXISTS airtable_id_map;
