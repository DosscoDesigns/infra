"""JE #3: post open A/R + A/P at 2026-04-30 cutover.

Posts the 2 open invoices and 4 open iDex bills as JE entries with
customer / vendor refs. We deliberately do NOT create real Invoice / Bill
records — the income / expense for these open items was already captured
in JE #2's YTD activity (Wave's 4/30 TB includes them). Real records would
double-count.

Customer / vendor aging works fine from JE entries. When Jason receives
payment, he matches against the A/R balance per customer; when he pays
iDex, he matches against the A/P balance per vendor.

After this JE, the cumulative OBE balance carries the migration scar
tissue (~$586 CR), which Jason can clean up post-cutover with a single
JE moving OBE → Owner's Equity.

Run from src/:
    python -m migration.option_b_open_items                # dry-run
    python -m migration.option_b_open_items --execute      # apply
"""
from __future__ import annotations

import argparse
import sys
from decimal import Decimal

from qbo import QBOClient

D0 = Decimal("0")

# Open A/R: 2 invoices at 2026-04-30
OPEN_AR = [
    {"customer": "NATCA - PA", "amount": Decimal("1128.39"), "memo": "INV-000562 (Wave) — open at cutover"},
    {"customer": "River Christian Church", "amount": Decimal("340.00"), "memo": "INV-000565 (Wave) — open at cutover"},
]

# Open A/P: 4 iDex bills (POs 20095-20098) totaling $1,334
OPEN_AP = [
    {"vendor": "iDex International", "amount": Decimal("1334.00"),
     "memo": "iDex POs 20095-20098 (Wave) — open at cutover"},
]


def post_je3(client: QBOClient, *, dry_run: bool) -> None:
    accounts = {a["Name"]: a["Id"] for a in client.query("SELECT * FROM Account MAXRESULTS 1000")}
    customers = {c["DisplayName"]: c["Id"] for c in client.query("SELECT * FROM Customer MAXRESULTS 1000")}
    vendors = {v["DisplayName"]: v["Id"] for v in client.query("SELECT * FROM Vendor MAXRESULTS 1000")}

    # Resolve A/R + A/P account IDs
    ar_id = accounts.get("Accounts receivable")
    ap_id = accounts.get("Accounts payable")
    obe_id = accounts.get("Opening Balance Equity")
    if not (ar_id and ap_id and obe_id):
        raise RuntimeError("Missing system A/R, A/P, or OBE account in QBO")

    lines = []
    total_dr = D0
    total_cr = D0

    print("=== JE #3 — Open A/R + A/P at 2026-04-30 ===\n")
    print(f"{'Account':45} {'Customer/Vendor':30} {'DR':>12} {'CR':>12}")
    print("-" * 105)

    for item in OPEN_AR:
        cust_id = customers.get(item["customer"])
        if not cust_id:
            raise RuntimeError(f"Customer {item['customer']!r} not in QBO")
        amt = float(item["amount"])
        total_dr += item["amount"]
        print(f"{'Accounts receivable':45} {item['customer'][:30]:30} {f'${amt:,.2f}':>12} {'':>12}")
        lines.append({
            "DetailType": "JournalEntryLineDetail",
            "Amount": amt,
            "Description": item["memo"],
            "JournalEntryLineDetail": {
                "PostingType": "Debit",
                "AccountRef": {"value": ar_id},
                "Entity": {
                    "Type": "Customer",
                    "EntityRef": {"value": cust_id},
                },
            },
        })

    for item in OPEN_AP:
        vendor_id = vendors.get(item["vendor"])
        if not vendor_id:
            raise RuntimeError(f"Vendor {item['vendor']!r} not in QBO")
        amt = float(item["amount"])
        total_cr += item["amount"]
        print(f"{'Accounts payable':45} {item['vendor'][:30]:30} {'':>12} {f'${amt:,.2f}':>12}")
        lines.append({
            "DetailType": "JournalEntryLineDetail",
            "Amount": amt,
            "Description": item["memo"],
            "JournalEntryLineDetail": {
                "PostingType": "Credit",
                "AccountRef": {"value": ap_id},
                "Entity": {
                    "Type": "Vendor",
                    "EntityRef": {"value": vendor_id},
                },
            },
        })

    # Plug to OBE
    diff = total_dr - total_cr
    if diff != 0:
        if diff > 0:
            # More debits — credit OBE to balance
            amt = float(diff)
            total_cr += diff
            print(f"{'Opening Balance Equity':45} {'(plug)':30} {'':>12} {f'${amt:,.2f}':>12}")
            lines.append({
                "DetailType": "JournalEntryLineDetail",
                "Amount": amt,
                "Description": "Migration plug — open items",
                "JournalEntryLineDetail": {
                    "PostingType": "Credit",
                    "AccountRef": {"value": obe_id},
                },
            })
        else:
            amt = float(-diff)
            total_dr += -diff
            print(f"{'Opening Balance Equity':45} {'(plug)':30} {f'${amt:,.2f}':>12} {'':>12}")
            lines.append({
                "DetailType": "JournalEntryLineDetail",
                "Amount": amt,
                "Description": "Migration plug — open items",
                "JournalEntryLineDetail": {
                    "PostingType": "Debit",
                    "AccountRef": {"value": obe_id},
                },
            })

    print("-" * 105)
    print(f"{'TOTAL':45} {'':30} {f'${total_dr:,.2f}':>12} {f'${total_cr:,.2f}':>12}  diff=${total_dr-total_cr:,.2f}")

    if dry_run:
        print("\n(Dry run — pass --execute to post.)")
        return

    payload = {
        "TxnDate": "2026-04-30",
        "PrivateNote": "Wave→QBO migration: open A/R + A/P at cutover",
        "Line": lines,
    }
    result = client.create("JournalEntry", payload)
    print(f"\n  ✓ JE #3 posted Id={result['Id']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    client = QBOClient()
    post_je3(client, dry_run=not args.execute)
    return 0


if __name__ == "__main__":
    sys.exit(main())
