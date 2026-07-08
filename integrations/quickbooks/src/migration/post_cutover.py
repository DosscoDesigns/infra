"""Post-cutover JEs: OBE cleanup, NATCA payment, Mac Mini Q1 depreciation.

Standalone runner. Each function below posts a single JE via the QBO API.
Idempotency check: looks for an existing JE with the same PrivateNote and
skips if found.

Run from src/:
    python -m migration.post_cutover --obe              # post OBE cleanup
    python -m migration.post_cutover --natca-payment    # post NATCA payment
    python -m migration.post_cutover --mac-mini-q1      # post Mac Mini Q1 depreciation
    python -m migration.post_cutover --all              # all three
"""
from __future__ import annotations

import argparse
import sys
from typing import Optional

from qbo import QBOClient


def _accounts(client: QBOClient) -> dict[str, dict]:
    return {a["Name"]: a for a in client.query("SELECT * FROM Account MAXRESULTS 1000")}


def _customers(client: QBOClient) -> dict[str, str]:
    return {c["DisplayName"]: c["Id"] for c in client.query("SELECT * FROM Customer MAXRESULTS 1000")}


def _je_already_posted(client: QBOClient, note_marker: str) -> bool:
    """Return True if a JournalEntry exists whose PrivateNote contains note_marker.

    QBO doesn't expose PrivateNote in queries — fetch all JEs and filter client-side."""
    for je in client.query("SELECT * FROM JournalEntry MAXRESULTS 1000"):
        if note_marker.lower() in (je.get("PrivateNote") or "").lower():
            return True
    return False


def post_obe_cleanup(client: QBOClient) -> None:
    note = "Migration: clear OBE → Owner's Equity (A4/A11 historical income recognition)"
    if _je_already_posted(client, "clear OBE"):
        print("  ⏭ OBE cleanup already posted — skipping")
        return
    accts = _accounts(client)
    obe_id = accts["Opening Balance Equity"]["Id"]
    oe_id = accts["Owner's Equity"]["Id"]
    payload = {
        "TxnDate": "2026-04-30",
        "PrivateNote": note,
        "Line": [
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": 586.20,
                "Description": "Close migration OBE — A4/A11 net of A5",
                "JournalEntryLineDetail": {
                    "PostingType": "Debit",
                    "AccountRef": {"value": obe_id},
                },
            },
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": 586.20,
                "Description": "Recognize historical RCC reimbursement income as accumulated equity",
                "JournalEntryLineDetail": {
                    "PostingType": "Credit",
                    "AccountRef": {"value": oe_id},
                },
            },
        ],
    }
    result = client.create("JournalEntry", payload)
    print(f"  ✓ OBE cleanup posted Id={result['Id']} (DR OBE 586.20, CR Owner's Equity 586.20)")


def post_natca_payment(client: QBOClient) -> None:
    note = "NATCA-PA INV-000562 payment receipt with merchant fee"
    if _je_already_posted(client, "INV-000562 payment"):
        print("  ⏭ NATCA payment already posted — skipping")
        return
    accts = _accounts(client)
    custs = _customers(client)
    bluevine_id = accts["Bluevine (707)"]["Id"]
    fees_id = accts["Merchant Account Fees"]["Id"]
    ar_id = accts["Accounts receivable"]["Id"]
    natca_id = custs["NATCA - PA"]
    payload = {
        "TxnDate": "2026-04-30",
        "PrivateNote": note,
        "Line": [
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": 1094.47,
                "Description": "Net deposit from NATCA-PA INV-000562",
                "JournalEntryLineDetail": {
                    "PostingType": "Debit",
                    "AccountRef": {"value": bluevine_id},
                },
            },
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": 33.92,
                "Description": "Processing fee on NATCA-PA INV-000562",
                "JournalEntryLineDetail": {
                    "PostingType": "Debit",
                    "AccountRef": {"value": fees_id},
                },
            },
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": 1128.39,
                "Description": "Apply NATCA-PA payment to INV-000562",
                "JournalEntryLineDetail": {
                    "PostingType": "Credit",
                    "AccountRef": {"value": ar_id},
                    "Entity": {
                        "Type": "Customer",
                        "EntityRef": {"value": natca_id},
                    },
                },
            },
        ],
    }
    result = client.create("JournalEntry", payload)
    print(f"  ✓ NATCA payment posted Id={result['Id']} (DR Bluevine 1094.47, DR Fees 33.92, CR A/R NATCA-PA 1128.39)")


