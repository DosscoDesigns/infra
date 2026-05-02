"""Chart of accounts reconciler.

Compares the target plan in account_plan.py against live QBO state and
produces a list of operations: CREATE, RENAME, INACTIVATE, KEEP."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from qbo import QBOClient

from .account_plan import ALL_TARGET_ACCOUNTS, AccountSpec, QBO_DEFAULTS_TO_LEAVE_ALONE


@dataclass
class AccountOp:
    op: str            # "create" | "rename" | "inactivate" | "keep" | "skip-default"
    name: str
    qbo_id: Optional[str] = None
    spec: Optional[AccountSpec] = None
    reason: str = ""

    def __str__(self) -> str:
        target = f" -> {self.spec.name}" if self.op == "rename" and self.spec else ""
        idstr = f" Id={self.qbo_id}" if self.qbo_id else ""
        return f"  [{self.op.upper():12}] {self.name}{target}{idstr}  {self.reason}"


def _norm(s: str) -> str:
    return s.strip().lower()


def plan_accounts(client: QBOClient) -> list[AccountOp]:
    """Inspect QBO live state, compare to target, return ordered ops."""
    existing = client.query("SELECT * FROM Account MAXRESULTS 1000")
    by_norm_name: dict[str, list[dict]] = {}
    for a in existing:
        by_norm_name.setdefault(_norm(a.get("Name", "")), []).append(a)

    ops: list[AccountOp] = []
    target_names_norm = {_norm(s.name) for s in ALL_TARGET_ACCOUNTS}

    # Pass 1: for each target, decide create / keep / rename
    for spec in ALL_TARGET_ACCOUNTS:
        matches = by_norm_name.get(_norm(spec.name), [])
        if matches:
            # Pick the active one if multiple
            chosen = next((m for m in matches if m.get("Active")), matches[0])
            ops.append(AccountOp(
                op="keep",
                name=spec.name,
                qbo_id=chosen["Id"],
                spec=spec,
                reason=f"already exists (Id={chosen['Id']}, type={chosen.get('AccountType')})",
            ))
            continue
        ops.append(AccountOp(op="create", name=spec.name, spec=spec))

    # Pass 2: for each existing account NOT in target, decide what to do
    target_names = {_norm(s.name) for s in ALL_TARGET_ACCOUNTS}
    for norm_name, matches in by_norm_name.items():
        if norm_name in target_names:
            continue
        for a in matches:
            name = a.get("Name", "")
            if norm_name in QBO_DEFAULTS_TO_LEAVE_ALONE:
                ops.append(AccountOp(
                    op="skip-default",
                    name=name,
                    qbo_id=a["Id"],
                    reason="QBO system account, cannot inactivate",
                ))
                continue

            # Safety: never auto-inactivate Bank or Credit Card accounts.
            # These are typically bank-feed connected; inactivating breaks the feed.
            if a.get("AccountType") in ("Bank", "Credit Card"):
                ops.append(AccountOp(
                    op="skip-default",
                    name=name,
                    qbo_id=a["Id"],
                    reason=(
                        f"{a.get('AccountType')} account — likely bank-feed connected. "
                        "Manual decision required: keep, or disconnect feed first then inactivate via UI."
                    ),
                ))
                continue

            # Anything else QBO seeded — inactivate
            if a.get("Active"):
                ops.append(AccountOp(
                    op="inactivate",
                    name=name,
                    qbo_id=a["Id"],
                    reason=f"QBO default ({a.get('AccountType')}/{a.get('AccountSubType')}), not in our target chart",
                ))

    return ops


def print_plan(ops: list[AccountOp]) -> None:
    by_op: dict[str, list[AccountOp]] = {}
    for o in ops:
        by_op.setdefault(o.op, []).append(o)

    print("\n=== Chart of Accounts plan ===")
    for op_kind in ("create", "rename", "keep", "inactivate", "skip-default"):
        items = by_op.get(op_kind, [])
        if not items:
            continue
        print(f"\n{op_kind.upper()} ({len(items)}):")
        for o in items:
            print(o)

    print("\nSummary:")
    for op_kind in ("create", "rename", "keep", "inactivate", "skip-default"):
        print(f"  {op_kind:12}: {len(by_op.get(op_kind, []))}")
    print(f"  TOTAL ops:    {len(ops)}")


def apply_plan(client: QBOClient, ops: list[AccountOp]) -> None:
    """Execute operations against QBO. Order: creates → renames → inactivates."""
    creates = [o for o in ops if o.op == "create"]
    inactivates = [o for o in ops if o.op == "inactivate"]
    renames = [o for o in ops if o.op == "rename"]

    print(f"\nApplying {len(creates)} creates, {len(renames)} renames, {len(inactivates)} inactivates...")

    failures: list[tuple[str, Exception]] = []
    for o in creates:
        assert o.spec is not None
        payload: dict = {
            "Name": o.spec.name,
            "AccountType": o.spec.account_type,
            "AccountSubType": o.spec.account_sub_type,
        }
        if o.spec.description:
            # QBO caps Description at 100 chars
            payload["Description"] = o.spec.description[:100]
        try:
            result = client.create("Account", payload)
        except Exception as exc:
            print(f"  FAILED create {o.spec.name}: {exc}")
            failures.append((o.spec.name, exc))
            continue
        o.qbo_id = result["Id"]
        print(f"  created {o.spec.name} -> Id={o.qbo_id}")
    if failures:
        print(f"\n  {len(failures)} create(s) failed — see above")

    for o in renames:
        # Sparse update: needs Id + SyncToken + new Name
        existing = client.query(f"SELECT * FROM Account WHERE Id = '{o.qbo_id}'")[0]
        payload = {
            "Id": o.qbo_id,
            "SyncToken": existing["SyncToken"],
            "Name": o.spec.name if o.spec else o.name,
            "sparse": True,
        }
        client.update("Account", payload)
        print(f"  renamed Id={o.qbo_id} -> {payload['Name']}")

    inactivate_failures: list[tuple[str, Exception]] = []
    for o in inactivates:
        try:
            existing = client.query(f"SELECT * FROM Account WHERE Id = '{o.qbo_id}'")[0]
            payload = {
                "Id": o.qbo_id,
                "SyncToken": existing["SyncToken"],
                "Name": existing["Name"],
                "Active": False,
                "sparse": True,
            }
            client.update("Account", payload)
            print(f"  inactivated Id={o.qbo_id} ({o.name})")
        except Exception as exc:
            print(f"  FAILED inactivate Id={o.qbo_id} ({o.name}): {exc}")
            inactivate_failures.append((o.name, exc))
    if inactivate_failures:
        print(f"\n  {len(inactivate_failures)} inactivate(s) failed — see above")
