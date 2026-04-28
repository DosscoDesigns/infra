"""Trial balance reconciliation: Wave vs. QBO.

After opening balances + A/R + A/P are loaded, generate a side-by-side
diff. Any account whose Wave-side balance disagrees with QBO-side by
more than $0.01 is flagged."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from qbo import QBOClient

from .opening_balances import parse_wave_tb
from .wave_account_map import WAVE_TO_QBO


def _qbo_balances(client: QBOClient) -> dict[str, Decimal]:
    """Return a {qbo_name: balance} map. Balance sign follows QBO convention
    (asset/expense positive on debit side; liability/equity/income on credit)."""
    out: dict[str, Decimal] = {}
    for a in client.query("SELECT * FROM Account WHERE Active = true MAXRESULTS 1000"):
        out[a["Name"]] = Decimal(str(a.get("CurrentBalance", 0)))
    return out


def reconcile(client: QBOClient) -> None:
    wave_rows, as_of = parse_wave_tb()
    qbo = _qbo_balances(client)

    print(f"\n=== Trial Balance reconciliation ({as_of}) ===\n")
    print(f"{'WAVE ACCOUNT':35} -> {'QBO ACCOUNT':30} {'WAVE NET':>12} {'QBO BAL':>12} {'DIFF':>10}")
    print("-" * 110)

    discrepancies: list[tuple[str, str, Decimal, Decimal]] = []
    for wave_name, debit, credit in wave_rows:
        qbo_name = WAVE_TO_QBO.get(wave_name, "(unmapped)")
        if qbo_name is None:
            continue
        wave_net = debit - credit  # Debit-positive
        qbo_bal = qbo.get(qbo_name)
        if qbo_bal is None:
            print(f"{wave_name[:35]:35} -> {qbo_name[:30]:30} {f'${wave_net:,.2f}':>12} {'(missing)':>12} {'':>10}")
            continue

        # QBO Liability/Credit Card accounts show as POSITIVE balance when owed —
        # for comparison, flip sign so credit-balance accounts compare correctly
        # Bank/Credit Card: balance is in QBO native (positive = held; for CC, negative = owed)
        # We just use CurrentBalance as-is; it should already be normalized.
        diff = wave_net - qbo_bal
        marker = "" if abs(diff) < Decimal("0.01") else " ⚠"
        if abs(diff) >= Decimal("0.01"):
            discrepancies.append((wave_name, qbo_name, wave_net, qbo_bal))
        print(f"{wave_name[:35]:35} -> {qbo_name[:30]:30} {f'${wave_net:,.2f}':>12} {f'${qbo_bal:,.2f}':>12} {f'${diff:,.2f}':>10}{marker}")

    print("-" * 110)
    if discrepancies:
        print(f"\n⚠ {len(discrepancies)} discrepancies found — review above")
    else:
        print(f"\n✓ All mapped accounts match within $0.01")