def ensure_mac_mini_ad_account(client: QBOClient) -> str:
    """Create 'Accum. Depr. - Mac Mini 2023' if missing. Returns the account Id."""
    existing = client.find_by_name("Account", "Accum. Depr. - Mac Mini 2023")
    if existing:
        return existing["Id"]
    payload = {
        "Name": "Accum. Depr. - Mac Mini 2023",
        "AccountType": "Fixed Asset",
        "AccountSubType": "AccumulatedDepreciation",
    }
    result = client.create("Account", payload)
    print(f"  ✓ Created account 'Accum. Depr. - Mac Mini 2023' Id={result['Id']}")
    return result["Id"]


def post_mac_mini_q1(client: QBOClient) -> None:
    """Post Q1 2026 depreciation for Mac Mini.

    Cost basis: $316.05; useful life 5 years; half-year convention first/last year.
    Year 1 (2026, first year): annual depreciation = (316.05 / 5) / 2 = $31.605
    Quarterly: 31.605 / 4 = $7.90 per quarter (with $0.005 rounded out)
    """
    note = "Mac Mini 2023 Q1 2026 depreciation"
    if _je_already_posted(client, "Mac Mini 2023 Q1 2026"):
        print("  ⏭ Mac Mini Q1 depreciation already posted — skipping")
        return
    accts = _accounts(client)
    depr_expense_id = accts["Depreciation Expense"]["Id"]
    mac_ad_id = ensure_mac_mini_ad_account(client)
    payload = {
        "TxnDate": "2026-03-31",
        "PrivateNote": note,
        "Line": [
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": 7.90,
                "Description": "Mac Mini 2023 Q1 2026 (5yr SL, half-year convention)",
                "JournalEntryLineDetail": {
                    "PostingType": "Debit",
                    "AccountRef": {"value": depr_expense_id},
                },
            },
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": 7.90,
                "Description": "Mac Mini 2023 Q1 2026 AD",
                "JournalEntryLineDetail": {
                    "PostingType": "Credit",
                    "AccountRef": {"value": mac_ad_id},
                },
            },
        ],
    }
    result = client.create("JournalEntry", payload)
    print(f"  ✓ Mac Mini Q1 AD posted Id={result['Id']} ($7.90 — first-year half-year)")


def post_fldor_reattribute(client: QBOClient) -> None:
    """Move JE #2's FL DOR $222.44 DR from 4/30 to 3/31 so AST's Q2 view is clean.

    Posts two JEs:
      JE A (2026-03-31): DR FL DOR Payable $222.44 / CR Owner's Equity $222.44
      JE B (2026-04-30): CR FL DOR Payable $222.44 / DR Owner's Equity $222.44

    Net effect on FL DOR Payable: same final balance ($56.19), but the $222.44
    reduction now happens in Q1 instead of Q2, leaving the Q2 sales tax return
    showing $0 activity (just the $56.19 carryover balance).
    """
    note_a = "FL DOR re-attribution to Q1 (part A — move reduction to 3/31)"
    note_b = "FL DOR re-attribution to Q1 (part B — reverse 4/30 line from JE #2)"
    if _je_already_posted(client, "FL DOR re-attribution"):
        print("  ⏭ FL DOR re-attribution already posted — skipping")
        return
    accts = _accounts(client)
    fldor_id = accts["Florida Department of Revenue Payable"]["Id"]
    oe_id = accts["Owner's Equity"]["Id"]

    je_a = {
        "TxnDate": "2026-03-31",
        "PrivateNote": note_a,
        "Line": [
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": 222.44,
                "Description": "Q1 2026 net FL sales tax activity (was on 4/30 in JE #2)",
                "JournalEntryLineDetail": {
                    "PostingType": "Debit",
                    "AccountRef": {"value": fldor_id},
                },
            },
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": 222.44,
                "Description": "Offset for FL DOR re-attribution",
                "JournalEntryLineDetail": {
                    "PostingType": "Credit",
                    "AccountRef": {"value": oe_id},
                },
            },
        ],
    }
    result_a = client.create("JournalEntry", je_a)
    print(f"  ✓ JE A posted Id={result_a['Id']} (Q1 DR FL DOR 222.44 / CR OE 222.44)")

    je_b = {
        "TxnDate": "2026-04-30",
        "PrivateNote": note_b,
        "Line": [
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": 222.44,
                "Description": "Reverse JE #2 FL DOR line — re-attributed to Q1",
                "JournalEntryLineDetail": {
                    "PostingType": "Credit",
                    "AccountRef": {"value": fldor_id},
                },
            },
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": 222.44,
                "Description": "Offset reverse for FL DOR re-attribution",
                "JournalEntryLineDetail": {
                    "PostingType": "Debit",
                    "AccountRef": {"value": oe_id},
                },
            },
        ],
    }
    result_b = client.create("JournalEntry", je_b)
    print(f"  ✓ JE B posted Id={result_b['Id']} (Q2 CR FL DOR 222.44 / DR OE 222.44 — reverses JE #2 line)")


