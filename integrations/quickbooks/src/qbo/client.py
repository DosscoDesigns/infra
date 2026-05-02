"""Thin REST client over the QBO Accounting API.

Methods return parsed JSON dicts. Idempotency is the caller's job — most
migration modules check for existing records before creating, since QBO has
no upsert primitive."""
from __future__ import annotations

import time
from typing import Any, Optional

import requests

from .tokens import TokenManager

PROD_BASE = "https://quickbooks.api.intuit.com/v3/company"
MINOR_VERSION = "70"  # current as of 2026

# Retry tuning
_MAX_RETRIES = 3
_BACKOFF_BASE = 1.0  # seconds


class QBOError(RuntimeError):
    def __init__(self, status: int, body: Any, message: str = ""):
        self.status = status
        self.body = body
        super().__init__(f"QBO API error {status}: {message or body}")


class QBOClient:
    def __init__(self, tokens: Optional[TokenManager] = None) -> None:
        self.tokens = tokens or TokenManager()
        self._session = requests.Session()

    @property
    def realm_id(self) -> str:
        return self.tokens.realm_id

    @property
    def base_url(self) -> str:
        return f"{PROD_BASE}/{self.realm_id}"

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.tokens.access_token()}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[dict[str, Any]] = None,
        json: Optional[dict[str, Any]] = None,
    ) -> dict:
        url = f"{self.base_url}/{path.lstrip('/')}"
        params = {**(params or {}), "minorversion": MINOR_VERSION}

        last_exc: Optional[Exception] = None
        for attempt in range(_MAX_RETRIES):
            try:
                resp = self._session.request(
                    method, url, params=params, json=json,
                    headers=self._headers(), timeout=60,
                )
            except requests.RequestException as exc:
                last_exc = exc
                time.sleep(_BACKOFF_BASE * (2**attempt))
                continue

            if resp.status_code == 429:
                # Rate limited — back off
                time.sleep(_BACKOFF_BASE * (2 ** (attempt + 1)))
                continue
            if 500 <= resp.status_code < 600:
                time.sleep(_BACKOFF_BASE * (2**attempt))
                continue

            try:
                body = resp.json() if resp.text else {}
            except ValueError:
                body = {"_raw": resp.text}

            if resp.status_code >= 400:
                fault = body.get("Fault", {}) if isinstance(body, dict) else {}
                msg = ""
                if isinstance(fault, dict):
                    errs = fault.get("Error", [])
                    if errs and isinstance(errs, list):
                        msg = "; ".join(
                            f"{e.get('code', '?')}: {e.get('Message', '')} — {e.get('Detail', '')}"
                            for e in errs
                        )
                raise QBOError(resp.status_code, body, msg)

            return body

        raise QBOError(0, None, f"exhausted retries ({last_exc})")

    # --- High-level helpers ---

    def query(self, sql: str) -> list[dict]:
        """Execute a QBO SQL-like query, returning the entity list."""
        body = self._request("GET", "query", params={"query": sql})
        qresp = body.get("QueryResponse", {})
        # Find the entity list (key varies by entity type)
        for key, val in qresp.items():
            if isinstance(val, list):
                return val
        return []

    def company_info(self) -> dict:
        return self._request("GET", f"companyinfo/{self.realm_id}")["CompanyInfo"]

    def create(self, entity: str, payload: dict) -> dict:
        return self._request("POST", entity.lower(), json=payload)[entity]

    def update(self, entity: str, payload: dict) -> dict:
        # QBO uses sparse update via the same POST endpoint with Id + SyncToken
        return self._request("POST", entity.lower(), json=payload)[entity]

    def delete(self, entity: str, qbo_id: str, sync_token: str) -> dict:
        """Delete a transaction. Most QBO transactions support delete via
        POST /<entity>?operation=delete with {Id, SyncToken} payload."""
        return self._request(
            "POST", entity.lower(),
            params={"operation": "delete"},
            json={"Id": qbo_id, "SyncToken": sync_token},
        )

    def find_by_name(self, entity: str, name: str, name_field: str = "Name") -> Optional[dict]:
        # Escape single quotes for QBO SQL
        safe = name.replace("'", "\\'")
        sql = f"SELECT * FROM {entity} WHERE {name_field} = '{safe}'"
        results = self.query(sql)
        return results[0] if results else None
