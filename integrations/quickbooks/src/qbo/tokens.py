"""Token manager for QBO OAuth.

Single source of truth for the ROTATING refresh token is the Supabase
`integration_tokens` row (provider='qbo') — the SAME row the DD Platform worker
(apps/worker/src/lib/qbo.js) uses. Keeping one shared row is what prevents the two
consumers from invalidating each other's refresh token: QBO rotates the refresh
token on refresh, so two independent stores of the same authorization lineage would
eventually break each other. That is the outage this design exists to avoid.

Static OAuth client credentials (id/secret) still come from 1Password — they don't
rotate. The realm id and the rotating refresh/access tokens live in Supabase.

Refresh coordination mirrors the worker: compare-and-swap on `version`. A refresh
only persists if the row hasn't changed since we read it; a losing writer re-reads
and adopts the winner's token instead of pushing a second rotation to Intuit.

Bootstrap (one-time cutover): `python -m qbo.tokens seed` copies the CURRENT 1Password
refresh token + realm into the Supabase row — same lineage, NOT a new OAuth grant.
"""
from __future__ import annotations

import base64
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Optional

import requests
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

OAUTH_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
CLIENT_ITEM = "op://DEV/dd.intuit.client-prod"
TOKENS_ITEM = "op://DEV/dd.intuit.tokens-prod"  # seed origin / backup only
SUPABASE_ITEM = "op://DEV/dd.prod.supabase"
ENC_KEY_ITEM = "op://DEV/dd.intuit.token-enc/credential"

ACCESS_MARGIN_S = 300  # refresh 5 min before expiry
PROVIDER = "qbo"
ENC_PREFIX = "gcm:"


def _enc_key() -> bytes:
    """AES-256 key (32 bytes), base64, shared with the worker's QBO_TOKEN_ENC_KEY."""
    b64 = os.environ.get("QBO_TOKEN_ENC_KEY") or _op_read(ENC_KEY_ITEM)
    return base64.b64decode(b64)


def _encrypt(plaintext: Optional[str]) -> Optional[str]:
    """gcm:base64( iv[12] || ciphertext || tag[16] ) — matches apps/worker/src/lib/qbo.js."""
    if plaintext is None:
        return None
    iv = os.urandom(12)
    ct_tag = AESGCM(_enc_key()).encrypt(iv, plaintext.encode(), None)  # ciphertext||tag
    return ENC_PREFIX + base64.b64encode(iv + ct_tag).decode()


def _decrypt(value: Optional[str]) -> Optional[str]:
    if not value or not value.startswith(ENC_PREFIX):
        return value
    raw = base64.b64decode(value[len(ENC_PREFIX):])
    iv, ct_tag = raw[:12], raw[12:]
    return AESGCM(_enc_key()).decrypt(iv, ct_tag, None).decode()


