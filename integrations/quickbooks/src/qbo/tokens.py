"""Token manager: read from 1Password, refresh-on-expiry, persist rotation."""
from __future__ import annotations

import subprocess
import time
from dataclasses import dataclass
from typing import Optional

import requests

OAUTH_TOKEN_URL = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
CLIENT_ITEM = "op://DEV/dd.intuit.client-prod"
TOKENS_ITEM = "op://DEV/dd.intuit.tokens-prod"


def _op_read(ref: str) -> str:
    out = subprocess.run(
        ["op", "read", ref], capture_output=True, text=True, check=True
    )
    return out.stdout.strip()


def _op_edit_credential(item_title: str, new_value: str) -> None:
    subprocess.run(
        ["op", "item", "edit", item_title, f"credential={new_value}"],
        capture_output=True, text=True, check=True,
    )


@dataclass
class Tokens:
    client_id: str
    client_secret: str
    refresh_token: str
    realm_id: str
    access_token: Optional[str] = None
    access_expires_at: float = 0.0  # epoch seconds


class TokenManager:
    """Manages QBO OAuth tokens. Reads from 1Password, refreshes access tokens
    on demand, and persists rotated refresh tokens back to 1Password."""

    def __init__(self) -> None:
        self._tokens: Optional[Tokens] = None

    def _load(self) -> Tokens:
        if self._tokens is not None:
            return self._tokens
        self._tokens = Tokens(
            client_id=_op_read(f"{CLIENT_ITEM}/username"),
            client_secret=_op_read(f"{CLIENT_ITEM}/credential"),
            refresh_token=_op_read(f"{TOKENS_ITEM}/credential"),
            realm_id=_op_read(f"{TOKENS_ITEM}/username"),
        )
        return self._tokens

    @property
    def realm_id(self) -> str:
        return self._load().realm_id

    def access_token(self) -> str:
        """Return a valid access token, refreshing if necessary.
        Tokens are valid for 1 hour; we refresh with 5 min of safety margin."""
        t = self._load()
        if t.access_token and time.time() < (t.access_expires_at - 300):
            return t.access_token

        resp = requests.post(
            OAUTH_TOKEN_URL,
            auth=(t.client_id, t.client_secret),
            headers={"Accept": "application/json"},
            data={"grant_type": "refresh_token", "refresh_token": t.refresh_token},
            timeout=30,
        )
        resp.raise_for_status()
        body = resp.json()

        t.access_token = body["access_token"]
        t.access_expires_at = time.time() + int(body["expires_in"])

        new_rt = body["refresh_token"]
        if new_rt != t.refresh_token:
            # Intuit rotated the refresh token; persist the new one.
            _op_edit_credential("dd.intuit.tokens-prod", new_rt)
            t.refresh_token = new_rt

        return t.access_token
