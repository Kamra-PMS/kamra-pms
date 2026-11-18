# Kamra Enterprise

Enterprise is an opt-in in the same open-source app. Community stays the
default and keeps every feature it has today. Enterprise adds the tools
below. There is no licence key and no per-room fee.

## Turn it on

1. Open **Settings → Enterprise**.
2. Set **Edition** to **Enterprise**.
3. Switch on only the pieces you want. Pricing, SMS, surveys, housekeeping
   priority, maintenance and the website each have their own switch.
4. Save provider secrets on the **Enterprise** desk. They are stored
   encrypted and are not written into the activity log.

A whole site can force the edition with `site_config.json`:

```json
{ "kamra_edition": "Enterprise" }
```

That turns the edition on for every property. The individual switches
still decide which jobs run.

The desk is at `/kamra/enterprise`. MCP tools for the same calls are in
the [tool reference](/mcp-tools). A property left on Community gets a
clear refusal from those calls.

## What each claim does

| Brochure claim | Where it lives | How it behaves |
| --- | --- | --- |
| Dynamic pricing | Settings → Enterprise → Dynamic pricing | **Suggest** shows a forecast and does not change quotes. **Auto** passes predicted occupancy into your hurdle tiers. If no tier matches, an open band applies and the rate guardrail still holds. Quotes, the booking page and the channel manager all read that rate. |
| Occupancy forecast | Enterprise desk, `occupancy_forecast` | Rooms already sold, plus pace and the same weekday's history. Peak and low days, and a staffing hint of about 14 cleans per attendant. |
| Guest offers | Guest profile and `guest_recommendations` | Dietary notes, preferred room type and view, special occasions, plus earlier stays and outlet charges. The desk sees offers. Nothing is posted by itself. |
| Anomaly alerts | Enterprise desk, after 04:30 | Compares room revenue, other revenue, payments, vendor bills and occupancy with earlier same-weekdays. Opens an alert when the move is both statistically unusual and at least the minimum percent. |
| ERPNext journals | Settings → Enterprise → ERPNext sync | One summary journal per day for closed invoices. **Same site** needs ERPNext installed. **Remote** POSTs to your ERPNext URL with an API token. Missing accounts or a failed call are reported as a failure. CSV export for Tally and Zoho is unchanged. |
| SMS | Settings → Enterprise → SMS provider | **Log** stores the text and does not send it. **HTTP** POSTs `{to, from, text, property, purpose}` to your URL. A 2xx response counts as sent. |
| VIP welcome | VIP welcome switch | The 06:00 job messages VIP arrivals in the next two days by SMS (if configured), email and WhatsApp. |
| Satisfaction survey | Surveys switch | The morning after check-out, Kamra sends a link. The guest scores 1 to 5 at `/kamra/survey/<token>`. |
| Property website | Property website switch | Public pages at `/hotel/<slug>`: rooms, facilities, gallery, policies, questions, and a link to book. Arabic and English follow the guest language. Facilities group amenities written as `Pool: heated`. `/stay` and `/book` stay available either way. |
| Key encoder | Settings → Front Desk → Door locks = HTTP | At check-in Kamra POSTs `action: issue` with the room and the stay window. The secret is sent as `Authorization: Bearer <secret>`. A failure does not undo check-in. The manual adapter is still the default. |
| Arrival-priority housekeeping | Prioritize cleans by arrival | Pending departure cleans for a same-day arrival become High. A VIP, or an arrival by noon, becomes Urgent. |
| Preventive maintenance | Maintenance plans on the Enterprise desk | A plan with an interval opens a Maintenance ticket when it is due, then moves the next date forward. |

## SMS and encoder contract

Both adapters are HTTP. Kamra does not ship a vendor account.

SMS body:

```json
{"to": "+967...", "from": "HOTEL", "text": "...", "property": "Wadi Jarif", "purpose": "vip_welcome"}
```

Set the auth header name in Settings. The default is `Authorization`. A raw
token is sent as `Bearer <token>`. If your vendor wants a different scheme,
paste the full header value and set the header name.

Encoder body:

```json
{"action": "issue", "room_number": "204", "valid_from": "...", "valid_to": "...", "key_count": 2}
```

`action` is `issue` or `revoke`. A 2xx JSON body may include `key_ids`.
`{"ok": false, "message": "..."}` is shown to the desk.

You can still register a Python `DoorLockAdapter` from another Frappe app.
See [Integrations](/integrations).

## ERPNext accounts

Set the debtors account and the room revenue account. Food and beverage
uses its own account when you set one, otherwise it folds into room
revenue. Tax uses its account, or folds into room revenue when you leave
it blank, so the journal still balances.

The voucher `cheque_no` is `KAMRA-<property>-<date>`. A second run on the
same date returns the existing journal instead of posting another.

## Jobs

| Time | What |
| --- | --- |
| 04:30 | Anomaly scan and ERPNext sync for yesterday, when those switches are on |
| 06:00 | VIP welcomes, departure surveys, arrival-priority cleans, due maintenance |

Community properties are skipped.
