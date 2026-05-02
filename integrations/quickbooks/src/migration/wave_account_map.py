"""Wave account name -> QBO account name mapping.

Used by opening_balances.py to translate Wave's trial balance lines to
the new QBO chart of accounts. Lines marked None are intentionally skipped:
- AR and AP go through open-invoice/open-bill creation, not the JE
- QBO system-managed accounts (Sales Tax Liability, Retained Earnings) get
  handled by QBO automation, not by us
- Wave-internal clearing accounts have zero balance and are dropped
"""

# Map Wave's TB ACCOUNTS column to QBO Account name (or None to skip line)
WAVE_TO_QBO: dict[str, str | None] = {
    # === Asset / Bank & Cash ===
    "Cash on Hand": "Cash on Hand",
    "Dossco Designs LLC (707)": "Bluevine (707)",
    "Wave Payments": "Undeposited Funds",
    "PayPal": None,                          # Net-zero, dropped
    "Vendor Credit": None,                   # Net-zero, dropped
    "Bad Debt Clearing": None,               # Net-zero, Wave-only
    "Invoice Clearing": None,                # Net-zero, Wave-only
    "Wave Payroll Clearing": None,           # No payroll

    # === Asset / Inventory (collapsed to single QBO account) ===
    "Hats On Hand - SJCA": "Inventory - Apparel & Materials",
    "Hats on Hand": "Inventory - Apparel & Materials",
    "Marketing Materials on Hand": "Inventory - Apparel & Materials",
    "Samples": "Inventory - Apparel & Materials",
    "Shirts OH - RCC": "Inventory - Apparel & Materials",
    "Shirts OH - SJCA": "Inventory - Apparel & Materials",
    "Shirts on Hand": "Inventory - Apparel & Materials",
    "Transfers": "Inventory - Apparel & Materials",

    # === Asset / Fixed ===
    "Consew 226R-1": "Equipment - Consew 226R-1",
    "Consew 226R-1 - AD": "Accum. Depr. - Consew 226R-1",
    "Fusion IQ 2024": "Equipment - Fusion IQ 2024",
    "Fusion IQ 2024 - AD": "Accum. Depr. - Fusion IQ 2024",
    "Mac Mini - 2023": "Computer Equipment - Mac Mini 2023",
    "Mac Mini 2023 - AD": None,              # No AD posted yet
    "Nikon D90": "Camera - Nikon D90",
    "Nikon D90 - AD": "Accum. Depr. - Nikon D90",
    "Heat Press - Thornburry": None,         # Disposed in 2024

    # === Skipped: A/R and A/P go through open invoice/bill creation ===
    "Accounts Receivable": None,
    "Accounts Payable": None,

    # === Liabilities ===
    "JASON DOSS -01005": "Amex (1005)",
    "Affirm": None,                          # Loan paid off (per 10.5)
    "San Mar Terms": "SanMar A/P (Net 30)",
    "Clay County": None,                     # QBO AST manages this
    "CLAY": None,                            # Wave-archived dup
    "Payroll Liabilities": None,             # No payroll

    # === Equity ===
    # Wave's "Owner's Equity" closes prior-year P&L into it. QBO keeps prior
    # earnings in Retained Earnings (system-managed). Map both into QBO's
    # Owner's Equity for now; YTD profit is handled separately below.
    "Owner Investment / Drawings": "Owner's Draw",
    "Owner's Equity": "Owner's Equity",
    "Profit for all prior years": None,       # Routed to Retained Earnings via balancing
    # NOTE: "Profit between Jan 1, YYYY and ..." is YTD net income — we
    # collapse all of equity into Owner's Equity at cutover. QBO's
    # Retained Earnings is auto-managed.
}


# Wave income/expense accounts: their YTD activity is already baked into
# Wave's equity at cutover. We do NOT post them as JE lines (they'd
# double-count). Going forward, new income/expense in QBO posts fresh.
# Listed here for documentation; not used in the mapping.
WAVE_INCOME_EXPENSE_SKIP: set[str] = set()  # All P&L accounts auto-skipped
