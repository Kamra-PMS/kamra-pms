# Try the live demo

**[demo.kamrapms.com](https://demo.kamrapms.com)** runs the latest stable
release, seeded with a full sample hotel — rooms, guests, reservations,
folios, a restaurant menu and experiences. It's shared and **resets every
night**: create bookings, post charges, break nothing. Don't run a real
property on it.

To wipe and reseed by hand:

```
bench --site demo.kamrapms.com execute kamra.scripts.reset_demo.execute
```

## One-tap logins

The sign-in screen shows a button per role. Each opens the same hotel
through different eyes. **This is a shared playground, not a live PMS** —
bookings, extra properties, users and pasted API keys are wiped every
night at 04:15 (site time). Don't put real guests or payments here.

| Role | What they see |
| --- | --- |
| System Admin | Everything, plus user management and developer settings |
| Hotel Admin (GM) | Runs the property end to end, no IT surfaces |
| Front Desk | Bookings, check-in/out, folios, night audit |
| Revenue | Rate plans, seasons, vouchers, guardrails |
| Finance | Billing, GST invoices, reports |
| Housekeeping | The room board and the floor phone app |

## Worth trying

- The **guest booking page**: [demo.kamrapms.com/book](https://demo.kamrapms.com/book) — no login
- The **housekeeping phone app**: `/hk` on a phone
- The **restaurant POS + kitchen display** under the F&B app
- A **QR menu**: F&B → Outlets, then `/menu/<outlet>` as a guest would

There's also **nightly.kamrapms.com** running the develop branch — newest
features, occasionally rough.
