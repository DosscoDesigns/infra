"""Option B opening: post 2025-12-31 opening JE + 2026-04-30 YTD activity JE.

Two journal entries:

1. JE #1 dated 2025-12-31: balance sheet positions from Wave's 12/31/2025
   trial balance. 2025 P&L is rolled into Retained Earnings (single net-
   income line) rather than replayed line-by-line.

2. JE #2 dated 2026-04-30: deltas between 12/31/2025 TB and 4/30/2026 TB.
   This captures Jan–Apr 2026 P&L activity plus the corresponding balance
   sheet movement (cash, inventory, A/R, A/P, equity changes).

A/R and A/P are excluded from both JEs. Open invoices and bills are loaded
through the ar_ap module against actual customer/vendor records.

Run from src/:
    python -m migration.option_b               # dry-run
    python -m migration.option_b --execute     # apply
"""
from __future__ import annotations

import argparse
import csv
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Optional

from qbo import QBOClient

WAVE_DIR = Path(__file__).resolve().parents[4] / "TEMP" / "wave-export"

D0 = Decimal("0")


def _money(s: str) -> Decimal:
    if not s:
        return D0
    s = s.strip().replace("$", "").replace(",", "").replace('"', "")
    if not s:
        return D0
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except Exception:
        return D0


# Wave name -> QBO name for balance sheet accounts only.
WAVE_BS_TO_QBO: dict[str, str | None] = {
    # Cash + bank
    "Cash on Hand": "Cash on Hand",
    "Dossco Designs LLC (707)": "Bluevine (707)",
    "Wave Payments": "Stripe Clearing",  # Wave Payments funds-in-transit
    # Inventory (collapsed to single QBO account)
    "Hats On Hand - SJCA": "Inventory - Apparel & Materials",
    "Hats on Hand": "Inventory - Apparel & Materials",
    "Marketing Materials on Hand": "Inventory - Apparel & Materials",
    "Samples": "Inventory - Apparel & Materials",
    "Shirts OH - RCC": "Inventory - Apparel & Materials",
    "Shirts OH - SJCA": "Inventory - Apparel & Materials",
    "Shirts on Hand": "Inventory - Apparel & Materials",
    # Fixed assets
    "Consew 226R-1": "Equipment - Consew 226R-1",
    "Consew 226R-1 - AD": "Accum. Depr. - Consew 226R-1",
    "Fusion IQ 2024": "Equipment - Fusion IQ 2024",
    "Fusion IQ 2024 - AD": "Accum. Depr. - Fusion IQ 2024",
    "Nikon D90": "Camera - Nikon D90",
    "Nikon D90 - AD": "Accum. Depr. - Nikon D90",
    "Mac Mini - 2023": "Computer Equipment - Mac Mini 2023",
    # Liabilities
    "JASON DOSS -01005": "Amex (1005)",
    "San Mar Terms": "SanMar A/P (Net 30)",
    "Clay County": "Florida Department of Revenue Payable",
    # Equity
    "Owner Investment / Drawings": "Owner's Draw",
    "Owner's Equity": "Owner's Equity",
    "Profit for all prior years": "Retained Earnings",
    # Skipped (handled by open invoices/bills, or not migrated)
    "Accounts Receivable": None,
    "Accounts Payable": None,
}

