---
title: ERPNext and Frappe HR with Kamra
description: Optional same-site accounting and HR - Marketplace, own server, and what each system owns.
---

# ERPNext and Frappe HR with Kamra

Kamra is the **hotel** system (rooms, folios, cashier, night audit, POS).
[ERPNext](https://erpnext.com) is the optional **company books** (chart of
accounts, invoicing, bank, tax reports). [Frappe HR](https://frappe.io/hr)
(`hrms`) is the optional **people** system (employees, leave, payroll).

You can run all three on **one Frappe site** - same login, same Apps
grid (`/apps`), different tiles for different jobs. Kamra’s Marketplace
install does **not** force ERPNext or HR: most hotels already use Tally,
Zoho, Xero, or a local accountant.

## Who owns what

| Concern | System |
| --- | --- |
| Guest folios, cashier till, night audit, POS cash | **Kamra** |
| Chart of accounts, GL, bank reconciliation, budgets | **ERPNext** |
| Payroll, leave, attendance | **Frappe HR** |
| Closed guest invoices → books (today) | **Kamra → Accounting Export** (CSV for Tally / Zoho / ERPNext) |

This matches the usual PMS pattern: front office feeds the ledger; it
does not replace it.

## Packaging (one Marketplace app, three practical setups)

1. **PMS only** - install Kamra (+ `payments`). Use Finance → Accounting
   Export for your existing ledger.
2. **PMS + books** - same site, also install **ERPNext**.
3. **PMS + books + HR** - same site, also install **Frappe HR** (after
   ERPNext).

Country or compliance apps (for example India Compliance) install on the
same site when you need them - they are not part of the Kamra package.

## Where to find the apps after install

Open **`/apps`** (or the app switcher in the Desk top bar):

- **Kamra** → hotel UI at `/kamra`
- **Accounting** (and Selling, Stock, …) → ERPNext workspaces
- **HR** / payroll → Frappe HR

Give staff roles so Front Desk lives in Kamra, Accounts in ERPNext, and
HR in Frappe HR.

## Frappe Cloud (Marketplace)

Marketplace **Kamra** only installs `payments` + `kamra` on your site.
To add books and HR on **that same site**:

1. Create a site on a **Frappe v16** bench (see
   [Frappe Cloud marketplace](/self-hosting/frappe-cloud)).
2. Marketplace → install **Kamra**. Complete `/kamra/setup`.
3. On the **same site**, install **ERPNext** from Marketplace / Site Apps
   (use a v16-compatible release - same major as your bench).
4. Optionally install **Frappe HR** (`hrms`) the same way (it depends on
   ERPNext).
5. Run ERPNext’s company / chart-of-accounts setup, then open `/apps` and
   confirm Kamra, Accounting, and HR tiles.

You do **not** need a second Frappe Cloud site for accounting.

**Versions:** Kamra is the approved Marketplace `main` SHA. ERPNext and
HR follow whatever Frappe Cloud ships on that v16 bench. Keep majors
aligned (Kamra + ERPNext + HRMS all on Frappe **v16**).

## Own server (bench)

After Kamra is running (see [Install with bench](/self-hosting/bench)):

```bash
cd frappe-bench

# Same major as your Frappe (v16)
bench get-app --branch version-16 erpnext
bench get-app --branch version-16 hrms

bench --site pms.yourhotel.com install-app erpnext
bench --site pms.yourhotel.com install-app hrms

bench --site pms.yourhotel.com migrate
bench build --app erpnext --app hrms
```

Then open `/apps`, finish the ERPNext setup wizard (Company, chart of
accounts), and map staff roles.

For **Docker** images built with only `payments` + `kamra`, either:

- add `erpnext` and `hrms` to your `apps.json` and rebuild the image, or
- `bench get-app` / `install-app` inside the backend container on an
  existing site (same commands as above).

Plan **more RAM** when ERPNext + HR share the box (8 GB is a safer
floor for a busy property than the Kamra-only 4 GB minimum).

## Own server - without ERPNext

If your accountant stays on Tally, Zoho, or another ledger:

1. Install Kamra only.
2. In Kamra: Finance → **Accounting Export**.
3. Download closed invoices in the format your books import.

No ERPNext required.

## Day-to-day bridge

### Without ERPNext on the site

Close stays and settle folios in Kamra, export from **Accounting
Export**, and import into Tally, Zoho or your ledger.

### With ERPNext on the same site: post the day automatically

Settings → Finance → **ERPNext books** (Finance and Hotel Admin):

1. Set the **ERPNext company** (and a **cost center** if you use one).
2. Fill the **account map**, one `key = ERPNext account` per line:

   ```
   Guest = Guest Ledger - HC
   Deposit = Guest Deposits - HC
   AR = City Ledger - HC
   Package = Package Ledger - HC
   Tax = Output Tax - HC
   4000 = Room Revenue - HC      # a GL code (set on the transaction code)
   3000 = Laundry Revenue - HC   # or a transaction code
   9001 = Cash - HC
   ```

   Map the four Kamra ledgers to plain asset or liability accounts, not
   to a Receivable or Payable account type: ERPNext asks for a party on
   those, and a day's total has none.
3. Switch on **Post the day to ERPNext at night audit**.

After each night audit, the closed business date goes to ERPNext as one
submitted **Journal Entry**. Every Kamra ledger posting is one leg (its
ledger account); the other leg is the account of the GL code the line
was posted with (else its transaction code), with a charge's tax split
out to **Tax**. The entry always balances, so the day's revenue ties to
the GL with no manual export. Each business date posts once. If a key is
missing from the map, nothing posts for that day and the error log says
which keys to add; then post it again.

For developers: `kamra.erpnext_bridge.preview_daily_journal` (what a
date would post, and the missing keys - works without ERPNext),
`post_daily_journal`, and `reverse_daily_journal` (cancels the entry in
ERPNext, which writes the reversing GL, so the date can post again after
a correction). Each post is kept in **ERPNext Sync Log**.

### Supplier bills

With **Post supplier bills to ERPNext** on, an approved supplier bill
posts a Journal Entry against the ERPNext **Supplier** (created from the
vendor's name when missing, in the supplier group you set): debit the
account mapped for its expense category (else `Expense`) and `Purchase
Tax`, credit `Creditors` with the supplier as party. Each payment clears
it: debit `Creditors`, credit `Pay:<mode>` (for example `Pay:Bank
Transfer`) or `Bank`. A post that fails never blocks the bill;
`kamra.erpnext_bridge.sync_vendor_bills` posts whatever is missing.
Ingredient stock stays in Kamra; it is not mirrored to ERPNext stock.

### Frappe HR: link staff to their Employee

With Frappe HR installed, `kamra.erpnext_bridge.staff_employees` lists
each Kamra login with its Employee, and `link_employee(user, employee)`
links them through the Employee's own **User ID**, so HR and Kamra agree
on who is who. Payroll journals from Frappe HR post into the same
ERPNext company.

## What Kamra will not do

- Bundle ERPNext or HR into every Marketplace install
- Replace Chart of Accounts, bank recon, or statutory filings inside
  the PMS
- Rebuild payroll inside Kamra

## Related

- [Frappe Cloud marketplace](/self-hosting/frappe-cloud)
- [Install with bench](/self-hosting/bench)
- [Quickstart (Docker)](/quickstart)
- [Features - billing & export](/features)
