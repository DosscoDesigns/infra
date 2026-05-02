"""Option B trial balance reconciliation: Wave 4/30 vs QBO 4/30.

Pulls QBO's actual TrialBalance report (not CurrentBalance fields, which
miss P&L) and compares against Wave's 4/30 TB after applying the same
account mapping used by option_b.py.

Run from src/:
    python -m migration.reconcile_b
"""
from __future__ import annotations

from decimal import Decimal

from qbo import QBOClient

from .option_b import find_tb, parse_tb, WAVE_BS_TO_QBO, WAVE_PL_TO_QBO


def fetch_qbo_tb(client: QBOClient, as_of: str) -> dict[str, Decimal]:
    r = client._request("GET", "reports/TrialBalance",
                       params={"start_date": as_of, "end_date": as_of,
                               "accounting_method": "Accrual"})
    rows = r.get("Rows", {}).get("Row", [])
    out: dict[str, Decimal] = {}
    for row in rows:
        cols = row.get("ColData", [])
        if len(cols) < 3:
            continue
        name = cols[0].get("value", "")
        if not name or name.startswith("TOTAL"):
            continue
        d = Decimal(cols[1].get("value", "") or "0")
        c = Decimal(cols[2].get("value", "") or "0")
        out[name] = d - c  # debit-positive net
    return out


def main() -> int:
    client = QBOClient()

    # Wave side
    tb_path = find_tb("2026-04-30")
    wave_rows, _ = parse_tb(tb_path)
    print(f"Wave TB:  {tb_path.name}\n")

    # Aggregate Wave by QBO account name
    wave_by_qbo: dict[str, Decimal] = {}
    inventory_aggregate = Decimal("0")
    skipped: list[str] = []
    unmapped: list[tuple[str, Decimal]] = []

    for wave_name, (d, c) in wave_rows.items():
        net = d - c
        if wave_name in WAVE_BS_TO_QBO:
            qbo = WAVE_BS_TO_QBO[wave_name]
        elif wave_name in WAVE_PL_TO_QBO:
            qbo = WAVE_PL_TO_QBO[wave_name]
        else:
            unmapped.append((wave_name, net))
            continue

        if qbo is None:
            skipped.append(f"{wave_name} (${net:,.2f})")
            continue

        if qbo == "Inventory - Apparel & Materials":
            inventory_aggregate += net
            wave_by_qbo[qbo] = wave_by_qbo.get(qbo, Decimal("0")) + net
            continue

        wave_by_qbo[qbo] = wave_by_qbo.get(qbo, Decimal("0")) + net

    # QBO side
    qbo_tb = fetch_qbo_tb(client, "2026-04-30")

    print(f"=== Trial Balance Reconciliation @ 2026-04-30 ===\n")
    print(f"{'QBO Account':45} {'Wave Net':>12} {'QBO Net':>12} {'Diff':>12}")
    print("-" * 90)

    discrepancies = []
    all_qbo_names = set(wave_by_qbo) | set(qbo_tb)
    for qbo_name in sorted(all_qbo_names):
        wave_net = wave_by_qbo.get(qbo_name)
        qbo_net = qbo_tb.get(qbo_name)
        if wave_net is None:
            wave_str = "(missing)"
            wave_val = Decimal("0")
        else:
            wave_val = wave_net
            wave_str = f"${wave_net:,.2f}"
        if qbo_net is None:
            qbo_str = "(missing)"
            qbo_val = Decimal("0")
        else:
            qbo_val = qbo_net
            qbo_str = f"${qbo_net:,.2f}"
        diff = wave_val - qbo_val
        marker = "" if abs(diff) < Decimal("0.01") else "  ⚠"
        if abs(diff) >= Decimal("0.01"):
            discrepancies.append((qbo_name, wave_val, qbo_val, diff))
        print(f"{qbo_name[:45]:45} {wave_str:>12} {qbo_str:>12} {f'${diff:,.2f}':>12}{marker}")

    print("-" * 90)
    print(f"\nSkipped (intentionally): {len(skipped)}")
    for s in skipped:
        print(f"  - {s}")
    print(f"\nUnmapped Wave accounts: {len(unmapped)}")
    for n, v in unmapped:
        print(f"  - {n}: ${v:,.2f}")
    print(f"\nDiscrepancies (>$0.01): {len(discrepancies)}")
    if discrepancies:
        total = sum(d[3] for d in discrepancies)
        print(f"  Total absolute diff: ${sum(abs(d[3]) for d in discrepancies):,.2f}")
        print(f"  Net diff:            ${total:,.2f}")

    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
