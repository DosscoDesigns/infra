# DD Secrets Management

All DD project secrets live in the **`Dossco Designs LLC`** 1Password vault and are injected into processes at runtime via `op run`. No real `.env` file is ever written to disk.

This is a **single-developer, multi-environment** version of the NATCA pattern (`~/dev/mynatca/platform/dev-standards/rules/secrets-management.md`). Simplified for a solo workflow but structured to scale to staging/prod when needed.

## How It Works

```
~/.zshenv ── OP_SERVICE_ACCOUNT_TOKEN (default: NATCA token)
                        │
                        ▼
cd ~/dev/dd  ──► direnv loads .envrc ──► OP_SERVICE_ACCOUNT_TOKEN overridden (DD token)
                        │
                        ▼
            op run --env-file=.env.template -- <cmd>
                        │
                        ▼
            secrets resolved from 1Password → injected as env vars
            → child process has secrets in memory only
            → never written to disk
```

**Session persistence:** The DD service account token is auto-exported by `direnv` on every `cd` into `~/dev/dd`. One-time `direnv allow` per machine, then every new shell, terminal, editor, and Claude Code session picks it up automatically. No logins, no Touch ID, no prompts.

## File Layout

| File | Committed? | Purpose |
|---|---|---|
| `~/dev/dd/.envrc` | **no** (gitignored) | Exports `OP_SERVICE_ACCOUNT_TOKEN` for DD work; loaded by direnv |
| `~/dev/dd/dd/.env.template` | **yes** | Committed template with `op://` references for every env var |
| `~/dev/dd/dd/.env` | **no** (gitignored) | Legacy — delete once template workflow verified |

## 1Password Item Structure

Items follow the NATCA naming convention: **`<project>.<env>.<service>`** for env-specific items, **`<project>.<service>`** for env-agnostic items.

| Item | Category | Env | Fields |
|---|---|---|---|
| `dd.local.supabase` | Database | `env:local` | `url`, `service_role_key` |
| `dd.airtable` | API Credential | `env:cross-env` | `credential`, `vite_token`, `base_id` |
| `dd.cloudinary` | API Credential | `env:cross-env` | `cloud_name`, `api_key`, `api_secret` |
| `dd.sanmar` | API Credential | `env:cross-env` | `customer_number`, `username`, `password`, `soap_url`, `sftp_host`, `sftp_port`, `sftp_user`, `sftp_pass` |

All items tagged `project:dd`. Env-specific items tagged by environment; env-agnostic items (SanMar, Cloudinary — same creds regardless of dev/staging/prod) tagged `env:cross-env`.

### Adding new environments

When DD adds staging or production Supabase, create new items following the pattern:

```
dd.staging.supabase    (tags: env:staging, project:dd)
dd.prod.supabase       (tags: env:prod,    project:dd)
```

Keep the field structure identical so env-specific `.env.template` files can share the same variable names.

## Quick Start (new machine)

```bash
# 1. Install tools
brew install 1password-cli direnv

# 2. Add direnv hook (one-time, already done on this machine)
echo 'eval "$(direnv hook zsh)"' >> ~/.zshrc
source ~/.zshrc

# 3. Create ~/dev/dd/.envrc with the DD service account token
#    (Get token from 1Password: "1Password Service Account - DD Dev" or similar)
cat > ~/dev/dd/.envrc <<'EOF'
export OP_SERVICE_ACCOUNT_TOKEN="ops_..."
EOF
chmod 600 ~/dev/dd/.envrc

# 4. Approve the .envrc
cd ~/dev/dd
direnv allow

# 5. Verify everything resolves
cd ~/dev/dd/dd
pnpm run secrets:validate
```

## Reference URI Format

```
op://<Vault Name>/<Item Name>/<Field>
```

Example: `op://Dossco Designs LLC/dd.local.supabase/service_role_key`

Vault names with spaces work inside `op://` URIs — no quoting or escaping needed.

## Adding a New Secret

1. Add the field to the appropriate 1Password item (or create a new item per the naming convention)
2. Add a line to `.env.template`:
   ```
   NEW_SECRET=op://Dossco Designs LLC/dd.<env>.<service>/<field>
   ```
3. Commit the template change — `pnpm run dev` picks it up automatically

## Adding a New Service

Use `op item create`:

```bash
op item create \
  --category "API Credential" \
  --vault "Dossco Designs LLC" \
  --title "dd.<env>.<service>" \
  --tags "env:<env>,project:dd" \
  "field1[text]=value" \
  "secret1[concealed]=value"
```

Use `Database` category for DB connection items, `API Credential` for tokens/keys, `Server` for SSH/SFTP-only items.

## Escape Hatches

If `op` is broken or you're offline:

```bash
pnpm run dev:raw        # skips op run — requires manual .env fallback
```

Don't rely on `:raw` for normal work. It exists for debugging and offline recovery.

## Service Account Permissions

The DD service account has **read-write** access to the `Dossco Designs LLC` vault. For production runtime you'd want a separate **read-only** token, but for a single-dev workflow with local-only secrets the write access is convenient for managing items via CLI.

If a machine is compromised or a token leaks, rotate in 1Password:
1. 1Password web → Integrations → Service Accounts → DD Dev → Regenerate
2. Update `~/dev/dd/.envrc` with the new token
3. `direnv reload`

## Related

- NATCA full standard: `~/dev/mynatca/platform/dev-standards/rules/secrets-management.md`
- Dev ports: `BRAIN/_System/DEV-SETUP/DEV_PORTS.md`
- Supabase local setup: `BRAIN/_System/DEV-SETUP/Local-Supabase-Setup.md`
