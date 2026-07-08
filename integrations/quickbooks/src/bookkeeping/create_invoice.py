"""Create an ad-hoc QBO invoice.

Looks up the customer and item by name, builds an Invoice payload, and
either prints it (dry-run, default) or POSTs it to QBO with `--apply`.

Defaults (per `feedback_invoice_defaults.md`):
    TxnDate  = today
    DueDate  = today + 30
    DocNumber = auto-assigned by QBO (omitted from payload)

Usage:
    python -m bookkeeping.create_invoice \\
        --customer "River Christian Church" \\
        --line 5:"Custom Marketing Materials":240:"Sail Flag — RCC w/ waves design"

    # Add --apply to actually create. Default is dry-run.

`--line` is repeatable; format is QTY:ITEM_NAME:UNIT_PRICE:DESCRIPTION
(colons inside DESCRIPTION are fine — splits at most 4 times).
"""
from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from decimal import Decimal

from qbo import QBOClient

# DD's modern "Project" custom field (App-Foundations GraphQL id tail). Set via
# the enhanced-custom-fields API path, NOT CustomerMemo and NOT a legacy slot.
PROJECT_CUSTOM_FIELD_ID = "1000000001"


def parse_line(spec: str) -> dict:
    parts = spec.split(":", 3)
    if len(parts) != 4:
        raise ValueError(f"--line must be QTY:ITEM:UNIT_PRICE:DESCRIPTION, got {spec!r}")
    qty, item_name, unit_price, description = parts
    return {
        "qty": Decimal(qty),
        "item_name": item_name,
        "unit_price": Decimal(unit_price),
        "description": description,
    }


def build_payload(client: QBOClient, customer_name: str, lines: list[dict],
                  txn_date: str, due_date: str, memo: str | None = None) -> dict:
    customer = client.find_by_name("Customer", customer_name, "DisplayName")
    if not customer:
        raise SystemExit(f"Customer {customer_name!r} not found in QBO")

    qbo_lines = []
    for li in lines:
        item = client.find_by_name("Item", li["item_name"])
        if not item:
            raise SystemExit(f"Item {li['item_name']!r} not found in QBO")
        amount = li["qty"] * li["unit_price"]
        qbo_lines.append({
            "DetailType": "SalesItemLineDetail",
            "Amount": float(amount),
            "Description": li["description"],
            "SalesItemLineDetail": {
                "ItemRef": {"value": item["Id"], "name": item["Name"]},
                "Qty": float(li["qty"]),
                "UnitPrice": float(li["unit_price"]),
                "TaxCodeRef": {"value": "NON"},
            },
        })

    payload = {
        "CustomerRef": {"value": customer["Id"], "name": customer["DisplayName"]},
        "TxnDate": txn_date,
        "DueDate": due_date,
        "Line": qbo_lines,
    }
    if memo:
        payload["CustomerMemo"] = {"value": memo}
    return payload


def print_plan(payload: dict) -> None:
    cust = payload["CustomerRef"]["name"]
    print(f"\nCustomer:  {cust}")
    print(f"TxnDate:   {payload['TxnDate']}")
    print(f"DueDate:   {payload['DueDate']}")
    print(f"DocNumber: (auto-assigned)")
    if payload.get("CustomerMemo"):
        print(f"Memo:      {payload['CustomerMemo']['value']}")
    print("\nLines:")
    total = Decimal("0")
    for li in payload["Line"]:
        d = li["SalesItemLineDetail"]
        amount = Decimal(str(li["Amount"]))
        total += amount
        print(f"  {d['Qty']:>4g}x {d['ItemRef']['name']:<30}  "
              f"@ ${d['UnitPrice']:>8,.2f}  = ${amount:>10,.2f}")
        print(f"        {li['Description']}")
    print(f"\n{'Total':>54}: ${total:>10,.2f}\n")


def main() -> int:
    p = argparse.ArgumentParser(description="Create a QBO invoice.")
    p.add_argument("--customer", required=True, help="QBO customer DisplayName")
    p.add_argument("--line", action="append", required=True,
                   help="QTY:ITEM:UNIT_PRICE:DESCRIPTION (repeatable)")
    p.add_argument("--txn-date", default=date.today().isoformat())
    p.add_argument("--due-date",
                   default=(date.today() + timedelta(days=30)).isoformat())
    p.add_argument("--memo", default=None,
                   help="CustomerMemo shown on the invoice (optional).")
    p.add_argument("--project", default=None,
                   help="Value for the modern 'Project' custom field (optional).")
    p.add_argument("--apply", action="store_true",
                   help="Actually POST to QBO. Default is dry-run.")
    args = p.parse_args()

    lines = [parse_line(spec) for spec in args.line]
    client = QBOClient()
    payload = build_payload(client, args.customer, lines, args.txn_date,
                            args.due_date, args.memo)

    print_plan(payload)
    if args.project:
        print(f"Project:   {args.project}  (modern custom field)")

    if not args.apply:
        print("(dry-run — pass --apply to create the invoice in QBO)")
        return 0

    result = client.create("Invoice", payload)
    print(f"Created Invoice Id={result['Id']}  DocNumber={result.get('DocNumber')}  "
          f"Total=${result.get('TotalAmt'):,.2f}")

    if args.project:
        client.set_invoice_custom_fields(
            result["Id"],
            [{"DefinitionId": PROJECT_CUSTOM_FIELD_ID, "StringValue": args.project}],
        )
        print(f"  Set Project custom field = {args.project!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
