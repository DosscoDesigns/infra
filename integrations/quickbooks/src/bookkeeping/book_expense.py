"""Book a vendor expense (QBO Purchase) — the reusable, parameterized path.

This replaces the per-transaction ``create_<vendor>_<date>.py`` one-offs for the
common case: a single vendor expense paid from a bank/credit-card account, posted
to one expense account (optionally tagged to a customer, optionally split across
several lines), with an optional receipt PDF attached.

The QBO machinery (auth, query, create, PDF attach) lives in ``qbo.QBOClient`` —
this script only assembles the Purchase payload from CLI args and calls it.

Examples
--------
Single-line vendor expense + receipt (the Arq/CCC case)::

    python -m bookkeeping.book_expense \
        --vendor "Haystack Software LLC" --amount 49.99 \
        --account 155 --pay 110 --date 2026-08-12 \
        --doc 1154047 --pdf receipts/arq/Receipt-Order-1154047.pdf \
        --memo "Arq 7 — Mac backup software, perpetual license" --apply

Customer-tagged resale line (the VistaPrint/RCC case)::

    python -m bookkeeping.book_expense \
        --vendor VistaPrint --amount 722.24 --account 139 --pay 110 \
        --doc VP_V0FLKX61 --customer-name "River Christian Church" \
        --pdf "$HOME/Desktop/receipts/.../Order.pdf" --apply

Split across customers (the SanMar EMBARK/RCC case)::

    python -m bookkeeping.book_expense \
        --vendor SanMar --pay 166 --date 2026-05-13 \
        --line 44.85:132:"Embark Church":"EMBARK portion" \
        --line 36.38:132:"River Christian Church":"RCC portion" --apply

Dry-run is the default; pass ``--apply`` to actually POST to QBO.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from qbo import QBOClient, QBOError

# Sensible DD defaults (override on the CLI):
DEFAULT_PAYMENT_TYPE = "CreditCard"  # matches Amex-1005-paid expenses


def _fmt(amount: float) -> str:
    return f"${amount:,.2f}"


# --------------------------------------------------------------------------- #
# Resolution helpers
# --------------------------------------------------------------------------- #
def resolve_vendor(client: QBOClient, ref: str, *, create: bool, apply: bool) -> Optional[str]:
    """Return a Vendor Id. ``ref`` is an Id (all digits) or a display name.

    A name does an exact match first, then a LIKE match. With ``--create-vendor``
    a not-found name is created (on ``--apply``); otherwise a miss is an error.
    """
    if ref.isdigit():
        return ref

    safe = ref.replace("'", "\\'")
    rows = client.query(
        f"SELECT Id, DisplayName FROM Vendor WHERE DisplayName = '{safe}' MAXRESULTS 2"
    )
    if not rows:
        rows = client.query(
            f"SELECT Id, DisplayName FROM Vendor WHERE DisplayName LIKE '%{safe}%' MAXRESULTS 5"
        )
    if len(rows) == 1:
        return rows[0]["Id"]
    if len(rows) > 1:
        names = [f"{r['DisplayName']} (Id={r['Id']})" for r in rows]
        raise SystemExit(f"Ambiguous vendor '{ref}': {names} — pass an exact name or --vendor-id.")

    # Not found
    if not create:
        raise SystemExit(
            f"No vendor matches '{ref}'. Re-run with --create-vendor to create it, "
            f"or pass an existing --vendor-id."
        )
    if not apply:
        print(f"  • Vendor '{ref}' not found — would create it (--apply)")
        return None
    vend = client.create("Vendor", {"DisplayName": ref})
    print(f"  ✓ Created Vendor '{ref}' Id={vend['Id']}")
    return vend["Id"]


def resolve_customer(client: QBOClient, ref: str) -> str:
    """Return a Customer Id. ``ref`` is an Id (all digits) or a display name."""
    if ref.isdigit():
        return ref
    safe = ref.replace("'", "\\'")
    rows = client.query(
        f"SELECT Id, DisplayName FROM Customer WHERE DisplayName = '{safe}' MAXRESULTS 2"
    )
    if not rows:
        rows = client.query(
            f"SELECT Id, DisplayName FROM Customer WHERE DisplayName LIKE '%{safe}%' MAXRESULTS 5"
        )
    if not rows:
        raise SystemExit(f"No customer matches '{ref}'.")
    if len(rows) > 1:
        names = [f"{r['DisplayName']} (Id={r['Id']})" for r in rows]
        raise SystemExit(f"Ambiguous customer '{ref}': {names} — pass an exact name or the Id.")
    return rows[0]["Id"]


def _account_name(client: QBOClient, account_id: str) -> str:
    try:
        acct = client._request("GET", f"account/{account_id}")["Account"]
        return f"{acct['Name']} ({acct['AccountType']})"
    except QBOError:
        return f"Id={account_id} (unresolved)"


# --------------------------------------------------------------------------- #
# Line parsing
# --------------------------------------------------------------------------- #
class Line:
    """One expense line: amount, expense account, optional customer, description."""

    def __init__(self, amount: float, account_id: str,
                 customer_ref: Optional[str], description: Optional[str]):
        self.amount = amount
        self.account_id = account_id
        self.customer_ref = customer_ref      # name or Id, resolved later
        self.description = description
        self.customer_id: Optional[str] = None

    def payload(self) -> dict:
        detail = {"AccountRef": {"value": self.account_id}}
        if self.customer_id:
            detail["CustomerRef"] = {"value": self.customer_id}
        line: dict = {
            "DetailType": "AccountBasedExpenseLineDetail",
            "Amount": round(self.amount, 2),
            "AccountBasedExpenseLineDetail": detail,
        }
        if self.description:
            line["Description"] = self.description
        return line


def parse_line_spec(spec: str) -> Line:
    """Parse ``AMOUNT:ACCOUNT[:CUSTOMER[:DESCRIPTION]]``.

    Fields are colon-separated; DESCRIPTION may itself contain colons (only the
    first three colons are treated as delimiters). CUSTOMER/DESCRIPTION optional.
    """
    parts = spec.split(":", 3)
    if len(parts) < 2:
        raise SystemExit(f"--line '{spec}' must be at least AMOUNT:ACCOUNT")
    try:
        amount = float(parts[0])
    except ValueError:
        raise SystemExit(f"--line '{spec}': amount '{parts[0]}' is not a number")
    account_id = parts[1].strip()
    if not account_id:
        raise SystemExit(f"--line '{spec}': missing expense account Id")
    customer = parts[2].strip() if len(parts) >= 3 and parts[2].strip() else None
    description = parts[3] if len(parts) == 4 and parts[3] else None
    return Line(amount, account_id, customer, description)


# --------------------------------------------------------------------------- #
# Idempotency
# --------------------------------------------------------------------------- #
def find_existing(client: QBOClient, doc_number: Optional[str], vendor_id: Optional[str]) -> Optional[dict]:
    if not doc_number:
        return None
    safe = doc_number.replace("'", "\\'")
    rows = client.query(
        f"SELECT * FROM Purchase WHERE DocNumber = '{safe}' MAXRESULTS 5"
    )
    for p in rows:
        if vendor_id is None or (p.get("EntityRef") or {}).get("value") == vendor_id:
            return p
    return None


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def build_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="book_expense",
        description="Book a vendor expense (QBO Purchase), optionally with a PDF receipt.",
    )
    vend = p.add_mutually_exclusive_group(required=True)
    vend.add_argument("--vendor", help="Vendor display name (resolved; use --create-vendor to add).")
    vend.add_argument("--vendor-id", help="Vendor Id (skip name lookup).")
    p.add_argument("--create-vendor", action="store_true",
                   help="Create the vendor if --vendor name isn't found.")

    p.add_argument("--pay", required=True, metavar="ACCOUNT_ID",
                   help="Payment account Id (bank or credit card the expense was paid from).")
    p.add_argument("--payment-type", default=DEFAULT_PAYMENT_TYPE,
                   choices=["CreditCard", "Cash", "Check"],
                   help=f"QBO PaymentType (default {DEFAULT_PAYMENT_TYPE}).")

    # Single-line convenience OR repeatable --line for splits.
    p.add_argument("--amount", type=float, help="Line amount (single-line mode).")
    p.add_argument("--account", metavar="ACCOUNT_ID", help="Expense account Id (single-line mode).")
    p.add_argument("--customer", help="Customer Id or name to tag the single line (optional).")
    p.add_argument("--customer-name", help="Alias for --customer by name (optional).")
    p.add_argument("--line", action="append", default=[], metavar="AMOUNT:ACCT[:CUST[:DESC]]",
                   help="Repeatable split line. Overrides --amount/--account when present.")

    p.add_argument("--date", dest="txn_date", default=None,
                   help="TxnDate YYYY-MM-DD (default: QBO today).")
    p.add_argument("--doc", dest="doc_number", default=None,
                   help="DocNumber (order/invoice #). Enables duplicate detection.")
    p.add_argument("--memo", default=None, help="PrivateNote + default line description.")
    p.add_argument("--pdf", default=None, help="Path to a receipt PDF to attach.")

    p.add_argument("--apply", action="store_true", help="POST to QBO. Default is a dry-run.")
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    args = build_args(argv)

    # Validate PDF up front so a dry-run catches a bad path too.
    pdf_path: Optional[Path] = None
    if args.pdf:
        pdf_path = Path(args.pdf).expanduser()
        if not pdf_path.exists():
            raise SystemExit(f"Missing PDF: {pdf_path}")

    # Build lines.
    if args.line:
        lines = [parse_line_spec(s) for s in args.line]
    else:
        if args.amount is None or not args.account:
            raise SystemExit("Provide either --line, or both --amount and --account.")
        cust = args.customer or args.customer_name
        lines = [Line(args.amount, args.account, cust, args.memo)]

    total = round(sum(l.amount for l in lines), 2)

    client = QBOClient()

    # Resolve vendor.
    if args.vendor_id:
        vendor_id: Optional[str] = args.vendor_id
        vendor_label = f"Id={vendor_id}"
    else:
        vendor_id = resolve_vendor(client, args.vendor, create=args.create_vendor, apply=args.apply)
        vendor_label = args.vendor + (f" (Id={vendor_id})" if vendor_id else " (new)")

    # Resolve customers per line.
    for l in lines:
        if l.customer_ref:
            l.customer_id = resolve_customer(client, l.customer_ref)

    # Plan output.
    print("=== Expense plan ===")
    print(f"  Vendor:      {vendor_label}")
    print(f"  TxnDate:     {args.txn_date or '(QBO today)'}")
    print(f"  Paid via:    {_account_name(client, args.pay)}  [Id={args.pay}]  {args.payment_type}")
    if args.doc_number:
        print(f"  DocNumber:   {args.doc_number}")
    if args.memo:
        print(f"  Memo:        {args.memo}")
    if pdf_path:
        print(f"  Attach:      {pdf_path.name}")
    for i, l in enumerate(lines, 1):
        cust = f"  cust={l.customer_ref}->Id={l.customer_id}" if l.customer_id else ""
        print(f"  Line {i}:      {_fmt(l.amount)}  -> {_account_name(client, l.account_id)} "
              f"[Id={l.account_id}]{cust}")
    print(f"  Total:       {_fmt(total)}")

    if not args.apply:
        print("\n(dry-run — pass --apply to create the Purchase"
              + (" and attach the PDF)" if pdf_path else ")"))
        return 0

    # Idempotency guard.
    existing = find_existing(client, args.doc_number, vendor_id)
    if existing:
        print(f"\n⏭ Purchase with DocNumber '{args.doc_number}' already exists "
              f"(Id={existing['Id']}, {_fmt(float(existing.get('TotalAmt', 0)))}) — skipping create.")
        return 0

    payload: dict = {
        "PaymentType": args.payment_type,
        "AccountRef": {"value": args.pay},
        "EntityRef": {"value": vendor_id, "type": "Vendor"},
        "Line": [l.payload() for l in lines],
    }
    if args.txn_date:
        payload["TxnDate"] = args.txn_date
    if args.doc_number:
        payload["DocNumber"] = args.doc_number
    if args.memo:
        payload["PrivateNote"] = args.memo

    result = client.create("Purchase", payload)
    print(f"\n  ✓ Purchase Id={result['Id']}  Total={_fmt(float(result['TotalAmt']))}")

    if pdf_path:
        attached = client.upload_attachable(
            str(pdf_path), entity_type="Purchase", entity_id=result["Id"],
            content_type="application/pdf",
            note=args.memo or (f"{args.vendor or vendor_label} — {args.doc_number or ''}").strip(" —"),
        )
        print(f"      Attached PDF Id={attached.get('Id')}  ({attached.get('FileName')})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
