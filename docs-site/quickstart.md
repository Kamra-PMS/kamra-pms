# Quickstart (Docker)

The fastest path to a running Kamra: one Docker-capable Linux server,
**three questions**, roughly ten minutes. We **pull** the published image —
we do not compile Frappe on your VPS.

## What you need

- A server or VPS: **2 vCPU · 4 GB RAM · 40 GB disk** (Ubuntu 22.04/24.04)
- Docker Engine ≥ 24 with Compose v2 (the installer can install Docker for you)
- A domain (e.g. `pms.yourhotel.com`) pointed at the server

::: tip Where to get a server
One-click / affiliate paths: [Hostinger](/self-hosting/hostinger),
[DigitalOcean](/self-hosting/digitalocean), [Linode](/self-hosting/linode).
Or [AWS](/self-hosting/aws). Prefer managed? [Frappe Cloud](/self-hosting/frappe-cloud)
or [Kamra Cloud](https://kamrapms.com/cloud/).
:::

## One command

```bash
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | bash
```

You will be asked for:

| Field | Example |
| --- | --- |
| Site domain | `pms.yourhotel.com` |
| Admin email | `you@yourhotel.com` |
| Admin password | (min 10 characters — **there is no default**) |

The script pulls `ghcr.io/kamra-pms/kamra:latest`, starts MariaDB + Redis +
Kamra, creates the site, installs `payments` + `kamra`, enables the
scheduler, and points `/` at `/kamra`.

## Sign in and set up

Open `http://<server-ip>:8080/kamra` (or `https://pms.yourhotel.com` after
DNS + TLS).

| Field | Use |
| --- | --- |
| Username | `Administrator` |
| Email | the admin email you entered |
| Password | the password you set |

Then open **`/kamra/setup`** and create your property. Product UI is
`/kamra`; Frappe Desk at `/app` is an admin escape hatch (accounting apps,
etc.) — not the hotel.

Forgot the password?

```bash
cd /opt/kamra/frappe_docker
docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
  -f compose.yaml -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml -f overrides/compose.noproxy.yaml \
  exec backend bench --site pms.yourhotel.com set-admin-password '<new-password>'
```

## TLS

```bash
apt install -y certbot python3-certbot-nginx
# Put nginx in front of port 8080, then:
certbot --nginx -d pms.yourhotel.com
```

## Updating

```bash
cd /opt/kamra/frappe_docker
docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
  -f compose.yaml -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml -f overrides/compose.noproxy.yaml pull
docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
  -f compose.yaml -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml -f overrides/compose.noproxy.yaml up -d
docker compose --project-name kamra --env-file /opt/kamra/kamra.env \
  -f compose.yaml -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml -f overrides/compose.noproxy.yaml \
  exec backend bench --site pms.yourhotel.com migrate
```

## Build from source (developers only)

Hoteliers should not use this path. Contributors who need a custom image:

```bash
git clone https://github.com/frappe/frappe_docker && cd frappe_docker
# apps.json with payments + kamra-pms, then layered Containerfile build —
# see CONTRIBUTING.md and .github/workflows/release.yml
```

Next: [production checklist](/self-hosting/#after-install-production-checklist) ·
[email setup](/self-hosting/email) · [AI assistant](/ai-and-mcp) ·
[ERPNext & HR (optional)](/self-hosting/erpnext-hr)
