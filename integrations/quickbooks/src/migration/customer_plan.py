"""Customer migration plan: dedupes + sub-customer hierarchy per AUDIT.md §6.

Loads Wave's `DD - customers.csv`, applies dedupe merges, and assigns
parent/sub relationships. Resulting plan is consumed by customers.py."""
from __future__ import annotations

import csv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

WAVE_EXPORT_DIR = Path(__file__).resolve().parents[4] / "TEMP" / "wave-export"
WAVE_CUSTOMERS_CSV = WAVE_EXPORT_DIR / "DD - customers.csv"


@dataclass
class CustomerSpec:
    display_name: str            # QBO DisplayName (must be unique across all)
    given_name: str = ""
    family_name: str = ""
    email: str = ""
    phone: str = ""
    address_line1: str = ""
    city: str = ""
    state: str = ""
    postal_code: str = ""
    country: str = ""
    parent_display_name: Optional[str] = None  # For sub-customers
    notes: str = ""


# === Dedupe rules (per AUDIT.md §6) ===
# Maps Wave display names that should be DROPPED (merged into the canonical
# entry). The canonical (kept) entry is the value.
DEDUPE_MAP: dict[str, str] = {
    # Two Nathan Freeman records — same person, same phone. Keep the one with
    # the RCC email as the canonical record (it's also the RCC-staff one).
    # The Wave file has two rows literally both named "Nathan Freeman".
    # In Wave-export order, row 47 is the bellsouth.net email, row 48 the RCC.
    # We disambiguate by email when reading.
    # Special handling in code below.

    # Apostrophe variant — "Rene’ Smith" (curly U+2019) merges into "Rene Smith"
    "Rene\u2019 Smith": "Rene Smith",

    # Cape Web + Jason Michaud share capewebit@gmail.com — Cape Web is the company
    # canonical record; drop the personal "Jason Michaud" record.
    "Jason Michaud": "Cape Web",
}

# Customers to drop entirely (one side of a duplicate identified by email)
EMAILS_TO_DROP_FOR_NATHAN = {"nathanfreeman@bellsouth.net"}


# === Parent/sub-customer hierarchy ===
# Parents must be created before subs.
PARENTS: list[str] = [
    "River Christian Church",
    "SJCA",
]

# Maps sub-customer display name -> parent display name
SUB_CUSTOMER_PARENT: dict[str, str] = {
    # River Christian Church staff
    "Anthony Favors": "River Christian Church",
    "Cathy Reigner": "River Christian Church",
    "Nathan Freeman": "River Christian Church",   # The RCC one (after dedupe)
    "Trav Eslinger": "River Christian Church",
    "River Preschool": "River Christian Church",  # entity sub, not person
    # SJCA staff/groups
    "Heather Davis": "SJCA",
    "Megan Cutlip": "SJCA",
    "SJCA Lions Council": "SJCA",
}


def _norm_phone(p: str) -> str:
    """Strip everything but digits."""
    return "".join(ch for ch in p if ch.isdigit())


def load_wave_customers() -> list[dict]:
    """Read Wave customers CSV, return list of raw row dicts."""
    rows = []
    with open(WAVE_CUSTOMERS_CSV, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def build_customer_plan() -> list[CustomerSpec]:
    """Apply dedupes + hierarchy to produce a clean customer plan.

    Order of returned specs is important: parents first, then subs, then flat.
    """
    raw = load_wave_customers()
    specs: list[CustomerSpec] = []
    seen_display_names: set[str] = set()

    def _spec_from_row(row: dict, *, parent: Optional[str] = None) -> CustomerSpec:
        return CustomerSpec(
            display_name=row["Customer Name"].strip(),
            given_name=row.get("First Name", "").strip(),
            family_name=row.get("Last Name", "").strip(),
            email=row.get("Email", "").strip(),
            phone=row.get("Phone", "").strip() or row.get("Mobile", "").strip(),
            address_line1=row.get("Address Line 1", "").strip(),
            city=row.get("City", "").strip(),
            state=row.get("Province Name", "").strip(),
            postal_code=row.get("Postal Code", "").strip(),
            country=row.get("Country Name", "").strip(),
            parent_display_name=parent,
        )

    # Pass 1: drop the dedupe-target rows (the side being merged AWAY)
    filtered: list[dict] = []
    for row in raw:
        name = row["Customer Name"].strip()
        email = row.get("Email", "").strip().lower()

        # Skip the Nathan Freeman with bellsouth email (keeping the RCC one)
        if name == "Nathan Freeman" and email in EMAILS_TO_DROP_FOR_NATHAN:
            continue
        # Skip rows whose display name is a dedupe-target
        if name in DEDUPE_MAP:
            continue

        filtered.append(row)

    # Pass 2: build parent customers FIRST so they exist before subs
    parent_rows = [r for r in filtered if r["Customer Name"].strip() in PARENTS]
    for row in parent_rows:
        spec = _spec_from_row(row)
        specs.append(spec)
        seen_display_names.add(spec.display_name)

    # Pass 3: sub-customers
    sub_rows = [r for r in filtered if r["Customer Name"].strip() in SUB_CUSTOMER_PARENT]
    for row in sub_rows:
        name = row["Customer Name"].strip()
        spec = _spec_from_row(row, parent=SUB_CUSTOMER_PARENT[name])
        specs.append(spec)
        seen_display_names.add(spec.display_name)

    # Pass 4: everyone else (flat)
    for row in filtered:
        name = row["Customer Name"].strip()
        if name in seen_display_names:
            continue
        if name in PARENTS or name in SUB_CUSTOMER_PARENT:
            continue
        spec = _spec_from_row(row)
        specs.append(spec)
        seen_display_names.add(name)

    return specs
