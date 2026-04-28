"""Items migration plan: map Wave products to QBO Service/NonInventory items.

Per AUDIT.md §5, all items are Service or NonInventory — no QBO inventory
tracking. Income/expense accounts reference our new chart of accounts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ItemSpec:
    name: str
    item_type: str           # "Service" or "NonInventory"
    income_account: str      # Name of QBO income account
    expense_account: Optional[str] = None  # Name of QBO expense account (only if Type=NonInventory or has cost tracking)
    description: str = ""
    unit_price: Optional[float] = None
    taxable: bool = False    # Apply FL Clay County 7.5% tax


# All items active enough to be worth keeping post-migration, mapped to new QBO accounts
ITEMS: list[ItemSpec] = [
    # --- Apparel (primary revenue) ---
    ItemSpec("Custom Apparel", "NonInventory",
             income_account="Sales - Apparel",
             expense_account="Shirts",
             description="Custom decorated apparel — shirts/garments with screen print, embroidery, or transfer",
             unit_price=10.50,
             taxable=True),
    ItemSpec("Custom Apparel - Youth", "NonInventory",
             income_account="Sales - Apparel",
             expense_account="Shirts",
             description="Custom decorated youth apparel",
             unit_price=9.50,
             taxable=True),

    # --- Marketing Materials ---
    ItemSpec("Custom Marketing Materials", "NonInventory",
             income_account="Sales - Marketing Materials",
             expense_account="Marketing Materials - Resale",
             description="Stickers, banners, flyers, promotional printed items",
             unit_price=0,
             taxable=True),

    # --- Web/Hosting ---
    ItemSpec("Basic Hosting", "Service",
             income_account="Sales - Web/Hosting",
             description="Basic website hosting, domain registration, and maintenance",
             unit_price=75),
    ItemSpec("Basic Hosting - Non Profit", "Service",
             income_account="Sales - Web/Hosting",
             description="Basic website hosting and maintenance for non-profit organizations",
             unit_price=75),
    ItemSpec("Basic Website Design", "Service",
             income_account="Sales - Web/Hosting",
             description="Website planning, design, and migration for new clients",
             unit_price=599),
    ItemSpec("Google Workspace Setup - Non-Profit", "Service",
             income_account="Sales - Web/Hosting",
             description="Google Workspace setup for non-profit organizations",
             unit_price=100),
    ItemSpec("Basic Email Account", "Service",
             income_account="Sales - Web/Hosting",
             expense_account="Subscriptions",
             description="Basic email account with 5GB storage. IMAP/POP and calendar.",
             unit_price=2),
    ItemSpec("Advanced Email Account", "Service",
             income_account="Sales - Web/Hosting",
             expense_account="Subscriptions",
             description="Advanced email account with 50GB storage",
             unit_price=5),
    ItemSpec("Wordpress Plugin - WP Forms", "Service",
             income_account="Sales - Web/Hosting",
             expense_account="Plugins / Software for Resale",
             description="Wordpress plugin for advanced styling and form processing",
             unit_price=12),
    ItemSpec("Embroidery Digitizing", "Service",
             income_account="Sales - Web/Hosting",
             expense_account="Embroidery Digitizing",
             description="Digitizing fees for embroidery designs"),

    # --- Design / Other Services ---
    ItemSpec("Design Fee", "Service",
             income_account="Sales - Design/Other",
             description="Custom design work fee",
             unit_price=30),
    ItemSpec("Engraving", "Service",
             income_account="Sales - Design/Other",
             description="Engraving on customer-supplied items"),
    ItemSpec("Laser Engraving", "Service",
             income_account="Sales - Design/Other",
             description="Laser engraving (e.g., wood discs)",
             unit_price=10),

    # --- Imprint placement tiers (sold per shirt) ---
    ItemSpec("Imprint Placement (<24)", "Service",
             income_account="Sales - Apparel",
             description="Additional placement on small runs (<24 pieces)",
             unit_price=9, taxable=True),
    ItemSpec("Imprint Placement (25-49)", "Service",
             income_account="Sales - Apparel",
             description="Additional placement on 25-49 piece runs",
             unit_price=5, taxable=True),
    ItemSpec("Imprint Placement (50-74)", "Service",
             income_account="Sales - Apparel",
             description="Additional placement on 50-74 piece runs",
             unit_price=3.25, taxable=True),
    ItemSpec("Imprint Placement (75-99)", "Service",
             income_account="Sales - Apparel",
             description="Additional placement on 75-99 piece runs",
             unit_price=2.75, taxable=True),
    ItemSpec("Imprint Placement (100+)", "Service",
             income_account="Sales - Apparel",
             description="Additional placement on 100+ piece runs",
             unit_price=1.5, taxable=True),

    # --- Other apparel-side items ---
    ItemSpec("Vinyl", "NonInventory",
             income_account="Sales - Apparel",
             expense_account="Vinyl Supplies",
             description="Vinyl per square foot",
             unit_price=2, taxable=True),
    ItemSpec("Screen Print - Screens", "NonInventory",
             income_account="Sales - Apparel",
             expense_account="Screen Print",
             description="Screen-print screens (charged when new screens needed)",
             unit_price=20, taxable=True),
    ItemSpec("Shipping", "Service",
             income_account="Sales - Apparel",
             description="Estimated shipping (replace with actual at fulfillment)",
             unit_price=30),
    ItemSpec("Card Processing Fee", "Service",
             income_account="Sales - Apparel",
             description="2.9% + $0.30 processing fee passed to customer",
             unit_price=87),

    # --- Slime Co ---
    ItemSpec("Slime", "NonInventory",
             income_account="Sales - Slime Co",
             description="Slime kit",
             unit_price=14, taxable=True),
]
