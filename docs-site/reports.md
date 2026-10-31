# Reports and dashboards

Kamra's reports answer the daily questions: how full were we, what did we
earn, what came in, are we on budget, where does the business come from,
and are guest requests handled in time. **Reports** (in the Front Desk,
Revenue, Operations and Finance menus) lists every report in one place,
showing only the ones your role can open. Today's key numbers sit on
[Today](/front-desk); Revenue Manager, Finance and Hotel Admin also get the
Revenue dashboard and portfolio views.

![Reports: every report in one place, grouped as Daily, Revenue, Finance and Operations](/img/reports/hub.png)

![The Manager flash: occupancy, ADR, RevPAR, RevPAX and the day's revenue, the last 14 days, today's movement, collections and the next 7 days](/img/reports/manager-flash.png)

## Before you start

- **Run the night audit.** Occupancy, ADR, RevPAR and room revenue count
  the room nights posted on folios, and the [night audit](/night-audit)
  posts them. Until tonight's audit runs, today shows no room revenue.
- **Set your monthly targets** if you want budget vs actual: see
  [Track the month against budget](#track-the-month-against-budget).
- Money is shown in the property's currency and tax columns follow your
  country pack ([Country setup](/country-setup)).

## See today at a glance

Today's headline numbers, collections, outstanding and month-to-date ADR,
RevPAR and occupancy are on **Front Desk → Today**; each tile opens the
list or report behind it. For the department view, open **Revenue →
Revenue Dashboard** (also under **Reports**). **This property** shows:

- **Occupancy** today, **ADR** and **RevPAR** (month to date),
  **Revenue** and **Collections** today, and **Outstanding** (owed on
  open folios);
- **Statistics (month to date)**: occupancy, revenue, ADR, RevPAR and
  rooms sold;
- **Housekeeping**: clean, dirty, inspected and out-of-order rooms, open
  and overdue tasks;
- **Finance**: collected today, outstanding and open folios.

![The property dashboard: headline tiles, month-to-date statistics, and the Housekeeping and Finance panels](/img/reports/dashboard.png)

**All properties** (shown when you have more than one property, for
Finance, Revenue Manager and Hotel Admin) rolls the same numbers up across
the portfolio, with a **By property** table: occupancy, arrivals,
departures, in-house, revenue, collected and outstanding for each hotel.

![The portfolio dashboard: properties, occupancy, arrivals, in-house, revenue and collections across three properties, and the By property table](/img/reports/portfolio.png)

## Check the hotel on your phone

**Reports → Owner view** (also under **Revenue** and **Finance**, or
search for "owner") is one column made for a phone. Pick **Today**,
**Yesterday** or **Month to date** and it shows:

- **Revenue** for the period, with occupancy, rooms sold, ADR and RevPAR,
  and the split between rooms, food and beverage, and other income;
- **Guests**: arrivals, departures, in house and no-shows;
- **Money**: what was collected (by payment mode), what guests still owe
  on open bills, and what companies owe on the city ledger, with the
  overdue part;
- **Next 7 days**: how full each night is from bookings on hand;
- **Night audits**: the last five, each opening its audit pack.

The figures are the manager flash's, so the two always agree. If you have
more than one property, the list at the top switches hotel, and **All
properties, today** shows each one's occupancy, revenue, collections and
outstanding. The owner view is for Finance, Revenue Manager, Night
Auditor and Hotel Admin; the front desk can't open it. Revenue Managers
see everything except the audit packs.

Tip: add the page to your phone's home screen from the browser's share
menu to open it like an app.

## Build a custom report

Open **Reports → Custom reports**. You build a report from a **dataset**:
arrivals, departures, in-house, no-shows and cancellations, occupancy by
day, folio charges, payments, voids, contribution, housekeeping tasks,
room status, lost and found, POS orders and kitchen times. You only see the datasets
your role can open (see [Who sees which report](#who-sees-which-report)).

1. Open **New report**, pick a dataset, choose columns and optional
   filters, set the date range (up to 92 days), and press **Preview**.
2. **Save** to keep the definition under **My reports**. Finance and
   Hotel Admin can **share** a report with the property and set a
   **Daily** or **Weekly** email schedule (recipients + time).
3. **CSV**, **Print** and **Email** work for new or saved reports.
   Scheduled sends attach yesterday (or the last 7 days for weekly) as
   CSV.

### Group and drill down

Pick a column in **Group by** and press **Preview**: you get one row per
value, with the number columns added up. For housekeeping tasks, **Clean
minutes** is the average over the cleans that were timed, not a sum.

Click a group row to see the rows behind it. **Back to summary** returns
to the grouped view. The grouping is saved with the report and used in
its emails.

## Send a department pack

Open **Reports → Department packs**. A pack puts several grouped reports
on one page:

| Pack | What's on it |
|---|---|
| **Front Office pack** | Occupancy by day, arrivals by source, in house by room type, no-shows and cancellations |
| **Housekeeping pack** | Room status now, tasks by type and by attendant with average clean minutes, lost and found |
| **F&B pack** | Sales and covers by outlet, orders by status, items sold, kitchen turnaround |
| **Hotel Manager pack** | Occupancy and revenue, revenue by source, collections by mode, charges by type, voids and allowances |

1. Set the **From** and **To** dates.
2. Press **Open** for a printable page, or **Email now** and type the
   addresses.
3. Finance and Hotel Admin can press **Email every Monday** to send it
   at 07:00 each Monday with the last 7 days. The schedule shows under
   **My reports**, where you can open, email or delete it.

A pack only holds the parts your role can open. A night auditor's Hotel
Manager pack has occupancy, collections and charges, but no voids. The
page follows the language you use Kamra in, and Arabic reads right to
left.

## Who sees which report

Each report checks your roles, the same way its screen does, and the
Kamra Agent and Claude (MCP) follow the same rules: they never show
someone a report their role can't open.

| Role | Fixed reports | Custom report datasets | Packs |
|---|---|---|---|
| Front Desk | Manager flash, shift report, SLA, F&B dashboard, wastage, banquet registers | Arrivals, departures, in-house, no-shows, occupancy, housekeeping tasks, room status, lost and found, POS orders | All four |
| Night Auditor | Manager flash, shift report | Arrivals, departures, in-house, no-shows, occupancy, folio charges, payments | Front Office, Hotel Manager |
| Finance | Manager flash, shift report, voids, F&B dashboard, wastage, banquet registers | Front office datasets, folio charges, payments, voids, contribution, POS orders | Front Office, F&B, Hotel Manager |
| Housekeeping, Housekeeping Supervisor | None | Housekeeping tasks, room status, lost and found | Housekeeping |
| F&B Manager | F&B dashboard, wastage | POS orders, POS items, kitchen times | F&B |

Hotel Admin sees everything. A dataset also needs its module switched on
for the property (**Settings → Modules**).

## Read the manager flash

Open **Reports → Manager flash**. The **Manager flash** is the morning report
for one date. Pick it in the right-hand date box. To see a range, set the
left-hand date to an earlier day (up to 92 days): the tiles, the daily
table, movement and collections then cover the whole range, and
**Revenue (day)** becomes **Revenue**. Month to date and the next 7 days
don't change.

- **Occupancy**, **ADR**, **RevPAR**, **RevPAX** and **Revenue (day)**
  split into room, F&B and other. RevPAX is total guest spend (room, F&B,
  experiences, extras) per in-house guest.
- **Last 14 days**: Occ %, ADR, RevPAR and revenue per day, with the
  month-to-date total.
- **Movement**: arrivals, departures, in-house and no-shows.
- **Collections**: what was collected that day, by payment mode.
- **Next 7 days**: occupancy on the books for the coming week.

Press **Print** for a paper copy. **Cashier shift report** and
**Ledgers** at the top open the cashier and ledger screens (see
[Billing](/billing#count-the-drawer-and-close-the-till)). Finance and Hotel
Admin users also get **Voids & Allowances**, the list of every void,
allowance and cancelled invoice (see
[Billing](/billing#review-voids-and-allowances)).

The same flash is the first report in each night's
[audit pack](/night-audit#print-the-audit-pack).

## Track the month against budget

Open **Reports → Revenue reports**. **Budget vs Actual** compares the
month to date with your targets: **Room Revenue**, **Occupancy %**, **ADR
/ ARR** and **RevPAR**, each with the variance and how much of the target
you have reached.

"Actual" counts room nights posted to folios, and End of Day posts each
night, so tonight counts after tonight's audit. Occupancy and RevPAR are
worked out over the days of the month that have passed up to the business
date, not the whole month, so they compare fairly with a monthly target.
The note under the table says how many room nights are posted and over
how many days. If sold nights are still waiting for End of Day, it says
how many, in amber.

![Budget vs Actual for the month: actual month to date, target, variance and attainment for room revenue, occupancy, ADR and RevPAR, with the note on posted and not-yet-posted room nights below](/img/reports/budget-vs-actual.png)

1. Use the arrows to pick the month.
2. Press **Set targets** (or **Edit targets** once the month has them).
3. Type the targets in the **Target** column and press **Save targets**.

![Editing the ADR target for the month and saving it](/img/reports/set-targets.gif)

Revenue Manager, Finance and Hotel Admin users can save targets.

## See where the business comes from

**Contribution analysis** on **Reports → Revenue reports** groups the
bookings arriving in a date range **By source**, **By company** or **By
travel agent**: bookings, room nights, revenue and share of the total.

![Contribution analysis by source: bookings, room nights, revenue and share for Manual, Phone, AI Agent, Website, OTA and Walk-in](/img/reports/contribution.png)

It counts confirmed, in-house and checked-out bookings by their arrival
date, at the booking's total including tax. Bookings with no source,
company or agent are shown as **Direct**.

## Check guest-request response times

Open **Reports → SLA report**. For guest requests created in the date
range (the last 30 days by default) it shows the number of **Tickets**,
how many are **Resolved**, the **Breach rate** and the average time to
resolve, then the same by category and by priority, and **Overdue now**:
open requests already past their due time, oldest first.

![The Operations SLA report: tickets, resolved, breach rate and average resolve time, the breakdown by category and priority, and the overdue queue](/img/reports/sla.png)

A request counts as breached when it was resolved after its due time, or
is still open past it. Due times come from **Settings → Operations**; see
[Operations](/operations).

## Send invoices to your accountant

Open **Finance → Accounting Export** (Finance and Hotel Admin).

1. Pick the date range. It defaults to the last 30 days.
2. Pick the format: **Generic CSV**, **Tally**, **Zoho Books** or
   **ERPNext**.
3. Check the preview, then press **Download CSV**.

![Accounting Export in Generic CSV: the date range, the format, the totals line, and one preview row per service code with the item, SAC/HSN, GST %, taxable value and the CGST and SGST split](/img/reports/accounting-export.png)

The export lists every invoice closed in the range: number, date, party
and their tax ID, place of supply, taxable value, the tax split your
country pack uses (CGST and SGST in India, a single tax column elsewhere)
and the total. How the rows are laid out depends on the format:

- **Generic CSV** and **Zoho Books** give one row per service code and
  tax rate on each invoice, so a bill with a room, a dinner and laundry
  has a row for each. Generic CSV adds **Item**, **SAC/HSN**, the tax %,
  **Line Total** and **Invoice Total** columns; Zoho Books uses its own
  **Item Name**, **HSN/SAC**, **Item Tax %** and **Item Total**.
- **Tally** and **ERPNext** give one row per invoice.

The preview shows the first 12 rows; the download has them all.

## Good to know

- **Single-day reports also take a range.** The F&B dashboard, the
  cashier shift report, folio history, room insights and the banquet
  pipeline have a **From** and **To** date. Leave the end date alone for
  one day.
- **Dashboards and the flash use the calendar date**, not the hotel's
  business date. Between midnight and the night audit, "today" on the
  dashboard is already the new day.
- **Occupancy counts rooms with a room night posted**, not rooms with a
  guest in them.
- **Contribution revenue is the booking value**, not what was posted on
  the folio; use budget vs actual or the flash for posted revenue.
- **The audit pack keeps each night's reports as they were**, so a
  reprint of a past day matches the original.

## Troubleshooting

**Occupancy and room revenue show 0 for today.** Tonight's night audit
hasn't run yet. Earlier days are on the flash's 14-day table.

**All properties is missing on the dashboard.** You have access to only
one property.

**The accounting export is empty.** It lists closed invoices only. Folios
still open (guests in house) are not in it.

## For developers

The numbers come from `kamra.dashboards.property_dashboard` and
`portfolio_dashboard`, and `kamra.reports.manager_flash`,
`budget_vs_actual`, `save_budget`, `contribution` and `sla_report`; the
export is `kamra.accounting.export_invoices`. Finance and Hotel Admin can
also pull every void, allowance and invoice cancellation with
`kamra.reports.void_allowance_report`, the endpoint behind the **Voids &
Allowances** screen. See
[Dashboards](/api-reference#dashboards) and [Reports](/api-reference#reports)
in the API reference. Agents get the daily picture from the
`owner_briefing` and `position_briefing` [MCP tools](/mcp-tools#briefings).
