-- Source: DosscoDesigns/slime feat/manufacturing-calculator c47d8d2, db/migrations/0001_slime_traceability.sql
-- APPLIED TO PROD 2026-11-20 directly via the pooler (Jason's OK in JARVIS-dd), together with:
--   create role slime_app login password '<op://DEV/slime.db>';   (password lives only in 1Password)
-- Local stacks: create the slime_app role first (any password) or the grants below fail.

-- The Slime Guys: batch traceability (bulk color lots → packed kit lots).
--
-- Applied by the dd session into DD's Supabase (it owns ~/dev/dd/infra).
-- Trace chain: supplier lot → bulk color lot → pack lot (one FNSKU) → FBA label.
-- The recipe is NOT stored here; it lives only in the SLIME_RECIPE env var.
--
-- SECURITY: the `slime` schema must NOT be added to the Data API's exposed
-- schemas. The app connects as the dedicated `slime_app` role over Postgres,
-- never through PostgREST, so neither the anon key nor a leaked service key
-- can reach these tables over HTTP.

create schema if not exists slime;

create table slime.bulk_lots (
  id              bigserial primary key,
  lot_code        text not null unique,            -- YYMMDD-CC-RUN, e.g. 261030-YL-42
  made_on         date not null,
  color           text not null check (color in ('red','yellow','green','blue')),
  color_code      text not null check (color_code in ('RD','YL','GR','BL')),
  run_no          integer not null check (run_no > 0),
  base_ingredient text check (base_ingredient in ('poly','malto')),
  base_lb         numeric(8,2) check (base_lb > 0),
  pouches_filled  integer not null check (pouches_filled >= 0),
  supplier_lots   text,
  location        text,
  notes           text,
  created_at      timestamptz not null default now(),
  unique (made_on, color, run_no)
);

-- One row per FNSKU packed in a packing run. Every row of a run shares the
-- run's lot_code (MP-YYMMDD-RUN); the variant tells them apart.
create table slime.pack_lots (
  id          bigserial primary key,
  lot_code    text not null,                        -- MP-YYMMDD-RUN
  packed_on   date not null,
  run_no      integer not null check (run_no > 0),
  variant_id  text not null,                        -- e.g. multi-20, red-40 (src/lib/packaging.ts)
  fnsku       text,
  kits        integer not null check (kits > 0),
  packed_by   text,
  location    text,
  notes       text,
  created_at  timestamptz not null default now(),
  unique (lot_code, variant_id)
);

-- Which bulk lots went into which pack lot. The lot follows the material.
create table slime.pack_components (
  pack_lot_id  bigint not null references slime.pack_lots(id) on delete cascade,
  bulk_lot_id  bigint not null references slime.bulk_lots(id) on delete restrict,
  pouches_used integer not null check (pouches_used > 0),
  primary key (pack_lot_id, bulk_lot_id)
);

create index pack_components_bulk_idx on slime.pack_components (bulk_lot_id);

-- security_invoker: the view reads with the caller's rights, so it can't see past RLS.
create view slime.bulk_lot_balances with (security_invoker = true) as
select b.*,
       coalesce(sum(c.pouches_used), 0)::int                    as pouches_used,
       (b.pouches_filled - coalesce(sum(c.pouches_used), 0))::int as pouches_remaining
from slime.bulk_lots b
left join slime.pack_components c on c.bulk_lot_id = b.id
group by b.id;

-- Lock down: nothing for the API roles, everything for the app role.
alter table slime.bulk_lots       enable row level security;
alter table slime.pack_lots       enable row level security;
alter table slime.pack_components enable row level security;

revoke all on schema slime from public;
do $$
begin
  if exists (select 1 from pg_roles where rolname = 'anon') then
    execute 'revoke all on all tables in schema slime from anon, authenticated';
  end if;
  if exists (select 1 from pg_roles where rolname = 'service_role') then
    execute 'revoke all on all tables in schema slime from service_role';
  end if;
end $$;

-- Create the role first: create role slime_app login password '<from 1Password>';
grant usage on schema slime to slime_app;
grant select, insert, update, delete on all tables in schema slime to slime_app;
grant usage, select on all sequences in schema slime to slime_app;
-- RLS policies for the app role only; every other role has no policy and so no rows.
-- (Not bypassrls: Supabase's postgres role is not a superuser and can't grant it.)
create policy slime_app_all on slime.bulk_lots       for all to slime_app using (true) with check (true);
create policy slime_app_all on slime.pack_lots       for all to slime_app using (true) with check (true);
create policy slime_app_all on slime.pack_components for all to slime_app using (true) with check (true);
