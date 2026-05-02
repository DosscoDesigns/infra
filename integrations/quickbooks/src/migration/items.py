"""Item reconciler: diff target vs. live QBO, produce ops."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from qbo import QBOClient

from .item_plan import ITEMS, ItemSpec


@dataclass
class ItemOp:
    op: str           # "create" | "keep" | "skip-system"
    spec: Optional[ItemSpec]
    qbo_id: Optional[str] = None
    reason: str = ""

    def __str__(self) -> str:
        name = self.spec.name if self.spec else "?"
        idstr = f" Id={self.qbo_id}" if self.qbo_id else ""
        type_str = f" [{self.spec.item_type}]" if self.spec else ""
        return f"  [{self.op.upper():12}] {name}{type_str}{idstr}  {self.reason}"


def _norm(s: str) -> str:
    return s.strip().lower()


def _build_account_lookup(client: QBOClient) -> dict[str, str]:
    """Map account name -> Id, for active accounts only."""
    out: dict[str, str] = {}
    for a in client.query("SELECT * FROM Account WHERE Active = true MAXRESULTS 1000"):
        out[a.get("Name", "")] = a["Id"]
    return out


def plan_items(client: QBOClient) -> list[ItemOp]:
    existing = client.query("SELECT * FROM Item MAXRESULTS 1000")
    by_norm = {_norm(i.get("Name", "")): i for i in existing}

    ops: list[ItemOp] = []
    target_norms: set[str] = set()
    for spec in ITEMS:
        target_norms.add(_norm(spec.name))
        match = by_norm.get(_norm(spec.name))
        if match:
            ops.append(ItemOp(op="keep", spec=spec, qbo_id=match["Id"], reason="already exists"))
        else:
            ops.append(ItemOp(op="create", spec=spec))

    for norm_name, i in by_norm.items():
        if norm_name in target_norms:
            continue
        ops.append(ItemOp(
            op="skip-system",
            spec=None,
            qbo_id=i["Id"],
            reason=f"Not in plan: {i.get('Name')!r} — leaving alone (e.g., QBO sample 'Services')",
        ))
    return ops


def print_plan(ops: list[ItemOp]) -> None:
    by_op: dict[str, list[ItemOp]] = {}
    for o in ops:
        by_op.setdefault(o.op, []).append(o)
    print("\n=== Items plan ===")
    for kind in ("create", "keep", "skip-system"):
        items = by_op.get(kind, [])
        if not items:
            continue
        print(f"\n{kind.upper()} ({len(items)}):")
        for o in items:
            print(o)
    print("\nSummary:")
    for kind in ("create", "keep", "skip-system"):
        print(f"  {kind:12}: {len(by_op.get(kind, []))}")
    print(f"  TOTAL ops:    {len(ops)}")


def apply_plan(client: QBOClient, ops: list[ItemOp]) -> None:
    creates = [o for o in ops if o.op == "create"]
    if not creates:
        print("\nNo items to create.")
        return

    print(f"\nApplying {len(creates)} item creates...")
    accounts = _build_account_lookup(client)

    failures: list[tuple[str, Exception]] = []
    for o in creates:
        spec = o.spec
        assert spec is not None
        income_id = accounts.get(spec.income_account)
        if not income_id:
            print(f"  FAILED {spec.name}: income account {spec.income_account!r} not found")
            failures.append((spec.name, RuntimeError(f"missing income account {spec.income_account!r}")))
            continue

        payload: dict = {
            "Name": spec.name,
            "Type": spec.item_type,
            "IncomeAccountRef": {"value": income_id},
            "Taxable": spec.taxable,
        }
        if spec.description:
            payload["Description"] = spec.description[:4000]  # QBO Item description limit
        if spec.unit_price is not None:
            payload["UnitPrice"] = spec.unit_price
        if spec.expense_account:
            exp_id = accounts.get(spec.expense_account)
            if exp_id:
                payload["ExpenseAccountRef"] = {"value": exp_id}
            else:
                print(f"  WARN: expense account {spec.expense_account!r} not found for {spec.name} — skipping expense link")

        try:
            result = client.create("Item", payload)
        except Exception as exc:
            print(f"  FAILED create {spec.name}: {exc}")
            failures.append((spec.name, exc))
            continue
        o.qbo_id = result["Id"]
        tax_marker = " [TAX]" if spec.taxable else ""
        print(f"  created {spec.name}{tax_marker} -> Id={o.qbo_id}")

    if failures:
        print(f"\n  {len(failures)} create(s) failed")
