"""Target chart of accounts for Dossco Designs LLC, per AUDIT.md §4.

Each entry is what we want in QBO after migration. The reconciler compares
this plan against live QBO state and produces a diff."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class AccountSpec:
    name: str
    account_type: str           # QBO AccountType enum value
    account_sub_type: str       # QBO AccountSubType enum value
    description: str = ""
    classification: str = ""    # Asset/Liability/Equity/Revenue/Expense (auto in QBO)


# Bank & Cash
# IMPORTANT: Bluevine (707) and Amex (1005) are already created in QBO and
# linked to live bank feeds. Names match exactly what's in QBO. Reconciler
# will mark these KEEP, not CREATE, not INACTIVATE.
BANK_AND_CASH = [
    AccountSpec("Cash on Hand", "Bank", "CashOnHand", "Petty cash"),
    AccountSpec("Bluevine (707)", "Bank", "Checking",
                "Primary operating account, last 3 = 707. Bank-feed connected."),
    AccountSpec("Undeposited Funds", "Other Current Asset", "UndepositedFunds",
                "Holding for QBO Payments / customer payments not yet deposited"),
    AccountSpec("Stripe Clearing", "Other Current Asset", "OtherCurrentAssets",
                "Stripe Payment Link / Checkout receipts pending payout to Bluevine"),
]

# Inventory (single combined per audit §4)
INVENTORY = [
    AccountSpec("Inventory - Apparel & Materials", "Other Current Asset", "Inventory",
                "Combined inventory stub. Real inventory tracked in DD platform app, not QBO."),
]

# Accounts Receivable / Sales Tax
AR_AND_TAX = [
    # AccountsReceivable + SalesTaxPayable are typically auto-created by QBO; we'll
    # detect existing ones rather than creating duplicates.
]

# Fixed Assets — paired with accumulated depreciation accounts where applicable
FIXED_ASSETS = [
    AccountSpec("Equipment - Consew 226R-1", "Fixed Asset", "MachineryAndEquipment"),
    AccountSpec("Accum. Depr. - Consew 226R-1", "Fixed Asset", "AccumulatedDepreciation"),
    AccountSpec("Equipment - Fusion IQ 2024", "Fixed Asset", "MachineryAndEquipment"),
    AccountSpec("Accum. Depr. - Fusion IQ 2024", "Fixed Asset", "AccumulatedDepreciation"),
    AccountSpec("Computer Equipment - Mac Mini 2023", "Fixed Asset", "OtherFixedAssets",
                "Used Mac Mini purchased 2026; first AD entry pending (per A7)"),
    AccountSpec("Camera - Nikon D90", "Fixed Asset", "OtherFixedAssets"),
    AccountSpec("Accum. Depr. - Nikon D90", "Fixed Asset", "AccumulatedDepreciation"),
]

# Liabilities
LIABILITIES = [
    AccountSpec("Amex (1005)", "Credit Card", "CreditCard",
                "American Express ending 1005, primary business card. Bank-feed connected."),
    AccountSpec("SanMar A/P (Net 30)", "Other Current Liability", "OtherCurrentLiabilities",
                "Net-30 trade payable with SanMar; tracked separately from primary A/P"),
]

# Equity (most are auto-created by QBO; we add what's needed)
EQUITY = [
    AccountSpec("Owner's Draw", "Equity", "OwnersEquity",
                "Cumulative owner draws"),
    AccountSpec("Owner's Equity", "Equity", "OwnersEquity",
                "Owner contributions and retained capital"),
]

# Income
INCOME = [
    AccountSpec("Sales - Apparel", "Income", "SalesOfProductIncome",
                "Custom apparel decoration revenue (primary)"),
    AccountSpec("Sales - Marketing Materials", "Income", "SalesOfProductIncome",
                "Stickers, banners, promo printed materials"),
    AccountSpec("Sales - Web/Hosting", "Income", "ServiceFeeIncome",
                "Hosting, email, website design, plugins, software subscriptions"),
    AccountSpec("Sales - Design/Other", "Income", "ServiceFeeIncome",
                "Design fees, engraving, other one-off services"),
    AccountSpec("Sales - Slime Co", "Income", "SalesOfProductIncome",
                "The Slime Co revenue (kept separate for entity reporting)"),
    AccountSpec("Sales Discounts", "Income", "DiscountsRefundsGiven",
                "Customer discounts, shown as negative income"),
    AccountSpec("Other Income - Rewards", "Other Income", "OtherMiscellaneousIncome",
                "Credit card rewards / cashback"),
    AccountSpec("Other Income - Interest", "Other Income", "OtherMiscellaneousIncome",
                "Bank interest income"),
]

# Cost of Goods Sold
COGS = [
    AccountSpec("Shirts", "Cost of Goods Sold", "SuppliesMaterialsCogs",
                "Blank shirts purchased for decoration (collapsed: was Shirts/Shirts-RCC/RPK/SJCA/NATCA)"),
    AccountSpec("Shirt Transfers", "Cost of Goods Sold", "SuppliesMaterialsCogs",
                "Heat-applied transfers"),
    AccountSpec("Hats", "Cost of Goods Sold", "SuppliesMaterialsCogs",
                "Blank hats purchased for decoration"),
    AccountSpec("Embroidery Service", "Cost of Goods Sold", "OtherCostsOfServiceCos",
                "Outsourced embroidery work"),
    AccountSpec("Embroidery Digitizing", "Cost of Goods Sold", "OtherCostsOfServiceCos",
                "Digitizing fees for embroidery designs"),
    AccountSpec("Screen Print", "Cost of Goods Sold", "OtherCostsOfServiceCos",
                "Outsourced screen printing + screens (collapsed)"),
    AccountSpec("Plugins / Software for Resale", "Cost of Goods Sold", "SuppliesMaterialsCogs",
                "Software/plugins purchased to resell to clients"),
    AccountSpec("Marketing Materials - Resale", "Cost of Goods Sold", "SuppliesMaterialsCogs",
                "Promotional materials cost"),
    AccountSpec("Vinyl Supplies", "Cost of Goods Sold", "SuppliesMaterialsCogs",
                "Vinyl for sign/banner work"),
]

# Operating Expenses
OPEX = [
    AccountSpec("Advertising & Promotion", "Expense", "AdvertisingPromotional"),
    AccountSpec("Bad Debt Expense", "Expense", "BadDebts"),
    AccountSpec("Bank Service Charges", "Expense", "BankCharges"),
    AccountSpec("Computer – Hosting", "Expense", "OtherBusinessExpenses",
                "Web hosting and cloud services for own infra"),
    AccountSpec("Depreciation Expense", "Expense", "Depreciation"),
    AccountSpec("Equipment", "Expense", "EquipmentRental",
                "Small equipment purchases below capitalization threshold"),
    AccountSpec("Insurance - Liability", "Expense", "Insurance"),
    AccountSpec("Interest Expense", "Expense", "InterestPaid"),
    AccountSpec("Loss on Disposal", "Expense", "OtherMiscellaneousServiceCost",
                "Asset write-offs on disposal"),
    AccountSpec("Meals and Entertainment", "Expense", "Entertainment"),
    AccountSpec("Merchant Account Fees", "Expense", "BankCharges",
                "QBO Payments + Stripe processing fees"),
    AccountSpec("Office Supplies", "Expense", "OfficeGeneralAdministrativeExpenses"),
    AccountSpec("Professional Fees", "Expense", "LegalProfessionalFees"),
    AccountSpec("RD - Youth Ministry Resources", "Expense", "OtherBusinessExpenses",
                "Reseller discount/commission. Rename to Slime Co reseller costs later (per A5)."),
    AccountSpec("Repairs & Maintenance", "Expense", "RepairMaintenance"),
    AccountSpec("Sales Tax", "Expense", "TaxesPaid",
                "Sales tax paid on items purchased for resale (input tax)"),
    AccountSpec("Shipping Fee", "Expense", "ShippingFreightDelivery"),
    AccountSpec("Subscriptions", "Expense", "OtherBusinessExpenses",
                "Software subscriptions and recurring memberships"),
    AccountSpec("Telephone – Wireless", "Expense", "Utilities"),
    AccountSpec("Vendor Processing Fee", "Expense", "BankCharges",
                "Card-processing fees passed through from vendors"),
]

# Other Expense (separated from OpEx for tax treatment, per A2)
OTHER_EXPENSE = [
    AccountSpec("Charitable Contributions", "Other Expense", "OtherMiscellaneousExpense",
                "Cash donations. Reclassified from Wave's 'Donations Given' OpEx (per A2)."),
]

ALL_TARGET_ACCOUNTS: list[AccountSpec] = (
    BANK_AND_CASH + INVENTORY + AR_AND_TAX + FIXED_ASSETS + LIABILITIES +
    EQUITY + INCOME + COGS + OPEX + OTHER_EXPENSE
)


# Names (lowercased) of QBO default accounts that QBO does not let us delete or
# rename, that we can simply leave inactive after the migration.
QBO_DEFAULTS_TO_LEAVE_ALONE = {
    "accounts payable",
    "accounts receivable",
    "opening balance equity",
    "retained earnings",
    "uncategorized expense",
    "uncategorized income",
    "inventory shrinkage",
}
