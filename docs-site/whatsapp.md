# WhatsApp on your own number

Kamra talks to guests over WhatsApp through **Meta's official Cloud
API**, on a number you own. Nothing sits in between: no gateway
markup, no per-message fee to Kamra — Meta bills you directly at
their per-conversation rates (marketing/utility conversations are a
few cents; most hotel traffic falls in the cheaper *utility* bucket,
and guest-initiated *service* conversations are free).

What you get once connected:

- **Booking confirmation + self check-in link** sent automatically on
  every confirmed booking
- **Payment requests** from the desk
- **Guest replies** land in *Operations → WhatsApp* as chat threads,
  and messages from in-house guests also raise a Service Ticket
- Housekeeping SLA escalations to managers on WhatsApp

## Step 1 — get a WhatsApp Business number from Meta

You need a Meta developer app with the WhatsApp product. About 20
minutes, free:

1. Go to [developers.facebook.com](https://developers.facebook.com) →
   **My Apps → Create App** → type **Business**.
2. In the new app, click **Add product → WhatsApp → Set up**. Meta
   attaches a *test number* immediately — fine for trying things out.
3. To use **your own number**: WhatsApp → **API Setup → Add phone
   number**. The number must not be registered on the WhatsApp app
   (a fresh SIM or a landline that can receive a verification call
   works well). Complete [business verification](https://www.facebook.com/business/help/2058515294227817)
   in Meta Business Manager — this is the step that takes a day or
   two of Meta's review.
4. From **WhatsApp → API Setup**, note two values:
   - **Phone number ID** (a long number under the phone dropdown)
   - a **permanent access token**: create a *System User* in
     [Business settings → Users → System users](https://business.facebook.com/settings/system-users),
     give it access to the app with the `whatsapp_business_messaging`
     permission, and **Generate token** with no expiry.

## Step 2 — connect it in Kamra

*Operations → Channels → New* (you need the Hotel Admin role):

| Field | Value |
|---|---|
| Channel | WhatsApp |
| Provider | Meta Business |
| Phone number (display) | your number, e.g. `+91 98…` |
| Meta phone number ID | from API Setup |
| Access token | the permanent System User token |
| Webhook verify token | any string you invent — you'll paste the same one into Meta |
| Template language code | `en` (or the language your templates are approved in) |
| Active | ✓ |

## Step 3 — point Meta's webhook at Kamra

This is what makes **incoming** guest messages appear.

1. In the Meta app: **WhatsApp → Configuration → Webhook → Edit**.
2. Callback URL:
   `https://YOUR-SITE/api/method/kamra.whatsapp.webhook`
3. Verify token: the same string you entered on the Channels screen.
   Click **Verify and save** — Kamra answers Meta's challenge.
4. Under **Webhook fields**, subscribe to **messages**.

From now on, anything a guest writes to your number shows up in
*Operations → WhatsApp* as a conversation thread, and — if the sender
matches an in-house guest — raises a Service Ticket on the desk queue.

## Step 4 — register your message templates

WhatsApp only lets a business **start** a conversation with a
pre-approved template (guests writing to you first need no template —
that opens a free-form 24-hour session). Create these in
[Meta Business Manager → WhatsApp Manager → Message templates](https://business.facebook.com/wa/manage/message-templates/),
category **Utility**, then put their names on the Channels screen.

**`kamra_booking_confirmation`** — variables are guest, property,
check-in, check-out:

> Hello {{1}}! Your booking at {{2}} is confirmed — arriving {{3}},
> departing {{4}}. We look forward to hosting you. Reply to this
> message any time; a person answers.

**`kamra_precheckin_link`** — guest, link:

> {{1}}, skip the front-desk queue: complete your check-in online
> before you arrive — {{2}}

**`kamra_payment_request`** — guest, amount, note:

> Hello {{1}}, a payment of {{2}} is due for your stay ({{3}}). You
> can pay online or at the front desk.

Approval usually takes minutes for Utility templates. Once approved,
type each template's exact name into the matching field on the
Channels connection.

::: tip Designing more templates
The community [frappe_whatsapp](https://github.com/shridarpatil/frappe_whatsapp)
app has a visual, drag-and-drop template builder with a live
compliance checklist ([PR #247](https://github.com/shridarpatil/frappe_whatsapp/pull/247)) —
useful for prototyping template copy before you register it with Meta.
:::

## Step 5 — send and receive

Nothing else to configure:

- **Automatic**: every new confirmed booking sends the confirmation
  and, if the template is set, the self check-in link. Housekeeping
  escalations go to the manager's number.
- **Conversations**: *Operations → WhatsApp* is the inbox — threads on
  the left, chat on the right, reply box at the bottom. Replies
  deliver free-form while the guest's 24-hour session window is open
  (any guest message reopens it); outside the window, WhatsApp only
  accepts templates, and the screen tells you so.
- **Payment requests**: from the stay, `send_payment_request` posts
  the amount with your payment template.
- Every message in both directions is stored as a *WhatsApp Message*
  record, so the history is queryable and auditable.

## Campaigns and marketing broadcasts

Kamra's built-in integration is deliberately **transactional** — the
messages a stay generates. For marketing broadcasts (offers to past
guests, campaign blasts), install the community
[frappe_whatsapp](https://github.com/shridarpatil/frappe_whatsapp)
app alongside Kamra on the same bench:

```bash
bench get-app https://github.com/shridarpatil/frappe_whatsapp
bench --site yoursite install-app frappe_whatsapp
```

It uses the same Meta credentials, adds template syncing from Frappe,
notification-on-doctype-event rules, and bulk sends. Keep marketing
lists consented — WhatsApp bans numbers that message people who
didn't opt in.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| Webhook verification fails | Verify token on the Channels screen doesn't match what you typed in Meta, or the connection isn't Active |
| Outbound shows **Failed** with `(#132001)` | Template name or language doesn't match an approved template |
| Outbound Failed with `Re-engagement message` | The 24-hour session closed — use a template, or wait for the guest to write |
| Messages send but nothing arrives inbound | Webhook fields not subscribed to **messages** |
| `401` from Meta | Token expired — use a System User token, not the 24-hour test token |
