# Self-hosting Kamra

Own your PMS end to end. Ways to install:

| Method | Effort | Best for |
| --- | --- | --- |
| [Hostinger VPS + one command](/self-hosting/hostinger) | Buy a VPS, paste one line | Cheapest path, India / SEA |
| [Docker quickstart](/quickstart) on any VPS | One command, three prompts | DigitalOcean, Linode, AWS, your own box |
| [Bench install](/self-hosting/bench) | Classic Frappe bench | Teams already running Frappe / ERPNext |
| [Frappe Cloud Marketplace](/self-hosting/frappe-cloud) | Point and click | Managed Frappe hosting, no server |

Every feature is included — there is no paid edition to upgrade to.

Want company books or HR on the same Frappe site? That is optional —
see [ERPNext and Frappe HR](/self-hosting/erpnext-hr) (Marketplace and
own-server steps).

## Server requirements

| | Minimum | Recommended (20+ rooms, POS) |
| --- | --- | --- |
| CPU | 2 vCPU | 4 vCPU |
| RAM | 4 GB | 8 GB |
| Disk | 40 GB SSD | 80 GB SSD |
| OS | Ubuntu 22.04/24.04 LTS (any Docker-capable Linux) | — |

Measured on our own servers: a full single-property stack (database,
cache, workers, web) idles around 600 MB of RAM — 4 GB leaves comfortable
headroom for busy days. By default the Docker installer **builds the
image on your server** (20–45 minutes the first time; on boxes under 8 GB
it adds a swap file for the build). With access to the
[prebuilt image](#docker-images) it pulls instead — a few minutes, no
build memory needed.

**Also needed:** a domain or subdomain (`pms.yourhotel.com`) pointed at
the server; ports 80/443 open; SSL via Let's Encrypt.

## Docker images

Each release is published to `ghcr.io/kamra-pms/kamra`
(linux/amd64). The [installer](/quickstart#faster-pull-the-prebuilt-image)
uses it with `KAMRA_PULL=1`; the package is not public yet, so the server
needs `docker login ghcr.io` with a `read:packages` token until it is.

| Tag | What it is | Use for |
| --- | --- | --- |
| `stable` | The newest release (moves on every release) | What the installer follows; it pins the `vX.Y.Z` it resolves to |
| `vX.Y.Z` | One release, never changes | **Pin this in production** |
| `nightly` | Latest green `develop` | Testing only |

`latest` is an alias of `stable` kept for older scripts. The three newest
releases plus `stable` and `nightly` are kept; older tags are pruned
weekly, so pin a recent release and update regularly.

### What's in the image

Only public, open-source code: **Frappe**, **payments** and **Kamra**
(built from their public GitHub repositories at the release tag, on
GitHub Actions — see `.github/workflows/release.yml`). The image holds **no
site data and no secrets**: your database, uploaded files, site config,
passwords and API keys live in Docker volumes and `kamra.env` on **your**
server, never in the image. Anyone can rebuild the same image from source
with `KAMRA_BUILD=1`.

## Typical monthly cost

| Provider | Plan that fits | Price | Guide |
| --- | --- | --- | --- |
| Hostinger | KVM 2 (2 vCPU / 8 GB) | ~₹549/mo | [Guide](/self-hosting/hostinger) |
| DigitalOcean | Basic 4 GB | ~$24/mo | [Guide](/self-hosting/digitalocean) |
| Linode | Shared 4 GB | ~$24/mo | [Guide](/self-hosting/linode) |
| AWS | t3.medium + EBS | ~$30/mo | [Guide](/self-hosting/aws) |

Hyperscaler storefronts (free self-host AMI, planned):
[AWS / Azure / GCP](/self-hosting/marketplace/hyperscalers).

::: tip Rather not run a server?
Install from the [Frappe Cloud Marketplace](/self-hosting/frappe-cloud) —
Frappe hosts, backs up and updates it — and add our
[implementation](https://kamrapms.com/implementation/) if you want
migration and training done for you. You can export everything and move
to self-hosting any time; that's the point of open source.
:::

## After install — production checklist

1. **Create your property** — sign in at `/kamra` as `Administrator` with
   the admin password you chose at install — there is **no default** —
   then open **`/kamra/setup`** (rooms, room types, rates).
2. **Staff users & roles** — Hotel Admin / Front Desk / Revenue / Finance /
   Housekeeping; roles decide what each person sees.
3. **Email** — [set up SMTP](/self-hosting/email) for confirmations,
   invoices and briefings.
4. **Payments** — add gateway keys in the payments app (e.g. Razorpay
   Settings); turn off test mode.
5. **Scheduler** — `install.sh` enables it; night audit runs at 03:00 site
   time and housekeeping SLAs escalate every 15 min.
6. **Backups** — `bench backup --with-files` on cron to off-site storage.
7. **Security** — `developer_mode 0`, strong admin password, HTTPS only.
8. **AI (optional)** — [bring your own model](/ai-and-mcp) or Connect Claude
   over MCP; then optionally Connect HeyKoala WhatsApp from Marketplace.

## Updating (Docker install)

```bash
sudo /opt/kamra/install.sh update
```

It first takes a full backup (`bench backup --with-files`) and **aborts if
the backup fails**. Build installs then rebuild the image from the branch
recorded in `/opt/kamra/apps.json` (pin a release with
`KAMRA_BRANCH=v2.6.4`; 10–30 minutes); pull installs pull the newest
`:stable` and pin it (or `KAMRA_TAG=vX.Y.Z`; a few minutes). Both recreate
the containers and run `bench migrate` on every site. Details:
[quickstart → Updating](/quickstart#updating).

Bench self-host:

```bash
cd frappe-bench/apps/kamra && git pull
bench --site pms.yourhotel.com migrate
bench build && bench restart
```

Run the eval harness after any update — deterministic checks over money,
tax and availability logic:

```bash
bench --site pms.yourhotel.com console
>>> from kamra.scripts.eval_harness import execute; execute()
```
