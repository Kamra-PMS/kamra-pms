# Install with bench (bare metal)

For teams who prefer a classic Frappe bench over Docker.

## Prerequisites

- Python **3.14** (Frappe v16 requirement) · Node **≥ 20** + yarn
- MariaDB **10.6+ / 11.x** (utf8mb4) · Redis
- wkhtmltopdf (invoice PDFs) · nginx + supervisor for production

## Install

```bash
pip install frappe-bench
bench init --frappe-branch v16.25.0 frappe-bench && cd frappe-bench
bench get-app payments
bench get-app kamra https://github.com/Kamra-PMS/kamra-pms --branch main
bench new-site pms.yourhotel.com --admin-password <strong-password>
bench --site pms.yourhotel.com install-app kamra
sudo bench setup production $(whoami)   # nginx + supervisor + SSL
```

Kamra ships its built front-end, so the product UI is live at `/kamra`
immediately — no Node server in production. Sign in as `Administrator` or
`admin@example.com` with the `--admin-password` you just set.

Continue with the
[production checklist](/self-hosting/#after-install-production-checklist).
