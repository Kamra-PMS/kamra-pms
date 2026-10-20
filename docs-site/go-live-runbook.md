# Go-live runbook: switch on one night

This runbook moves a hotel from its old PMS to Kamra in one night. You
bring over the bookings, the companies, and the money that is still
open at the old system's last close. Then you check that everything
ties out before the desk starts on Kamra.

It works with any old system. You fill in Kamra's own CSV templates
from the old system's reports. You do not need an export in a special
format.

Do the [go-live checklist](/go-live) first: property, rooms, rates,
staff, and a dress rehearsal. This page covers only the night of the
switch.

## What you need

- A login with the **Finance** or **Hotel Admin** role. Opening
  balances and companies are Finance work. The screen refuses other
  roles.
- **Admin → Go-live Import** in Kamra (`/kamra/go-live`). A new
  property also gets it as the last step of the setup wizard.
- The three templates. Download each one from its tab (**Download
  template**):

| File | One row per | Columns |
| --- | --- | --- |
| Bookings | reservation (future, in-house and past) | Reservation No, Guest Name, Phone, Email, Room Type, Room, Check In, Check Out, Adults, Children, Total Amount, Status, Source |
| Companies | corporate account | Company Name, Tax ID, Contact Name, Contact Phone, Contact Email, Credit Allowed, Credit Limit, Credit Days, Account No |
| Opening balances | open balance | Type, Reservation No, Guest Name, Room, Check In, Check Out, Room Type, Company, Invoice No, Invoice Date, Amount, Mode |

Column names are matched loosely ("Arrival" or "Check-in Date" both
work). The preview shows how each column was read. Dates can be
`DD/MM/YYYY`, `MM/DD/YYYY` or `YYYY-MM-DD`; the preview tells you
which order it found.

## The night

### 1. Freeze the old system

Pick a quiet night. Tell the team the time after which nothing is
entered in the old system.

Run the old system's **last night audit**. Every figure you export must
come from after that close. Kamra starts billing from its own business
date. Every night before it belongs to the old system.

Check Kamra's business date: it must be the first day Kamra runs.
**End of Day** shows it.

### 2. Export

From the old system, fill in the templates:

1. **Bookings.** Take every future booking and every guest in house.
   Optionally add past stays, so returning guests are recognised.
   - Keep the old **Reservation No**. A re-run uses it to skip rows
     that are already in. The opening-balance file uses it to find the
     stay.
   - In-house guests need their **Room**. Status `In House` or
     `Checked In`.
2. **Companies.** Take every corporate account that is billed on
   credit or has a balance. `Credit Allowed` is Yes or No. A credit
   limit on its own means Yes. `Credit Days` is the company's payment
   terms (`30`, `30 days`, `Net 30`, or `0` / `On receipt` for due on
   the invoice date); a value turns off **Use property default** for that
   company. Leave it blank to follow the property default. Each city ledger bill is then due on its invoice
   date + the credit days, so the aging matches the old system's.
3. **Opening balances.** Take the closing balances of the last night
   audit. Use one row per balance. The `Type` column is one of:

   | Type | Amount is | How Kamra posts it |
   | --- | --- | --- |
   | `In-house` | what the guest owes on the old folio. Use a negative amount if the guest is in credit. Use **0 if the guest is settled**. | One *Opening Balance* line on the guest folio (Guest ledger). |
   | `City ledger` | one unpaid company invoice, with Company, Invoice No and Invoice Date. Use a negative amount for money a company paid ahead. | Billed to the company's city ledger, dated on the original invoice, so aging stays correct. A credit becomes an unapplied payment. |
   | `Deposit` | an advance a future booking has already paid, with Mode (Cash, Card, UPI, Bank Transfer). | An *Advance* payment on the booking (Deposit ledger). The booking's advance paid goes up. |

   Include **every in-house guest**, even at 0. The row also tells
   Kamra that the nights before go-live were billed by the old system.
   At checkout Kamra bills only the nights from go-live on.

Example:

