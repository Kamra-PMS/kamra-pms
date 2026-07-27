# Channel manager (OTA sync)

Kamra syncs availability and rates to the OTAs — and receives their
bookings — through a channel manager. The integration is a provider
seam: adapters ship for **Channex.io** (usable today, self-serve),
**STAAH** and **AioSell** (ready; they activate with the credentials
those companies issue to connectivity partners).

## Recommended: Channex.io, bring your own account

[Channex.io](https://channex.io) is API-first channel-manager
infrastructure — self-serve signup, per-property pricing paid directly
to them, certified with Booking.com, Agoda, Expedia, Airbnb and more.

1. Create a Channex account, add your property and rooms, connect your
   OTA channels in their dashboard.
2. In Kamra: *Revenue → Channel Manager → New*: provider **Channex**,
   your Channex **user API key**, the Channex **property id**, and a
   **webhook secret** you invent. Tick Active.
3. *Revenue → OTA Room Mappings*: one row per room type — your room
   type against the Channex `room_type_id` and `rate_plan_id`.
4. In Channex, register a **booking webhook** pointing at
   `https://YOUR-SITE/api/method/kamra.channel_manager.webhook?connection=CMC-XXXXX`
   (the exact URL shows on the connection row), sending your secret in
   the `X-Webhook-Secret` header.

That's the whole setup. From then on:

- **Availability and rates push automatically** — every hour, and again
  right after any booking lands (from any source), so an OTA can't
  oversell a room the front desk just gave away. Rates come from the
  pricing engine with demand premiums and hurdle floors applied.
- **OTA bookings arrive as reservations** — source OTA, the channel's
  name and booking reference kept, the guest matched by phone/email or
  created, the OTA's sell price preserved (never re-priced), and the
  same capacity and double-booking rules a front-desk booking obeys.
  Modifications and cancellations match on the OTA reference.
- The connection row shows the **last push and its result**; failures
  land in the activity log.

## STAAH and AioSell

Both adapters ship in the codebase with the transport isolated to one
function each. To activate: join
[STAAH's connectivity-partner program](https://www.staah.com) or ask
[AioSell](https://aiosell.com/connect-to-aiosell/) for PMS-connect
access, then enter the credentials and endpoint they issue on the
connection row. No code changes needed for the standard flows; field
name adjustments against their partner docs are expected on first
certification.

## Is any of this gated?

No. The integrations are open source like everything else. You pay the
channel manager directly for their service; on Kamra Cloud we can
bundle and manage it for you as a connected service.
