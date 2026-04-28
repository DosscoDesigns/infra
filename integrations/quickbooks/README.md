# QuickBooks Online Integration

Python client + migration tooling for the Dossco Designs Wave→QBO migration and ongoing Stripe→QBO bookkeeping.

## Layout

```
src/qbo/           QBO API client + token manager
src/migration/     One-shot Wave→QBO migration modules (chart of accounts, customers, items, opening balances, A/R, A/P, reconciliation)
src/bookkeeping/   Phase 2 helpers — create Sales Receipts from Stripe transactions
tests/             Smoke + unit tests
plans/             Generated migration plans (dry-run output) — gitignored
```

## Credentials

All secrets in 1Password DEV vault:
- `dd.intuit.client-prod` — OAuth client ID + secret
- `dd.intuit.tokens-prod` — refresh token + realm ID

The client reads these at runtime via `op read`. No `.env` files with secrets.

## Migration usage

```bash
# Dry run — print the plan without writing
python -m migration --dry-run --all

# Single step
python -m migration --step accounts --dry-run

# Actually execute
python -m migration --all
```

See `~/dev/dd/infra/TEMP/wave-export/AUDIT.md` for the full migration plan and decisions.
