"""List register transactions with NO bank-feed match (uncleared).

When a downloaded bank/card transaction is matched or added in the Banking UI,
QBO stamps the linked transaction Cleared (C); reconciling stamps it R. A
manual entry that no feed line has ever confirmed stays blank ("Uncleared").
Those are the phantoms/laggards: entered in QBO but not (yet) seen at the bank
— e.g. the 24HW order booked at its email total when the card was charged
less, or an anticipated refund that hasn't posted.

Uses the TransactionList report API (cleared status is not exposed on
Purchase objects in the v3 API). Note: the report replica can lag writes by a
few minutes, and brand-new entries legitimately show Uncleared until the feed
catches up — recent rows are usually fine, OLD rows are the smell.

Usage:
    python -m bookkeeping.list_uncleared                     # last 90 days, all accounts
    python -m bookkeeping.list_uncleared --account 1005      # Amex 1005 only
    python -m bookkeeping.list_uncleared --start 2026-06-01 --account SanMar
"""
from __future__ import annotations

import argparse
from datetime import date, timedelta

from qbo import QBOClient


def walk(rows: dict):
    for r in rows.get("Row", []):
        if r.get("Rows"):
            yield from walk(r["Rows"])
        if r.get("ColData"):
            yield [cd.get("value", "") for cd in r["ColData"]]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start", default=str(date.today() - timedelta(days=90)))
    ap.add_argument("--end", default=str(date.today()))
    ap.add_argument("--account", default=None,
                    help="substring filter on the register account name, e.g. '1005'")
    args = ap.parse_args()

    c = QBOClient()
    body = c._request("GET", "reports/TransactionList", params={
        "start_date": args.start,
        "end_date": args.end,
        "cleared": "Uncleared",
        "columns": "tx_date,txn_type,doc_num,name,memo,account_name,subt_nat_amount",
    })

    rows = [v for v in walk(body.get("Rows", {}))]
    if args.account:
        rows = [v for v in rows if args.account.lower() in v[5].lower()]

    if not rows:
        print(f"No uncleared transactions {args.start}..{args.end}"
              + (f" on '{args.account}'" if args.account else ""))
        return

    print(f"Uncleared (no bank-feed match) {args.start}..{args.end}"
          + (f" on '{args.account}'" if args.account else "") + ":\n")
    total = 0.0
    for d, ttype, num, name, memo, acct, amt in rows:
        total += float(amt or 0)
        print(f"  {d}  {ttype:<20} {amt:>10}  {name:<28} {acct:<18} "
              f"{(num or memo)[:40]}")
    print(f"\n  {len(rows)} transactions, net {total:,.2f}")


if __name__ == "__main__":
    main()
