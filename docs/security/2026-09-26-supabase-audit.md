# DD Supabase security audit — 2026-09-26

Requested by Jason ("definitely want RLS and security audit"). Performed by JARVIS-dd against
production project `bbrpsznwntrhvnobhxkp`. Every finding below was verified, not inferred:
statically from `pg_catalog`, then dynamically — on a prod-faithful local copy for anything
that would write, and live against prod (count-only, no row data pulled) for reads.

## Fixed tonight — applied to production and verified live

| # | Severity | Finding | Fix | Live proof after |
|---|---|---|---|---|
| 1 | **Critical** | Four views ran as their owner and bypassed RLS. With the **public anon key**, `v_orders` returned all **479 orders** incl. first/last name, business name, phone, notes, PO numbers; `order_messaging_state` all 479. The `orders` table itself correctly returned 0. | `security_invoker = true` on all 4 views; revoked anon/authenticated on the 3 private ones (`000100`) | anon `v_orders` 200/479 → **401** |
| 2 | **Critical** | Four policies *named* "Service role full access" were `FOR ALL USING (true) TO public`, and anon held INSERT/UPDATE/DELETE/TRUNCATE. On the local copy the anon key **deleted all 7,699 SanMar SKU mappings** (`vendor_variant_refs`, rolled back). Also `vendors`, `vendor_product_refs`, `category_mappings`. | Replaced with SELECT-only; revoked writes from anon/authenticated (`000100`) | anon POST `vendors` → **401**; reads still 206 |
| 3 | **High** | Storage policies *named* "Service role upload/update/delete" only checked `bucket_id`, role public — the anon key could upload any file (no size/MIME limit) into the public `decorations` bucket, overwrite customer-facing art, or delete it. | Dropped the three write policies; public read kept (`000200`) | anon upload → **403 RLS**; art still readable |
| 4 | Low | anon/authenticated held TRUNCATE on every table (TRUNCATE ignores RLS). Not reachable via PostgREST today. | Revoked (`000100`) | — |

Nothing in deployed code (`dd` origin/main) used any of the closed paths: the admin app reads
with the service_role key and the worker writes server-side as service_role, both of which
bypass RLS. Verified after apply: storefront reads (products 70, variants 8,539, orgs 12) and
admin reads (v_orders 479) all still work.

## Open — not fixed tonight

_Updated 2026-09-26 ~20:3x: **D, H, I and J–L are all fixed in three stacked `dd` PRs, none merged — merge order #127 → #128 → #129, Jason's word.** Each verified on its branch. Priority is now **A (the leaked key) → merge #127–#129**._

| # | Severity | Finding | Status |
|---|---|---|---|
| J | Medium | `/po` ungated — `POST /generate` writes purchase orders. | Fixed in #129 |
| K | Medium | `/print` ungated — `POST /zpl` prints arbitrary labels on the Zebra printers in Jason's house. | Fixed in #129 |
| L | Low | `/webhooks` verified the Twilio signature but **failed open** if `TWILIO_AUTH_TOKEN` was unset. Prod sets it (checked env key names only), so latent. | Fixed (fail-closed) in #129 |
| — | Bug | `verifyToken` crashed on a malformed token (`timingSafeEqual` RangeError), so every admin route returned 500 instead of 401. | Fixed in #127 |

After #129 the only ungated worker mounts are `/health`, `/auth`, `/public` (capability tokens), `/store` (public storefront), `/webhooks` (signature-verified) and `/qbo` connect/callback (secret + state), checked against `index.js`. `POST /square/devices/release` is deliberately left open: `sendBeacon` can't send headers, and it only releases the caller's own session reservation.

| # | Severity | Finding | Owner / next step |
|---|---|---|---|
| A | **Critical** | **The live admin bundle ships the prod `service_role` JWT** (`/assets/index-Bn4TgS-O.js`, sha256[:12] `b99469340ee9`, re-verified 2026-09-26). Anyone who downloads the admin JS has unrestricted read/write to the whole database; every fix above is moot against that holder. Public since at least 2026-09-04. | `dd` PR #117 (open, mergeable) stops publishing it — **then the key must be rotated**, since it has already been public. Runbook: `dd/docs/security/service-role-rotation.md`. Jason's word (prod deploy + rotation). |
| B | Medium | All 26 `public` functions are EXECUTE-able by anon via `/rpc`. All but two are SECURITY INVOKER, so RLS is the backstop and the service-role-only tables hold. The two SECURITY DEFINER ones are trigger functions (not callable as RPC). | Revoke EXECUTE from anon on everything the storefront does not call. |
| C | Medium | Supplier cost is anon-readable: `v_products.min_cost/max_cost`, `vendor_variant_refs.vendor_cost`. Business-sensitive, not PII. | Column-level revoke once the storefront's exact column use is confirmed. |
| D | **High** | Unauthenticated worker endpoints `/api/sanmar/*` (incl. `po/submit`, which places real SanMar orders — dd-ops item 106) and `/api/import/*`. dd-admin confirmed `/import` open by using it. Also found while fixing: `verifyToken` crashed on a malformed token (`timingSafeEqual` RangeError), so every admin route returned **500 instead of 401**. | **Fixed in `dd` PR #127, not merged** — the six web callers that sent no token now do. |
| H | **Critical** | **`POST /square/refund` is unauthenticated** (`square.js:499`, mounted bare at `index.js:45`; the only global middleware is request logging; `cors()` allows all origins). An anonymous request with a `paymentId` and `amount` issues a real Square refund. **Chains with A:** payment IDs are RLS-protected from the anon key, but the leaked service_role key reads `payments` — so anyone can refund every Square payment DD has taken. Verified statically only; a live POST moves money. | **Fixed in `dd` PR #128, not merged.** Caller audit: admin screens only. |
| I | **High** | **`POST /messages/send` is unauthenticated** (`messages.js:49`, mounted bare): SMS and email from DD's accounts to any recipient — spam/phishing in DD's name, billed to DD, deliverability damage. | **Fixed in `dd` PR #128, not merged.** |
| E | Low | 24 functions have no fixed `search_path`. Low risk for SECURITY INVOKER, but hygiene. | Set `search_path = public` when next touched. |
| F | Process | Migrations have been split across two repos since 2026-08-01 (`infra/` stops at 07-27, later ones in `dd/supabase/migrations`), and prod is applied directly — so no migration history reproduces prod. `infra/scripts/pull-prod-schema.sh` (PR #3) exists because of this. | Consolidate: new migrations land in `infra/` only. |
| G | Process | The "Service role …" naming trap: service_role bypasses RLS and never needs a policy, so a policy *named* for it but missing a role check is always a hole. Findings 2 and 3 were both this. | Review rule: no policy may be named for a role it does not check. |

## Applied migrations (all in `supabase/migrations/`, rollbacks in `supabase/rollbacks/`)

- `20260927000100_close_anon_exposure.sql` — findings 1, 2, 4
- `20260927000200_storage_write_policies.sql` — finding 3 (separate transaction on purpose)
- `20260927000300_quotes_module.sql` — dd-admin's quote schema (#116). One change by JARVIS-dd:
  its `CREATE OR REPLACE VIEW` now carries `WITH (security_invoker = true)` — replacing a view
  silently resets that option, which would have undone part of fix 1. Tested on a prod-state copy.

Each was rehearsed on a fresh prod-state local copy in prod order, re-run for idempotency, and
pre-flighted against prod's live definitions before applying.