def _op_read(ref: str) -> str:
    out = subprocess.run(
        ["op", "read", ref], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def _supabase_conf() -> tuple[str, str]:
    """(url, service_role_key) from env, falling back to 1Password."""
    url = os.environ.get("SUPABASE_URL") or _op_read(f"{SUPABASE_ITEM}/url")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or _op_read(
        f"{SUPABASE_ITEM}/service_role_key"
    )
    return url.rstrip("/"), key


@dataclass
class Tokens:
    client_id: str
    client_secret: str
    realm_id: Optional[str] = None
    refresh_token: Optional[str] = None
    access_token: Optional[str] = None
    access_expires_at: float = 0.0  # epoch seconds
    version: int = 0


class TokenStoreError(RuntimeError):
    pass


class TokenManager:
    """Reads static client creds from 1Password and the rotating token from the
    shared Supabase `integration_tokens` row. Refreshes access tokens on demand and
    persists rotation via compare-and-swap."""

    def __init__(self) -> None:
        self._client: Optional[Tokens] = None
        self._base: Optional[str] = None
        self._key: Optional[str] = None
        self._cached_access: Optional[str] = None
        self._cached_expires: float = 0.0
        self._cached_realm: Optional[str] = None

    # ---- Supabase REST plumbing ----

    def _conf(self) -> tuple[str, str]:
        if self._base is None or self._key is None:
            self._base, self._key = _supabase_conf()
        return self._base, self._key

    def _headers(self) -> dict:
        _, key = self._conf()
        return {
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def _read_row(self) -> dict:
        base, _ = self._conf()
        resp = requests.get(
            f"{base}/rest/v1/integration_tokens",
            params={"provider": f"eq.{PROVIDER}", "select": "*"},
            headers=self._headers(),
            timeout=30,
        )
        resp.raise_for_status()
        rows = resp.json()
        if not rows:
            raise TokenStoreError(
                "integration_tokens row missing — run the migration and `python -m qbo.tokens seed`"
            )
        row = rows[0]
        # Decrypt token fields so callers see plaintext (see qbo.js for the format).
        row["refresh_token"] = _decrypt(row.get("refresh_token"))
        row["access_token"] = _decrypt(row.get("access_token"))
        return row

    def _cas_update(self, expected_version: int, patch: dict) -> list:
        """PATCH the row only if version still matches. Returns updated rows (empty
        if the CAS lost)."""
        base, _ = self._conf()
        headers = {**self._headers(), "Prefer": "return=representation"}
        resp = requests.patch(
            f"{base}/rest/v1/integration_tokens",
            params={"provider": f"eq.{PROVIDER}", "version": f"eq.{expected_version}"},
            headers=headers,
            json=patch,
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()

    # ---- Client creds (static, 1Password) ----

    def _load_client(self) -> Tokens:
        if self._client is None:
            self._client = Tokens(
                client_id=_op_read(f"{CLIENT_ITEM}/username"),
                client_secret=_op_read(f"{CLIENT_ITEM}/credential"),
            )
        return self._client

    # ---- Public API (unchanged signature for QBOClient) ----

    @property
    def realm_id(self) -> str:
        if self._cached_realm:
            return self._cached_realm  # realm never changes for a connection
        row = self._read_row()
        if not row.get("realm_id"):
            raise TokenStoreError("no realm_id stored — run `python -m qbo.tokens seed`")
        self._cached_realm = row["realm_id"]
        return self._cached_realm

    def access_token(self) -> str:
        """Return a valid access token, refreshing (with CAS) if necessary."""
        # In-memory cache avoids a Supabase round-trip on every API call.
        if self._cached_access and time.time() < (self._cached_expires - ACCESS_MARGIN_S):
            return self._cached_access

        row = self._read_row()
        if row.get("realm_id"):
            self._cached_realm = row["realm_id"]
        expires_at = _parse_ts(row.get("access_expires_at"))
        if row.get("access_token") and time.time() < (expires_at - ACCESS_MARGIN_S):
            self._cached_access, self._cached_expires = row["access_token"], expires_at
            return row["access_token"]

        refresh_token = row.get("refresh_token")
        if not refresh_token:
            raise TokenStoreError("no refresh_token stored — run `python -m qbo.tokens seed`")

        client = self._load_client()
        resp = requests.post(
            OAUTH_TOKEN_URL,
            auth=(client.client_id, client.client_secret),
            headers={"Accept": "application/json"},
            data={"grant_type": "refresh_token", "refresh_token": refresh_token},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()

        new_access = body["access_token"]
        new_expires = time.time() + int(body["expires_in"])
        new_refresh = body.get("refresh_token", refresh_token)

        updated = self._cas_update(
            row["version"],
            {
                "access_token": _encrypt(new_access),
                "access_expires_at": _iso(new_expires),
                "refresh_token": _encrypt(new_refresh),
                "version": row["version"] + 1,
                "updated_at": _iso(time.time()),
            },
        )
        if not updated:
            # Lost the race — another writer rotated. Adopt their token.
            fresh = self._read_row()
            if not fresh.get("access_token"):
                raise TokenStoreError("token vanished after CAS loss")
            self._cached_access = fresh["access_token"]
            self._cached_expires = _parse_ts(fresh.get("access_expires_at"))
            return fresh["access_token"]

        self._cached_access, self._cached_expires = new_access, new_expires
        return new_access


def _parse_ts(value: Optional[str]) -> float:
    if not value:
        return 0.0
    # Supabase returns ISO8601 with offset, e.g. 2026-08-10T19:00:00+00:00
    from datetime import datetime
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return 0.0


def _iso(epoch: float) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch, tz=timezone.utc).isoformat()


def seed_from_1password(force: bool = False) -> None:
    """One-time cutover: copy the CURRENT 1Password refresh token + realm into the
    shared Supabase row (same lineage, not a new grant). Refuses to overwrite an
    existing refresh_token unless force=True."""
    tm = TokenManager()
    row = tm._read_row()
    if row.get("refresh_token") and not force:
        print(
            f"integration_tokens already seeded (version {row['version']}). "
            "Pass --force to overwrite.",
            file=sys.stderr,
        )
        return
    refresh_token = _op_read(f"{TOKENS_ITEM}/credential")
    realm_id = _op_read(f"{TOKENS_ITEM}/username")
    updated = tm._cas_update(
        row["version"],
        {
            "realm_id": realm_id,
            "refresh_token": _encrypt(refresh_token),
            "access_token": None,
            "access_expires_at": None,
            "version": row["version"] + 1,
            "updated_at": _iso(time.time()),
        },
    )
    if not updated:
        raise TokenStoreError("seed CAS failed — row changed concurrently, retry")
    print(f"Seeded QBO tokens into Supabase (realm {realm_id}, version {updated[0]['version']}).")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "seed":
        seed_from_1password(force="--force" in args)
    else:
        print("usage: python -m qbo.tokens seed [--force]", file=sys.stderr)
        sys.exit(2)
