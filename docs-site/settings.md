# Settings

Everything a property configures lives in **Settings** (the gear in the
side bar). Each part of Kamra has its own page, and each page says who may
change it. Every change is checked against its limits and written to the
**Activity Log** with the old and new values.

![The settings hub: pages grouped as Property, Modules, Access, Integrations and You](/img/settings/hub.png)

## Find a setting

Type in **Search settings** (or press **/**) and pick the result. It opens
the right page and scrolls to the setting.

![Searching settings for no-show and jumping to it](/img/settings/search.gif)

## Change a setting

1. Open the page (for example **Front Desk**).
2. Change the values. Each changed setting gets an amber dot, and a bar at
   the bottom counts the unsaved changes.
3. Press **Save changes** in that bar (or **Discard**). If a value is out of range
   ("can't be above 60"), nothing is saved and the page says which one.

A setting that isn't at its default shows **Reset to default** under it.

![A module settings page with its sections and the module switch](/img/settings/module-page.png)

You only see the pages your role may change. The **Changed by** line under
each page title lists those roles; Hotel Admin can change all of them.

## The pages

| Page | What's on it | Guide |
| --- | --- | --- |
| Property | Name, legal name, logo, country (which selects the tax and invoicing pack), currency, time zone, address, tax registration number | [Country setup](/country-setup) |
| Stay policies | Check-in and check-out times, minimum stay, free cancellation window, cancellation and no-show fees, deposits | [Reservations](/reservations) |
| Privacy & data | How long guest data and messages are kept, the privacy contact | |
| Front Desk | Arrivals, holds, no-shows and the day view | [Front desk](/front-desk) |
| Housekeeping | Task deadlines, room turnover and laundry pricing | [Housekeeping](/housekeeping) |
| Operations | Guest request deadlines by priority | [Operations](/operations) |
| F&B | Auto-accept KOT, void slips, table reservation window, kitchen printers, POS speed check | [F&B](/fnb#settings) |
| Banquets & Groups | Quotation margins, payment milestones, follow-ups | [Banquets](/banquets) |
| Revenue | How far the house may oversell, demand pricing | [Revenue](/revenue) |
| Finance | Room tax, fees, cashier controls (PIN, cash refund limits) | [Billing](/billing) |
| Booking Engine | The public `/book` page: on or off, instant or request to book, how guests pay | [Booking engine](/booking-engine) |

Pages for the parts of Kamra you can switch off (Housekeeping, Operations,
F&B, Banquets, Revenue, Booking Engine…) have a **Module on** switch at the
top. Only Hotel Admin can switch modules. A module that's off disappears
from the side bar for everyone, and its tools are hidden from AI agents.

## Add staff and give access

**Settings → Staff & access** lists everyone who can sign in, with their
roles and the properties they can reach.

![Staff & access: each person's roles and property access](/img/settings/staff.png)

1. Press **Add staff**.
2. Enter their **Full name** and **Email** (they sign in with it).
3. Tick their **Roles**. Each role says what it opens.
4. Choose **Property access**: all properties (including ones added
   later), or only some.
5. Leave **Email them a link to set a password** on to send an invite, or
   turn it off and share access yourself.

![The Add staff panel with the role descriptions](/img/settings/add-staff.png)

To change someone later, press **Manage** on their row. From there you can
change roles and properties, **Reset cashier PIN**, or **Deactivate** them.
Deactivated staff can't sign in, and their history stays. You can't change
your own access, and only IT can change an IT administrator.

## What each role can do

**Settings → Roles & permissions** shows which apps each role opens and
which settings pages it may change. Roles are fixed bundles: every screen,
API call and AI tool checks them on the server.

![The roles matrix: apps each role opens and settings each role may change](/img/settings/roles.png)

| Role | Day to day |
| --- | --- |
| Hotel Admin | Runs the property: every app, all settings, staff and access |
| Front Desk | Bookings, check-in and out, guests, folios, the cashier till |
| Revenue Manager | Rates, seasons, guardrails, channels, the booking engine, banquet sales |
| Finance | Billing, ledgers, night audit, exports, tax and cashier controls |
| Night Auditor | End of Day: arrivals, departures, cashier closure, the audit pack |
| Housekeeping Supervisor | The room board, inspections, task deadlines, laundry pricing |
| Housekeeping | Their own tasks, room status, lost & found, usually on the phone app |

IT (System Manager) also manages developer keys and adds properties.

## Switch modules off

**Settings → Modules** lists every module with its switch, so you can turn
off what this property doesn't run (a guesthouse with no restaurant turns
F&B off). Its apps leave the launcher, search and the AI agent's tools for
everyone. Front Desk and Admin are always on. Nothing is deleted;
switching a module back on brings it back as it was.

![Settings → Modules](/img/settings/modules.png)

## Integrations

- **Payments**: the gateway used for payment links (advances, deposits,
  folio settlement). Which gateways are offered depends on the country
  pack. See [Billing](/billing).

  ![Payments settings](/img/settings/payments.png)

- **AI assistant**: bring your own AI key (any OpenAI-compatible service)
  for **Kamra Agent** in the console. Guest contact and ID fields are
  removed before anything is sent to the model.

  ![AI assistant settings: provider, model and key](/img/settings/ai.png)

- **Claude & MCP**: let staff connect Claude to this property's tools. See
  [Connect your AI](/ai-and-mcp).
- **ZATCA e-invoicing**: shown for Saudi Arabia only. See
  [Country setup](/country-setup).

## Appearance

**Settings → Appearance** sets the theme (light, dark or follow the
system) and the language
for this browser only. Choosing Arabic switches the layout to right to
left.

![Appearance: theme and language](/img/settings/appearance.png)

## Good to know

- Settings are per property. With several properties, switch property at
  the top of the screen before changing them.
- Nothing else writes these values: the night audit, booking engine and
  POS all read the same settings, so a change takes effect at once.
- The Activity Log (**Admin → Activity Log**) shows who changed which
  setting, when, from what to what.

## For developers

Pages and values come from one registry in `kamra/settings.py`
(`settings_schema`, `save_settings`); code reads a value with
`get_setting(property, key)`. Staff and roles are in `kamra/staff.py`. See
the [API reference](/api-reference).
