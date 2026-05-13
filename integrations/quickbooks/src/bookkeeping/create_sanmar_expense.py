"""Create a QBO Purchase (expense) for a SanMar order on terms.

Defaults: paid via SanMar Terms (166), posts to Shirts (132).
Split across two customers via line-level CustomerRef.

No PDF on first run — attach once invoice arrives in email.

Usage:
    python -m bookkeeping.create_sanmar_expense              # dry-run
    python -m bookkeeping.create_sanmar_expense --apply      # execute
"""
from __future__ import annotations

import argparse
import sys

from qbo import QBOClient

# QBO constants
VENDOR_ID = "69"            # SanMar
PAYMENT_ACCOUNT_ID = "166"  # SanMar Terms
EXPENSE_ACCOUNT_ID = "132"  # Shirts (COGS)

TXN_DATE = "2026-05-13"
TOTAL = 81.23

# Split
EMBARK_AMOUNT = 44.85
RCC_AMOUNT = round(TOTAL - EMBARK_AMOUNT, 2)  # 36.38

PRIVATE_NOTE = (
    f"SanMar terms order — split: EMBARK ${EMBARK_AMOUNT:.2f} / "
    f"RCC ${RCC_AMOUNT:.2f}. Invoice pending."
)


def _find_customer(client: QBOClient, name: str) -> str:
    results = client.query(
        f"SELECT Id, DisplayName FROM Customer WHERE DisplayName LIKE '%{name}%' MAXRESULTS 5"
    )
    if not results:
        raise RuntimeError(f"No customer found matching '{name}'")
    if len(results) > 1:
        names = [r["DisplayName"] for r in results]
        raise RuntimeError(f"Ambiguous customer '{name}': {names}")
    return results[0]["Id"]


def build_payload(embark_cust_id: str, rcc_cust_id: str) -> dict:
    def line(amount: float, cust_id: str, desc: str) -> dict:
        return {
            "DetailType": "AccountBasedExpenseLineDetail",
            "Amount": amount,
            "Description": desc,
            "AccountBasedExpenseLineDetail": {
                "AccountRef": {"value": EXPENSE_ACCOUNT_ID},
                "CustomerRef": {"value": cust_id},
            },
        }

    return {
        "PaymentType": "CreditCard",
        "AccountRef": {"value": PAYMENT_ACCOUNT_ID},
        "EntityRef": {"value": VENDOR_ID, "type": "Vendor"},
        "TxnDate": TXN_DATE,
        "PrivateNote": PRIVATE_NOTE,
        "Line": [
            line(EMBARK_AMOUNT, embark_cust_id, f"EMBARK portion — SanMar terms"),
            line(RCC_AMOUNT, rcc_cust_id, f"RCC portion — SanMar terms"),
        ],
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true",
                   help="Actually create the Purchase. Default is dry-run.")
    args = p.parse_args()

    client = QBOClient()

    print("Looking up customers...")
    embark_id = _find_customer(client, "Embark Church")
    rcc_id = _find_customer(client, "River Christian Church")

    vendor = client._request("GET", f"vendor/{VENDOR_ID}")["Vendor"]
    pay_acct = client._request("GET", f"account/{PAYMENT_ACCOUNT_ID}")["Account"]
    exp_acct = client._request("GET", f"account/{EXPENSE_ACCOUNT_ID}")["Account"]

    print(f"\n=== SanMar terms expense plan ===")
    print(f"  Vendor:     {vendor['DisplayName']} (Id={VENDOR_ID})")
    print(f"  TxnDate:    {TXN_DATE}")
    print(f"  Paid via:   {pay_acct['Name']} ({pay_acct['AccountType']})")
    print(f"  Posts to:   {exp_acct['Name']} ({exp_acct['AccountType']})")
    print(f"  Line 1:     EMBARK (Id={embark_id})  ${EMBARK_AMOUNT:.2f}")
    print(f"  Line 2:     RCC    (Id={rcc_id})  ${RCC_AMOUNT:.2f}")
    print(f"  Total:      ${TOTAL:.2f}")
    print(f"  Note:       {PRIVATE_NOTE}")
    print()

    if not args.apply:
        print("(dry-run — pass --apply to create the Purchase)")
        return 0

    payload = build_payload(embark_id, rcc_id)
    result = client.create("Purchase", payload)
    print(f"Created Purchase Id={result['Id']}  Total=${result['TotalAmt']:,.2f}")
    print("No attachment yet — run upload_attachable once invoice PDF arrives.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
