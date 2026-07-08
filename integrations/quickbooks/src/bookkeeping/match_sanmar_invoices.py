"""Match incoming SanMar invoice PDFs to existing QBO Purchase records,
add DocNumber + PrivateNote, and attach the PDF as a QBO Attachable.

Bank-feed-imported Purchases on the SanMar Terms credit-card account come in
with no DocNumber, no notes, and just a single line posting to Shirts COGS.
The actual invoice arrives by email a few days later. This matcher does the
final tying-out: identify the existing Purchase by amount, stamp the invoice
metadata, and attach the source PDF.

Usage:
    python -m bookkeeping.match_sanmar_invoices               # dry-run
    python -m bookkeeping.match_sanmar_invoices --apply       # do it

Match list is hard-coded below — edit before running for a new batch.
"""
from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass

from qbo import QBOClient


@dataclass(frozen=True)
class InvoiceMatch:
    pdf_path: str
    purchase_id: str          # existing QBO Purchase to update
    expected_amount: float    # safety check before update
    doc_number: str           # invoice number, e.g. INV-160042467
    sales_order: str          # SanMar SO-XXX
    summary: str              # one-line items summary
    ship_to: str              # recipient


# 2026-06-03 batch — one RCC invoice (dated 6/3, due 7/3, Net30)
MATCHES: list[InvoiceMatch] = [
    InvoiceMatch(
        pdf_path="/Users/jason/dev/dd/infra/integrations/quickbooks/receipts/sanmar/SanMar-Invoice-INV-160990177.pdf",
        purchase_id="133",
        expected_amount=149.62,
        doc_number="INV-160990177",
        sales_order="SO-161752574",
        summary="33 DT Perfect Tri Tees DM130 Navy Frost (13 XS / 9 S / 11 M) + 1 PA Zephyr J344 Dress Blue Navy M + 1 DM130 Heathered Teal XL — 100% RCC",
        ship_to="DD shop — Jacksonville (10940 New Kings Rd)",
    ),
]


def build_note(m: InvoiceMatch) -> str:
    return f"{m.sales_order} — {m.summary} — Ship to: {m.ship_to}"


def verify_and_plan(client: QBOClient) -> list[tuple[InvoiceMatch, dict]]:
    """Fetch each Purchase, sanity-check the amount, return (match, current_purchase)."""
    plan = []
    for m in MATCHES:
        body = client._request("GET", f"purchase/{m.purchase_id}")
        p = body["Purchase"]
        if abs(p["TotalAmt"] - m.expected_amount) > 0.005:
            raise SystemExit(
                f"Purchase {m.purchase_id} amount mismatch: expected ${m.expected_amount}, got ${p['TotalAmt']}"
            )
        plan.append((m, p))
    return plan


def print_plan(plan: list[tuple[InvoiceMatch, dict]]) -> None:
    print("\n=== SanMar invoice match plan ===\n")
    for m, p in plan:
        existing_doc = p.get("DocNumber") or "(none)"
        existing_note = p.get("PrivateNote") or "(none)"
        print(f"Purchase Id={m.purchase_id}  TxnDate={p['TxnDate']}  Total=${p['TotalAmt']:,.2f}")
        print(f"  Set DocNumber:   {existing_doc} -> {m.doc_number}")
        print(f"  Set PrivateNote: {existing_note}")
        print(f"                -> {build_note(m)}")
        print(f"  Attach PDF:      {m.pdf_path.rsplit('/', 1)[-1]}")
        print()


def apply(client: QBOClient, plan: list[tuple[InvoiceMatch, dict]]) -> None:
    for m, p in plan:
        # Sparse update DocNumber + PrivateNote.
        # QBO Purchase sparse update still requires PaymentType + AccountRef in
        # the payload — pass them through unchanged from the existing record.
        updated = client.sparse_update(
            "Purchase",
            qbo_id=p["Id"],
            sync_token=p["SyncToken"],
            fields={
                "DocNumber": m.doc_number,
                "PrivateNote": build_note(m),
                "PaymentType": p["PaymentType"],
                "AccountRef": p["AccountRef"],
            },
        )
        print(f"  Updated Purchase Id={m.purchase_id}  DocNumber={updated['DocNumber']}")

        # Upload PDF as Attachable
        attached = client.upload_attachable(
            m.pdf_path,
            entity_type="Purchase",
            entity_id=m.purchase_id,
            content_type="application/pdf",
            note=f"SanMar invoice {m.doc_number} — {m.sales_order}",
        )
        print(f"    Attached PDF Id={attached.get('Id')}  ({attached.get('FileName')})")
        print()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Actually update QBO. Default is dry-run.")
    args = p.parse_args()

    client = QBOClient()
    plan = verify_and_plan(client)
    print_plan(plan)

    if not args.apply:
        print("(dry-run — pass --apply to update Purchases and upload attachments)")
        return 0

    apply(client, plan)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
