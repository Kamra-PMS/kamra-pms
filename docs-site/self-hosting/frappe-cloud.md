# Install via Frappe Cloud

[Frappe Cloud](https://frappecloud.com) is managed Frappe hosting by the
framework's makers — Marketplace installs, backups and updates handled for
you.

::: danger Shared trial sites cannot install Kamra
You need a **private bench** (payment method on file; Frappe’s USD 25+
site plans). Shared / trial sites only install featured apps — Kamra will
not appear there. Do not start on a trial site and expect to “upgrade into”
Marketplace installs.
:::

## Foolproof checklist

1. **Sign up** at Frappe Cloud and **add a payment method**.
2. Create a **private bench group** on **Frappe v16**.
3. Create a **new site** on that bench (not a shared trial site).
4. On the bench: **Marketplace → search Kamra → Add** → deploy.
5. On the site: **Install app** Kamra (`payments` comes with it).
6. Open **`https://<your-site>/kamra`** — **not** `/app`.
7. Sign in as **Administrator** with the site password from create-site
   (there is no Kamra default password).
8. You are sent to **`/kamra/setup`** until the first property exists.
   Desk tiles (Accounting, Stock, …) appear only if you later install
   ERPNext — they are not Kamra.

Kamra itself is free on Frappe Cloud. Billing is only for the site.

Product walkthrough: [live demo](https://demo.kamrapms.com).

## What a Marketplace install actually does

Frappe Cloud clones `Kamra-PMS/kamra-pms` at the approved `main` SHA,
installs `payments`, then `bench --site <site> install-app kamra`. It
does **not** run `npm`. The UI is the committed build under
`kamra/public/frontend`.

That is why every release must keep:

- `pyproject.toml` with `requires-python >= 3.10` and Frappe
  `>=16.0.0-dev,<17.0.0`
- `required_apps = ["payments"]`
- `add_to_apps_screen` + `/kamra/<path:app_path>` route
- the prebuilt SPA (`index.html` pointing at `/assets/kamra/frontend/`)

## Simulation we run before each release

Two layers, both in GitHub Actions:

1. **Offline pack check** (`python kamra/scripts/marketplace_install_check.py`)
   — the same gates FC's auditor cares about, without MariaDB.
2. **Full bench path** (CI job *Backend eval harness*) —
   `bench init` → `get-app payments` → `get-app kamra` → `new-site` →
   `install-app kamra` → eval harness + front-desk journey +
   fresh-install role/SPA asserts.

Locally (from a clone of `main`):

```bash
python kamra/scripts/marketplace_install_check.py
```

## Optional: ERPNext and Frappe HR on the same site

Marketplace Kamra does **not** install company books or HR. If you want
Accounting and payroll on the **same** Frappe Cloud site, install
**ERPNext** and optionally **Frappe HR** from Site Apps / Marketplace
after Kamra. Those apps add Desk workspaces — the hotel still runs at
`/kamra`. Full steps: [ERPNext and Frappe HR with Kamra](/self-hosting/erpnext-hr).
