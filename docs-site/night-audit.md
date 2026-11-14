# Night audit

The night audit closes the hotel's business date. It posts the night's
room charges for every in-house guest, applies the no-show policy, saves
an audit pack of the day's reports and moves the business date on by one
day. You can close the day by hand from **Night Audit**, and it runs on
its own every night at each property's set time (03:00 unless you change
it). Front Desk, Finance, Night Auditor and Hotel Admin users can run it.

## Before you start

1. **Check the no-show rules.** **Settings → Front Desk → Night audit &
   no-shows** decides when an arrival that never came becomes a No Show;
   the fee is **Settings → Stay policies → No-show charge**. See
   [Settings](#settings).
2. **Decide what blocks the audit.** **Settings → Front Desk → Night audit
   checklist** sets which checks stop a manual run, the high-balance
   threshold and what the automatic run does when something is still open.
3. **Give your night auditor the Night Auditor role** if they don't have
   Front Desk or Finance: **Settings → Staff & access**. It can close the
   day and override blockers, check guests in and out, close cashier
   sessions, and view folios, the cashier summary and reports.

## Open Night Audit

Open **Finance → Night Audit** (also under **Front Desk**, or type *night
audit*, *end of day* or *EOD* in search, Ctrl/Cmd+K). You see one card per
property: its business date and local time, arrivals and departures still
pending, open cashiers, open POS bills, and **Ready** or the number of
blockers. Press **Close the day** (or **Review and close** when something
blocks).

![Night Audit: one card per property with arrivals and departures pending, open cashiers and open POS bills, and the audit history with From and To dates and Export CSV](/img/night-audit/manage.png)

## The close-the-day page

One page shows everything for the business date:

- **The top line**: the date you are closing, a badge (**Ready**, **N to
  look at** or **Date stuck**) and the **Close** button.
- **N of M checks clear**, with a bar, and what is stopping the close.
- **Needs you**: only the checks that found something, blocking ones
  first. Each has its list and the buttons that clear it.
- **For information**: checks that only inform (vacant rooms, for
  example) and checks you have overridden.
- **All clear**: every check that found nothing, folded into one line.
- **Tills on this date**: expected and counted cash for every session.
- **Notes for the manager**: weather, incidents, hand-over. They save when
  you leave the box and print on the audit pack.

![Closing the day: the date and the Close button at the top, how many checks are clear, and under Needs you the departures still in house with How to clear this and the list](/img/night-audit/close-day.png)

What each check does when it finds something:

| Check | What you do |
| --- | --- |
| Arrivals not checked in | **Check in** or **Mark no-show**. Each row shows what the no-show policy will do with it. |
| Departures still in house | **Check out**, **Extend stay**, or **Quick check out** every zero-balance departure at once. Blocks by default. |
| High balances, balances on departed stays, companies over their limit, overdue company bills | Review; open the folio or Receivables. |
| Open outlet bills | Settle them in the outlet. Blocks by default. |
| Outlet bills posted to rooms | Look for a wrong-room posting. |
| Rate variance and zero-rate rooms | Room nights posted away from the booked rate. |
| Room status | Rooms where the front office and the room board disagree. |
| Open tills | Type the counted cash and press **Count and close**. Blocks by default. |

Every list can be searched and sorted.

**Mark no-show** applies the property's policy straight away: the stay
becomes a No Show and the fee is posted on the business date, or waived
for an OTA booking. Only a Confirmed arrival due on or before the
business date can be marked.

The same **Mark no-show** button is on the Arrivals card on **Today** (for
an arrival due on or before the business date) and on the reservation
page, for Front Desk and Night Auditor. Before anything posts, a confirm
step shows the fee the policy will post with tax (or why there is none),
what the guest already paid, and what is left over. After you confirm,
the room is free for a walk-in at once: the channels get the new
availability and other open desk screens refresh.

### When the guest paid more than the fee

If the advance is larger than the no-show fee, the rest is credit on the
folio. The confirm step then offers:

- **Refund it to the guest**: pick how, give a reason. It goes through the
  normal refund (open till, cashier PIN) and leaves the deposit ledger.
- **Keep it as a forfeited deposit**: give a reason. Kamra posts a
  **Forfeited advance (no-show)** line at the room's tax rate so the folio
  settles at zero.

**Settings → Front Desk → Night audit & no-shows → When a no-show paid
more than the fee** decides which one is picked first. **Decide later**
leaves the credit on the folio; the audit pack lists every no-show still
in credit under **No-shows still in credit** for the morning.

## Clear or override a blocker

Three checks block the close by default: open tills, open restaurant
bills, and guests due out who are still checked in. While one has items,
the **Close** button stays off. Either fix it (check the guest out, settle
the restaurant bill, close the till), or override it:

1. Read **How to clear this** under the check: the usual fixes, **Ask
   Kamra Agent to help**, and what happens **If you override**.
2. Type the reason in the box under the list, for example *"Late
   checkouts approved by the duty manager"*.
3. Press **Override with reason**. The check moves to **For information**.

Your name, the time and the reason are saved on the audit, listed under
the notes, printed in the pack and written to the Activity log. Warnings
never block: look them over and close.

A cashier can also close their own till on **Finance → My Till**: see
[Billing](/billing#count-the-drawer-and-close-the-till).

## Close the day

1. When nothing blocks, press **Close** at the top (it names the date).
2. Kamra posts the night and shows what it did: room nights posted and
   their amount, no-shows, and the new business date.
3. The audit pack opens on the same page. Every table in it has **Export
   CSV**.

![Closing the day: overriding the blockers with a reason, counting and closing the till, adding a note and pressing Close](/img/night-audit/run-close.gif)

It cannot be undone. The audit closes only the property's current
business date, and only once that day has started on the server: you
can't run tomorrow's audit tonight.

## What the audit posts

For every guest checked in on the business date:

- one **Room** night at the rate confirmed at booking for that night
  (season, demand pricing and rate plan included), routed to the company
  folio when the company pays the room;
- the **Meal Plan** for the night, if the stay has one;
- the **Room levy** (city or tourism tax), if the property has one;
- an **Extra Guests** charge, if the stay has one agreed.

Nights already on the folio are skipped, so running it again, or a
checkout that already posted the night, never charges twice. A missing
guest folio is opened.

For arrivals that never came, the no-show policy applies: the stay
becomes **No Show** and the **No-show charge** (first night or full stay)
is posted on the date being closed, unless the arrival is held as a late
arrival or the fee is waived for an OTA booking.

The audit also removes waitlist entries two days past their requested
departure.

## Email reports after the audit

Any custom report can go out by email as soon as the audit closes the
day: open it under **Reports → Custom reports**, set **Email schedule** to
**After night audit**, add the recipients and **Save**. Each one is sent
for the business date just closed, as a CSV. See
[Build a custom report](/reports#build-a-custom-report).

## Print the audit pack

After the close, the pack lists the final reports on the left. Pick one to
read it, then **Print** or **Download PDF** (choose *Save as PDF* in the
print dialog); **Print all** prints the whole pack on A4. Every table has
**Export CSV**, with the raw figures:

- Night audit report: the day, month to date and year to date side by
  side (room nights, occupancy, rooms, ADR, RevPAR, food, beverage,
  banquets, meal plan and minibar, other, total); food and beverage for
  each outlet; banquets; and the guest ledger, advance deposits and city
  ledger brought forward, moved today and carried forward. Food and
  beverage come from the restaurant bills, paid at the outlet or charged
  to a room, with liquor items as beverage. In India the year runs from
  1 April. Audits closed before this report have no copy of it.
- Manager's flash
- Journal by cashier and transaction code
- Cashier summary
- Guest ledger detail
- City ledger / AR summary
- Deposit ledger balance
- Trial balance, whose total line says whether the ledgers match the
  folios: **Agrees with folios** or **Differs from folios by** an amount
- Occupancy & revenue (Occ %, ADR, RevPAR)
- No-shows and cancellations
- Rate variance
- Pre-checks and exceptions, with every acknowledgement

![The audit pack's final reports for a closed business date](/img/night-audit/audit-pack.png)

The pack is saved on the audit when it runs, so reprinting a past night
gives exactly what was printed that night. Find past audits in **Audit
history** at the bottom of **Night Audit**: pick **From** and **To** dates,
press **Export CSV** for the list, or **Print** in the **Audit pack**
column. Automatic runs appear
there with trigger **Scheduled**. If a pack is missing, press
**Rebuild pack**  -  that recreates the printable reports without posting
charges again.

On the property card, **Print pack** opens the latest run's pack when one
was saved.

![Audit history: each closed business date with its status, trigger, room nights, amount posted, no-shows, exceptions and a link to its audit pack](/img/night-audit/history.png)

## The automatic run

Kamra checks every 15 minutes. Once a property's clock is past its
**Run at** time (default 03:00, plus any **Wait after that time**) and its
business date is still behind the calendar date, it runs the audit for
that property. The clock is the property's **Time zone** (Settings →
Property), so two hotels in different time zones each close at their own
03:00. Turn **Run the night audit automatically** off to close the day
only by hand; the Night Audit card then shows **automatic audit off**. These live
in **Settings → Front Desk → Automatic night audit**, which Hotel Admin
can change.

The automatic run does the same work as the manual run. If a blocking
check is still open, it follows **Scheduled audit when checks block**:

- **Run and report exceptions** (default): the date rolls, and the open
  items are recorded as exceptions in the pack.
- **Hold and alert**: the business date stays where it is, and Hotel
  Admin and Finance users get an in-app notification and an email. The
  Night Audit card shows **Audit held**: clear blockers and press **Review
  and close**, then print the pack.

If someone already closed the day by hand, the automatic run skips it. A
held, skipped or failed day is tried once a day, not every 15 minutes. A
failed run alerts Hotel Admin users.

Every run, automatic or by hand, is listed under **Night audit runs** on
the same settings page: when it started, who ran it (or the scheduler),
the result (Closed, Held, Skipped or Failed) and why. Night Audit shows
the next automatic run on each property card.

If a few days were missed (the server was down, say), the automatic run
closes them one per 15 minute check, oldest first, up to three days. A property more
than three days behind is not closed automatically: Hotel Admin and
Finance get an alert, so someone can check in-house stays and arrivals
before weeks of room nights and no-show fees are posted. Close those days
from Night Audit.

### If the business date looks stuck

A completed audit for the open business date with the date not rolled
(after a restore or ops change) shows **Date stuck**. Press **Advance
date**  -  Kamra moves the business date forward without posting room
nights again. You cannot undo a completed night audit. The automatic run
does the same on its own when it finds a stuck date, then closes the day
that is actually due.

## Settings

![Settings → Front Desk → Night audit checklist](/img/night-audit/settings.png)

| Setting | Where | Default | What it does |
| --- | --- | --- | --- |
| Open tills block the audit | Settings → Front Desk → Night audit checklist | On | Off lists open cashier sessions as a warning. |
| Open restaurant bills block the audit | Settings → Front Desk → Night audit checklist | On | Off lists them as a warning. |
| Departures still in house block the audit | Settings → Front Desk → Night audit checklist | On | Off lists them as a warning. |
| Extend unchecked-out departures one night | Settings → Front Desk → Night audit checklist | Off | On: a guest still checked in past their departure date gets one more night when the audit runs, through the same path as **Extend stay**, and that night is posted. A stay that can't be extended (the room is booked) stays on the checklist. The departures check lists these guests as a warning instead of a blocker. |
| Flag in-house folios owing more than | Settings → Front Desk → Night audit checklist | 50000 | 0 turns the high-balance check off. |
| Rate variance tolerance | Settings → Front Desk → Night audit checklist | 1 | How far (in currency units) a posted room night may be from the booked rate before it is listed. |
| Run the night audit automatically | Settings → Front Desk → Automatic night audit | On | Off: only staff close the day. |
| Run at | Settings → Front Desk → Automatic night audit | 03:00 | Property local time. |
| Wait after that time | Settings → Front Desk → Automatic night audit | 0 min | Up to 120 minutes extra, for outlets still posting. |
| Scheduled audit when checks block | Settings → Front Desk → Night audit checklist | Run and report exceptions | Or **Hold and alert**. |
| Mark no-shows | Settings → Front Desk → Night audit & no-shows | At audit for arrival date | **One day later** keeps the arrival Due In until the next day's audit. |
| Hold late arrivals until the next audit | Settings → Front Desk → Night audit & no-shows | On | An arrival due on the day being closed stays Due In if it is flagged **Late arrival** or its ETA is later than the moment the audit runs. An ETA before 06:00 counts as after midnight. |
| No no-show fee on OTA bookings | Settings → Front Desk → Night audit & no-shows | On | OTA bookings are still marked No Show, but no fee is posted. |
| When a no-show paid more than the fee | Settings → Front Desk → Night audit & no-shows | Refund | **Refund** or **Keep as forfeited deposit**: the choice offered first for the rest of the advance. |
| Release non-guaranteed arrivals at | Settings → Front Desk → Night audit & no-shows | Blank (off) | At this time, today's arrivals with no advance, payment or deposit, and not from an OTA or a company, are cancelled with no fee. |
| No-show charge | Settings → Stay policies → Cancellation & no-show | First Night | **None**, **First Night** or **Full Stay**. |

## Good to know

- **Anyone who can close the day can override a blocker.** The check
  is on the role (Front Desk, Finance, Night Auditor, Hotel Admin), and
  the name and reason are recorded.
- **Room nights bill the rate confirmed at booking.** A later rate
  change or a new season never changes a confirmed stay.
- **The audit never posts a night past the departure date.** A guest who
  is still in house after their departure date gets no night until you
  extend the stay.
- **Dashboards and reports count posted room nights**, so today's
  occupancy and room revenue show once the audit has run.

## Troubleshooting

**"Night audit is blocked: …"** A blocking check still has items. Resolve
them, or override each one with a reason under its list.

**"Business date … is already ahead of today."** Today's audit has
already run. The next one can run once the next calendar day has started.

**"Night audit can only close the current business date."** The audit
closes one date at a time, the one shown on the card.

**The automatic run didn't roll the date.** Check **Night audit runs**
for the reason. Usually the property is set to **Hold and alert** and
something was blocking: check the alert, clear the items and close the
day by hand. If automatic runs are off, nothing runs on its own.

## For developers

Agents run the same checklist with the `night_audit_precheck` MCP tool and
the audit with `run_night_audit` (blockers are acknowledged with a note):
see [MCP tools](/mcp-tools#night-audit). The page's endpoints
(`kamra.night_audit.eod_session`, `eod_progress` for notes, `eod_acknowledge`,
`eod_mark_no_show`, `eod_overview`, `night_audit_pack`,
`night_audit_history`, `night_audit_schedule`) are in the
[API reference](/api-reference#night-audit-end-of-day-checklist-audit-pack).
