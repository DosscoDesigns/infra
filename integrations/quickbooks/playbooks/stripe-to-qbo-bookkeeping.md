# Stripe → QBO Bookkeeping (Phase 2 Playbook)

Periodic bookkeeping workflow for Stripe-collected revenue (payment links and
website checkout) until dd-platform automates it via webhooks. Same "Claude
fills the gap" pattern as the dossco-invoice-wave skill.

## When to invoke

User says one of:
- "Book this week's Stripe to QBO"
- "Sync Stripe transactions"
- "Reconcile Stripe charges"
- "Book the [date range] Stripe activity"

Or it's a scheduled run (e.g., every Monday morning).

## What this skill does NOT cover

- **Formal QBO invoices.** Those are paid via QBO Payments natively; QBO marks
  the invoice paid automatically. No manual work needed.
- **dd-platform-automated payments.** Once dd-platform receives the Stripe
  webhook and writes to QBO directly, this skill goes away.

## Inputs needed

For each Stripe transaction to book:
- Customer name (from Stripe metadata or Jason's note)
- Item(s) sold (line items + quantity + unit price)
- Stripe charge ID (for cross-reference)
- Charge total
- Stripe processing fee
- Net deposit amount
- Payment date
- Whether FL Clay County 7.5% sales tax applies (apparel/marketing/slime: yes; services: no)

If anything is missing or ambiguous, **stop and ask Jason via Telegram** —
better than guessing.

## Step-by-step

### Step 1: Pull Stripe activity

Either:
- Jason exports a CSV from Stripe Dashboard → Payments → Export, OR
- We read directly from Stripe API (future enhancement; not built yet)

For each completed payment in the period:
1. Note charge ID, amount, fee, net, customer email, metadata
2. Identify customer in QBO (by email or name — see Step 2)
3. Map line items (see Step 3)

### Step 2: Identify customer in QBO

```python
from qbo import QBOClient
c = QBOClient()
match = c.find_by_name("Customer", "Display Name", "DisplayName")
```

If customer doesn't exist in QBO:
- For ad-hoc one-off buyer: create a generic "Stripe Web Buyer" customer
  (one-time use), OR ask Jason if they should be a permanent customer
- For website e-commerce: aggregate to "DD Web Sales" or "Slime Co Web Sales"
  customer (per AUDIT.md §10)

### Step 3: Map line items to QBO items

QBO items already exist (see chart of items). Match by name; fall back to:
- Apparel orders → "Custom Apparel" (or "Custom Apparel - Youth" for youth sizes)
- Slime orders → "Slime"
- Other → ask Jason

### Step 4: Create QBO Sales Receipt

```python
sales_receipt = {
    "CustomerRef": {"value": cust_id},
    "TxnDate": "2026-05-15",
    "PaymentMethodRef": {"value": stripe_pm_id},  # Or omit
    "DepositToAccountRef": {"value": stripe_clearing_id},  # NOT bank — Stripe Clearing!
    "PrivateNote": f"Stripe charge {charge_id}",
    "Line": [
        {
            "DetailType": "SalesItemLineDetail",
            "Amount": 100.00,
            "Description": "...",
            "SalesItemLineDetail": {
                "ItemRef": {"value": item_id},
                "Qty": 1,
                "UnitPrice": 100.00,
                "TaxCodeRef": {"value": "TAX"},  # If taxable
            },
        },
    ],
}
client.create("SalesReceipt", sales_receipt)
```

**Critical:** deposit account is `Stripe Clearing`, NOT Bluevine. The Stripe
payout to Bluevine is a separate transaction matched in the bank feed.

### Step 5: Book the Stripe processing fee

A separate Expense entry (or include as a negative line in the Sales Receipt
if QBO supports it for your case):

```python
fee_expense = {
    "AccountRef": {"value": stripe_clearing_id},  # PAID FROM Stripe Clearing
    "PaymentType": "Cash",
    "TxnDate": "2026-05-15",
    "PrivateNote": f"Stripe fee on charge {charge_id}",
    "Line": [{
        "DetailType": "AccountBasedExpenseLineDetail",
        "Amount": 3.20,
        "AccountBasedExpenseLineDetail": {
            "AccountRef": {"value": merchant_fees_id},
        },
    }],
}
client.create("Purchase", fee_expense)
```

### Step 6: Verify Stripe Clearing balance reflects net pending payouts

After booking all charges + fees for the period, the Stripe Clearing balance
should equal Stripe's "available" + "pending" balance from the Dashboard.

If they disagree: stop, investigate (refund? dispute? missing charge?).

### Step 7: Wait for Stripe payout, match in bank feed

When Stripe payouts hit Bluevine (1–2 days after charge):
- Bank feed shows lump deposit
- In QBO: open the For Review tab → match deposit → Stripe Clearing
- Stripe Clearing balance decreases as deposits come in

This step is the user's job in QBO web UI, not API.

### Step 8: Report back

```
✅ Stripe → QBO sync for [date range]
   Charges booked:    N transactions, $X.XX total
   Fees booked:       $Y.YY
   Net to Stripe Clearing: $Z.ZZ
   Pending payout to Bluevine
```

Or on partial:
```
⚠ Stripe → QBO sync for [date range]
   Booked:   N of M transactions
   Skipped:  M-N (see notes)
   Reasons:  customer unknown / item ambiguous / amount mismatch / ...
   Asked Jason via Telegram for clarification
```

## Reference: account IDs

Pull at runtime — IDs change between sandbox / prod. Common ones:

```python
accounts = {a["Name"]: a["Id"] for a in client.query("SELECT * FROM Account WHERE Active = true MAXRESULTS 1000")}
stripe_clearing = accounts["Stripe Clearing"]
merchant_fees = accounts["Merchant Account Fees"]
bluevine = accounts["Bluevine (707)"]
```

## Edge cases

| Situation | Handling |
|---|---|
| Refund issued | Create a Refund Receipt in QBO referencing the original Sales Receipt; book negative on Stripe Clearing (Stripe Dashboard shows a negative entry too) |
| Disputed charge / chargeback | Hold off — these usually resolve over weeks. Ask Jason. |
| Subscription billing (future) | Stripe-side recurring; same Sales Receipt approach per period |
| Multi-currency | Not in scope; all USD |
| Mid-period reconciliation mismatch | Stop, dump current state, ask Jason. Don't guess. |

## Why Stripe Clearing as a holding account

Stripe payouts are batched. A single Bluevine deposit may represent N charges.
If we booked each charge directly to Bluevine, the bank feed match would fail
because totals don't align. Stripe Clearing absorbs each charge individually
and gets cleared in lumps when payouts arrive — clean trail, easy
reconciliation.

## Once dd-platform automates this

When dd-platform's QBO integration ships:
- Stripe `payment_intent.succeeded` webhook → dd-platform creates the Sales
  Receipt via Intuit MCP/API automatically
- Stripe `charge.refunded` webhook → dd-platform creates Refund Receipt
- Stripe `payout.paid` webhook → optional auto-match to clear Stripe Clearing
- This playbook becomes vestigial; only used for backfill or anomalies
