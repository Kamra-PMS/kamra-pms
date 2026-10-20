# Quickstart (Docker)

The fastest self-host path: one Docker-capable Linux server, **three
questions**, then the installer gets the Kamra image (Frappe + payments +
kamra) and creates your site. By default it **builds the image on your
VPS**; if you have access to the prebuilt image on `ghcr.io` it can
[pull it instead](#faster-pull-the-prebuilt-image) in a few minutes.

## What you need

- A server or VPS: **2 vCPU · 4 GB RAM · 40 GB disk** minimum (Ubuntu
  22.04/24.04); **4 vCPU · 8 GB** recommended. Under 8 GB the installer adds
  a swap file so the image build doesn't run out of memory — it just builds
  slower.
- Docker Engine ≥ 24 with Compose v2 (the installer can install Docker for you)
- A domain (e.g. `pms.yourhotel.com`) pointed at the server
- **20–45 minutes** for the first image build (a few minutes when
  [pulling the prebuilt image](#faster-pull-the-prebuilt-image))

::: tip Where to get a server
One-click / affiliate paths: [Hostinger](/self-hosting/hostinger),
[DigitalOcean](/self-hosting/digitalocean), [Linode](/self-hosting/linode).
Or [AWS](/self-hosting/aws). Prefer managed? [Frappe Cloud](/self-hosting/frappe-cloud).
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

The script clones `frappe_docker`, builds a local `kamra:local` image
(payments + kamra from GitHub), starts MariaDB + Redis + Kamra, creates
the site, enables the scheduler, and points `/` at `/kamra`.

## Faster: pull the prebuilt image

Every release is also published as a Docker image,
`ghcr.io/kamra-pms/kamra`. Pulling it skips the 20–45 minute build (no
buildx, no swap file) — usually **2–5 minutes** on a VPS connection:

```bash
curl -fsSL https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/install.sh | KAMRA_PULL=1 bash
```

The installer pulls `:stable`, works out which release that is (say
`v2.6.16`) and **pins** it, so a restart never moves you to a new version
— only `install.sh update` does. Pick a tag with `KAMRA_TAG=v2.6.16`
(or `nightly` for testing).

::: warning Registry access
The image package is not public yet. Until it is, log the server in to
`ghcr.io` first with a GitHub token that has `read:packages`:
`echo "$TOKEN" | docker login ghcr.io -u <github-user> --password-stdin`.
Without access the installer says so and falls back to building.
:::

Forks or extra apps (a custom `apps.json`)? Stay on the build path:
`KAMRA_BUILD=1 KAMRA_APPS_JSON=/path/to/apps.json bash install.sh`.

See [Docker images](/self-hosting/#docker-images) for tags and what is
inside the image.

## Try it on your laptop

To look around before you buy a server, a single compose file runs the
prebuilt image with MariaDB and Redis and creates a site for you (same
registry access as above):

```bash
curl -fsSLO https://raw.githubusercontent.com/Kamra-PMS/kamra-pms/main/deploy/compose/quickstart.yaml
export KAMRA_ADMIN_PASSWORD='pick-a-password'
export KAMRA_DB_PASSWORD="$(openssl rand -hex 16)"
docker compose -f quickstart.yaml up -d
docker compose -f quickstart.yaml logs -f create-site   # wait for "Kamra is ready"
```

Open <http://localhost:8080/kamra> and sign in as `Administrator` with
`KAMRA_ADMIN_PASSWORD`. Nothing is published beyond `127.0.0.1`.
`docker compose -f quickstart.yaml down -v` deletes it all. This is for
evaluation — use the installer for a real hotel.

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
sudo /opt/kamra/install.sh update
```

Every update first takes a full backup (`bench backup --with-files`, kept
in `sites/<site>/private/backups`) and **stops if the backup fails**. Then:

- **Build installs** rebuild the image from the branch recorded in
  `/opt/kamra/apps.json` (fetching the latest Kamra code). Pin a release
  with `sudo KAMRA_BRANCH=v2.6.4 /opt/kamra/install.sh update`. 10–30
  minutes; the site stays up until the containers are recreated.
- **Pull installs** pull the newest `:stable`, pin the release it resolves
  to, and recreate — a few minutes. Move to a specific release with
  `sudo KAMRA_TAG=v2.6.16 /opt/kamra/install.sh update`.

Either way it then runs `bench migrate` on every site.

Next: [production checklist](/self-hosting/#after-install-production-checklist) ·
[email setup](/self-hosting/email) · [AI assistant](/ai-and-mcp) ·
[ERPNext & HR (optional)](/self-hosting/erpnext-hr)
