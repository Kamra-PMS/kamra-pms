# Email (SMTP) setup

Kamra uses Frappe's built-in email stack - no custom mailer. You need one
**outgoing** account (confirmations, invoices, briefings) and optionally
an **incoming** one (replies → Frappe inbox).

## 1. Get SMTP credentials

Any provider works: Amazon SES, Zoho Mail, Google Workspace, Mailgun,
Postmark, or your hotel's existing mail host. You need the SMTP host,
port (587 STARTTLS typical), username and password/app-password.

## 2. Create the Email Account

Frappe Desk (`https://your-site/app`) → **Email Account → New**:

- Email address: `frontdesk@yourhotel.com`
- Enable **Outgoing**, set SMTP server/port/credentials
- Tick **Default Outgoing** (exactly one account must have this)
- Optional: enable Incoming (IMAP) to capture replies

Send a test from **Email Account → Send Test Email**.

## 3. Deliverability (do not skip)

Add **SPF, DKIM and DMARC** DNS records for the sending domain - without
them, booking confirmations land in spam. Your SMTP provider documents
the exact records.

## 4. What sends email

- Booking/invoice emails triggered from documents (Print → Email)
- Frappe **Notification** rules (e.g. new website bookings, SLA breaches)
- Scheduled digests wired to the owner-briefing API

Monitor the **Email Queue** doctype for sent/failed messages; the
scheduler must be enabled for background sending.
