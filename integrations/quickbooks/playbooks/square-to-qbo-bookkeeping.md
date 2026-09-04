# Square → QBO Bookkeeping

Companion to `stripe-to-qbo-bookkeeping.md`. Square is the RPK/RCC students'
store card processor; this is how its money reaches QBO.

## The one rule that matters

**The daily sales email is the trigger. The payout is the entry.**

Square sends "Dossco Designs, LLC—Your Daily Sales Summary Report for <date>"
around 12:55am for the prior day. Do not post it. It is a report, and its
window does not match a payout's:

| | window | Sep 3 2026 |
|---|---|---|
| Daily summary email | local midnight → midnight (EDT) | $110.00, 6 charges, $4.99 fees |
| Payout `po_b24e32bf` | Square's own batch cutoff | $98.00 gross, 5 charges, $4.34 fees → **$93.66 net** |

The sixth charge ($12.00, 10:27pm EDT Sep 3) fell past the cutoff and paid out
the next day. Booking the email *and* the payout double-counts. Booking only
the email leaves the books unmatchable against the bank feed, since Bluevine
sees the $93.66 lump, not the $110.00.

So: when the daily email arrives, run the sync. It books whatever payouts have
actually settled, which is where the money is. Every dollar still lands within
a day or two of the sale.

## Running it

```bash
cd ~/dev/dd/infra/integrations/quickbooks
direnv exec ~/dev/dd env PYTHONPATH=src ./.venv/bin/python -m bookkeeping.sync_square_payouts            # dry-run
direnv exec ~/dev/dd env PYTHONPATH=src ./.venv/bin/python -m bookkeeping.sync_square_payouts --apply    # post
```

`direnv exec ~/dev/dd` is required — Claude sessions otherwise inherit the NATCA
`op` token and the 1Password reads fail.

Idempotent: it queries QBO for an existing Deposit carrying the payout id in its
`PrivateNote` (amount+date as a backstop) and skips those. Re-running is safe,
and a dry-run over history should report every past payout as "already booked"
— that is the regression test for the posting model.

## What gets written

```
Deposit → Bluevine (707), TxnDate = payout arrival_date
  + gross  → Sales - Apparel (124), Entity = the store's QBO customer
  - fees   → Merchant Account Fees (149)
  = payout net
PrivateNote records the payout id and the full charge decomposition.
```

No clearing account. Square payouts settle daily and are small, so the
Stripe-Clearing pattern buys nothing here — unlike Stripe, one payout is
usually one day's charges and the bank feed matches directly.

## What it refuses to do

It auto-posts only what it can fully explain, and skips loudly (non-zero exit)
on anything else:

- **any entry that is not a plain `CHARGE`** — refunds, disputes, adjustments,
  held funds all change the accounting and need a human
- **an unknown payment note** — `STORE_NOTES` maps the note to a QBO customer;
  an unmapped note is not guessed at
- **a payout mixing stores** — the RCC 30% split is a judgement call and is
  never automated

When it says NEEDS A HUMAN, decompose that payout by hand (see the historical
`create_square_deposit_*.py` scripts for the shape) or ask Jason. Do not widen
`STORE_NOTES` to make a warning go away without confirming what the store is.

## Mail routing

Once the sync has run for that day, file the daily summary to `dd:finances`.
It stays in INBOX until then — Jason's inbox is his to-do list, so an unbooked
day should still be visible there.
