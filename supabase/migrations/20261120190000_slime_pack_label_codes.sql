-- Source: DosscoDesigns/slime feat/manufacturing-calculator f7f1c35, db/migrations/0002_slime_pack_label_codes.sql
-- NOT YET APPLIED TO PROD — waits for Jason's OK; apply directly via the pooler, then update this line.
-- Pre-check 2026-11-20 (prod, read-only): constraint pack_lots_lot_code_variant_id_key exists,
-- slime.pack_lots/bulk_lots/pack_components all 0 rows, only FK into pack_lots is on id.
-- Pack rows now carry the code printed on the label, not a per-run code.
--
-- A single-color kit filled from one bulk lot is labelled with that lot's
-- code (261120-RD-41), so the same code can recur across packing runs for
-- the same FNSKU. Kits that span lots, and every multi, get MP-YYMMDD-NN.
-- run_no stays as the packing-run counter that groups rows for reprinting.
alter table slime.pack_lots drop constraint if exists pack_lots_lot_code_variant_id_key;
create index if not exists pack_lots_lot_code_idx on slime.pack_lots (lot_code);
create index if not exists pack_lots_run_no_idx on slime.pack_lots (run_no);