# Wave P&L account name -> QBO account name. Used in JE #2 to post 2026 YTD
# activity. Value of None means intentionally drop.
WAVE_PL_TO_QBO: dict[str, str | None] = {
    # Income
    "Interest": "Other Income - Interest",
    "Rewards": "Other Income - Rewards",
    "Sales": "Services",  # generic Wave "Sales" → QBO Services revenue (catch-all)
    "Sales - Apparel": "Sales - Apparel",
    "Sales - Marketing Materials": "Sales - Marketing Materials",
    "Sales - The Slime Co": "Sales - Slime Co",
    "Sales - Design Fee": "Sales - Design/Other",
    "Sales - Software Subscription": "Sales - Web/Hosting",
    "Sales Discounts": "Sales Discounts",
    # COGS
    "Embroidery Digitizing": "Embroidery Digitizing",
    "Embroidery Service": "Embroidery Service",
    "Hats": "Hats",
    "Marketing Materials - Resale": "Marketing Materials - Resale",
    "Plugins": "Plugins / Software for Resale",
    "Shirt Transfers": "Shirt Transfers",
    "Shirts": "Shirts",
    "Screen Print Service": "Screen Print",
    "Screen Print Screens": "Screen Print",
    "Vinyl Supplies": "Vinyl Supplies",
    # Operating expenses
    "Advertising & Promotion": "Advertising & Promotion",
    "Bad Debt Expense": "Bad debt expense",
    "Bank Service Charges": "Bank Service Charges",
    "Computer – Hosting": "Computer – Hosting",
    "Donations Given": "Charitable Contributions",
    "Insurance - Liability": "Insurance - Liability",
    "Interest Expense": "Interest Expense",
    "Meals and Entertainment": "Meals and Entertainment",
    "Merchant Account Fees": "Merchant Account Fees",
    "Office Supplies": "Office Supplies",
    "Professional Fees": "Professional Fees",
    "RD - SD Enterprises": None,  # Sunset per A5 — drop
    "RD - Youth Ministry Resources": "RD - Youth Ministry Resources",
    "Repairs & Maintenance": "Repairs & maintenance",
    "Sales Tax": "Sales Tax",
    "Shipping Fee": "Shipping Fee",
    "Subscriptions": "Subscriptions",
    "Telephone – Wireless": "Telephone – Wireless",
    "Vendor Processing Fee": "Vendor Processing Fee",
    "Equipment": None,  # generic Wave Equipment expense — categorize as needed
    "Depreciation Expense": "Depreciation Expense",
}


@dataclass
class JELine:
    qbo_account: str
    debit: Decimal = D0
    credit: Decimal = D0
    description: str = ""

    @property
    def amount(self) -> Decimal:
        return self.debit if self.debit else self.credit

    @property
    def posting_type(self) -> str:
        return "Debit" if self.debit else "Credit"


def parse_tb(path: Path) -> tuple[dict[str, tuple[Decimal, Decimal]], str]:
    """Parse a Wave TB CSV. Returns ({account: (debit, credit)}, as_of)."""
    rows: dict[str, tuple[Decimal, Decimal]] = {}
    as_of = ""
    skip_names = {
        "Assets", "Liabilities", "Equity", "Income", "Expenses",
        "Cost of Goods Sold", "Operating Expenses", "Gross Profit", "Net Profit",
    }
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.reader(f):
            if not r:
                continue
            joined = ",".join(r)
            if joined.startswith("As of"):
                as_of = r[0].replace("As of ", "").strip()
            if len(r) < 4:
                continue
            account = r[1].strip()
            if not account or account in skip_names:
                continue
            if account.startswith("Total "):
                continue
            d, c = _money(r[2]), _money(r[3])
            if d == 0 and c == 0:
                continue
            rows[account] = (d, c)
    return rows, as_of


def find_tb(date_str: str) -> Path:
    """Find Wave TB CSV for a specific 'as of' date."""
    for p in sorted(WAVE_DIR.glob("*Trial Balance*.csv")):
        with open(p, encoding="utf-8-sig") as f:
            head = f.read(500)
        if f"As of {date_str}" in head:
            return p
    raise FileNotFoundError(f"No TB found for {date_str} in {WAVE_DIR}")


# === JE #1: Opening at 2025-12-31 ===

