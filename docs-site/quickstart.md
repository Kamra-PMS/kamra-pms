# Quickstart (Docker)

The fastest path to a running Kamra: one Docker-capable Linux server, four
steps, roughly 20 minutes.

## What you need

- A server or VPS: **2 vCPU · 4 GB RAM · 40 GB disk** (Ubuntu 22.04/24.04)
- Docker Engine ≥ 24 with Compose v2
- A domain (e.g. `pms.yourhotel.com`) pointed at the server

::: tip Where to get a server
Any provider works. We keep short getting-started pages for
[Hostinger](/self-hosting/hostinger), [DigitalOcean](/self-hosting/digitalocean),
[Linode](/self-hosting/linode) and [AWS](/self-hosting/aws).
:::

## 1. Build an image with Kamra in it

```bash
git clone https://github.com/frappe/frappe_docker && cd frappe_docker

cat > apps.json <<'EOF'
[
  {"url": "https://github.com/frappe/payments", "branch": "develop"},
  {"url": "https://github.com/Kamra-PMS/kamra-pms", "branch": "main"}
]
EOF

docker build -t kamra:latest \
  --build-arg FRAPPE_BRANCH=v16.25.0 \
  --secret id=apps_json,src=apps.json \
  -f images/layered/Containerfile .
```

## 2. Start the stack

Follow frappe_docker's compose setup with your image (set
`CUSTOM_IMAGE=kamra` and `CUSTOM_TAG=latest` in the env file), then:

```bash
docker compose --env-file your.env \
  -f compose.yaml \
  -f overrides/compose.mariadb.yaml \
  -f overrides/compose.redis.yaml \
  -f overrides/compose.noproxy.yaml up -d
```

## 3. Create your site

```bash
docker compose exec backend \
  bench new-site pms.yourhotel.com \
    --admin-password <strong-password> \
    --install-app payments --install-app kamra
docker compose exec backend \
  bench --site pms.yourhotel.com enable-scheduler
```

## 4. Sign in and set up

Open `https://pms.yourhotel.com/kamra`. There is **no default password**.

| Field | Use |
| --- | --- |
| Username | `Administrator` |
| or email | `admin@example.com` (same user) |
| Password | the `--admin-password` you set in step 3 |

Then create your property (rooms, room types, rates). Product UI is `/kamra`; Frappe Desk at `/app` is an admin escape hatch.

Forgot the password? On this Docker stack:

```bash
docker compose exec backend \
  bench --site pms.yourhotel.com set-admin-password <new-password>
```

Next steps: [production checklist](/self-hosting/#after-install-production-checklist) ·
[email setup](/self-hosting/email) · [connect your AI](/ai-and-mcp)
