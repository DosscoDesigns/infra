"""One-shot: dump existing QBO state so we can see what defaults shipped."""
import json
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from qbo import QBOClient


def main() -> int:
    c = QBOClient()
    accounts = c.query("SELECT * FROM Account MAXRESULTS 1000")
    print(f"=== Accounts: {len(accounts)} ===")
    by_type = {}
    for a in accounts:
        key = f"{a.get('AccountType')} / {a.get('AccountSubType', '')}"
        by_type.setdefault(key, []).append(a)
    for typ in sorted(by_type):
        print(f"\n{typ}")
        for a in sorted(by_type[typ], key=lambda x: x.get("Name", "")):
            active = "" if a.get("Active") else " [INACTIVE]"
            classif = a.get("Classification", "")
            cur = a.get("CurrentBalance", 0)
            print(f"  {a['Name']:<55} bal={cur:>10}  cls={classif}{active}")

    print(f"\n=== Customers ===")
    for c_ in c.query("SELECT * FROM Customer MAXRESULTS 100"):
        print(f"  Id={c_.get('Id')} Name={c_.get('DisplayName')!r} Active={c_.get('Active')}")

    print(f"\n=== Items ===")
    for i in c.query("SELECT * FROM Item MAXRESULTS 100"):
        print(f"  Id={i.get('Id')} Name={i.get('Name')!r} Type={i.get('Type')} Active={i.get('Active')}")

    print(f"\n=== Invoices ===")
    for inv in c.query("SELECT * FROM Invoice MAXRESULTS 100"):
        print(f"  Id={inv.get('Id')} DocNumber={inv.get('DocNumber')!r} Total={inv.get('TotalAmt')} CustomerRef={inv.get('CustomerRef', {}).get('name')}")

    print(f"\n=== Vendors ===")
    for v in c.query("SELECT * FROM Vendor MAXRESULTS 100"):
        print(f"  Id={v.get('Id')} Name={v.get('DisplayName')!r}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