def build_opening_je(tb_1231: dict[str, tuple[Decimal, Decimal]]) -> tuple[list[JELine], list[str]]:
    """Build the 2025-12-31 opening JE.

    Posts balance sheet accounts at their 12/31 values. 2025 P&L net income
    is computed from the same TB and added as a single Retained Earnings
    credit (or debit if loss).

    Returns (lines, warnings).
    """
    lines: list[JELine] = []
    warnings: list[str] = []
    inventory_total = D0
    income_total = D0   # net of debits
    expense_total = D0  # net of debits

    pl_keywords_income = {"Interest", "Rewards", "Sales"}
    pl_keywords_sales_disc = {"Sales Discounts"}

    for acct, (d, c) in tb_1231.items():
        # Detect P&L lines: anything in WAVE_PL_TO_QBO is P&L
        if acct in WAVE_PL_TO_QBO:
            # Income-natured: net = credit - debit (income increases credits)
            # Expense/COGS: net = debit - credit
            net = d - c
            if (
                acct in pl_keywords_income
                or acct.startswith("Sales -")
                or acct == "Sales"
            ):
                income_total += -net  # income side: credits positive
            elif acct in pl_keywords_sales_disc:
                income_total -= net   # contra-income
            else:
                expense_total += net
            continue

        if acct not in WAVE_BS_TO_QBO:
            warnings.append(f"Unmapped account in 12/31 TB: {acct!r}")
            continue
        qbo = WAVE_BS_TO_QBO[acct]
        if qbo is None:
            continue
        if qbo == "Inventory - Apparel & Materials":
            inventory_total += d - c
            continue
        lines.append(JELine(qbo, debit=d, credit=c, description=f"From Wave: {acct}"))

    # Inventory aggregate
    if inventory_total > 0:
        lines.append(JELine("Inventory - Apparel & Materials", debit=inventory_total,
                            description="Combined inventory at 12/31/2025"))
    elif inventory_total < 0:
        lines.append(JELine("Inventory - Apparel & Materials", credit=-inventory_total,
                            description="Combined inventory at 12/31/2025"))

    # 2025 net income → Retained Earnings
    net_income_2025 = income_total - expense_total
    if net_income_2025 > 0:
        lines.append(JELine("Retained Earnings", credit=net_income_2025,
                            description="2025 net income rolled to RE"))
    elif net_income_2025 < 0:
        lines.append(JELine("Retained Earnings", debit=-net_income_2025,
                            description="2025 net loss rolled to RE"))

    return lines, warnings


# === JE #2: 2026-04-30 YTD activity ===

def build_ytd_je(
    tb_1231: dict[str, tuple[Decimal, Decimal]],
    tb_0430: dict[str, tuple[Decimal, Decimal]],
) -> tuple[list[JELine], list[str]]:
    """Build the 2026-04-30 YTD activity JE.

    Two different posting rules depending on account class:
      - Balance sheet (WAVE_BS_TO_QBO): post DELTA = (4/30 net) - (12/31 net),
        because QBO already has the 12/31 starting balance from JE #1.
      - P&L (WAVE_PL_TO_QBO): post the 4/30 net value directly. QBO's P&L
        accounts started at $0 after JE #1 (2025 P&L was rolled into RE),
        so the 4/30 Wave value IS the 2026 YTD activity.
    """
    lines: list[JELine] = []
    warnings: list[str] = []
    all_accts = set(tb_1231) | set(tb_0430)
    inventory_delta = D0

    for acct in all_accts:
        # Skip A/R and A/P (handled by ar_ap module)
        if acct in {"Accounts Receivable", "Accounts Payable"}:
            d1, c1 = tb_1231.get(acct, (D0, D0))
            d2, c2 = tb_0430.get(acct, (D0, D0))
            delta = (d2 - c2) - (d1 - c1)
            warnings.append(f"Skipped delta for {acct}: ${delta:,.2f} (handled via open invoices/bills)")
            continue

        # Skip Wave's "Profit for all prior years" delta — JE #1 already
        # rolled 2025 net income into RE in QBO, so any movement on this
        # account between 12/31 and 4/30 reflects Wave's automatic year-end
        # close that we manually replicated in JE #1.
        if acct == "Profit for all prior years":
            continue

        d1, c1 = tb_1231.get(acct, (D0, D0))
        d2, c2 = tb_0430.get(acct, (D0, D0))
        net1 = d1 - c1
        net2 = d2 - c2

        if acct in WAVE_BS_TO_QBO:
            qbo = WAVE_BS_TO_QBO[acct]
            if qbo is None:
                continue
            amount = net2 - net1  # delta
            desc = f"2026 BS change: {acct}"
        elif acct in WAVE_PL_TO_QBO:
            qbo = WAVE_PL_TO_QBO[acct]
            if qbo is None:
                continue
            amount = net2  # 4/30 value = YTD activity
            desc = f"2026 YTD activity: {acct}"
        else:
            warnings.append(f"Unmapped account in YTD: {acct!r} (Wave 4/30 D={d2} C={c2})")
            continue

        if amount == 0:
            continue

        if qbo == "Inventory - Apparel & Materials":
            inventory_delta += amount
            continue

        if amount > 0:
            lines.append(JELine(qbo, debit=amount, description=desc))
        else:
            lines.append(JELine(qbo, credit=-amount, description=desc))

    if inventory_delta > 0:
        lines.append(JELine("Inventory - Apparel & Materials", debit=inventory_delta,
                            description="2026 YTD inventory change"))
    elif inventory_delta < 0:
        lines.append(JELine("Inventory - Apparel & Materials", credit=-inventory_delta,
                            description="2026 YTD inventory change"))

    return lines, warnings


