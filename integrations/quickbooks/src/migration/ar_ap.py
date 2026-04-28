"""Open A/R + A/P entries.

Loads the 2 open invoices (Wave 'sent' status) as QBO Invoice records
referencing the right customers. Loads the open iDex bill (and any other
recent gear-sale bills Jason added) as QBO Bill records.

These are deliberately built as separate from the opening-balance JE so
that QBO's aging reports work correctly — A/R and A/P need to be tied
to actual invoice/bill records, not just balance entries.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional

from qbo import QBOClient

WAVE_EXPORT_DIR = Path(__file__).resolve().parents[4] / "TEMP" / "wave-export"


def _money(s: str) -> Decimal:
    if not s:
        return Decimal("0")
    s = s.strip().replace("$", "").replace(",", "").replace('"', "")
    return Decimal(s) if s else Decimal("0")


@dataclass
class OpenInvoice:
    customer_name: str
    invoice_number: str
    invoice_date: str
    due_date: str
    total: Decimal
    balance_due: Decimal
    line_items: list[dict] = field(default_factory=list)


def load_open_invoices() -> list[OpenInvoice]:
    """Read invoices_items.csv (since invoices.csv has no line detail)
    and return only those still 'sent' (unpaid) per the Wave invoices.csv."""
    inv_path = WAVE_EXPORT_DIR / "DD - invoices.csv"
    items_path = WAVE_EXPORT_DIR / "DD - invoices_items.csv"

    sent_numbers: dict[str, dict] = {}
    with open(inv_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            if r.get("Status") == "sent":
                sent_numbers[r["Invoice Number"]] = r

    by_inv: dict[str, OpenInvoice] = {}
    with open(items_path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            num = r.get("Invoice Number", "")
            if num not in sent_numbers:
                continue
            if num not in by_inv:
                hdr = sent_numbers[num]
                by_inv[num] = OpenInvoice(
                    customer_name=hdr["Customer Name"],
                    invoice_number=num,
                    invoice_date=hdr.get("Invoice Date", ""),
                    due_date=hdr.get("Due Date", ""),
                    total=_money(hdr.get("Invoice Total", "0")),
                    balance_due=_money(hdr.get("Invoice Due", "0")),
                )
            by_inv[num].line_items.append({
                "name": r.get("Item Name", "").strip(),
                "qty": _money(r.get("Quantity", "0")),
                "unit_price": _money(r.get("Unit Price", "0")),
                "total": _money(r.get("Item Total", "0")),
                "description": r.get("Description", "").strip(),
            })
    return list(by_inv.values())


@dataclass
class OpenBill:
    vendor_name: str
    bill_date: str
    due_date: str
    amount: Decimal
    description: str = ""


# Hardcoded list of open A/P bills. Per AUDIT.md decision: skip historical
# bills, only enter open ones. iDex is the lone known open bill ($1,149)
# from Wave Aged Payables; user mentioned adding more for gear-sale processing.
# Update this list at cutover after re-exporting Wave's Aged Payables.
KNOWN_OPEN_BILLS: list[OpenBill] = [
    OpenBill(
        vendor_name="iDex International",
        bill_date="2026-03-15",   # placeholder — get actual at cutover
        due_date="2026-04-15",    # placeholder
        amount=Decimal("1149.00"),
        description="Embroidery services — open balance from Wave Aged Payables at cutover",
    ),
]


def plan_open_ar(client: QBOClient) -> list[OpenInvoice]:
    """Build the list of open invoices to create. No-op if customer not found."""
    return load_open_invoices()


def plan_open_ap(client: QBOClient) -> list[OpenBill]:
    return list(KNOWN_OPEN_BILLS)


def print_plan(invoices: list[OpenInvoice], bills: list[OpenBill]) -> None:
    print("\n=== Open A/R (invoices to create) ===")
    for inv in invoices:
        print(f"  {inv.customer_name} INV-{inv.invoice_number}  ${inv.balance_due:>10,.2f}  due {inv.due_date}")
        for li in inv.line_items:
            print(f"    {li['qty']}x {li['name'] or '(no item)'} @ ${li['unit_price']} = ${li['total']}")
            if li['description']:
                first_line = li['description'].splitlines()[0][:80]
                print(f"        {first_line}")

    print("\n=== Open A/P (bills to create) ===")
    for b in bills:
        print(f"  {b.vendor_name}  ${b.amount:>10,.2f}  bill {b.bill_date}  due {b.due_date}")
        print(f"    {b.description}")
    print(f"\nTotal A/R: ${sum((i.balance_due for i in invoices), Decimal(0)):,.2f}")
    print(f"Total A/P: ${sum((b.amount for b in bills), Decimal(0)):,.2f}")


def apply_ar(client: QBOClient, invoices: list[OpenInvoice]) -> None:
    if not invoices:
        return
    customers = {c["DisplayName"]: c["Id"] for c in client.query("SELECT * FROM Customer WHERE Active = true MAXRESULTS 1000")}
    items = {i["Name"]: i["Id"] for i in client.query("SELECT * FROM Item MAXRESULTS 1000")}

    print(f"\nApplying {len(invoices)} open A/R invoices...")
    for inv in invoices:
        cust_id = customers.get(inv.customer_name)
        if not cust_id:
            print(f"  SKIP {inv.invoice_number}: customer {inv.customer_name!r} not found")
            continue

        # Build line items — fall back to a single description line if items don't match
        je_lines = []
        for li in inv.line_items:
            item_id = items.get(li["name"])
            if not item_id:
                # Use a generic Service item as fallback
                fallback = items.get("Custom Apparel") or list(items.values())[0]
                item_id = fallback
            je_lines.append({
                "DetailType": "SalesItemLineDetail",
                "Amount": float(li["total"]),
                "Description": li["description"][:4000] if li["description"] else None,
                "SalesItemLineDetail": {
                    "ItemRef": {"value": item_id},
                    "Qty": float(li["qty"]),
                    "UnitPrice": float(li["unit_price"]),
                },
            })

        payload = {
            "CustomerRef": {"value": cust_id},
            "TxnDate": inv.invoice_date,
            "DueDate": inv.due_date,
            "DocNumber": inv.invoice_number,
            "PrivateNote": f"Migrated from Wave at cutover — open balance ${inv.balance_due}",
            "Line": je_lines,
        }
        try:
            result = client.create("Invoice", payload)
            print(f"  created Invoice {inv.invoice_number} for {inv.customer_name} -> Id={result['Id']}")
        except Exception as exc:
            print(f"  FAILED {inv.invoice_number}: {exc}")


def apply_ap(client: QBOClient, bills: list[OpenBill]) -> None:
    if not bills:
        return
    print(f"\nApplying {len(bills)} open A/P bills...")
    # Look up A/P account
    ap = client.find_by_name("Account", "Accounts Payable")
    # Open bills typically post to a COGS/Expense account; for iDex (embroidery),
    # use Embroidery Service as the expense account
    embroidery = client.find_by_name("Account", "Embroidery Service")

    for b in bills:
        # Find or create vendor
        vendor = client.find_by_name("Vendor", b.vendor_name, "DisplayName")
        if not vendor:
            vendor = client.create("Vendor", {"DisplayName": b.vendor_name})
            print(f"  created vendor {b.vendor_name} -> Id={vendor['Id']}")

        # Pick expense account — iDex defaults to Embroidery Service
        exp_acct = embroidery
        if not exp_acct:
            print(f"  SKIP {b.vendor_name} bill: Embroidery Service account not found")
            continue

        payload = {
            "VendorRef": {"value": vendor["Id"]},
            "TxnDate": b.bill_date,
            "DueDate": b.due_date,
            "PrivateNote": b.description,
            "Line": [{
                "DetailType": "AccountBasedExpenseLineDetail",
                "Amount": float(b.amount),
                "Description": b.description,
                "AccountBasedExpenseLineDetail": {
                    "AccountRef": {"value": exp_acct["Id"]},
                },
            }],
        }
        try:
            result = client.create("Bill", payload)
            print(f"  created Bill from {b.vendor_name} ${b.amount} -> Id={result['Id']}")
        except Exception as exc:
            print(f"  FAILED {b.vendor_name}: {exc}")
