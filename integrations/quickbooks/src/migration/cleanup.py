"""Reconcile pre-filled QBO state against the AUDIT plan.

Cleans up duplicates introduced during prior pre-fill, deletes sample data,
and seeds vendors with material 2025-2026 activity. Idempotent and safe to
re-run.

Run from project root:
    .venv/bin/python -m migration.cleanup            # dry-run
    .venv/bin/python -m migration.cleanup --execute  # apply
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

from qbo import QBOClient


# Vendors to seed: ≥10 transactions in Wave 2025-2026, minus those already in
# QBO and minus Wave itself (going away).
VENDORS_TO_SEED = [
    "iDex International",
    "SanMar",
    "Transfer Express",
    "Amazon",
    "Pirate Ship",
    "S&S Activewear",
    "Akwa",
    "Augusta Sportswear",
    "Shopify",
    "Adobe",
    "Cloudflare",
    "iStock Photo",
    "Digital Ocean",
]


def find_account_dups(accounts: list[dict]) -> list[tuple[str, list[dict]]]:
    """Group active accounts by lowercase name; return groups with >1 entry."""
    by_name: dict[str, list[dict]] = {}
    for a in accounts:
        if not a.get("Active"):
            continue
        key = a["Name"].strip().lower()
        by_name.setdefault(key, []).append(a)
    return [(k, v) for k, v in by_name.items() if len(v) > 1]


def pick_canonical(group: list[dict]) -> tuple[dict, list[dict]]:
    """From a same-name group, pick the one to keep + the ones to deactivate.

    Heuristics:
      1. Prefer the one with non-zero CurrentBalance (data is attached).
      2. Otherwise prefer the one with parent-account relationship intact.
      3. Otherwise prefer the lowest Id (typically QBO default).
    """
    with_balance = [a for a in group if float(a.get("CurrentBalance", 0)) != 0]
    if with_balance:
        keeper = with_balance[0]
    else:
        keeper = sorted(group, key=lambda a: int(a["Id"]))[0]
    losers = [a for a in group if a["Id"] != keeper["Id"]]
    return keeper, losers


# Default accounts shadowed by user-named replacements that are safe to
# deactivate. Specifically EXCLUDED:
#   - "Accounts payable" / "Accounts receivable" lowercase: QBO system A/P
#     and A/R. Deactivating breaks native invoice/bill workflows.
#   - "Cost of goods sold": kept as catch-all; no harm leaving active.
EXPLICIT_DEACTIVATIONS = {
    "Cash": "Replaced by 'Cash on Hand'",
    "Other income": "Replaced by 'Other Income - Interest' / 'Other Income - Rewards'",
    "Equipment": "Generic; fixed-asset Equipment-* accounts in use",
    "Other business expenses": "Catch-all; specific accounts cover real spend",
}


def sample_data_to_delete(client: QBOClient) -> list[tuple[str, dict]]:
    """Sample $5 invoice + Sample Customer are intentionally preserved per
    wizard_cleanup.py — the $5 is a real QBO Payments promo Jason already
    received. Returning empty list."""
    return []


def plan(client: QBOClient) -> dict:
    """Build a dict of {section: [actions]} for review."""
    accounts = client.query("SELECT * FROM Account MAXRESULTS 1000")
    vendors = client.query("SELECT * FROM Vendor MAXRESULTS 1000")
    existing_vendor_names = {v["DisplayName"].lower() for v in vendors}

    # 1. Duplicate-name account groups
    dup_groups = find_account_dups(accounts)
    dup_actions = []
    for name_key, group in dup_groups:
        keeper, losers = pick_canonical(group)
        for loser in losers:
            dup_actions.append({
                "id": loser["Id"], "name": loser["Name"],
                "type": loser.get("AccountType"),
                "subtype": loser.get("AccountSubType"),
                "balance": loser.get("CurrentBalance", 0),
                "sync_token": loser["SyncToken"],
                "reason": f"Duplicate of {keeper['Name']!r} (Id={keeper['Id']})",
            })

    # 2. Explicit deactivations (default accounts shadowed by user-named)
    by_name = {a["Name"]: a for a in accounts if a.get("Active")}
    explicit_actions = []
    for name, reason in EXPLICIT_DEACTIVATIONS.items():
        a = by_name.get(name)
        if not a:
            continue
        # Don't try to deactivate something with a balance.
        if float(a.get("CurrentBalance", 0)) != 0:
            continue
        # Don't double-act if already in dup_actions.
        if any(d["id"] == a["Id"] for d in dup_actions):
            continue
        explicit_actions.append({
            "id": a["Id"], "name": a["Name"],
            "type": a.get("AccountType"),
            "subtype": a.get("AccountSubType"),
            "balance": 0,
            "sync_token": a["SyncToken"],
            "reason": reason,
        })

    # 3. Vendors to seed
    vendor_actions = [
        v for v in VENDORS_TO_SEED
        if v.lower() not in existing_vendor_names
    ]

    # 4. Sample data to delete
    sample_actions = sample_data_to_delete(client)

    return {
        "deactivate_dup_accounts": dup_actions,
        "deactivate_default_accounts": explicit_actions,
        "create_vendors": vendor_actions,
        "delete_sample": sample_actions,
    }


def print_plan(p: dict) -> None:
    print("=== Plan ===\n")
    print(f"Deactivate duplicate accounts: {len(p['deactivate_dup_accounts'])}")
    for a in p["deactivate_dup_accounts"]:
        print(f"  Id={a['id']:<4} {a['name']:<45} {a['type']}/{a['subtype']:<25}  bal={a['balance']}")
        print(f"            ↳ {a['reason']}")
    print()
    print(f"Deactivate default-shadowed accounts: {len(p['deactivate_default_accounts'])}")
    for a in p["deactivate_default_accounts"]:
        print(f"  Id={a['id']:<4} {a['name']:<45} {a['type']}/{a['subtype']:<25}")
        print(f"            ↳ {a['reason']}")
    print()
    print(f"Create vendors: {len(p['create_vendors'])}")
    for v in p["create_vendors"]:
        print(f"  + {v}")
    print()
    print(f"Delete sample data: {len(p['delete_sample'])}")
    for entity, obj in p["delete_sample"]:
        if entity == "Invoice":
            print(f"  - Invoice Id={obj['Id']} DocNumber={obj.get('DocNumber')!r} "
                  f"Total={obj.get('TotalAmt')} Customer={obj.get('CustomerRef',{}).get('name')}")
        else:
            print(f"  - {entity} Id={obj['Id']} Name={obj.get('DisplayName')!r}")


def deactivate_account(client: QBOClient, action: dict) -> None:
    payload = {
        "Id": action["id"],
        "SyncToken": action["sync_token"],
        "Name": action["name"],
        "Active": False,
        "sparse": True,
    }
    client.update("Account", payload)


def create_vendor(client: QBOClient, name: str) -> dict:
    return client.create("Vendor", {"DisplayName": name})


def execute(client: QBOClient, p: dict) -> None:
    print("=== Executing ===\n")

    print("Deleting sample data first (frees account balances)...")
    for entity, obj in p["delete_sample"]:
        try:
            client.delete(entity, obj["Id"], obj["SyncToken"])
            print(f"  ✓ Deleted {entity} Id={obj['Id']}")
        except Exception as exc:
            print(f"  ✗ {entity} Id={obj['Id']}: {exc}")

    print("\nDeactivating duplicate accounts...")
    for a in p["deactivate_dup_accounts"]:
        try:
            deactivate_account(client, a)
            print(f"  ✓ Deactivated Id={a['id']} {a['name']!r}")
        except Exception as exc:
            print(f"  ✗ Id={a['id']} {a['name']!r}: {exc}")

    print("\nDeactivating default-shadowed accounts...")
    for a in p["deactivate_default_accounts"]:
        try:
            deactivate_account(client, a)
            print(f"  ✓ Deactivated Id={a['id']} {a['name']!r}")
        except Exception as exc:
            print(f"  ✗ Id={a['id']} {a['name']!r}: {exc}")

    print("\nCreating vendors...")
    for v in p["create_vendors"]:
        try:
            res = create_vendor(client, v)
            print(f"  ✓ Created Vendor Id={res['Id']} {v!r}")
        except Exception as exc:
            print(f"  ✗ {v!r}: {exc}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true",
                        help="Apply changes (default: dry-run)")
    args = parser.parse_args()

    client = QBOClient()
    p = plan(client)
    print_plan(p)

    if args.execute:
        print()
        execute(client, p)
    else:
        print("\n(Dry run — pass --execute to apply.)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