def balance_to_obe(lines: list[JELine]) -> Optional[JELine]:
    td = sum((l.debit for l in lines), D0)
    tc = sum((l.credit for l in lines), D0)
    diff = td - tc
    if diff == 0:
        return None
    if diff > 0:
        return JELine("Opening Balance Equity", credit=diff, description="Balancing entry")
    return JELine("Opening Balance Equity", debit=-diff, description="Balancing entry")


def print_je(title: str, lines: list[JELine], balancer: Optional[JELine], date: str, warnings: list[str]) -> None:
    print(f"\n=== {title} (TxnDate {date}) ===\n")
    print(f"{'ACCOUNT':50} {'DEBIT':>14} {'CREDIT':>14}")
    print("-" * 80)
    for l in sorted(lines, key=lambda x: x.qbo_account):
        d = f"${l.debit:,.2f}" if l.debit else ""
        c = f"${l.credit:,.2f}" if l.credit else ""
        print(f"{l.qbo_account[:50]:50} {d:>14} {c:>14}")
    if balancer:
        d = f"${balancer.debit:,.2f}" if balancer.debit else ""
        c = f"${balancer.credit:,.2f}" if balancer.credit else ""
        print(f"{balancer.qbo_account[:50]:50} {d:>14} {c:>14}  ← plug")
    all_lines = lines + ([balancer] if balancer else [])
    td = sum((l.debit for l in all_lines), D0)
    tc = sum((l.credit for l in all_lines), D0)
    print("-" * 80)
    print(f"{'TOTAL':50} {f'${td:,.2f}':>14} {f'${tc:,.2f}':>14}  diff=${td-tc:,.2f}")
    if warnings:
        print(f"\n  Warnings ({len(warnings)}):")
        for w in warnings:
            print(f"    - {w}")


def post_je(client: QBOClient, lines: list[JELine], balancer: Optional[JELine], date: str, note: str) -> str:
    accounts = {a["Name"]: a["Id"] for a in client.query("SELECT * FROM Account MAXRESULTS 1000")}

    all_lines = lines + ([balancer] if balancer else [])
    je_lines = []
    for l in all_lines:
        acct_id = accounts.get(l.qbo_account)
        if not acct_id:
            raise RuntimeError(f"QBO account {l.qbo_account!r} not found")
        je_lines.append({
            "DetailType": "JournalEntryLineDetail",
            "Amount": float(l.amount),
            "Description": l.description,
            "JournalEntryLineDetail": {
                "PostingType": l.posting_type,
                "AccountRef": {"value": acct_id},
            },
        })

    payload = {"TxnDate": date, "PrivateNote": note, "Line": je_lines}
    result = client.create("JournalEntry", payload)
    return result["Id"]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    args = parser.parse_args()

    tb_1231_path = find_tb("2025-12-31")
    tb_0430_path = find_tb("2026-04-30")
    print(f"12/31/2025 TB: {tb_1231_path.name}")
    print(f"4/30/2026 TB:  {tb_0430_path.name}\n")

    tb_1231, _ = parse_tb(tb_1231_path)
    tb_0430, _ = parse_tb(tb_0430_path)

    # JE #1: Opening
    je1_lines, je1_warn = build_opening_je(tb_1231)
    je1_balancer = balance_to_obe(je1_lines)
    print_je("JE #1 — Opening Balance", je1_lines, je1_balancer, "2025-12-31", je1_warn)

    # JE #2: YTD activity
    je2_lines, je2_warn = build_ytd_je(tb_1231, tb_0430)
    je2_balancer = balance_to_obe(je2_lines)
    print_je("JE #2 — 2026 YTD Activity", je2_lines, je2_balancer, "2026-04-30", je2_warn)

    if not args.execute:
        print("\n(Dry run — pass --execute to post both JEs.)")
        return 0

    print("\n=== Executing ===")
    client = QBOClient()
    je1_id = post_je(client, je1_lines, je1_balancer, "2025-12-31",
                     "Wave→QBO migration: opening balance at 2025-12-31")
    print(f"  ✓ JE #1 posted Id={je1_id}")
    je2_id = post_je(client, je2_lines, je2_balancer, "2026-04-30",
                     "Wave→QBO migration: 2026 YTD activity (Jan–Apr summary)")
    print(f"  ✓ JE #2 posted Id={je2_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
