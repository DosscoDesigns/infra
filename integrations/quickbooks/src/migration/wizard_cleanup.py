"""Step 0: clean up QBO setup-wizard opening-balance entries.

QBO's bank-connect setup wizard prompts for opening balances and creates
Deposit / Purchase transactions tagged 'Opening Balance from Bank' (or with
no description for some bank widgets). These need to be removed so our own
opening-balance JE can post the correct cutover-date trial balance values.

We deliberately do NOT delete:
- Sample Customer or Invoice #1001 (the $5 promo is real per Jason)
- Any transaction the user created themselves
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Optional

from qbo import QBOClient


WIZARD_DESC_MARKERS = ("opening balance from bank", "opening balance")
# Hard-coded date: only target wizard entries on the date QBO was set up.
# Adjust if Jason re-runs setup.
WIZARD_DATE = "2026-04-28"


@dataclass
class CleanupOp:
    entity: str           # Deposit | Purchase | Invoice
    qbo_id: str
    sync_token: str
    description: str
    amount: float
    target_account: str
    reason: str


def find_wizard_entries(client: QBOClient) -> list[CleanupOp]:
    """Identify wizard-generated opening-balance transactions to delete."""
    ops: list[CleanupOp] = []

    # Deposits — wizard creates these on bank/cash accounts
    for d in client.query("SELECT * FROM Deposit MAXRESULTS 100"):
        if d.get("TxnDate") != WIZARD_DATE:
            continue
        desc = (d.get("PrivateNote", "") or "").lower()
        if not any(m in desc for m in WIZARD_DESC_MARKERS):
            continue
        ops.append(CleanupOp(
            entity="Deposit",
            qbo_id=d["Id"],
            sync_token=d["SyncToken"],
            description=d.get("PrivateNote", "") or "(no description)",
            amount=float(d.get("TotalAmt", 0)),
            target_account=d.get("DepositToAccountRef", {}).get("name", "?"),
            reason="QBO setup-wizard opening balance for bank/cash account",
        ))

    # Purchases — wizard creates these on credit card accounts
    for p in client.query("SELECT * FROM Purchase MAXRESULTS 100"):
        if p.get("TxnDate") != WIZARD_DATE:
            continue
        desc = (p.get("PrivateNote", "") or "").lower()
        if not any(m in desc for m in WIZARD_DESC_MARKERS):
            # Be conservative: only delete if we're sure it's a wizard entry
            continue
        ops.append(CleanupOp(
            entity="Purchase",
            qbo_id=p["Id"],
            sync_token=p["SyncToken"],
            description=p.get("PrivateNote", "") or "(no description)",
            amount=float(p.get("TotalAmt", 0)),
            target_account=p.get("AccountRef", {}).get("name", "?"),
            reason="QBO setup-wizard opening balance for credit card account",
        ))

    return ops


def print_plan(ops: list[CleanupOp]) -> None:
    print(f"\n=== Wizard-cleanup plan: {len(ops)} transactions to delete ===")
    for o in ops:
        print(f"  [{o.entity:10}] Id={o.qbo_id:<4} ${o.amount:>10,.2f}  acct={o.target_account}")
        print(f"               desc: {o.description}")
        print(f"               reason: {o.reason}")


def apply_plan(client: QBOClient, ops: list[CleanupOp]) -> None:
    print(f"\nDeleting {len(ops)} wizard transactions...")
    for o in ops:
        try:
            client.delete(o.entity, o.qbo_id, o.sync_token)
            print(f"  deleted {o.entity} Id={o.qbo_id} (${o.amount:,.2f} on {o.target_account})")
        except Exception as exc:
            print(f"  FAILED {o.entity} Id={o.qbo_id}: {exc}")
