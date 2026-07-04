# Self-hosting Kamra

Own your PMS end to end. Two supported paths: **Docker (recommended)** or a
classic bench install.

## Prerequisites

**Server**

- Ubuntu 22.04/24.04 LTS (or any Docker-capable Linux)
- 2 vCPU / 4 GB RAM minimum (8 GB recommended for 20+ rooms + POS)
- 40 GB disk (database grows with folios/audit history)
- A domain or subdomain (e.g. `pms.yourhotel.com`) pointed at the server
- Ports 80/443 open; SSL via Let's Encrypt (frappe_docker or certbot)

**Software (Docker path)**

- Docker Engine ≥ 24 + Docker Compose v2 — that's it.

**Software (bare-metal bench path)**

- Python **3.14** (Frappe v16 requirement) · Node **≥ 20** + yarn
- MariaDB **10.6+ / 11.x** (utf8mb4) · Redis
- wkhtmltopdf (invoice PDFs) · nginx + supervisor (production)

**Accounts / keys (optional but typical)**

- SMTP credentials for email ([email setup](email-setup.md))
- Razorpay/Stripe keys for payment links (configure in the payments app)
- An LLM API key on your side if you connect an AI agent (BYOK — Kamra
  never proxies or marks up model calls)

## Install (Docker, recommended)

Use [frappe_docker](https://github.com/frappe/frappe_docker) and add Kamra
to your apps list:

```bash
git clone https://github.com/frappe/frappe_docker && cd frappe_docker
# build a custom image containing kamra + payments
export APPS_JSON_BASE64=$(base64 -w0 <<'EOF'
[
  {"url": "https://github.com/frappe/payments", "branch": "develop"},
  {"url": "https://github.com/Kamra-PMS/kamra-pms", "branch": "main"}
]
EOF
)
docker build -t yourorg/kamra:latest \
  --build-arg FRAPPE_BRANCH=v16.25.0 \
  --build-arg APPS_JSON_BASE64=$APPS_JSON_BASE64 \
  -f images/layered/Containerfile .
# then follow frappe_docker's compose guide (pwd.yml / docs) with your image
```

Create the site and install:

```bash
bench new-site pms.yourhotel.com --admin-password <strong-password>
bench --site pms.yourhotel.com install-app payments kamra
```

## Install (bare metal)

```bash
pip install frappe-bench
bench init --frappe-branch v16.25.0 frappe-bench && cd frappe-bench
bench get-app payments
bench get-app kamra https://github.com/Kamra-PMS/kamra-pms
bench new-site pms.yourhotel.com --admin-password <strong-password>
bench --site pms.yourhotel.com install-app kamra
sudo bench setup production $(whoami)   # nginx + supervisor + SSL
```

## After install — production checklist

1. **Create your property** — log in → Admin → *New Property* (the wizard),
   or connect an AI agent and say "onboard my hotel".
2. **Roles & users** — create staff users; see `kamra/scripts/seed_users.py`
   for the role model (Hotel Admin / Front Desk / Revenue / Finance /
   Housekeeping).
3. **Agent access** — run `kamra.scripts.seed_rbac_v2` to create the agent
   user + API keys; connect via [MCP](../mcp/kamra_mcp.py). Regenerate keys
   per deployment; never reuse dev keys.
4. **Email** — [set up outgoing email](email-setup.md) for confirmations,
   invoices and briefings.
5. **Payments** — add gateway keys in the payments app's settings (e.g.
   *Razorpay Settings*), then enable per-property *Payment Gateway
   Settings* (turn **off** test mode).
6. **Scheduler** — ensure `bench --site <site> enable-scheduler`; the night
   audit runs at 03:00 site time.
7. **Backups** — `bench --site <site> set-config backup_limit 10` and wire
   `bench backup --with-files` to cron/off-site storage. It's your data —
   that's the point.
8. **Security** — `developer_mode 0`, `ignore_csrf 0` (production default),
   strong admin password, and HTTPS only.

## Updating

```bash
cd frappe-bench/apps/kamra && git pull
bench --site pms.yourhotel.com migrate
bench build && bench restart
```

The eval harness (`kamra/scripts/eval_harness.py`) can be run via
`bench console` after any update — 12 checks on money, tax and
availability logic.
