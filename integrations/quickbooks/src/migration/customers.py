"""Customer reconciler: diff target vs. live QBO, produce ops."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from qbo import QBOClient

from .customer_plan import CustomerSpec, build_customer_plan


@dataclass
class CustomerOp:
    op: str            # "create" | "keep" | "skip-system"
    spec: Optional[CustomerSpec]
    qbo_id: Optional[str] = None
    reason: str = ""

    def __str__(self) -> str:
        name = self.spec.display_name if self.spec else "?"
        parent = f"  (sub of {self.spec.parent_display_name})" if self.spec and self.spec.parent_display_name else ""
        idstr = f" Id={self.qbo_id}" if self.qbo_id else ""
        return f"  [{self.op.upper():12}] {name}{parent}{idstr}  {self.reason}"


def _norm(s: str) -> str:
    return s.strip().lower()


def plan_customers(client: QBOClient) -> list[CustomerOp]:
    target = build_customer_plan()
    existing = client.query("SELECT * FROM Customer MAXRESULTS 1000")
    by_norm = {_norm(c.get("DisplayName", "")): c for c in existing}

    ops: list[CustomerOp] = []
    target_norms: set[str] = set()
    for spec in target:
        target_norms.add(_norm(spec.display_name))
        match = by_norm.get(_norm(spec.display_name))
        if match:
            ops.append(CustomerOp(
                op="keep",
                spec=spec,
                qbo_id=match["Id"],
                reason="already exists",
            ))
        else:
            ops.append(CustomerOp(op="create", spec=spec))

    # Note any QBO customers that aren't in our plan (e.g., Sample Customer)
    for norm_name, c in by_norm.items():
        if norm_name in target_norms:
            continue
        # We deliberately keep Sample Customer (the $5 promo invoice references it)
        ops.append(CustomerOp(
            op="skip-system",
            spec=None,
            qbo_id=c["Id"],
            reason=f"Not in plan: {c.get('DisplayName')!r} — leaving alone (e.g., QBO Sample Customer)",
        ))

    return ops


def print_plan(ops: list[CustomerOp]) -> None:
    by_op: dict[str, list[CustomerOp]] = {}
    for o in ops:
        by_op.setdefault(o.op, []).append(o)

    print("\n=== Customers plan ===")
    for kind in ("create", "keep", "skip-system"):
        items = by_op.get(kind, [])
        if not items:
            continue
        print(f"\n{kind.upper()} ({len(items)}):")
        # Group by parent for cleaner display
        for o in items:
            print(o)

    print("\nSummary:")
    for kind in ("create", "keep", "skip-system"):
        print(f"  {kind:12}: {len(by_op.get(kind, []))}")
    print(f"  TOTAL ops:    {len(ops)}")


def apply_plan(client: QBOClient, ops: list[CustomerOp]) -> None:
    creates = [o for o in ops if o.op == "create"]
    print(f"\nApplying {len(creates)} customer creates...")

    # Build an in-flight map of {display_name: qbo_id} so subs can reference parents
    name_to_id: dict[str, str] = {}
    # Pre-populate with any existing keeps
    for o in ops:
        if o.op == "keep" and o.spec and o.qbo_id:
            name_to_id[o.spec.display_name] = o.qbo_id

    # Execute in spec order (parents first thanks to build_customer_plan ordering)
    for o in creates:
        assert o.spec is not None
        spec = o.spec

        payload: dict = {"DisplayName": spec.display_name}
        if spec.given_name:
            payload["GivenName"] = spec.given_name
        if spec.family_name:
            payload["FamilyName"] = spec.family_name
        if spec.email:
            payload["PrimaryEmailAddr"] = {"Address": spec.email}
        if spec.phone:
            payload["PrimaryPhone"] = {"FreeFormNumber": spec.phone}

        billing = {}
        if spec.address_line1:
            billing["Line1"] = spec.address_line1
        if spec.city:
            billing["City"] = spec.city
        if spec.state:
            billing["CountrySubDivisionCode"] = spec.state
        if spec.postal_code:
            billing["PostalCode"] = spec.postal_code
        if spec.country:
            billing["Country"] = spec.country
        if billing:
            payload["BillAddr"] = billing

        if spec.parent_display_name:
            parent_id = name_to_id.get(spec.parent_display_name)
            if parent_id is None:
                # Look it up live (in case the parent was a "keep")
                parent = client.find_by_name("Customer", spec.parent_display_name, "DisplayName")
                if parent is None:
                    print(f"  WARN: parent {spec.parent_display_name!r} not found for sub {spec.display_name!r}, creating as flat")
                else:
                    parent_id = parent["Id"]
            if parent_id:
                payload["ParentRef"] = {"value": parent_id}
                payload["Job"] = True

        result = client.create("Customer", payload)
        o.qbo_id = result["Id"]
        name_to_id[spec.display_name] = result["Id"]
        suffix = f" (sub of {spec.parent_display_name})" if spec.parent_display_name else ""
        print(f"  created {spec.display_name}{suffix} -> Id={result['Id']}")