```csv
Type,Reservation No,Guest Name,Company,Invoice No,Invoice Date,Amount,Mode
In-house,R-1042,,,,,12600,
In-house,R-1051,,,,,0,
City ledger,,,Acme Travels,INV-881,10/09/2026,18000,
City ledger,,,Acme Travels,INV-902,14/10/2026,4500.50,
City ledger,,,Northwind Ltd,,,(2000),
Deposit,R-1077,,,,,3000,UPI
```

### 3. Preview

Work through the tabs in order. Bookings come first, because the
opening balances point at them. Companies come before the city ledger.

On each tab, upload the file (or paste it) and press **Preview**.
Nothing is written yet. Read what the preview shows:

- how each column was read, and any column it ignored
- the rows it will skip, and why (an unknown room, a company that is
  not on credit, a stay it cannot find)
- for opening balances: rows and total per category, and the business
  date the postings will carry

Fix the file and preview again until no row is skipped.

### 4. Import

Press **Import** on each tab, in order: Bookings, Companies, Opening
balances.

Re-running a file is safe. A row that is already in Kamra is skipped
and counted as "already posted", so a file that half-failed can be
fixed and run again. To change an amount that is already posted, do
not edit the file and re-import. Correct it on the folio or city
ledger with an allowance or credit note. Every correction stays on the
record.

What the import does **not** do:

- It puts no money in today's till. That money moved in the old
  system, before go-live.
- It counts no revenue. Opening balances use their own charge type,
  *Opening Balance* (transaction code `8900`). The day's revenue
  reports leave them out. They carry no tax, because the old system
  already taxed them.
- It does not let anyone post an opening balance by hand. The folio
  screens refuse the *Opening Balance* charge type.

### 5. Reconcile

Open **Reconcile** and press the button. Kamra compares each file
loaded in steps 1 to 3 with what is now in Kamra:

| Category | Compared |
| --- | --- |
| Bookings | rows in the file and reservations in Kamra |
| Companies | companies, credit allowed, credit limit and credit days |
| In-house guest balances | stays and total, guest by guest |
| Advance deposits | bookings and total, booking by booking |
| City ledger (AR) | invoices and total, plus a per-company table with each account's balance |

**Ready for go-live** shows only when every category matches and no
row of any file was left out. It also stays off while an imported
in-house guest has no opening-balance row.

Tie the per-company city ledger table to the old system's AR aging
report, and the in-house total to its guest ledger. If something
differs, the list under the table says which guest, booking or
invoice. Fix it, re-import (posted rows are skipped) and reconcile
again.

### 6. Go live

- Switch the channel manager to Kamra and retire the old system's OTA
  connections in the same hour. See the [channel manager
  guide](/channel-manager).
- Keep the old system read-only for reference.
- The desk works in Kamra from now on. Run the first **End of Day**
  on Kamra tonight. It bills tonight's room nights for the in-house
  guests you carried over.

## How it is posted (for auditors)

Every amount goes through Kamra's normal folio and ledger writers. No
row is written past them.

- **In-house:** one *Opening Balance* folio line, dated on the go-live
  business date, debit (or credit) on the Guest ledger.
- **City ledger:** each invoice is kept as a past-stay record with a
  Company folio. It carries the amount as an *Opening Balance* line
  and is moved to the company's AR by the same transfer a checkout
  uses. The AR invoice carries the old invoice number and date. The
  folio is then closed. A company credit is a city ledger payment
  with reference `opening-ar:…`. It settles the oldest open bills
  first.
- **Deposit:** an *Advance* folio payment with reference
  `opening-deposit:<reservation>`, credit on the Deposit ledger. It
  moves to the Guest ledger at check-in like any advance.

The import is recorded in the activity log with counts and totals.

Endpoints: `kamra.golive.*` in the [REST API reference](/api-reference)
(`preview_companies`, `run_companies`, `preview_opening`, `run_opening`,
`reconcile`, `csv_template`) and `kamra.migrate.preview_import` /
`run_import` for bookings.
