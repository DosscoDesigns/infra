"""Thin REST client over the QBO Accounting API.

Methods return parsed JSON dicts. Idempotency is the caller's job — most
migration modules check for existing records before creating, since QBO has
no upsert primitive."""
from __future__ import annotations

import json
import os
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
        # Default minorversion first so a caller-supplied one (e.g. "75" for
        # enhanced custom fields) takes precedence.
        params = {"minorversion": MINOR_VERSION, **(params or {})}

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

    def sparse_update(self, entity: str, qbo_id: str, sync_token: str, fields: dict) -> dict:
        """Partial update — only the supplied fields change. Requires `Id` + `SyncToken`."""
        payload = {"Id": qbo_id, "SyncToken": sync_token, "sparse": True, **fields}
        return self._request("POST", entity.lower(), json=payload)[entity]

    def upload_attachable(
        self, file_path: str, *, entity_type: str, entity_id: str,
        content_type: str = "application/pdf", file_name: Optional[str] = None,
        note: Optional[str] = None,
    ) -> dict:
        """Upload a file and link it to a QBO transaction (Purchase, Bill, Invoice, etc.).

        Returns the created Attachable record.
        """
        file_name = file_name or os.path.basename(file_path)
        metadata = {
            "AttachableRef": [{"EntityRef": {"type": entity_type, "value": entity_id}}],
            "FileName": file_name,
            "ContentType": content_type,
        }
        if note:
            metadata["Note"] = note

        url = f"{self.base_url}/upload"
        params = {"minorversion": MINOR_VERSION}
        headers = {
            "Authorization": f"Bearer {self.tokens.access_token()}",
            "Accept": "application/json",
        }
        with open(file_path, "rb") as fh:
            files = {
                "file_metadata_0": (None, json.dumps(metadata), "application/json"),
                "file_content_0": (file_name, fh, content_type),
            }
            resp = self._session.post(url, params=params, files=files,
                                      headers=headers, timeout=120)

        try:
            body = resp.json() if resp.text else {}
        except ValueError:
            body = {"_raw": resp.text}

        if resp.status_code >= 400:
            raise QBOError(resp.status_code, body)

        # Successful upload returns AttachableResponse[].Attachable
        ar = body.get("AttachableResponse", [])
        if ar and isinstance(ar, list) and ar[0].get("Attachable"):
            return ar[0]["Attachable"]
        # Some failures show up here even with 2xx status
        if ar and ar[0].get("Fault"):
            raise QBOError(0, body, str(ar[0]["Fault"]))
        return body

    # Modern ("enhanced") custom fields are INVISIBLE to the default v3 path —
    # they need minorversion>=75 + include=enhancedAllCustomFields, and are keyed
    # by the numeric tail of the App-Foundations GraphQL node id (e.g. "1000000001"
    # for DD's "Project" field). The legacy CustomField slots (DefinitionId 1-3)
    # are a SEPARATE system and won't reach them.
    ENHANCED_CF_PARAMS = {"minorversion": "75", "include": "enhancedAllCustomFields"}

    def set_invoice_custom_fields(self, invoice_id: str, fields: list[dict]) -> dict:
        """Set enhanced/modern custom field values on an invoice.

        `fields` is a list of {"DefinitionId": "1000000001", "StringValue": "..."}.
        Type defaults to StringType. Returns the updated Invoice.
        """
        inv = self._request(
            "GET", f"invoice/{invoice_id}", params=self.ENHANCED_CF_PARAMS
        )["Invoice"]
        payload = {
            "Id": invoice_id,
            "SyncToken": inv["SyncToken"],
            "sparse": True,
            "CustomField": [{"Type": "StringType", **f} for f in fields],
        }
        return self._request(
            "POST", "invoice", params=self.ENHANCED_CF_PARAMS, json=payload
        )["Invoice"]

    def find_by_name(self, entity: str, name: str, name_field: str = "Name") -> Optional[dict]:
        # Escape single quotes for QBO SQL
        safe = name.replace("'", "\\'")
        sql = f"SELECT * FROM {entity} WHERE {name_field} = '{safe}'"
        results = self.query(sql)
        return results[0] if results else None
