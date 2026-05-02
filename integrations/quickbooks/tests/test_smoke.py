"""Smoke test: verify token refresh + a basic API read against the live QBO company.

Run from the project root:
    .venv/bin/python -m tests.test_smoke
"""
import sys
import os

# Allow running from project root or from tests/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from qbo import QBOClient


def main() -> int:
    client = QBOClient()
    print(f"Realm ID: {client.realm_id}")
    print("Calling companyinfo...")
    info = client.company_info()
    print(f"  Company:        {info.get('CompanyName')}")
    print(f"  Legal name:     {info.get('LegalName')}")
    print(f"  Country:        {info.get('Country')}")
    print(f"  Fiscal start:   {info.get('FiscalYearStartMonth')}")
    print(f"  Started:        {info.get('CompanyStartDate')}")
    print()

    print("Querying existing entity counts...")
    for entity in ("Account", "Customer", "Item", "Vendor", "Invoice", "Bill", "JournalEntry"):
        rows = client.query(f"SELECT * FROM {entity} MAXRESULTS 1000")
        print(f"  {entity:15} {len(rows):>4}")

    print()
    print("Smoke test passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
