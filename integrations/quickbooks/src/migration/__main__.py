"""Migration CLI orchestrator.

Usage:
    python -m migration --dry-run --step accounts
    python -m migration --dry-run --all
    python -m migration --apply --step accounts
"""
from __future__ import annotations

import argparse
import sys

from qbo import QBOClient

from . import accounts, ar_ap, customers, items, opening_balances, reconcile, wizard_cleanup


STEPS = ["wizard-cleanup", "accounts", "customers", "items", "opening-balances", "ar-ap", "reconcile"]


def step_wizard_cleanup(client: QBOClient, *, apply: bool) -> int:
    ops = wizard_cleanup.find_wizard_entries(client)
    wizard_cleanup.print_plan(ops)
    if apply:
        wizard_cleanup.apply_plan(client, ops)
    return 0


def step_accounts(client: QBOClient, *, apply: bool) -> int:
    ops = accounts.plan_accounts(client)
    accounts.print_plan(ops)
    if apply:
        accounts.apply_plan(client, ops)
    return 0


def step_customers(client: QBOClient, *, apply: bool) -> int:
    ops = customers.plan_customers(client)
    customers.print_plan(ops)
    if apply:
        customers.apply_plan(client, ops)
    return 0


def step_items(client: QBOClient, *, apply: bool) -> int:
    ops = items.plan_items(client)
    items.print_plan(ops)
    if apply:
        items.apply_plan(client, ops)
    return 0


def step_opening_balances(client: QBOClient, *, apply: bool) -> int:
    rows, as_of = opening_balances.parse_wave_tb()
    lines, warnings = opening_balances.build_je_lines(rows)
    balancer = opening_balances.balance_to_opening_equity(lines)
    opening_balances.print_plan(lines, balancer, as_of, warnings)
    if apply:
        opening_balances.apply_plan(client, lines, balancer, as_of)
    return 0


def step_ar_ap(client: QBOClient, *, apply: bool) -> int:
    invoices = ar_ap.plan_open_ar(client)
    bills = ar_ap.plan_open_ap(client)
    ar_ap.print_plan(invoices, bills)
    if apply:
        ar_ap.apply_ar(client, invoices)
        ar_ap.apply_ap(client, bills)
    return 0


def step_reconcile(client: QBOClient, *, apply: bool) -> int:
    reconcile.reconcile(client)
    return 0


STEP_DISPATCH = {
    "wizard-cleanup": step_wizard_cleanup,
    "accounts": step_accounts,
    "customers": step_customers,
    "items": step_items,
    "opening-balances": step_opening_balances,
    "ar-ap": step_ar_ap,
    "reconcile": step_reconcile,
}


def main() -> int:
    parser = argparse.ArgumentParser(prog="migration")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--dry-run", action="store_true", help="Print plan only, no writes")
    mode.add_argument("--apply", action="store_true", help="Execute the plan against QBO")
    parser.add_argument("--step", choices=STEPS, help="Run a single step")
    parser.add_argument("--all", action="store_true", help="Run all steps in order")
    args = parser.parse_args()

    if not args.step and not args.all:
        parser.error("must specify --step <name> or --all")

    client = QBOClient()
    info = client.company_info()
    print(f"QBO company: {info.get('CompanyName')} (Realm {client.realm_id})")
    print(f"Mode: {'APPLY' if args.apply else 'DRY-RUN'}")

    steps = STEPS if args.all else [args.step]
    for step in steps:
        fn = STEP_DISPATCH.get(step)
        if fn is None:
            print(f"  [{step}] not yet implemented — skipping")
            continue
        print(f"\n{'='*60}\nStep: {step}\n{'='*60}")
        rc = fn(client, apply=args.apply)
        if rc != 0:
            return rc

    return 0


if __name__ == "__main__":
    sys.exit(main())