def post_fldor_carryover(client: QBOClient) -> None:
    """Move the $56.19 pre-migration FL DOR balance out of the AST-managed
    GlobalTaxPayable account into a regular Other Current Liability so it
    shows up in COA / reports while AST tracks Q2+ activity cleanly.

    Creates account "FL Sales Tax Carryover (pre-migration)" if missing,
    then posts a JE that zeros out FL DOR Payable and credits the carryover.
    """
    note = "Move pre-migration FL DOR balance to non-AST carryover account"
    if _je_already_posted(client, "FL DOR balance to non-AST"):
        print("  ⏭ FL DOR carryover JE already posted — skipping")
        return

    accts = _accounts(client)
    fldor_id = accts["Florida Department of Revenue Payable"]["Id"]

    # Ensure carryover account exists
    carryover = client.find_by_name("Account", "FL Sales Tax Carryover (pre-migration)")
    if not carryover:
        payload = {
            "Name": "FL Sales Tax Carryover (pre-migration)",
            "AccountType": "Other Current Liability",
            "AccountSubType": "OtherCurrentLiabilities",
            "Description": "Pre-migration FL sales tax balance from Wave. Archive after first Q2 2026 FL DOR filing clears it.",
        }
        carryover = client.create("Account", payload)
        print(f"  ✓ Created account 'FL Sales Tax Carryover (pre-migration)' Id={carryover['Id']}")
    carryover_id = carryover["Id"]

    je = {
        "TxnDate": "2026-04-30",
        "PrivateNote": note,
        "Line": [
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": 56.19,
                "Description": "Zero pre-migration AST balance",
                "JournalEntryLineDetail": {
                    "PostingType": "Debit",
                    "AccountRef": {"value": fldor_id},
                },
            },
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": 56.19,
                "Description": "Carryover from Wave migration — clear via Q2 2026 FL DOR payment",
                "JournalEntryLineDetail": {
                    "PostingType": "Credit",
                    "AccountRef": {"value": carryover_id},
                },
            },
        ],
    }
    result = client.create("JournalEntry", je)
    print(f"  ✓ Carryover JE posted Id={result['Id']} (DR FL DOR Payable 56.19 / CR FL Sales Tax Carryover 56.19)")


