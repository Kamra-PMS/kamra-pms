# Unit owners - a login for each owner, scoped to their units

For property managers who run units for several owners (serviced
apartments, holiday rentals, hotels with investor-owned rooms). Each
owner gets a login that sees **only their own units**: a calendar,
occupancy, bookings, room revenue and a monthly statement.

Open it from **Admin → Unit owners** (Hotel Admin). An owner signs in
and lands on their portal.

## Set up an owner

1. Press **Add owner** and type the owner's name.
2. Tick their **units**, and/or whole **unit types**. A unit type gives
   the owner every unit of that type, including units you add later.
3. Add one or more **login emails**: the owner, and for example their
   accountant. A new address becomes a login with no welcome mail; set its
   password in **Staff & Access**.
4. Pick the access:
   - **Read only** (default): calendar, occupancy, bookings, revenue and
     statements.
   - **Manage**: also hold a unit off sale, book a stay in one of their
     units, and set the rate of a unit type they own outright (every unit
     of that type is theirs, so the rate prices nobody else's unit).
5. Set the **commission %**. A unit can have its own percent (the box
   next to a ticked unit); blank uses the owner's.
6. **Show guest name and phone** is off by default. Identity documents
   are never shown to an owner.

Each login gets the Owner role and Frappe User Permissions on exactly
those rooms and the property, so the rest of Kamra stays closed to them.

## What Manage can do, and what still applies

A Manage owner's booking and rate go through the same functions the desk
uses, run as the governed agent login: availability, capacity, pricing,
the property's rate floor and ceiling and hurdle rates all apply. An
owner can't book or hold another owner's unit, or a unit already booked.

## Costs and the monthly statement

Press **Add cost** on an owner to charge them a cost (cleaning, a repair,
a fee) with a date. The owner's **Statement** for a month shows, per
unit, room nights, room revenue and commission, then the costs dated in
that month, and the payout:

> payout = room revenue - commission - costs

**Download statement** saves it as a CSV. Guest names are never on it.

## Owners with units at several properties

An owner whose units are at more than one property gets an **All my
properties** tab beside **This property**. It shows occupancy, room nights
and room revenue for each property and in total, and one month's statement
with the payout per property and overall. **Download statement** saves
every property's lines in one CSV. Press a property to open its own view.

Only properties the login is permitted for are listed. When the
properties use different currencies, the totals say **Mixed currencies**
instead of adding them up.

## Not yet

Role Profiles ("Owner - read-only", "Owner - manage") adjustable in the
Role Permission Manager come with the access-control work (#421). Until
then the owner record is the switch.

## For developers

`kamra.owners`: `my_portal`, `my_statement`, `my_overview`, `block_unit`,
`release_block`, `book_unit`, `set_unit_rate` (Owner role);
`desk`, `save_owner`, `add_owner_cost` (Hotel Admin).
