"""Opening balances JE: post the cutover trial balance to QBO.

Reads Wave's Trial Balance CSV, maps Wave accounts to QBO accounts via
wave_account_map.WAVE_TO_QBO, builds a single Journal Entry that brings
QBO to the same starting position as Wave at cutover.

A/R and A/P are explicitly excluded — they get loaded via the ar_ap module
as actual open invoices and bills, so QBO's aging works correctly.

The JE is balanced to QBO's "Opening Balance Equity" account (a system
account that QBO reconciles to Owner's Equity over time). Any tiny
rounding lands there visibly rather than being silently absorbed.
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Optional

from qbo import QBOClient

from .wave_account_map import WAVE_TO_QBO

WAVE_EXPORT_DIR = Path(__file__).resolve().parents[4] / "TEMP" / "wave-export"


def _money(s: str) -> Decimal:
    if not s:
        return Decimal("0")
    s = s.strip().replace("$", "").replace(",", "").replace('"', "")
    if not s:
        return Decimal("0")
    if s.startswith("(") and s.endswith(")"):
        s = "-" + s[1:-1]
    try:
        return Decimal(s)
    except Exception:
        return Decimal("0")


@dataclass
class JELine:
    qbo_account: str       # QBO account name
    debit: Decimal = Decimal("0")
    credit: Decimal = Decimal("0")
    description: str = ""

    @property
    def amount(self) -> Decimal:
        return self.debit if self.debit else self.credit

    @property
    def posting_type(self) -> str:
        return "Debit" if self.debit else "Credit"


def _find_tb_csv() -> Path:
    """Find the most recent Wave Trial Balance CSV in TEMP/wave-export/."""
    candidates = sorted(WAVE_EXPORT_DIR.glob("*Trial Balance*.csv"))
    if not candidates:
        raise FileNotFoundError(f"No Trial Balance CSV in {WAVE_EXPORT_DIR}")
    return candidates[-1]


def parse_wave_tb(path: Optional[Path] = None) -> tuple[list[tuple[str, Decimal, Decimal]], str]:
    """Parse a Wave TB CSV. Returns ([(account_name, debit, credit), ...], as_of_date)."""
    if path is None:
        path = _find_tb_csv()
    rows: list[tuple[str, Decimal, Decimal]] = []
    as_of = ""
    with open(path, encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        for r in reader:
            if not r:
                continue
            joined = ",".join(r)
            if joined.startswith("As of"):
                as_of = r[0].replace("As of ", "").strip()
            if len(r) < 4:
                continue
            account = r[1].strip()
            d_str = r[2].strip()
            c_str = r[3].strip()
            # Skip section headers, subtotals, and grand totals
            if not account:
                continue
            if account.startswith("Total ") or account in (
                "Assets", "Liabilities", "Equity", "Retained Earnings",
                "Cash and Bank", "Other Current Assets", "Long-term Assets",
                "Inventory", "Property, Plant, Equipment",
                "Current Liabilities", "Long-term Liabilities",
            ):
                continue
            # Both columns empty = section header
            if not d_str and not c_str:
                continue
            d = _money(d_str)
            c = _money(c_str)
            if d == 0 and c == 0:
                continue
            rows.append((account, d, c))
    return rows, as_of


def build_je_lines(wave_rows: list[tuple[str, Decimal, Decimal]]) -> tuple[list[JELine], list[str]]:
    """Translate Wave TB rows into JE lines via the WAVE_TO_QBO mapping.

    Returns (je_lines, warnings)."""
    lines: list[JELine] = []
    warnings: list[str] = []
    inventory_aggregate = Decimal("0")  # Combined inventory line accumulator

    for account, debit, credit in wave_rows:
        if account not in WAVE_TO_QBO:
            warnings.append(f"Wave account {account!r} not in WAVE_TO_QBO map — skipped")
            continue
        qbo_name = WAVE_TO_QBO[account]
        if qbo_name is None:
            continue  # Intentionally skipped

        if qbo_name == "Inventory - Apparel & Materials":
            # Aggregate all inventory contributions into one line
            inventory_aggregate += debit - credit
            continue

        line = JELine(
            qbo_account=qbo_name,
            debit=debit,
            credit=credit,
            description=f"From Wave: {account}",
        )
        lines.append(line)

    if inventory_aggregate != 0:
        if inventory_aggregate > 0:
            lines.append(JELine(
                qbo_account="Inventory - Apparel & Materials",
                debit=inventory_aggregate,
                description="Combined inventory opening balance",
            ))
        else:
            lines.append(JELine(
                qbo_account="Inventory - Apparel & Materials",
                credit=-inventory_aggregate,
                description="Combined inventory opening balance",
            ))

    return lines, warnings


def balance_to_opening_equity(lines: list[JELine]) -> JELine:
    """Add a balancing line to Opening Balance Equity. Returns the new line."""
    total_debit = sum((l.debit for l in lines), Decimal("0"))
    total_credit = sum((l.credit for l in lines), Decimal("0"))
    diff = total_debit - total_credit
    if diff == 0:
        return JELine(qbo_account="Opening Balance Equity", description="(no plug needed)")
    if diff > 0:
        # Debits exceed credits — credit OBE to balance
        return JELine(qbo_account="Opening Balance Equity", credit=diff, description="Cutover JE balancing entry")
    return JELine(qbo_account="Opening Balance Equity", debit=-diff, description="Cutover JE balancing entry")


def print_plan(lines: list[JELine], balancer: JELine, as_of: str, warnings: list[str]) -> None:
    print(f"\n=== Opening Balances JE plan (as of {as_of}) ===\n")
    print(f"{'ACCOUNT':45} {'DEBIT':>14} {'CREDIT':>14}")
    print("-" * 75)
    for l in lines:
        d = f"${l.debit:,.2f}" if l.debit else ""
        c = f"${l.credit:,.2f}" if l.credit else ""
        print(f"{l.qbo_account[:45]:45} {d:>14} {c:>14}")
    if balancer.amount > 0:
        d = f"${balancer.debit:,.2f}" if balancer.debit else ""
        c = f"${balancer.credit:,.2f}" if balancer.credit else ""
        print(f"{balancer.qbo_account[:45]:45} {d:>14} {c:>14}  ← plug")

    all_lines = lines + [balancer] if balancer.amount > 0 else lines
    td = sum((l.debit for l in all_lines), Decimal("0"))
    tc = sum((l.credit for l in all_lines), Decimal("0"))
    print("-" * 75)
    print(f"{'TOTAL':45} {f'${td:,.2f}':>14} {f'${tc:,.2f}':>14}  diff=${td-tc:,.2f}")
    if warnings:
        print(f"\nWarnings ({len(warnings)}):")
        for w in warnings:
            print(f"  - {w}")


def apply_plan(client: QBOClient, lines: list[JELine], balancer: JELine, as_of: str) -> None:
    accounts = {a["Name"]: a["Id"] for a in client.query("SELECT * FROM Account WHERE Active = true MAXRESULTS 1000")}
    # Opening Balance Equity is a system account that may not be in active list
    obe = client.find_by_name("Account", "Opening Balance Equity")
    if obe:
        accounts["Opening Balance Equity"] = obe["Id"]

    all_lines = lines + ([balancer] if balancer.amount > 0 else [])

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

    payload = {
        "TxnDate": as_of,
        "PrivateNote": f"Wave→QBO migration: opening balances at {as_of}",
        "Line": je_lines,
    }
    result = client.create("JournalEntry", payload)
    print(f"\n  Posted JournalEntry Id={result['Id']} TxnDate={as_of} with {len(je_lines)} lines")