def post_sanmar_to_cc(client: QBOClient) -> None:
    """Convert 'SanMar A/P (Net 30)' from Other Current Liability to a Credit
    Card type account so QBO's Expense form recognizes it as a payment method.

    QBO doesn't allow AccountType changes on existing accounts, so we create a
    new 'SanMar Terms' Credit Card account, migrate the balance via JE, and
    deactivate the old liability account.
    """
    note = "Convert SanMar A/P (Net 30) → SanMar Terms credit card type"
    if _je_already_posted(client, "SanMar Terms credit card"):
        print("  ⏭ SanMar Terms conversion already posted — skipping")
        return

    accts = _accounts(client)
    old = accts.get("SanMar A/P (Net 30)")
    if not old:
        print("  ⚠ Old 'SanMar A/P (Net 30)' account not found — nothing to convert")
        return

    # Create the new Credit Card account
    new = client.find_by_name("Account", "SanMar Terms")
    if not new:
        payload = {
            "Name": "SanMar Terms",
            "AccountType": "Credit Card",
            "AccountSubType": "CreditCard",
            "Description": "SanMar Net 30 trade credit (converted 2026-05-02 from liability)",
        }
        new = client.create("Account", payload)
        print(f"  ✓ Created Credit Card account 'SanMar Terms' Id={new['Id']}")
    new_id = new["Id"]

    # Pull current balance of the old account
    tb = client._request("GET", "reports/TrialBalance",
                       params={"start_date": "2026-05-02", "end_date": "2026-05-02",
                               "accounting_method": "Accrual"})
    old_balance: Optional[float] = None
    for row in tb.get("Rows", {}).get("Row", []):
        cols = row.get("ColData", [])
        if len(cols) >= 3 and cols[0].get("value") == "SanMar A/P (Net 30)":
            d = float(cols[1].get("value", "") or "0")
            c = float(cols[2].get("value", "") or "0")
            old_balance = c - d  # liability is credit-positive
            break
    if old_balance is None or old_balance <= 0:
        print(f"  ⚠ Could not determine SanMar A/P balance (got {old_balance}) — aborting migration")
        return
    print(f"  → Migrating ${old_balance:,.2f} from SanMar A/P (Net 30) to SanMar Terms")

    je = {
        "TxnDate": "2026-05-02",
        "PrivateNote": note,
        "Line": [
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": old_balance,
                "Description": "Zero out old SanMar A/P (Net 30) liability",
                "JournalEntryLineDetail": {
                    "PostingType": "Debit",
                    "AccountRef": {"value": old["Id"]},
                },
            },
            {
                "DetailType": "JournalEntryLineDetail",
                "Amount": old_balance,
                "Description": "Migrate balance to SanMar Terms credit card",
                "JournalEntryLineDetail": {
                    "PostingType": "Credit",
                    "AccountRef": {"value": new_id},
                },
            },
        ],
    }
    result = client.create("JournalEntry", je)
    print(f"  ✓ Migration JE posted Id={result['Id']}")

    # Deactivate the old account
    fresh = client.find_by_name("Account", "SanMar A/P (Net 30)")
    if fresh:
        deact = {
            "Id": fresh["Id"],
            "SyncToken": fresh["SyncToken"],
            "Name": fresh["Name"],
            "Active": False,
            "sparse": True,
        }
        client.update("Account", deact)
        print(f"  ✓ Deactivated old account 'SanMar A/P (Net 30)' Id={fresh['Id']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--obe", action="store_true")
    parser.add_argument("--natca-payment", action="store_true")
    parser.add_argument("--mac-mini-q1", action="store_true")
    parser.add_argument("--fldor-reattribute", action="store_true",
                        help="Move FL DOR $222.44 reduction from 4/30 to 3/31 so Q2 AST is clean")
    parser.add_argument("--fldor-carryover", action="store_true",
                        help="Move pre-migration $56.19 to a non-AST liability account so AST reports cleanly")
    parser.add_argument("--sanmar-to-cc", action="store_true",
                        help="Convert SanMar A/P (Net 30) liability into a Credit Card type account so it shows up as a payment method")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args()

    if not (args.obe or args.natca_payment or args.mac_mini_q1 or args.fldor_reattribute
            or args.fldor_carryover or args.sanmar_to_cc or args.all):
        parser.error("specify at least one of --obe / --natca-payment / --mac-mini-q1 / "
                     "--fldor-reattribute / --fldor-carryover / --sanmar-to-cc / --all")

    client = QBOClient()
    if args.all or args.obe:
        post_obe_cleanup(client)
    if args.all or args.natca_payment:
        post_natca_payment(client)
    if args.all or args.mac_mini_q1:
        post_mac_mini_q1(client)
    if args.all or args.fldor_reattribute:
        post_fldor_reattribute(client)
    if args.all or args.fldor_carryover:
        post_fldor_carryover(client)
    if args.all or args.sanmar_to_cc:
        post_sanmar_to_cc(client)
    return 0


if __name__ == "__main__":
    sys.exit(main())
